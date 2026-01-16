"""
Billing Application Service.

Orchestrates billing operations including tariff management,
bill simulation, and savings calculations.
"""
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from ...domain.entities.billing import (
    TariffPlan,
    TariffRates,
    TariffSlab,
    BillingSimulation,
    BillBreakdown,
    SavingsBreakdown,
    EnergyConsumption,
    DiscoProvider,
    TariffCategory,
)
from ...domain.services.billing_calculator import BillingCalculator
from ...infrastructure.database.repositories.billing_repository import SQLAlchemyBillingRepository
from ...infrastructure.database.repositories.site_repository import SQLAlchemySiteRepository
from ..interfaces.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


@dataclass
class SimulationRequest:
    """Request to create a billing simulation."""
    site_id: UUID
    period_start: date
    period_end: date
    tariff_plan_id: Optional[UUID] = None
    energy_consumed_kwh: Optional[Decimal] = None
    energy_generated_kwh: Optional[Decimal] = None
    energy_exported_kwh: Optional[Decimal] = None
    energy_imported_kwh: Optional[Decimal] = None
    peak_demand_kw: Optional[Decimal] = None
    peak_consumed_kwh: Optional[Decimal] = None
    off_peak_consumed_kwh: Optional[Decimal] = None
    notes: Optional[str] = None


@dataclass
class TariffCreateRequest:
    """Request to create a tariff plan."""
    disco_provider: str
    category: str
    name: str
    description: Optional[str] = None
    effective_from: date = None
    effective_to: Optional[date] = None
    rates: Dict[str, Any] = None
    supports_net_metering: bool = True
    supports_tou: bool = False
    source_url: Optional[str] = None
    notes: Optional[str] = None


