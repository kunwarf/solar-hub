"""
Net Metering Billing API endpoints.

Provides:
- Billing configuration management
- Running bill (to-date) queries
- Daily snapshots
- Billing months and cycles
- Capacity analysis
"""
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
    require_admin,
)
from ..schemas.net_metering_schemas import (
    BillingConfigCreate,
    BillingConfigResponse,
    RunningBillResponse,
    DailySnapshotResponse,
    DailySnapshotsListResponse,
    BillingMonthResponse,
    BillingMonthListResponse,
    BillingCycleResponse,
    BillingCycleListResponse,
    BillingSummaryResponse,
    BillingTrendResponse,
    BillingTrendItem,
    YearlyBillingSummaryResponse,
    CapacityStatusResponse,
    ForceCycleCloseRequest,
    ForceCycleCloseResponse,
    BackfillRequest,
    BackfillResponse,
    TouConfigSchema,
    TouWindowSchema,
    BillingPricesSchema,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User
from ...domain.entities.net_metering import (
    BillingConfig,
    BillingPrices,
    TouConfig,
    TouWindow,
    FixedProrationMode,
)
from ...domain.services.net_metering_calculator import NetMeteringCalculator
from ...infrastructure.database.repositories.net_metering_repository import (
    SQLAlchemyNetMeteringRepository,
)
from ...infrastructure.database.repositories.site_repository import (
    SQLAlchemySiteRepository,
)

router = APIRouter(prefix="/billing", tags=["Net Metering Billing"])


# =========================================================================
# Dependencies
# =========================================================================

async def get_net_metering_repo(
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> SQLAlchemyNetMeteringRepository:
    """Get net metering repository instance."""
    return SQLAlchemyNetMeteringRepository(uow._session)


async def get_site_repo(
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> SQLAlchemySiteRepository:
    """Get site repository instance."""
    return SQLAlchemySiteRepository(uow._session)


# =========================================================================
# Billing Config Endpoints
# =========================================================================

@router.get(
    "/config/{site_id}",
    response_model=BillingConfigResponse,
    summary="Get billing configuration",
)
async def get_billing_config(
    site_id: UUID,
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """Get billing configuration for a site."""
    config = await nm_repo.get_billing_config_by_site(site_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing configuration not found for this site",
        )

    return _config_to_response(config)


@router.post(
    "/config",
    response_model=BillingConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update billing configuration",
)
async def upsert_billing_config(
    request: BillingConfigCreate,
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Create or update billing configuration for a site."""
    # Build domain objects
    tou_windows = [
        TouWindow(start_hour=w.start_hour, end_hour=w.end_hour)
        for w in request.tou_config.peak_windows
    ]
    tou_config = TouConfig(
        peak_windows=tou_windows,
        timezone=request.tou_config.timezone,
    )

    prices = BillingPrices(
        price_offpeak_import=request.prices.price_offpeak_import,
        price_peak_import=request.prices.price_peak_import,
        price_offpeak_settlement=request.prices.price_offpeak_settlement,
        price_peak_settlement=request.prices.price_peak_settlement,
        fixed_charge_per_billing_month=request.prices.fixed_charge_per_billing_month,
    )

    config = BillingConfig(
        site_id=request.site_id,
        anchor_day=request.anchor_day,
        tou_config=tou_config,
        prices=prices,
        fixed_proration_mode=FixedProrationMode(request.fixed_proration_mode),
        net_metering_enabled=request.net_metering_enabled,
    )

    result = await nm_repo.upsert_billing_config(config)
    await uow.commit()

    return _config_to_response(result)


# =========================================================================
# Running Bill Endpoints
# =========================================================================

@router.get(
    "/running",
    response_model=RunningBillResponse,
    summary="Get running bill to-date",
)
async def get_running_bill(
    site_id: UUID = Query(..., description="Site ID"),
    target_date: Optional[date] = Query(None, description="Date (defaults to today)"),
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """
    Get running bill status for the current billing month.

    Shows provisional bill to-date with surplus/deficit indicator.
    """
    target_date = target_date or date.today()

    # Get config for billing month bounds
    config = await nm_repo.get_billing_config_by_site(site_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing configuration not found",
        )

    # Get billing period bounds for the target date
    month_start, month_end = config.get_billing_month_bounds(target_date)

    # Get latest snapshot (only from current billing period, not old data)
    snapshot = await nm_repo.get_daily_snapshot(site_id, target_date)

    if not snapshot:
        # Try yesterday if today's not ready yet (still within current billing period)
        yesterday = target_date - timedelta(days=1)
        if yesterday >= month_start:
            snapshot = await nm_repo.get_daily_snapshot(site_id, yesterday)

    # If no snapshot found for current billing period, return zeros
    # This happens when billing data is being regenerated after recalculation
    if not snapshot:
        from datetime import datetime, timezone as dt_timezone

        # Calculate days elapsed in billing period
        days_elapsed = (target_date - month_start).days + 1
        total_days = (month_end - month_start).days + 1
        progress_percent = (days_elapsed / total_days) * 100

        return RunningBillResponse(
            site_id=site_id,
            date=target_date,
            billing_month_id=None,
            billing_period_start=month_start,
            billing_period_end=month_end,
            days_elapsed=days_elapsed,
            total_days_in_month=total_days,
            progress_percent=progress_percent,
            import_off_kwh=0.0,
            export_off_kwh=0.0,
            import_peak_kwh=0.0,
            export_peak_kwh=0.0,
            solar_generation_kwh=0.0,
            load_consumption_kwh=0.0,
            net_import_off_kwh=0.0,
            net_import_peak_kwh=0.0,
            credits_off_cycle_kwh_balance=0.0,
            credits_peak_cycle_kwh_balance=0.0,
            bill_off_energy_rs=0.0,
            bill_peak_energy_rs=0.0,
            fixed_prorated_rs=0.0,
            expected_cycle_credit_rs=0.0,
            bill_raw_rs_to_date=0.0,
            bill_credit_balance_rs_to_date=0.0,
            bill_final_rs_to_date=0.0,
            surplus_deficit_flag="NEUTRAL",
            net_kwh_position=0.0,
            generated_at=datetime.now(dt_timezone.utc),
        )

    return RunningBillResponse(
        site_id=snapshot.site_id,
        date=snapshot.date,
        billing_month_id=snapshot.billing_month_id,
        billing_period_start=month_start,
        billing_period_end=month_end,
        days_elapsed=snapshot.days_elapsed,
        total_days_in_month=snapshot.total_days_in_month,
        progress_percent=snapshot.progress_percent,
        import_off_kwh=float(snapshot.import_off_kwh),
        export_off_kwh=float(snapshot.export_off_kwh),
        import_peak_kwh=float(snapshot.import_peak_kwh),
        export_peak_kwh=float(snapshot.export_peak_kwh),
        solar_generation_kwh=float(snapshot.solar_generation_kwh),
        load_consumption_kwh=float(snapshot.load_consumption_kwh),
        net_import_off_kwh=float(snapshot.net_import_off_kwh),
        net_import_peak_kwh=float(snapshot.net_import_peak_kwh),
        credits_off_cycle_kwh_balance=float(snapshot.credits_off_cycle_kwh_balance),
        credits_peak_cycle_kwh_balance=float(snapshot.credits_peak_cycle_kwh_balance),
        bill_off_energy_rs=float(snapshot.bill_off_energy_rs),
        bill_peak_energy_rs=float(snapshot.bill_peak_energy_rs),
        fixed_prorated_rs=float(snapshot.fixed_prorated_rs),
        expected_cycle_credit_rs=float(snapshot.expected_cycle_credit_rs),
        bill_raw_rs_to_date=float(snapshot.bill_raw_rs_to_date),
        bill_credit_balance_rs_to_date=float(snapshot.bill_credit_balance_rs_to_date),
        bill_final_rs_to_date=float(snapshot.bill_final_rs_to_date),
        surplus_deficit_flag=snapshot.surplus_deficit_flag.value,
        net_kwh_position=float(snapshot.net_kwh_position),
        generated_at=snapshot.generated_at,
    )


@router.get(
    "/daily",
    response_model=DailySnapshotsListResponse,
    summary="Get daily billing snapshots",
)
async def get_daily_snapshots(
    site_id: UUID = Query(..., description="Site ID"),
    from_date: Optional[date] = Query(None, description="Start date"),
    to_date: Optional[date] = Query(None, description="End date"),
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """
    Get daily billing snapshots for sparkline charts.

    Defaults to last 30 days if dates not specified.
    """
    to_date = to_date or date.today()
    from_date = from_date or (to_date - timedelta(days=30))

    snapshots = await nm_repo.get_daily_snapshots_for_period(
        site_id, from_date, to_date
    )

    return DailySnapshotsListResponse(
        snapshots=[
            DailySnapshotResponse(
                id=s.id,
                site_id=s.site_id,
                date=s.date,
                billing_month_id=s.billing_month_id,
                import_off_kwh=float(s.import_off_kwh),
                export_off_kwh=float(s.export_off_kwh),
                import_peak_kwh=float(s.import_peak_kwh),
                export_peak_kwh=float(s.export_peak_kwh),
                solar_generation_kwh=float(s.solar_generation_kwh),
                load_consumption_kwh=float(s.load_consumption_kwh),
                bill_final_rs_to_date=float(s.bill_final_rs_to_date),
                surplus_deficit_flag=s.surplus_deficit_flag.value,
                net_kwh_position=float(s.net_kwh_position),
                generated_at=s.generated_at,
            )
            for s in snapshots
        ],
        total=len(snapshots),
    )


# =========================================================================
# Billing Month Endpoints
# =========================================================================

@router.get(
    "/months",
    response_model=BillingMonthListResponse,
    summary="List billing months",
)
async def list_billing_months(
    site_id: UUID = Query(..., description="Site ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """List billing months for a site."""
    months = await nm_repo.list_billing_months(
        site_id=site_id,
        year=year,
        status=status,
        limit=limit,
        offset=offset,
    )

    return BillingMonthListResponse(
        months=[_month_to_response(m) for m in months],
        total=len(months),
    )


@router.get(
    "/months/{month_id}",
    response_model=BillingMonthResponse,
    summary="Get billing month details",
)
async def get_billing_month(
    month_id: UUID,
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """Get a specific billing month by ID."""
    month = await nm_repo.get_billing_month_by_id(month_id)

    if not month:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing month not found",
        )

    return _month_to_response(month)


# =========================================================================
# Billing Cycle Endpoints
# =========================================================================

@router.get(
    "/cycles",
    response_model=BillingCycleListResponse,
    summary="List billing cycles",
)
async def list_billing_cycles(
    site_id: UUID = Query(..., description="Site ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(12, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """List billing cycles for a site."""
    cycles = await nm_repo.list_billing_cycles(
        site_id=site_id,
        year=year,
        status=status,
        limit=limit,
        offset=offset,
    )

    return BillingCycleListResponse(
        cycles=[_cycle_to_response(c) for c in cycles],
        total=len(cycles),
    )


@router.get(
    "/cycles/{cycle_id}",
    response_model=BillingCycleResponse,
    summary="Get billing cycle details",
)
async def get_billing_cycle(
    cycle_id: UUID,
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """Get a specific billing cycle by ID."""
    cycle = await nm_repo.get_billing_cycle_by_id(cycle_id)

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing cycle not found",
        )

    return _cycle_to_response(cycle)


# =========================================================================
# Summary Endpoints
# =========================================================================

@router.get(
    "/summary",
    response_model=BillingSummaryResponse,
    summary="Get current billing summary",
)
async def get_billing_summary(
    site_id: UUID = Query(..., description="Site ID"),
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """
    Get quick summary of current billing month.

    Useful for dashboard billing card widget.
    """
    # Get config
    config = await nm_repo.get_billing_config_by_site(site_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing configuration not found",
        )

    # Get latest snapshot
    snapshot = await nm_repo.get_latest_daily_snapshot(site_id)

    # If no snapshot, return zeros for current billing period
    if not snapshot:
        today = date.today()
        month_start, month_end = config.get_billing_month_bounds(today)
        billing_month = config.get_billing_month_number(today)

        days_elapsed = (today - month_start).days + 1
        total_days = (month_end - month_start).days + 1
        days_remaining = total_days - days_elapsed
        progress_percent = (days_elapsed / total_days) * 100

        return BillingSummaryResponse(
            billing_month=billing_month,
            year=month_start.year,
            billing_period_start=month_start,
            billing_period_end=month_end,
            import_off_kwh=0.0,
            import_peak_kwh=0.0,
            export_off_kwh=0.0,
            export_peak_kwh=0.0,
            fixed_charge=float(config.prices.fixed_charge_per_billing_month),
            bill_amount=0.0,
            credit_balance=0.0,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
            progress_percent=progress_percent,
            estimated_savings_month=0.0,
            total_savings_since_install=0.0,
        )

    month_start, month_end = config.get_billing_month_bounds(snapshot.date)
    billing_month = config.get_billing_month_number(snapshot.date)

    # Calculate estimated monthly savings
    # Savings = what you would have paid without solar - what you actually paid with solar

    # Calculate average import rate (weighted by typical usage pattern)
    # Use 60% off-peak, 40% peak as typical residential pattern
    avg_import_rate = (
        (float(config.prices.price_offpeak_import) * 0.6) +
        (float(config.prices.price_peak_import) * 0.4)
    )

    # Cost WITHOUT solar = all load consumption bought from grid + fixed charges
    estimated_cost_without_solar = (
        float(snapshot.load_consumption_kwh) * avg_import_rate +
        float(snapshot.fixed_prorated_rs)  # Include fixed charges
    )

    # Cost WITH solar = actual bill (already includes fixed charges)
    actual_cost_with_solar = float(snapshot.bill_final_rs_to_date)

    # Monthly savings
    estimated_monthly_savings = max(0, estimated_cost_without_solar - actual_cost_with_solar)

    # Calculate total savings since installation
    # Sum savings from all finalized billing months
    total_savings_since_install = 0.0
    try:
        # Get all finalized billing months for this site
        all_months = await nm_repo.list_billing_months(
            site_id=site_id,
            status="finalized",
            limit=1000  # Get all finalized months
        )

        # Calculate savings for each finalized month
        for month in all_months:
            # Cost without solar = all load would be imported from grid + fixed charges
            load_consumption = float(month.load_consumption_kwh)
            estimated_cost_without_solar_month = (
                load_consumption * avg_import_rate +
                float(month.bill_fixed_rs)
            )

            # Cost with solar = actual bill paid
            actual_bill = float(month.bill_final_rs)

            # Savings for this month
            month_savings = max(0, estimated_cost_without_solar_month - actual_bill)
            total_savings_since_install += month_savings

        # Add current month's savings to the total
        total_savings_since_install += estimated_monthly_savings
    except Exception as e:
        # If calculation fails, log and return 0
        print(f"Failed to calculate total savings: {e}")
        total_savings_since_install = 0.0

    return BillingSummaryResponse(
        billing_month=billing_month,
        year=month_start.year,
        billing_period_start=month_start,
        billing_period_end=month_end,
        import_off_kwh=float(snapshot.import_off_kwh),
        import_peak_kwh=float(snapshot.import_peak_kwh),
        export_off_kwh=float(snapshot.export_off_kwh),
        export_peak_kwh=float(snapshot.export_peak_kwh),
        fixed_charge=float(config.prices.fixed_charge_per_billing_month),
        bill_amount=float(snapshot.bill_final_rs_to_date),
        credit_balance=float(snapshot.bill_credit_balance_rs_to_date),
        days_elapsed=snapshot.days_elapsed,
        days_remaining=snapshot.days_remaining,
        progress_percent=snapshot.progress_percent,
        estimated_savings_month=estimated_monthly_savings,
        total_savings_since_install=total_savings_since_install,
    )


@router.get(
    "/trend",
    response_model=BillingTrendResponse,
    summary="Get billing trend",
)
async def get_billing_trend(
    site_id: UUID = Query(..., description="Site ID"),
    months: int = Query(12, ge=1, le=24, description="Number of months"),
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """Get billing trend for charting."""
    trend_data = await nm_repo.get_billing_trend(site_id, months)

    return BillingTrendResponse(
        trend=[BillingTrendItem(**item) for item in trend_data],
        months=len(trend_data),
    )


@router.get(
    "/yearly/{site_id}/{year}",
    response_model=YearlyBillingSummaryResponse,
    summary="Get yearly billing summary",
)
async def get_yearly_summary(
    site_id: UUID,
    year: int,
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
):
    """Get aggregated billing summary for a year."""
    summary = await nm_repo.get_yearly_billing_summary(site_id, year)
    return YearlyBillingSummaryResponse(**summary)


# =========================================================================
# Capacity Analysis Endpoints
# =========================================================================

@router.get(
    "/capacity/status",
    response_model=CapacityStatusResponse,
    summary="Get capacity analysis",
)
async def get_capacity_status(
    site_id: UUID = Query(..., description="Site ID"),
    current_user: User = Depends(get_current_user),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
    site_repo: SQLAlchemySiteRepository = Depends(get_site_repo),
):
    """
    Analyze whether system is under/over-capacity.

    Based on last 12 months of billing data.
    """
    # Get site for installed capacity
    site = await site_repo.get_by_id(site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    # Get installed capacity from site configuration
    installed_kw = 0.0
    if site.configuration and site.configuration.installed_capacity_kw:
        installed_kw = float(site.configuration.installed_capacity_kw)

    # Get yearly summary
    current_year = date.today().year
    summary = await nm_repo.get_yearly_billing_summary(site_id, current_year)

    # Calculate required capacity for zero bill (simplified)
    # This is a rough estimate based on import/export ratio
    annual_bill = summary.get("total_bill_rs", 0)
    total_import = summary.get("total_import_kwh", 0)
    total_export = summary.get("total_export_kwh", 0)
    total_solar = summary.get("total_solar_kwh", 0)

    # Estimate required capacity
    if installed_kw > 0 and total_solar > 0:
        kwh_per_kw = total_solar / installed_kw
        if kwh_per_kw > 0 and total_import > total_export:
            extra_kwh_needed = total_import - total_export
            extra_kw_needed = extra_kwh_needed / kwh_per_kw
            required_kw = installed_kw + extra_kw_needed
        else:
            required_kw = installed_kw
    else:
        required_kw = installed_kw

    deficit_kw = required_kw - installed_kw

    # Determine status
    if deficit_kw > 0.25:
        capacity_status = "under-capacity"
    elif deficit_kw < -0.25:
        capacity_status = "over-capacity"
    else:
        capacity_status = "balanced"

    # Count months with positive bill
    months = await nm_repo.list_billing_months(site_id, year=current_year, limit=12)
    months_with_bill = sum(1 for m in months if float(m.bill_final_rs) > 0)

    return CapacityStatusResponse(
        site_id=site_id,
        installed_kw=installed_kw,
        required_kw_for_zero_bill=max(0, required_kw),
        deficit_kw=deficit_kw,
        status=capacity_status,
        annual_bill_rs=annual_bill,
        annual_import_kwh=total_import,
        annual_export_kwh=total_export,
        annual_solar_kwh=total_solar,
        months_with_positive_bill=months_with_bill,
    )


# =========================================================================
# Admin Endpoints
# =========================================================================

@router.post(
    "/cycle/close",
    response_model=ForceCycleCloseResponse,
    summary="Force close billing cycle (Admin)",
)
async def force_close_cycle(
    request: ForceCycleCloseRequest,
    current_user: User = Depends(require_admin),
    nm_repo: SQLAlchemyNetMeteringRepository = Depends(get_net_metering_repo),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Force close a billing cycle.

    Triggers settlement of remaining credits. Admin only.
    """
    cycle = await nm_repo.get_billing_cycle_by_id(request.cycle_id)
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing cycle not found",
        )

    if cycle.status.value == "finalized":
        return ForceCycleCloseResponse(
            success=False,
            cycle_id=request.cycle_id,
            settlement_total_rs=float(cycle.total_settlement_rs),
            message="Cycle already finalized",
        )

    # Get config for settlement prices
    config = await nm_repo.get_billing_config_by_site(cycle.site_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing configuration found",
        )

    # Finalize cycle
    cycle.finalize(
        config.prices,
        cycle.closing_credit_off_kwh,
        cycle.closing_credit_peak_kwh,
    )

    await nm_repo.update_billing_cycle(cycle)
    await uow.commit()

    return ForceCycleCloseResponse(
        success=True,
        cycle_id=request.cycle_id,
        settlement_total_rs=float(cycle.total_settlement_rs),
        message="Cycle closed successfully",
    )


# =========================================================================
# Helper Functions
# =========================================================================

def _config_to_response(config: BillingConfig) -> BillingConfigResponse:
    """Convert domain config to response."""
    return BillingConfigResponse(
        id=config.id,
        site_id=config.site_id,
        anchor_day=config.anchor_day,
        tou_config=TouConfigSchema(
            peak_windows=[
                TouWindowSchema(start_hour=w.start_hour, end_hour=w.end_hour)
                for w in config.tou_config.peak_windows
            ],
            timezone=config.tou_config.timezone,
        ),
        prices=BillingPricesSchema(
            price_offpeak_import=float(config.prices.price_offpeak_import),
            price_peak_import=float(config.prices.price_peak_import),
            price_offpeak_settlement=float(config.prices.price_offpeak_settlement),
            price_peak_settlement=float(config.prices.price_peak_settlement),
            fixed_charge_per_billing_month=float(config.prices.fixed_charge_per_billing_month),
        ),
        fixed_proration_mode=config.fixed_proration_mode.value,
        net_metering_enabled=config.net_metering_enabled,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _month_to_response(month) -> BillingMonthResponse:
    """Convert domain month to response."""
    return BillingMonthResponse(
        id=month.id,
        site_id=month.site_id,
        billing_cycle_id=month.billing_cycle_id,
        billing_month_number=month.billing_month_number,
        year=month.year,
        period_start_date=month.period_start_date,
        period_end_date=month.period_end_date,
        import_off_kwh=float(month.import_off_kwh),
        export_off_kwh=float(month.export_off_kwh),
        import_peak_kwh=float(month.import_peak_kwh),
        export_peak_kwh=float(month.export_peak_kwh),
        solar_generation_kwh=float(month.solar_generation_kwh),
        load_consumption_kwh=float(month.load_consumption_kwh),
        net_import_off_kwh=float(month.net_import_off_kwh),
        net_import_peak_kwh=float(month.net_import_peak_kwh),
        credits_applied_off_kwh=float(month.credits_applied_off_kwh),
        credits_applied_peak_kwh=float(month.credits_applied_peak_kwh),
        credits_generated_off_kwh=float(month.credits_generated_off_kwh),
        credits_generated_peak_kwh=float(month.credits_generated_peak_kwh),
        bill_off_energy_rs=float(month.bill_off_energy_rs),
        bill_peak_energy_rs=float(month.bill_peak_energy_rs),
        bill_fixed_rs=float(month.bill_fixed_rs),
        cycle_settlement_off_rs=float(month.cycle_settlement_off_rs),
        cycle_settlement_peak_rs=float(month.cycle_settlement_peak_rs),
        bill_raw_rs=float(month.bill_raw_rs),
        opening_credit_balance_rs=float(month.opening_credit_balance_rs),
        closing_credit_balance_rs=float(month.closing_credit_balance_rs),
        bill_final_rs=float(month.bill_final_rs),
        status=month.status.value,
        is_cycle_end_month=month.is_cycle_end_month,
        finalized_at=month.finalized_at,
        created_at=month.created_at,
        updated_at=month.updated_at,
    )


def _cycle_to_response(cycle) -> BillingCycleResponse:
    """Convert domain cycle to response."""
    return BillingCycleResponse(
        id=cycle.id,
        site_id=cycle.site_id,
        cycle_number=cycle.cycle_number,
        year=cycle.year,
        cycle_start_date=cycle.cycle_start_date,
        cycle_end_date=cycle.cycle_end_date,
        opening_credit_off_kwh=float(cycle.opening_credit_off_kwh),
        opening_credit_peak_kwh=float(cycle.opening_credit_peak_kwh),
        opening_cash_credit_rs=float(cycle.opening_cash_credit_rs),
        total_import_off_kwh=float(cycle.total_import_off_kwh),
        total_export_off_kwh=float(cycle.total_export_off_kwh),
        total_import_peak_kwh=float(cycle.total_import_peak_kwh),
        total_export_peak_kwh=float(cycle.total_export_peak_kwh),
        credits_generated_off_kwh=float(cycle.credits_generated_off_kwh),
        credits_consumed_off_kwh=float(cycle.credits_consumed_off_kwh),
        credits_generated_peak_kwh=float(cycle.credits_generated_peak_kwh),
        credits_consumed_peak_kwh=float(cycle.credits_consumed_peak_kwh),
        closing_credit_off_kwh=float(cycle.closing_credit_off_kwh),
        closing_credit_peak_kwh=float(cycle.closing_credit_peak_kwh),
        settlement_off_rs=float(cycle.settlement_off_rs),
        settlement_peak_rs=float(cycle.settlement_peak_rs),
        total_settlement_rs=float(cycle.total_settlement_rs),
        closing_cash_credit_rs=float(cycle.closing_cash_credit_rs),
        status=cycle.status.value,
        finalized_at=cycle.finalized_at,
        created_at=cycle.created_at,
        updated_at=cycle.updated_at,
    )
