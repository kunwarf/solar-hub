"""
Billing API endpoints.

Provides tariff management, billing simulation, and savings analysis.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
    require_admin,
)
from ..schemas.billing_schemas import (
    TariffPlanCreate,
    TariffPlanResponse,
    TariffListResponse,
    DiscosListResponse,
    DiscoWithCategoriesResponse,
    SimulationRequest,
    SimulationResponse,
    SimulationListResponse,
    YearlySummaryResponse,
    TariffComparisonRequest,
    TariffComparisonResponse,
    TariffComparisonItem,
    BillBreakdownSchema,
    SavingsBreakdownSchema,
)
from ...application.services.billing_service import (
    BillingService,
    SimulationRequest as ServiceSimulationRequest,
    TariffCreateRequest,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User
from ...domain.services.billing_calculator import BillingCalculator
from ...infrastructure.database.repositories.billing_repository import SQLAlchemyBillingRepository
from ...infrastructure.database.repositories.site_repository import SQLAlchemySiteRepository

router = APIRouter(prefix="/billing", tags=["Billing"])


# Dependency for billing service
async def get_billing_service(
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> BillingService:
    """Get billing service instance."""
    return BillingService(
        billing_repository=SQLAlchemyBillingRepository(uow._session),
        site_repository=SQLAlchemySiteRepository(uow._session),
        calculator=BillingCalculator(),
    )


# =========================================================================
# Tariff Endpoints
# =========================================================================

@router.get(
    "/tariffs",
    response_model=TariffListResponse,
    summary="List tariff plans",
)
async def list_tariffs(
    disco_provider: Optional[str] = Query(None, description="Filter by DISCO"),
    category: Optional[str] = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only show active tariffs"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
):
    """
    List available tariff plans.

    Filter by DISCO provider and/or tariff category.
    """
    tariffs = await billing_service.list_tariff_plans(
        disco_provider=disco_provider,
        category=category,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return TariffListResponse(
        tariffs=[_tariff_to_response(t) for t in tariffs],
        total=len(tariffs),
    )


@router.get(
    "/tariffs/discos",
    response_model=DiscosListResponse,
    summary="List DISCOs with categories",
)
async def list_discos(
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
):
    """
    Get list of DISCOs with their available tariff categories.

    Useful for building tariff selection UIs.
    """
    discos = await billing_service.get_discos_with_categories()

    return DiscosListResponse(
        discos=[
            DiscoWithCategoriesResponse(
                disco_provider=d["disco_provider"],
                categories=d["categories"],
            )
            for d in discos
        ]
    )


@router.get(
    "/tariffs/{tariff_id}",
    response_model=TariffPlanResponse,
    summary="Get tariff plan details",
)
async def get_tariff(
    tariff_id: UUID,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
):
    """Get a specific tariff plan by ID."""
    tariff = await billing_service.get_tariff_plan(tariff_id)

    if not tariff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tariff plan not found",
        )

    return _tariff_to_response(tariff)


@router.post(
    "/tariffs",
    response_model=TariffPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tariff plan (Admin)",
)
async def create_tariff(
    request: TariffPlanCreate,
    current_user: User = Depends(require_admin),
    billing_service: BillingService = Depends(get_billing_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Create a new tariff plan.

    Requires admin privileges.
    """
    # Convert schema to request
    rates_dict = request.rates.model_dump() if request.rates else {}

    tariff_request = TariffCreateRequest(
        disco_provider=request.disco_provider,
        category=request.category,
        name=request.name,
        description=request.description,
        effective_from=request.effective_from,
        effective_to=request.effective_to,
        rates=rates_dict,
        supports_net_metering=request.supports_net_metering,
        supports_tou=request.supports_tou,
        source_url=request.source_url,
        notes=request.notes,
    )

    tariff = await billing_service.create_tariff_plan(tariff_request, uow)
    return _tariff_to_response(tariff)


# =========================================================================
# Simulation Endpoints
# =========================================================================