class BillingService:
    """
    Application service for billing operations.

    Coordinates between domain services, repositories, and external services
    to provide billing functionality.
    """

    def __init__(
        self,
        billing_repository: SQLAlchemyBillingRepository,
        site_repository: SQLAlchemySiteRepository,
        calculator: BillingCalculator,
    ):
        self._billing_repo = billing_repository
        self._site_repo = site_repository
        self._calculator = calculator

    # =========================================================================
    # Tariff Management
    # =========================================================================

    async def get_tariff_plan(self, tariff_id: UUID) -> Optional[TariffPlan]:
        """Get a tariff plan by ID."""
        return await self._billing_repo.get_tariff_plan_by_id(tariff_id)

    async def get_site_tariff(
        self,
        site_id: UUID,
        check_date: Optional[date] = None,
    ) -> Optional[TariffPlan]:
        """
        Get applicable tariff for a site.

        Looks up site's DISCO and category to find the active tariff.
        """
        site = await self._site_repo.get_by_id(site_id)
        if not site:
            logger.error("Site %s not found", site_id)
            return None

        # Get DISCO and category from site's tariff configuration
        disco = site.tariff_config.get("disco_provider") if site.tariff_config else None
        category = site.tariff_config.get("category") if site.tariff_config else None

        if not disco or not category:
            logger.warning("Site %s does not have tariff configuration", site_id)
            return None

        return await self._billing_repo.get_active_tariff(
            disco_provider=disco,
            category=category,
            check_date=check_date,
        )

    async def list_tariff_plans(
        self,
        disco_provider: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TariffPlan]:
        """List tariff plans with optional filters."""
        return await self._billing_repo.list_tariff_plans(
            disco_provider=disco_provider,
            category=category,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def get_discos_with_categories(self) -> List[Dict[str, Any]]:
        """Get list of DISCOs with their available tariff categories."""
        return await self._billing_repo.get_discos_with_tariffs()

    async def create_tariff_plan(
        self,
        request: TariffCreateRequest,
        uow: UnitOfWork,
    ) -> TariffPlan:
        """
        Create a new tariff plan.

        Args:
            request: Tariff creation request
            uow: Unit of work for transaction

        Returns:
            Created tariff plan
        """
        # Convert rates dict to TariffRates
        rates_data = request.rates or {}
        slabs = []
        for slab_data in rates_data.get("slabs", []):
            slabs.append(TariffSlab(
                min_units=slab_data["min_units"],
                max_units=slab_data.get("max_units"),
                rate_per_kwh=Decimal(str(slab_data["rate_per_kwh"])),
                fixed_charges=Decimal(str(slab_data.get("fixed_charges", "0"))),
            ))

        rates = TariffRates(
            energy_charge_per_kwh=Decimal(str(rates_data.get("energy_charge_per_kwh", "0"))),
            slabs=slabs,
            peak_rate_per_kwh=Decimal(str(rates_data["peak_rate_per_kwh"])) if rates_data.get("peak_rate_per_kwh") else None,
            off_peak_rate_per_kwh=Decimal(str(rates_data["off_peak_rate_per_kwh"])) if rates_data.get("off_peak_rate_per_kwh") else None,
            fixed_charges_per_month=Decimal(str(rates_data.get("fixed_charges_per_month", "0"))),
            meter_rent=Decimal(str(rates_data.get("meter_rent", "0"))),
            fuel_price_adjustment=Decimal(str(rates_data.get("fuel_price_adjustment", "0"))),
            quarterly_tariff_adjustment=Decimal(str(rates_data.get("quarterly_tariff_adjustment", "0"))),
            electricity_duty_percent=Decimal(str(rates_data.get("electricity_duty_percent", "1.5"))),
            gst_percent=Decimal(str(rates_data.get("gst_percent", "17"))),
            tv_fee=Decimal(str(rates_data.get("tv_fee", "35"))),
            export_rate_per_kwh=Decimal(str(rates_data["export_rate_per_kwh"])) if rates_data.get("export_rate_per_kwh") else None,
            demand_charge_per_kw=Decimal(str(rates_data["demand_charge_per_kw"])) if rates_data.get("demand_charge_per_kw") else None,
        )

        tariff = TariffPlan(
            disco_provider=DiscoProvider(request.disco_provider),
            category=TariffCategory(request.category),
            name=request.name,
            description=request.description,
            effective_from=request.effective_from or date.today(),
            effective_to=request.effective_to,
            rates=rates,
            supports_net_metering=request.supports_net_metering,
            supports_tou=request.supports_tou,
            source_url=request.source_url,
            notes=request.notes,
        )

        created = await self._billing_repo.create_tariff_plan(tariff)
        await uow.commit()

        logger.info("Created tariff plan: %s for %s/%s", created.id, request.disco_provider, request.category)
        return created

    # =========================================================================
    # Billing Simulation
    # =========================================================================

    async def simulate_bill(
        self,
        request: SimulationRequest,
        uow: UnitOfWork,
    ) -> BillingSimulation:
        """
        Generate a billing simulation for a site.

        Args:
            request: Simulation request with energy data
            uow: Unit of work for transaction

        Returns:
            BillingSimulation with calculated bill
        """
        # Get tariff plan
        if request.tariff_plan_id:
            tariff = await self._billing_repo.get_tariff_plan_by_id(request.tariff_plan_id)
        else:
            tariff = await self.get_site_tariff(request.site_id)

        if not tariff:
            raise ValueError("No applicable tariff plan found for site")

        # Create consumption object
        consumption = EnergyConsumption(
            total_consumed_kwh=request.energy_consumed_kwh or Decimal("0"),
            total_generated_kwh=request.energy_generated_kwh or Decimal("0"),
            total_exported_kwh=request.energy_exported_kwh or Decimal("0"),
            total_imported_kwh=request.energy_imported_kwh or (request.energy_consumed_kwh or Decimal("0")),
            peak_consumed_kwh=request.peak_consumed_kwh,
            off_peak_consumed_kwh=request.off_peak_consumed_kwh,
            peak_demand_kw=request.peak_demand_kw,
        )

        # Calculate bill and savings
        bill_breakdown, savings_breakdown = self._calculator.calculate_bill_with_savings(
            consumption=consumption,
            tariff=tariff,
        )

        # Create simulation entity
        simulation = BillingSimulation(
            site_id=request.site_id,
            tariff_plan_id=tariff.id,
            period_start=request.period_start,
            period_end=request.period_end,
            energy_consumed_kwh=consumption.total_consumed_kwh,
            energy_generated_kwh=consumption.total_generated_kwh,
            energy_exported_kwh=consumption.total_exported_kwh,
            energy_imported_kwh=consumption.total_imported_kwh,
            peak_demand_kw=consumption.peak_demand_kw,
            bill_breakdown=bill_breakdown,
            savings_breakdown=savings_breakdown,
            estimated_bill_pkr=bill_breakdown.total_bill,
            estimated_savings_pkr=savings_breakdown.total_savings,
            notes=request.notes,
        )

        # Save simulation
        created = await self._billing_repo.create_simulation(simulation)
        await uow.commit()

        logger.info(
            "Created billing simulation for site %s: PKR %.2f (savings: PKR %.2f)",
            request.site_id,
            float(created.estimated_bill_pkr),
            float(created.estimated_savings_pkr),
        )
        return created

    async def get_simulation(self, simulation_id: UUID) -> Optional[BillingSimulation]:
        """Get a billing simulation by ID."""
        return await self._billing_repo.get_simulation_by_id(simulation_id)

    async def list_simulations(
        self,
        site_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BillingSimulation]:
        """List billing simulations for a site."""
        return await self._billing_repo.list_simulations_by_site(
            site_id=site_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )

    async def get_yearly_summary(
        self,
        site_id: UUID,
        year: int,
    ) -> Dict[str, Any]:
        """Get yearly billing summary for a site."""
        return await self._billing_repo.get_simulation_summary(site_id, year)

    async def compare_tariffs(
        self,
        site_id: UUID,
        tariff_ids: List[UUID],
        energy_consumed_kwh: Decimal,
        energy_generated_kwh: Decimal = Decimal("0"),
        energy_exported_kwh: Decimal = Decimal("0"),
    ) -> List[Dict[str, Any]]:
        """
        Compare different tariff plans for the same consumption.

        Args:
            site_id: Site ID
            tariff_ids: List of tariff plan IDs to compare
            energy_consumed_kwh: Total energy consumed
            energy_generated_kwh: Total energy generated
            energy_exported_kwh: Total energy exported

        Returns:
            List of comparison results
        """
        consumption = EnergyConsumption(
            total_consumed_kwh=energy_consumed_kwh,
            total_generated_kwh=energy_generated_kwh,
            total_exported_kwh=energy_exported_kwh,
            total_imported_kwh=energy_consumed_kwh - energy_generated_kwh + energy_exported_kwh,
        )

        results = []
        for tariff_id in tariff_ids:
            tariff = await self._billing_repo.get_tariff_plan_by_id(tariff_id)
            if not tariff:
                continue

            bill, savings = self._calculator.calculate_bill_with_savings(consumption, tariff)

            results.append({
                "tariff_id": str(tariff_id),
                "tariff_name": tariff.name,
                "disco_provider": tariff.disco_provider.value,
                "category": tariff.category.value,
                "total_bill": float(bill.total_bill),
                "energy_charges": float(bill.energy_charges),
                "total_taxes": float(bill.total_taxes),
                "export_credit": float(bill.export_credit),
                "total_savings": float(savings.total_savings),
                "savings_percent": float(savings.savings_percent),
            })

        # Sort by total bill (lowest first)
        results.sort(key=lambda x: x["total_bill"])
        return results
