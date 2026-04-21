"""
Net Metering Calculator Domain Service.

Implements Pakistan net metering rules with 3-month netting cycles.
Battery is ignored - all logic is based on netting grid imports/exports only.

Key features:
- Separate peak/off-peak credit pools
- 3-month netting cycles with credit carry-forward
- Cash settlement at cycle end
- Monetary carry-forward for negative bills
- Configurable anchor date billing months
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple, Dict, Any
import hashlib
import json

from ..entities.net_metering import (
    BillingConfig,
    BillingCycle,
    BillingMonth,
    DailyBillingSnapshot,
    CreditPool,
    BillingPrices,
    TouConfig,
    SurplusDeficitFlag,
    BillingStatus,
    HourlyEnergyData,
    MonthlyEnergyAggregate,
    FixedProrationMode,
)


@dataclass
class BillingCalculationResult:
    """Result of a billing calculation."""
    billing_month: BillingMonth
    off_pool: CreditPool
    peak_pool: CreditPool
    cash_balance: Decimal
    is_cycle_end: bool = False
    cycle_settlement_total: Decimal = Decimal("0")


@dataclass
class RunningBillResult:
    """Result of running bill calculation (to-date)."""
    snapshot: DailyBillingSnapshot
    off_pool_balance: Decimal
    peak_pool_balance: Decimal
    expected_settlement: Decimal


@dataclass
class AnnualSimulationResult:
    """Result of annual billing simulation."""
    billing_months: List[BillingMonth]
    billing_cycles: List[BillingCycle]
    total_bill_rs: Decimal
    total_import_kwh: Decimal
    total_export_kwh: Decimal
    final_cash_balance: Decimal
    months_with_positive_bill: int
    capacity_status: str  # "under-capacity", "over-capacity", "balanced"


class NetMeteringCalculator:
    """
    Pure domain service for net metering calculations.

    Implements:
    - TOU determination from timestamps
    - Hourly → billing month aggregation
    - 3-month netting cycle logic
    - Credit pool management
    - Cycle settlement
    - Monthly bill calculation
    - Monetary carry-forward
    - Running bill (to-date) calculation
    """

    def determine_tou_period(self, hour: int, tou_config: TouConfig) -> bool:
        """
        Determine if an hour is peak or off-peak.

        Args:
            hour: Hour of day (0-23)
            tou_config: TOU configuration

        Returns:
            True if peak, False if off-peak
        """
        return tou_config.is_peak_hour(hour)

    def aggregate_hourly_to_monthly(
        self,
        hourly_data: List[HourlyEnergyData],
        tou_config: TouConfig,
    ) -> MonthlyEnergyAggregate:
        """
        Aggregate hourly energy data into monthly TOU buckets.

        Args:
            hourly_data: List of hourly energy readings
            tou_config: TOU configuration for peak/off-peak determination

        Returns:
            MonthlyEnergyAggregate with TOU-split values
        """
        return MonthlyEnergyAggregate.from_hourly_data(hourly_data, tou_config)

    def calculate_raw_net_import(
        self,
        import_kwh: Decimal,
        export_kwh: Decimal,
    ) -> Decimal:
        """
        Calculate raw net import (before applying credits).

        Positive = net import (deficit)
        Negative = net export (surplus, generates credits)
        """
        return import_kwh - export_kwh

    def apply_cycle_credits(
        self,
        raw_net_import: Decimal,
        credit_pool: CreditPool,
    ) -> Tuple[Decimal, CreditPool, Decimal, Decimal]:
        """
        Apply cycle credits to offset imports.

        Args:
            raw_net_import: Raw net import (positive) or export (negative)
            credit_pool: Current credit pool balance

        Returns:
            Tuple of (net_import_after_credits, new_credit_pool, credits_applied, credits_generated)
        """
        if raw_net_import > 0:
            # Net import - try to apply credits
            new_pool, net_import = credit_pool.apply_credits(raw_net_import)
            credits_applied = raw_net_import - net_import
            return net_import, new_pool, credits_applied, Decimal("0")
        else:
            # Net export - generate new credits
            credits_generated = -raw_net_import
            new_pool = credit_pool.add_credits(credits_generated)
            return Decimal("0"), new_pool, Decimal("0"), credits_generated

    def settle_cycle_credits(
        self,
        off_pool: CreditPool,
        peak_pool: CreditPool,
        prices: BillingPrices,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Settle remaining credits to cash at cycle end.

        Args:
            off_pool: Off-peak credit pool
            peak_pool: Peak credit pool
            prices: Settlement prices

        Returns:
            Tuple of (off_settlement_rs, peak_settlement_rs, total_settlement_rs)
        """
        off_settlement = off_pool.settle(prices.price_offpeak_settlement)
        peak_settlement = peak_pool.settle(prices.price_peak_settlement)
        total_settlement = off_settlement + peak_settlement

        return (
            off_settlement.quantize(Decimal("0.01"), ROUND_HALF_UP),
            peak_settlement.quantize(Decimal("0.01"), ROUND_HALF_UP),
            total_settlement.quantize(Decimal("0.01"), ROUND_HALF_UP),
        )

    def calculate_monthly_bill(
        self,
        aggregate: MonthlyEnergyAggregate,
        off_pool: CreditPool,
        peak_pool: CreditPool,
        prices: BillingPrices,
        opening_cash_balance: Decimal,
        is_cycle_end: bool = False,
    ) -> BillingCalculationResult:
        """
        Calculate a complete monthly bill.

        Args:
            aggregate: Monthly energy aggregate by TOU period
            off_pool: Current off-peak credit pool
            peak_pool: Current peak credit pool
            prices: Billing prices
            opening_cash_balance: Monetary credit balance from previous month
            is_cycle_end: Whether this is the final month of a 3-month cycle

        Returns:
            BillingCalculationResult with bill and updated pools
        """
        # Process off-peak
        raw_net_off = self.calculate_raw_net_import(
            aggregate.import_off_kwh,
            aggregate.export_off_kwh,
        )
        net_import_off, new_off_pool, credits_applied_off, credits_gen_off = \
            self.apply_cycle_credits(raw_net_off, off_pool)

        # Process peak
        raw_net_peak = self.calculate_raw_net_import(
            aggregate.import_peak_kwh,
            aggregate.export_peak_kwh,
        )
        net_import_peak, new_peak_pool, credits_applied_peak, credits_gen_peak = \
            self.apply_cycle_credits(raw_net_peak, peak_pool)

        # Calculate energy charges
        bill_off_energy = (net_import_off * prices.price_offpeak_import).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        bill_peak_energy = (net_import_peak * prices.price_peak_import).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        bill_fixed = prices.fixed_charge_per_billing_month

        # Cycle settlement (only at cycle end)
        cycle_settlement_off = Decimal("0")
        cycle_settlement_peak = Decimal("0")
        cycle_settlement_total = Decimal("0")

        if is_cycle_end:
            cycle_settlement_off, cycle_settlement_peak, cycle_settlement_total = \
                self.settle_cycle_credits(new_off_pool, new_peak_pool, prices)
            # Reset credit pools after settlement
            new_off_pool = CreditPool(credits_kwh=Decimal("0"))
            new_peak_pool = CreditPool(credits_kwh=Decimal("0"))

        # Calculate raw bill (settlement is a credit, so negative)
        bill_raw = (
            bill_off_energy +
            bill_peak_energy +
            bill_fixed -
            cycle_settlement_total
        )

        # Apply monetary carry-forward
        if bill_raw > 0 and opening_cash_balance < 0:
            # Use credit to offset positive bill
            bill_final = max(Decimal("0"), bill_raw + opening_cash_balance)
            closing_cash_balance = min(Decimal("0"), opening_cash_balance + bill_raw)
        elif bill_raw <= 0:
            # Negative bill adds to credit
            bill_final = Decimal("0")
            closing_cash_balance = opening_cash_balance + bill_raw
        else:
            # No credit to apply
            bill_final = bill_raw
            closing_cash_balance = Decimal("0")

        # Create billing month record
        billing_month = BillingMonth(
            site_id=None,  # Will be set by caller
            import_off_kwh=aggregate.import_off_kwh,
            export_off_kwh=aggregate.export_off_kwh,
            import_peak_kwh=aggregate.import_peak_kwh,
            export_peak_kwh=aggregate.export_peak_kwh,
            solar_generation_kwh=aggregate.total_solar_kwh,
            load_consumption_kwh=aggregate.total_load_kwh,
            net_import_off_kwh=net_import_off,
            net_import_peak_kwh=net_import_peak,
            credits_applied_off_kwh=credits_applied_off,
            credits_applied_peak_kwh=credits_applied_peak,
            credits_generated_off_kwh=credits_gen_off,
            credits_generated_peak_kwh=credits_gen_peak,
            bill_off_energy_rs=bill_off_energy,
            bill_peak_energy_rs=bill_peak_energy,
            bill_fixed_rs=bill_fixed,
            cycle_settlement_off_rs=-cycle_settlement_off if is_cycle_end else Decimal("0"),
            cycle_settlement_peak_rs=-cycle_settlement_peak if is_cycle_end else Decimal("0"),
            bill_raw_rs=bill_raw,
            opening_credit_balance_rs=opening_cash_balance,
            closing_credit_balance_rs=closing_cash_balance,
            bill_final_rs=bill_final,
            is_cycle_end_month=is_cycle_end,
        )

        return BillingCalculationResult(
            billing_month=billing_month,
            off_pool=new_off_pool,
            peak_pool=new_peak_pool,
            cash_balance=closing_cash_balance,
            is_cycle_end=is_cycle_end,
            cycle_settlement_total=cycle_settlement_total,
        )

    def calculate_running_bill(
        self,
        daily_aggregates: List[MonthlyEnergyAggregate],
        billing_config: BillingConfig,
        off_pool: CreditPool,
        peak_pool: CreditPool,
        opening_cash_balance: Decimal,
        target_date: date,
    ) -> RunningBillResult:
        """
        Calculate running bill to-date for the current billing month.

        Args:
            daily_aggregates: List of daily energy aggregates for month to-date
            billing_config: Site billing configuration
            off_pool: Current off-peak credit pool
            peak_pool: Current peak credit pool
            opening_cash_balance: Monetary credit balance at start of month
            target_date: Target date for the snapshot

        Returns:
            RunningBillResult with snapshot and pool balances
        """
        # Sum up daily aggregates
        cumulative = MonthlyEnergyAggregate()
        for daily in daily_aggregates:
            cumulative.import_off_kwh += daily.import_off_kwh
            cumulative.export_off_kwh += daily.export_off_kwh
            cumulative.import_peak_kwh += daily.import_peak_kwh
            cumulative.export_peak_kwh += daily.export_peak_kwh
            cumulative.total_solar_kwh += daily.total_solar_kwh
            cumulative.total_load_kwh += daily.total_load_kwh

        prices = billing_config.prices

        # Calculate to-date with credits
        raw_net_off = self.calculate_raw_net_import(
            cumulative.import_off_kwh,
            cumulative.export_off_kwh,
        )
        net_import_off, current_off_pool, _, _ = \
            self.apply_cycle_credits(raw_net_off, off_pool)

        raw_net_peak = self.calculate_raw_net_import(
            cumulative.import_peak_kwh,
            cumulative.export_peak_kwh,
        )
        net_import_peak, current_peak_pool, _, _ = \
            self.apply_cycle_credits(raw_net_peak, peak_pool)

        # Calculate energy charges to-date
        bill_off_energy = (net_import_off * prices.price_offpeak_import).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        bill_peak_energy = (net_import_peak * prices.price_peak_import).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )

        # Get billing month bounds
        month_start, month_end = billing_config.get_billing_month_bounds(target_date)
        total_days = (month_end - month_start).days + 1
        days_elapsed = (target_date - month_start).days + 1

        # Fixed charge proration
        if billing_config.fixed_proration_mode == FixedProrationMode.LINEAR_BY_DAY:
            fixed_prorated = (
                prices.fixed_charge_per_billing_month *
                Decimal(days_elapsed) / Decimal(total_days)
            ).quantize(Decimal("0.01"), ROUND_HALF_UP)
        else:
            fixed_prorated = prices.fixed_charge_per_billing_month

        # Expected cycle settlement (preview)
        expected_settlement = current_off_pool.settle(prices.price_offpeak_settlement) + \
                            current_peak_pool.settle(prices.price_peak_settlement)

        # Calculate raw bill to-date
        bill_raw_to_date = bill_off_energy + bill_peak_energy + fixed_prorated

        # Apply monetary carry-forward
        if bill_raw_to_date > 0 and opening_cash_balance < 0:
            bill_final_to_date = max(Decimal("0"), bill_raw_to_date + opening_cash_balance)
            credit_balance_to_date = min(Decimal("0"), opening_cash_balance + bill_raw_to_date)
        elif bill_raw_to_date <= 0:
            bill_final_to_date = Decimal("0")
            credit_balance_to_date = opening_cash_balance + bill_raw_to_date
        else:
            bill_final_to_date = bill_raw_to_date
            credit_balance_to_date = Decimal("0")

        # Determine surplus/deficit
        net_kwh = cumulative.export_off_kwh + cumulative.export_peak_kwh - \
                  cumulative.import_off_kwh - cumulative.import_peak_kwh

        if net_kwh > Decimal("5"):  # 5 kWh threshold for "neutral"
            surplus_deficit = SurplusDeficitFlag.SURPLUS
        elif net_kwh < Decimal("-5"):
            surplus_deficit = SurplusDeficitFlag.DEFICIT
        else:
            surplus_deficit = SurplusDeficitFlag.NEUTRAL

        # Create snapshot
        snapshot = DailyBillingSnapshot(
            site_id=None,  # Will be set by caller
            date=target_date,
            import_off_kwh=cumulative.import_off_kwh,
            export_off_kwh=cumulative.export_off_kwh,
            import_peak_kwh=cumulative.import_peak_kwh,
            export_peak_kwh=cumulative.export_peak_kwh,
            solar_generation_kwh=cumulative.total_solar_kwh,
            load_consumption_kwh=cumulative.total_load_kwh,
            net_import_off_kwh=net_import_off,
            net_import_peak_kwh=net_import_peak,
            credits_off_cycle_kwh_balance=current_off_pool.credits_kwh,
            credits_peak_cycle_kwh_balance=current_peak_pool.credits_kwh,
            bill_off_energy_rs=bill_off_energy,
            bill_peak_energy_rs=bill_peak_energy,
            fixed_prorated_rs=fixed_prorated,
            expected_cycle_credit_rs=expected_settlement,
            bill_raw_rs_to_date=bill_raw_to_date,
            bill_credit_balance_rs_to_date=credit_balance_to_date,
            bill_final_rs_to_date=bill_final_to_date,
            surplus_deficit_flag=surplus_deficit,
            net_kwh_position=net_kwh,
            days_elapsed=days_elapsed,
            total_days_in_month=total_days,
            generated_at=datetime.now(timezone.utc),
        )

        return RunningBillResult(
            snapshot=snapshot,
            off_pool_balance=current_off_pool.credits_kwh,
            peak_pool_balance=current_peak_pool.credits_kwh,
            expected_settlement=expected_settlement,
        )

    def simulate_annual_billing(
        self,
        monthly_aggregates: List[MonthlyEnergyAggregate],
        billing_config: BillingConfig,
        start_month: int = 1,
        year: int = 2026,
    ) -> AnnualSimulationResult:
        """
        Simulate a full year of billing.

        Args:
            monthly_aggregates: 12 months of energy aggregates
            billing_config: Site billing configuration
            start_month: Starting billing month number (1-12)
            year: Year for the simulation

        Returns:
            AnnualSimulationResult with all months and cycles
        """
        if len(monthly_aggregates) != 12:
            raise ValueError("Must provide exactly 12 months of data")

        prices = billing_config.prices
        billing_months: List[BillingMonth] = []
        billing_cycles: List[BillingCycle] = []

        # Initialize state
        off_pool = CreditPool(credits_kwh=Decimal("0"))
        peak_pool = CreditPool(credits_kwh=Decimal("0"))
        cash_balance = Decimal("0")

        total_bill = Decimal("0")
        total_import = Decimal("0")
        total_export = Decimal("0")
        months_with_positive_bill = 0

        current_cycle: Optional[BillingCycle] = None

        for i, aggregate in enumerate(monthly_aggregates):
            month_num = ((start_month - 1 + i) % 12) + 1
            is_cycle_end = billing_config.is_cycle_end_month(month_num)

            # Start new cycle if needed
            if month_num in (1, 4, 7, 10) or current_cycle is None:
                cycle_num = billing_config.get_cycle_number(month_num)
                current_cycle = BillingCycle(
                    site_id=billing_config.site_id,
                    cycle_number=cycle_num,
                    year=year,
                    cycle_start_date=date(year, month_num, billing_config.anchor_day),
                    cycle_end_date=date(year, month_num + 2, billing_config.anchor_day - 1) if month_num <= 10 else date(year + 1, 1, billing_config.anchor_day - 1),
                    opening_credit_off_kwh=off_pool.credits_kwh,
                    opening_credit_peak_kwh=peak_pool.credits_kwh,
                    opening_cash_credit_rs=cash_balance if cash_balance < 0 else Decimal("0"),
                )

            # Calculate monthly bill
            result = self.calculate_monthly_bill(
                aggregate=aggregate,
                off_pool=off_pool,
                peak_pool=peak_pool,
                prices=prices,
                opening_cash_balance=cash_balance,
                is_cycle_end=is_cycle_end,
            )

            # Update billing month with identifiers
            result.billing_month.site_id = billing_config.site_id
            result.billing_month.billing_month_number = month_num
            result.billing_month.year = year
            result.billing_month.billing_cycle_id = current_cycle.id

            billing_months.append(result.billing_month)

            # Update state
            off_pool = result.off_pool
            peak_pool = result.peak_pool
            cash_balance = result.cash_balance

            # Track totals
            total_bill += result.billing_month.bill_final_rs
            total_import += aggregate.import_off_kwh + aggregate.import_peak_kwh
            total_export += aggregate.export_off_kwh + aggregate.export_peak_kwh

            if result.billing_month.bill_final_rs > 0:
                months_with_positive_bill += 1

            # Update cycle stats
            current_cycle.total_import_off_kwh += aggregate.import_off_kwh
            current_cycle.total_export_off_kwh += aggregate.export_off_kwh
            current_cycle.total_import_peak_kwh += aggregate.import_peak_kwh
            current_cycle.total_export_peak_kwh += aggregate.export_peak_kwh

            # Finalize cycle at end
            if is_cycle_end:
                current_cycle.closing_credit_off_kwh = off_pool.credits_kwh
                current_cycle.closing_credit_peak_kwh = peak_pool.credits_kwh
                current_cycle.settlement_off_rs = result.billing_month.cycle_settlement_off_rs
                current_cycle.settlement_peak_rs = result.billing_month.cycle_settlement_peak_rs
                current_cycle.total_settlement_rs = result.cycle_settlement_total
                current_cycle.closing_cash_credit_rs = cash_balance if cash_balance < 0 else Decimal("0")
                current_cycle.status = BillingStatus.FINALIZED
                current_cycle.finalized_at = datetime.now(timezone.utc)
                billing_cycles.append(current_cycle)
                current_cycle = None

        # Determine capacity status
        if total_bill > Decimal("0"):
            capacity_status = "under-capacity"
        elif cash_balance < Decimal("-1000"):  # Significant credit buildup
            capacity_status = "over-capacity"
        else:
            capacity_status = "balanced"

        return AnnualSimulationResult(
            billing_months=billing_months,
            billing_cycles=billing_cycles,
            total_bill_rs=total_bill,
            total_import_kwh=total_import,
            total_export_kwh=total_export,
            final_cash_balance=cash_balance,
            months_with_positive_bill=months_with_positive_bill,
            capacity_status=capacity_status,
        )

    def compute_config_hash(self, billing_config: BillingConfig) -> str:
        """
        Compute a hash of billing configuration for audit trail.

        Used to detect if configuration changed between calculations.
        """
        config_dict = {
            "anchor_day": billing_config.anchor_day,
            "tou_config": billing_config.tou_config.to_dict(),
            "prices": {
                "price_offpeak_import": str(billing_config.prices.price_offpeak_import),
                "price_peak_import": str(billing_config.prices.price_peak_import),
                "price_offpeak_settlement": str(billing_config.prices.price_offpeak_settlement),
                "price_peak_settlement": str(billing_config.prices.price_peak_settlement),
                "fixed_charge_per_billing_month": str(billing_config.prices.fixed_charge_per_billing_month),
            },
            "fixed_proration_mode": billing_config.fixed_proration_mode.value,
        }

        json_str = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def calculate_per_kw_production(
        self,
        solar_generation_kwh: Decimal,
        installed_capacity_kw: Decimal,
    ) -> Decimal:
        """
        Calculate production per kW of installed capacity.

        Used for capacity analysis.

        Args:
            solar_generation_kwh: Solar generation in kWh
            installed_capacity_kw: Installed PV capacity in kW

        Returns:
            kWh per kW for the period
        """
        if installed_capacity_kw <= 0:
            return Decimal("0")
        return (solar_generation_kwh / installed_capacity_kw).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