@router.post(
    "/simulate",
    response_model=SimulationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run billing simulation",
)
async def simulate_bill(
    request: SimulationRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Generate a billing simulation for a site.

    Calculates estimated electricity bill based on energy consumption
    and applicable tariff. Also provides savings analysis if solar
    generation data is included.
    """
    try:
        service_request = ServiceSimulationRequest(
            site_id=request.site_id,
            period_start=request.period_start,
            period_end=request.period_end,
            tariff_plan_id=request.tariff_plan_id,
            energy_consumed_kwh=Decimal(str(request.energy_consumed_kwh)),
            energy_generated_kwh=Decimal(str(request.energy_generated_kwh)),
            energy_exported_kwh=Decimal(str(request.energy_exported_kwh)),
            energy_imported_kwh=Decimal(str(request.energy_imported_kwh)) if request.energy_imported_kwh else None,
            peak_demand_kw=Decimal(str(request.peak_demand_kw)) if request.peak_demand_kw else None,
            peak_consumed_kwh=Decimal(str(request.peak_consumed_kwh)) if request.peak_consumed_kwh else None,
            off_peak_consumed_kwh=Decimal(str(request.off_peak_consumed_kwh)) if request.off_peak_consumed_kwh else None,
            notes=request.notes,
        )

        simulation = await billing_service.simulate_bill(service_request, uow)
        return _simulation_to_response(simulation)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/simulations",
    response_model=SimulationListResponse,
    summary="List simulations for a site",
)
async def list_simulations(
    site_id: UUID = Query(..., description="Site ID"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
):
    """List billing simulations for a site."""
    simulations = await billing_service.list_simulations(
        site_id=site_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return SimulationListResponse(
        simulations=[_simulation_to_response(s) for s in simulations],
        total=len(simulations),
    )


@router.get(
    "/simulations/{simulation_id}",
    response_model=SimulationResponse,
    summary="Get simulation details",
)
async def get_simulation(
    simulation_id: UUID,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
):
    """Get a specific billing simulation by ID."""
    simulation = await billing_service.get_simulation(simulation_id)

    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )

    return _simulation_to_response(simulation)


@router.get(
    "/summary/{site_id}/{year}",
    response_model=YearlySummaryResponse,
    summary="Get yearly billing summary",
)
async def get_yearly_summary(
    site_id: UUID,
    year: int,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
):
    """Get aggregated billing summary for a site for a specific year."""
    summary = await billing_service.get_yearly_summary(site_id, year)
    return YearlySummaryResponse(**summary)


# =========================================================================
# Comparison Endpoints
# =========================================================================

@router.post(
    "/compare",
    response_model=TariffComparisonResponse,
    summary="Compare tariff plans",
)
async def compare_tariffs(
    request: TariffComparisonRequest,
    site_id: UUID = Query(..., description="Site ID for context"),
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
):
    """
    Compare different tariff plans for the same energy consumption.

    Helps identify the most cost-effective tariff for a site.
    """
    results = await billing_service.compare_tariffs(
        site_id=site_id,
        tariff_ids=request.tariff_ids,
        energy_consumed_kwh=Decimal(str(request.energy_consumed_kwh)),
        energy_generated_kwh=Decimal(str(request.energy_generated_kwh)),
        energy_exported_kwh=Decimal(str(request.energy_exported_kwh)),
    )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid tariff plans found for comparison",
        )

    comparisons = [TariffComparisonItem(**r) for r in results]
    best_tariff = results[0]  # Already sorted by total_bill
    worst_tariff = results[-1]

    return TariffComparisonResponse(
        comparisons=comparisons,
        best_tariff_id=best_tariff["tariff_id"],
        potential_savings=worst_tariff["total_bill"] - best_tariff["total_bill"],
    )


# =========================================================================
# Helper Functions
# =========================================================================

def _tariff_to_response(tariff) -> TariffPlanResponse:
    """Convert tariff domain entity to response schema."""
    # Convert rates to dict
    rates_dict = {
        "energy_charge_per_kwh": str(tariff.rates.energy_charge_per_kwh),
        "fixed_charges_per_month": str(tariff.rates.fixed_charges_per_month),
        "meter_rent": str(tariff.rates.meter_rent),
        "fuel_price_adjustment": str(tariff.rates.fuel_price_adjustment),
        "quarterly_tariff_adjustment": str(tariff.rates.quarterly_tariff_adjustment),
        "electricity_duty_percent": str(tariff.rates.electricity_duty_percent),
        "gst_percent": str(tariff.rates.gst_percent),
        "tv_fee": str(tariff.rates.tv_fee),
    }

    if tariff.rates.slabs:
        rates_dict["slabs"] = [
            {
                "min_units": s.min_units,
                "max_units": s.max_units,
                "rate_per_kwh": str(s.rate_per_kwh),
                "fixed_charges": str(s.fixed_charges),
            }
            for s in tariff.rates.slabs
        ]

    if tariff.rates.peak_rate_per_kwh:
        rates_dict["peak_rate_per_kwh"] = str(tariff.rates.peak_rate_per_kwh)
    if tariff.rates.off_peak_rate_per_kwh:
        rates_dict["off_peak_rate_per_kwh"] = str(tariff.rates.off_peak_rate_per_kwh)
    if tariff.rates.export_rate_per_kwh:
        rates_dict["export_rate_per_kwh"] = str(tariff.rates.export_rate_per_kwh)
    if tariff.rates.demand_charge_per_kw:
        rates_dict["demand_charge_per_kw"] = str(tariff.rates.demand_charge_per_kw)

    return TariffPlanResponse(
        id=tariff.id,
        disco_provider=tariff.disco_provider.value,
        category=tariff.category.value,
        name=tariff.name,
        description=tariff.description,
        effective_from=tariff.effective_from,
        effective_to=tariff.effective_to,
        rates=rates_dict,
        supports_net_metering=tariff.supports_net_metering,
        supports_tou=tariff.supports_tou,
        source_url=tariff.source_url,
        notes=tariff.notes,
        created_at=tariff.created_at,
        updated_at=tariff.updated_at,
    )


def _simulation_to_response(simulation) -> SimulationResponse:
    """Convert simulation domain entity to response schema."""
    bill = simulation.bill_breakdown
    savings = simulation.savings_breakdown

    return SimulationResponse(
        id=simulation.id,
        site_id=simulation.site_id,
        tariff_plan_id=simulation.tariff_plan_id,
        period_start=simulation.period_start,
        period_end=simulation.period_end,
        energy_consumed_kwh=float(simulation.energy_consumed_kwh),
        energy_generated_kwh=float(simulation.energy_generated_kwh),
        energy_exported_kwh=float(simulation.energy_exported_kwh),
        energy_imported_kwh=float(simulation.energy_imported_kwh),
        peak_demand_kw=float(simulation.peak_demand_kw) if simulation.peak_demand_kw else None,
        bill_breakdown=BillBreakdownSchema(
            energy_charges=float(bill.energy_charges),
            slab_breakdown=bill.slab_breakdown,
            fixed_charges=float(bill.fixed_charges),
            meter_rent=float(bill.meter_rent),
            fuel_price_adjustment=float(bill.fuel_price_adjustment),
            quarterly_tariff_adjustment=float(bill.quarterly_tariff_adjustment),
            electricity_duty=float(bill.electricity_duty),
            gst=float(bill.gst),
            tv_fee=float(bill.tv_fee),
            export_credit=float(bill.export_credit),
            demand_charges=float(bill.demand_charges),
            subtotal=float(bill.subtotal),
            total_taxes=float(bill.total_taxes),
            total_bill=float(bill.total_bill),
        ),
        savings_breakdown=SavingsBreakdownSchema(
            bill_without_solar=float(savings.bill_without_solar),
            bill_with_solar=float(savings.bill_with_solar),
            total_savings=float(savings.total_savings),
            savings_percent=float(savings.savings_percent),
            export_income=float(savings.export_income),
            co2_avoided_kg=float(savings.co2_avoided_kg),
            trees_equivalent=float(savings.trees_equivalent),
        ),
        estimated_bill_pkr=float(simulation.estimated_bill_pkr),
        estimated_savings_pkr=float(simulation.estimated_savings_pkr),
        is_actual=simulation.is_actual,
        notes=simulation.notes,
        created_at=simulation.created_at,
        updated_at=simulation.updated_at,
    )
