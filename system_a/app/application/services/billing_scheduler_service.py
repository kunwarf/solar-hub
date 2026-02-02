"""
Billing Scheduler Application Service.

Orchestrates daily billing calculations for all sites.
Runs as a scheduled job to compute running bills and finalize billing periods.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from ...domain.entities.net_metering import (
    BillingConfig,
    BillingCycle,
    BillingMonth,
    DailyBillingSnapshot,
    CreditPool,
    BillingPrices,
    TouConfig,
    SurplusDeficitFlag,
    BillingStatus,
    MonthlyEnergyAggregate,
    HourlyEnergyData,
)
from ...domain.services.net_metering_calculator import (
    NetMeteringCalculator,
    BillingCalculationResult,
    RunningBillResult,
)
from ...infrastructure.database.repositories.net_metering_repository import (
    SQLAlchemyNetMeteringRepository,
)
from ...infrastructure.database.repositories.telemetry_repository import (
    SQLAlchemyTelemetryRepository,
)
from ...infrastructure.database.repositories.telemetry_system_b_repository import (
    SystemBTelemetryRepository,
)
from ...infrastructure.database.repositories.site_repository import (
    SQLAlchemySiteRepository,
)
from ...infrastructure.external.system_b_client import SystemBClient, SystemBClientError
from ..interfaces.unit_of_work import UnitOfWork
from ...config import settings

logger = logging.getLogger(__name__)


@dataclass
class DailyJobResult:
    """Result of daily billing job for a single site."""
    site_id: UUID
    date: date
    success: bool
    snapshot_id: Optional[UUID] = None
    billing_month_id: Optional[UUID] = None
    finalized_month: bool = False
    finalized_cycle: bool = False
    error: Optional[str] = None


@dataclass
class BulkJobResult:
    """Result of bulk daily billing job."""
    job_date: date
    total_sites: int
    successful: int
    failed: int
    site_results: List[DailyJobResult]
    duration_seconds: float


class BillingSchedulerService:
    """
    Application service for scheduled billing operations.

    Responsibilities:
    - Run daily billing job for all active sites
    - Compute running bill snapshots
    - Detect and finalize billing month boundaries
    - Detect and finalize 3-month cycle boundaries
    - Handle backfill for missed days
    """

    def __init__(
        self,
        net_metering_repo: SQLAlchemyNetMeteringRepository,
        telemetry_repo: SQLAlchemyTelemetryRepository,
        site_repo: SQLAlchemySiteRepository,
        calculator: NetMeteringCalculator,
        system_b_telemetry_repo: Optional[SystemBTelemetryRepository] = None,
    ):
        self._nm_repo = net_metering_repo
        self._telemetry_repo = telemetry_repo
        self._system_b_telemetry_repo = system_b_telemetry_repo
        self._site_repo = site_repo
        self._calculator = calculator

    async def run_daily_billing_job(
        self,
        target_date: Optional[date] = None,
        site_ids: Optional[List[UUID]] = None,
    ) -> BulkJobResult:
        """
        Run daily billing computation for all (or specified) sites.

        This is the main entry point called by the scheduler.

        Args:
            target_date: Date to compute billing for (defaults to yesterday)
            site_ids: Optional list of specific sites (defaults to all active)

        Returns:
            BulkJobResult with summary and per-site results
        """
        start_time = datetime.now()
        target_date = target_date or (date.today() - timedelta(days=1))

        logger.info("Starting daily billing job for %s", target_date)

        # Get sites to process
        if site_ids:
            sites = []
            for sid in site_ids:
                site = await self._site_repo.get_by_id(sid)
                if site:
                    sites.append(site)
        else:
            sites = await self._site_repo.list_active_sites(limit=1000)

        results: List[DailyJobResult] = []

        for site in sites:
            try:
                result = await self.compute_site_daily_snapshot(
                    site_id=site.id,
                    target_date=target_date,
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "Failed to process site %s for %s: %s",
                    site.id, target_date, e, exc_info=True
                )
                results.append(DailyJobResult(
                    site_id=site.id,
                    date=target_date,
                    success=False,
                    error=str(e),
                ))

        duration = (datetime.now() - start_time).total_seconds()
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        logger.info(
            "Daily billing job completed: %d/%d sites successful in %.2fs",
            successful, len(results), duration
        )

        return BulkJobResult(
            job_date=target_date,
            total_sites=len(results),
            successful=successful,
            failed=failed,
            site_results=results,
            duration_seconds=duration,
        )

    async def compute_site_daily_snapshot(
        self,
        site_id: UUID,
        target_date: date,
    ) -> DailyJobResult:
        """
        Compute daily billing snapshot for a single site.

        Args:
            site_id: Site to process
            target_date: Date to compute

        Returns:
            DailyJobResult with operation details
        """
        logger.debug("Computing daily snapshot for site %s date %s", site_id, target_date)

        # Get billing config
        config = await self._nm_repo.get_billing_config_by_site(site_id)
        if not config:
            logger.warning("No billing config for site %s, skipping", site_id)
            return DailyJobResult(
                site_id=site_id,
                date=target_date,
                success=False,
                error="No billing configuration",
            )

        # Get billing month bounds
        month_start, month_end = config.get_billing_month_bounds(target_date)
        billing_month_number = config.get_billing_month_number(target_date)
        year = month_start.year

        # Check if month boundary crossed (need to finalize previous month)
        finalized_month = False
        finalized_cycle = False

        if target_date == month_start:
            # First day of new billing month - check if we need to finalize previous
            prev_date = target_date - timedelta(days=1)
            prev_month = await self._nm_repo.get_billing_month_by_date(site_id, prev_date)
            if prev_month and prev_month.status == BillingStatus.ACTIVE:
                finalized_month = await self._finalize_billing_month(
                    site_id, prev_month.id, config
                )
                # Check if this was a cycle-end month
                if prev_month.is_cycle_end_month:
                    cycle = await self._nm_repo.get_active_billing_cycle(site_id, prev_date)
                    if cycle:
                        finalized_cycle = await self._finalize_billing_cycle(
                            site_id, cycle.id, config
                        )

        # Get or create current billing month
        billing_month = await self._ensure_billing_month_exists(
            site_id, year, billing_month_number, month_start, month_end, config
        )

        # Get or create current billing cycle
        cycle = await self._ensure_billing_cycle_exists(
            site_id, year, billing_month_number, config
        )

        # Get hourly telemetry data for month-to-date
        hourly_data = await self._get_hourly_telemetry_for_period(
            site_id, month_start, target_date
        )

        if not hourly_data:
            logger.warning(
                "No telemetry data for site %s from %s to %s",
                site_id, month_start, target_date
            )
            # Create empty snapshot
            snapshot = DailyBillingSnapshot(
                site_id=site_id,
                date=target_date,
                billing_month_id=billing_month.id,
                days_elapsed=(target_date - month_start).days + 1,
                total_days_in_month=(month_end - month_start).days + 1,
            )
            await self._nm_repo.upsert_daily_snapshot(snapshot)

            return DailyJobResult(
                site_id=site_id,
                date=target_date,
                success=True,
                snapshot_id=snapshot.id,
                billing_month_id=billing_month.id,
                finalized_month=finalized_month,
                finalized_cycle=finalized_cycle,
            )

        # Aggregate hourly data by day
        daily_aggregates = self._aggregate_hourly_to_daily(hourly_data, config.tou_config)

        # Get cycle credit pools
        off_pool, peak_pool = await self._get_cycle_credit_pools(cycle)

        # Get opening cash balance
        opening_cash = await self._get_opening_cash_balance(site_id, billing_month)

        # Calculate running bill
        result = self._calculator.calculate_running_bill(
            daily_aggregates=daily_aggregates,
            billing_config=config,
            off_pool=off_pool,
            peak_pool=peak_pool,
            opening_cash_balance=opening_cash,
            target_date=target_date,
        )

        # Update snapshot with site and month references
        result.snapshot.site_id = site_id
        result.snapshot.billing_month_id = billing_month.id

        # Persist snapshot
        saved_snapshot = await self._nm_repo.upsert_daily_snapshot(result.snapshot)

        logger.debug(
            "Saved daily snapshot for site %s: bill_to_date=%.2f, surplus=%s",
            site_id, float(result.snapshot.bill_final_rs_to_date),
            result.snapshot.surplus_deficit_flag.value,
        )

        return DailyJobResult(
            site_id=site_id,
            date=target_date,
            success=True,
            snapshot_id=saved_snapshot.id,
            billing_month_id=billing_month.id,
            finalized_month=finalized_month,
            finalized_cycle=finalized_cycle,
        )

    async def backfill_site(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[DailyJobResult]:
        """
        Backfill billing snapshots for a date range.

        Use when tariffs change or data was missing.

        Args:
            site_id: Site to backfill
            start_date: Start of backfill range
            end_date: End of backfill range

        Returns:
            List of DailyJobResult for each day
        """
        logger.info(
            "Backfilling site %s from %s to %s",
            site_id, start_date, end_date
        )

        results = []
        current = start_date

        while current <= end_date:
            result = await self.compute_site_daily_snapshot(site_id, current)
            results.append(result)
            current += timedelta(days=1)

        successful = sum(1 for r in results if r.success)
        logger.info(
            "Backfill completed: %d/%d days successful",
            successful, len(results)
        )

        return results

    async def force_close_cycle(
        self,
        site_id: UUID,
        cycle_id: UUID,
    ) -> bool:
        """
        Admin function to force-close a billing cycle.

        Args:
            site_id: Site ID
            cycle_id: Cycle to close

        Returns:
            True if successful
        """
        config = await self._nm_repo.get_billing_config_by_site(site_id)
        if not config:
            raise ValueError(f"No billing config for site {site_id}")

        return await self._finalize_billing_cycle(site_id, cycle_id, config)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _ensure_billing_month_exists(
        self,
        site_id: UUID,
        year: int,
        billing_month_number: int,
        month_start: date,
        month_end: date,
        config: BillingConfig,
    ) -> BillingMonth:
        """Get or create billing month record."""
        existing = await self._nm_repo.get_billing_month_by_year_number(
            site_id, year, billing_month_number
        )
        if existing:
            return existing

        # Get the cycle this month belongs to
        cycle = await self._ensure_billing_cycle_exists(
            site_id, year, billing_month_number, config
        )

        # Create new billing month
        month = BillingMonth(
            site_id=site_id,
            billing_cycle_id=cycle.id,
            billing_month_number=billing_month_number,
            year=year,
            period_start_date=month_start,
            period_end_date=month_end,
            is_cycle_end_month=config.is_cycle_end_month(billing_month_number),
            config_hash=self._calculator.compute_config_hash(config),
        )

        return await self._nm_repo.create_billing_month(month)

    async def _ensure_billing_cycle_exists(
        self,
        site_id: UUID,
        year: int,
        billing_month_number: int,
        config: BillingConfig,
    ) -> BillingCycle:
        """Get or create billing cycle record."""
        cycle_number = config.get_cycle_number(billing_month_number)

        existing = await self._nm_repo.get_billing_cycle_by_year_number(
            site_id, year, cycle_number
        )
        if existing:
            return existing

        # Calculate cycle dates
        first_month_of_cycle = ((cycle_number - 1) * 3) + 1
        cycle_start = date(year, first_month_of_cycle, config.anchor_day)

        last_month_of_cycle = first_month_of_cycle + 2
        if last_month_of_cycle <= 12:
            cycle_end_month = last_month_of_cycle + 1
            cycle_end_year = year
        else:
            cycle_end_month = 1
            cycle_end_year = year + 1

        if cycle_end_month > 12:
            cycle_end_month = 1
            cycle_end_year += 1

        cycle_end = date(cycle_end_year, cycle_end_month, config.anchor_day) - timedelta(days=1)

        # Get previous cycle's closing balances
        opening_off = Decimal("0")
        opening_peak = Decimal("0")
        opening_cash = Decimal("0")

        if cycle_number > 1:
            prev_cycle = await self._nm_repo.get_billing_cycle_by_year_number(
                site_id, year, cycle_number - 1
            )
            if prev_cycle and prev_cycle.status == BillingStatus.FINALIZED:
                # After settlement, kWh credits reset to 0, only cash carries forward
                opening_cash = prev_cycle.closing_cash_credit_rs
        elif year > 2020:  # Check previous year's Q4
            prev_cycle = await self._nm_repo.get_billing_cycle_by_year_number(
                site_id, year - 1, 4
            )
            if prev_cycle and prev_cycle.status == BillingStatus.FINALIZED:
                opening_cash = prev_cycle.closing_cash_credit_rs

        cycle = BillingCycle(
            site_id=site_id,
            cycle_number=cycle_number,
            year=year,
            cycle_start_date=cycle_start,
            cycle_end_date=cycle_end,
            opening_credit_off_kwh=opening_off,
            opening_credit_peak_kwh=opening_peak,
            opening_cash_credit_rs=opening_cash,
            config_hash=self._calculator.compute_config_hash(config),
        )

        return await self._nm_repo.create_billing_cycle(cycle)

    async def _finalize_billing_month(
        self,
        site_id: UUID,
        month_id: UUID,
        config: BillingConfig,
    ) -> bool:
        """Finalize a billing month."""
        month = await self._nm_repo.get_billing_month_by_id(month_id)
        if not month or month.status == BillingStatus.FINALIZED:
            return False

        # Get all daily snapshots for this month
        snapshots = await self._nm_repo.get_daily_snapshots_for_period(
            site_id, month.period_start_date, month.period_end_date
        )

        if snapshots:
            # Use the last snapshot's values for the final month record
            final_snapshot = snapshots[-1]

            month.import_off_kwh = final_snapshot.import_off_kwh
            month.export_off_kwh = final_snapshot.export_off_kwh
            month.import_peak_kwh = final_snapshot.import_peak_kwh
            month.export_peak_kwh = final_snapshot.export_peak_kwh
            month.solar_generation_kwh = final_snapshot.solar_generation_kwh
            month.load_consumption_kwh = final_snapshot.load_consumption_kwh
            month.net_import_off_kwh = final_snapshot.net_import_off_kwh
            month.net_import_peak_kwh = final_snapshot.net_import_peak_kwh
            month.bill_off_energy_rs = final_snapshot.bill_off_energy_rs
            month.bill_peak_energy_rs = final_snapshot.bill_peak_energy_rs
            month.bill_fixed_rs = config.prices.fixed_charge_per_billing_month
            month.bill_raw_rs = final_snapshot.bill_raw_rs_to_date
            month.bill_final_rs = final_snapshot.bill_final_rs_to_date
            month.closing_credit_balance_rs = final_snapshot.bill_credit_balance_rs_to_date

        month.status = BillingStatus.FINALIZED
        month.finalized_at = datetime.now()
        month.config_hash = self._calculator.compute_config_hash(config)

        await self._nm_repo.update_billing_month(month)

        logger.info(
            "Finalized billing month %s for site %s: bill=%.2f",
            month_id, site_id, float(month.bill_final_rs)
        )

        return True

    async def _finalize_billing_cycle(
        self,
        site_id: UUID,
        cycle_id: UUID,
        config: BillingConfig,
    ) -> bool:
        """Finalize a 3-month billing cycle with credit settlement."""
        cycle = await self._nm_repo.get_billing_cycle_by_id(cycle_id)
        if not cycle or cycle.status == BillingStatus.FINALIZED:
            return False

        # Get all months in this cycle
        months = await self._nm_repo.list_billing_months(
            site_id=site_id,
            year=cycle.year,
        )
        cycle_months = [
            m for m in months
            if m.billing_cycle_id == cycle_id
        ]

        # Calculate totals
        total_import_off = sum(m.import_off_kwh for m in cycle_months)
        total_export_off = sum(m.export_off_kwh for m in cycle_months)
        total_import_peak = sum(m.import_peak_kwh for m in cycle_months)
        total_export_peak = sum(m.export_peak_kwh for m in cycle_months)

        # Calculate final credit balances
        # Raw net = import - export
        raw_net_off = total_import_off - total_export_off
        raw_net_peak = total_import_peak - total_export_peak

        # Apply opening credits
        off_pool = CreditPool(credits_kwh=cycle.opening_credit_off_kwh)
        peak_pool = CreditPool(credits_kwh=cycle.opening_credit_peak_kwh)

        if raw_net_off > 0:
            # Net import - consume credits
            _, closing_off = off_pool.apply_credits(raw_net_off)
            cycle.credits_consumed_off_kwh = cycle.opening_credit_off_kwh - closing_off
            cycle.closing_credit_off_kwh = closing_off
        else:
            # Net export - generate credits
            cycle.credits_generated_off_kwh = -raw_net_off
            cycle.closing_credit_off_kwh = cycle.opening_credit_off_kwh + (-raw_net_off)

        if raw_net_peak > 0:
            _, closing_peak = peak_pool.apply_credits(raw_net_peak)
            cycle.credits_consumed_peak_kwh = cycle.opening_credit_peak_kwh - closing_peak
            cycle.closing_credit_peak_kwh = closing_peak
        else:
            cycle.credits_generated_peak_kwh = -raw_net_peak
            cycle.closing_credit_peak_kwh = cycle.opening_credit_peak_kwh + (-raw_net_peak)

        # Settle remaining credits to cash
        cycle.settlement_off_rs = cycle.closing_credit_off_kwh * config.prices.price_offpeak_settlement
        cycle.settlement_peak_rs = cycle.closing_credit_peak_kwh * config.prices.price_peak_settlement
        cycle.total_settlement_rs = cycle.settlement_off_rs + cycle.settlement_peak_rs

        # Update totals
        cycle.total_import_off_kwh = total_import_off
        cycle.total_export_off_kwh = total_export_off
        cycle.total_import_peak_kwh = total_import_peak
        cycle.total_export_peak_kwh = total_export_peak

        # Closing cash = opening + settlement (settlement is added as credit)
        cycle.closing_cash_credit_rs = cycle.opening_cash_credit_rs - cycle.total_settlement_rs

        cycle.status = BillingStatus.FINALIZED
        cycle.finalized_at = datetime.now()
        cycle.config_hash = self._calculator.compute_config_hash(config)

        await self._nm_repo.update_billing_cycle(cycle)

        logger.info(
            "Finalized billing cycle %s for site %s: settlement=%.2f",
            cycle_id, site_id, float(cycle.total_settlement_rs)
        )

        return True

    async def _get_hourly_telemetry_for_period(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[HourlyEnergyData]:
        """
        Get hourly telemetry data with optional dual-read validation.

        Supports three modes based on feature flags:
        1. System A only (default, legacy behavior)
        2. System B only (after migration)
        3. Dual-read with validation (during transition)
        """
        start_time = datetime.combine(start_date, datetime.min.time())
        end_time = datetime.combine(end_date, datetime.max.time())

        # Check if System B should be used (based on feature flags)
        use_system_b = settings.use_system_b_for_billing
        validate_data = settings.validate_system_b_data

        if use_system_b and self._system_b_telemetry_repo:
            logger.info(
                "Using System B for billing telemetry (site=%s, validation=%s)",
                site_id, validate_data
            )

            try:
                # Primary: Fetch from System B
                system_b_summaries = await self._system_b_telemetry_repo.get_hourly_summaries(
                    site_id=site_id,
                    start_time=start_time,
                    end_time=end_time,
                )

                system_b_data = [
                    HourlyEnergyData(
                        timestamp=summary.timestamp_hour,
                        hour=summary.timestamp_hour.hour,
                        load_kwh=summary.energy_consumed_kwh or Decimal("0"),
                        solar_kwh=summary.energy_generated_kwh or Decimal("0"),
                        grid_import_kwh=summary.energy_imported_kwh or Decimal("0"),
                        grid_export_kwh=summary.energy_exported_kwh or Decimal("0"),
                    )
                    for summary in system_b_summaries
                ]

                # Optional: Validate against System A
                if validate_data:
                    logger.info("Dual-read validation enabled for site %s", site_id)
                    try:
                        system_a_summaries = await self._telemetry_repo.get_hourly_summaries(
                            site_id=site_id,
                            start_time=start_time,
                            end_time=end_time,
                        )

                        system_a_data = [
                            HourlyEnergyData(
                                timestamp=summary.timestamp_hour,
                                hour=summary.timestamp_hour.hour,
                                load_kwh=summary.energy_consumed_kwh or Decimal("0"),
                                solar_kwh=summary.energy_generated_kwh or Decimal("0"),
                                grid_import_kwh=summary.energy_imported_kwh or Decimal("0"),
                                grid_export_kwh=summary.energy_exported_kwh or Decimal("0"),
                            )
                            for summary in system_a_summaries
                        ]

                        # Validate consistency
                        self._validate_data_consistency(
                            site_id=site_id,
                            system_a_data=system_a_data,
                            system_b_data=system_b_data,
                        )
                    except Exception as e:
                        logger.error(
                            "Validation failed for site %s: %s. Using System B data anyway.",
                            site_id, e, exc_info=True
                        )

                return system_b_data

            except SystemBClientError as e:
                logger.error(
                    "System B fetch failed for site %s: %s. Falling back to System A.",
                    site_id, e, exc_info=True
                )
                # Fallback to System A on error
                use_system_b = False

        # Fallback or default: Use System A
        if not use_system_b:
            logger.debug("Using System A for billing telemetry (site=%s)", site_id)
            summaries = await self._telemetry_repo.get_hourly_summaries(
                site_id=site_id,
                start_time=start_time,
                end_time=end_time,
            )

            hourly_data = []
            for summary in summaries:
                hourly_data.append(HourlyEnergyData(
                    timestamp=summary.timestamp_hour,
                    hour=summary.timestamp_hour.hour,
                    load_kwh=summary.energy_consumed_kwh or Decimal("0"),
                    solar_kwh=summary.energy_generated_kwh or Decimal("0"),
                    grid_import_kwh=summary.energy_imported_kwh or Decimal("0"),
                    grid_export_kwh=summary.energy_exported_kwh or Decimal("0"),
                ))

            return hourly_data

    def _validate_data_consistency(
        self,
        site_id: UUID,
        system_a_data: List[HourlyEnergyData],
        system_b_data: List[HourlyEnergyData],
        tolerance_kwh: Decimal = Decimal("0.1"),
    ) -> None:
        """
        Validate that System A and System B data match within tolerance.

        Logs discrepancies for monitoring but does not raise exceptions.

        Args:
            site_id: Site UUID for logging
            system_a_data: Data from System A (PostgreSQL)
            system_b_data: Data from System B (TimescaleDB)
            tolerance_kwh: Maximum acceptable difference in kWh
        """
        if len(system_a_data) != len(system_b_data):
            logger.warning(
                "Data count mismatch for site %s: System A has %d points, System B has %d points",
                site_id, len(system_a_data), len(system_b_data)
            )
            return

        total_discrepancies = 0
        max_discrepancy = Decimal("0")

        for a_point, b_point in zip(system_a_data, system_b_data):
            # Check timestamp alignment
            if a_point.timestamp != b_point.timestamp:
                logger.warning(
                    "Timestamp mismatch for site %s: A=%s, B=%s",
                    site_id, a_point.timestamp, b_point.timestamp
                )
                continue

            # Check each energy field
            diff_solar = abs(a_point.solar_kwh - b_point.solar_kwh)
            diff_load = abs(a_point.load_kwh - b_point.load_kwh)
            diff_import = abs(a_point.grid_import_kwh - b_point.grid_import_kwh)
            diff_export = abs(a_point.grid_export_kwh - b_point.grid_export_kwh)

            max_diff = max(diff_solar, diff_load, diff_import, diff_export)

            if max_diff > tolerance_kwh:
                total_discrepancies += 1
                max_discrepancy = max(max_discrepancy, max_diff)

                logger.warning(
                    "Data discrepancy at %s for site %s: "
                    "solar(A=%.3f, B=%.3f, diff=%.3f), "
                    "load(A=%.3f, B=%.3f, diff=%.3f), "
                    "import(A=%.3f, B=%.3f, diff=%.3f), "
                    "export(A=%.3f, B=%.3f, diff=%.3f)",
                    a_point.timestamp.isoformat(),
                    site_id,
                    float(a_point.solar_kwh),
                    float(b_point.solar_kwh),
                    float(diff_solar),
                    float(a_point.load_kwh),
                    float(b_point.load_kwh),
                    float(diff_load),
                    float(a_point.grid_import_kwh),
                    float(b_point.grid_import_kwh),
                    float(diff_import),
                    float(a_point.grid_export_kwh),
                    float(b_point.grid_export_kwh),
                    float(diff_export),
                )

        if total_discrepancies > 0:
            discrepancy_rate = (total_discrepancies / len(system_a_data)) * 100
            logger.warning(
                "Data validation summary for site %s: "
                "%d/%d points (%.2f%%) exceed tolerance of %.3f kWh. "
                "Max discrepancy: %.3f kWh",
                site_id,
                total_discrepancies,
                len(system_a_data),
                discrepancy_rate,
                float(tolerance_kwh),
                float(max_discrepancy),
            )
        else:
            logger.info(
                "Data validation passed for site %s: All %d points within tolerance",
                site_id,
                len(system_a_data),
            )

    def _aggregate_hourly_to_daily(
        self,
        hourly_data: List[HourlyEnergyData],
        tou_config: TouConfig,
    ) -> List[MonthlyEnergyAggregate]:
        """Aggregate hourly data into daily aggregates."""
        # Group by date
        daily_data: Dict[date, List[HourlyEnergyData]] = {}
        for hour in hourly_data:
            day = hour.timestamp.date()
            if day not in daily_data:
                daily_data[day] = []
            daily_data[day].append(hour)

        # Convert to daily aggregates
        aggregates = []
        for day in sorted(daily_data.keys()):
            hours = daily_data[day]
            agg = MonthlyEnergyAggregate.from_hourly_data(hours, tou_config)
            aggregates.append(agg)

        return aggregates

    async def _get_cycle_credit_pools(
        self,
        cycle: BillingCycle,
    ) -> tuple[CreditPool, CreditPool]:
        """Get current credit pool balances for a cycle."""
        # Start with opening balances
        off_credits = cycle.opening_credit_off_kwh
        peak_credits = cycle.opening_credit_peak_kwh

        # Add any credits generated minus consumed during cycle so far
        off_credits += cycle.credits_generated_off_kwh - cycle.credits_consumed_off_kwh
        peak_credits += cycle.credits_generated_peak_kwh - cycle.credits_consumed_peak_kwh

        return (
            CreditPool(credits_kwh=max(Decimal("0"), off_credits)),
            CreditPool(credits_kwh=max(Decimal("0"), peak_credits)),
        )

    async def _get_opening_cash_balance(
        self,
        site_id: UUID,
        billing_month: BillingMonth,
    ) -> Decimal:
        """Get opening cash balance for a billing month."""
        if billing_month.billing_month_number == 1:
            # First month of year - check previous year's last month
            prev_month = await self._nm_repo.get_billing_month_by_year_number(
                site_id, billing_month.year - 1, 12
            )
        else:
            prev_month = await self._nm_repo.get_billing_month_by_year_number(
                site_id, billing_month.year, billing_month.billing_month_number - 1
            )

        if prev_month:
            return prev_month.closing_credit_balance_rs

        return Decimal("0")
