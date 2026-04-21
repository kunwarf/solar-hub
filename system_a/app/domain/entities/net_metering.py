"""
Net Metering domain entities.

Handles 3-month netting cycles, TOU billing, and Pakistan net metering rules.
Battery is ignored - all logic is based on netting grid imports/exports only.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from .base import Entity, ValueObject


class SurplusDeficitFlag(str, Enum):
    """Net position indicator for billing period."""
    SURPLUS = "SURPLUS"    # Net export (credits generated)
    DEFICIT = "DEFICIT"    # Net import (billing charges)
    NEUTRAL = "NEUTRAL"    # Balanced


class BillingStatus(str, Enum):
    """Status of billing records."""
    ACTIVE = "active"          # In progress, can be modified
    FINALIZED = "finalized"    # Closed, immutable


class FixedProrationMode(str, Enum):
    """How to prorate fixed charges for partial months."""
    NONE = "none"              # Full fixed charge regardless of days
    LINEAR_BY_DAY = "linear_by_day"  # Prorate by elapsed days


@dataclass(frozen=True)
class TouWindow(ValueObject):
    """
    Time-of-Use window definition.

    Defines a peak hours window within a day.
    Hours are in 24-hour format (0-23).
    """
    start_hour: int  # 0-23
    end_hour: int    # 0-23 (exclusive)

    def __post_init__(self):
        if not 0 <= self.start_hour <= 23:
            raise ValueError(f"start_hour must be 0-23, got {self.start_hour}")
        if not 0 <= self.end_hour <= 23:
            raise ValueError(f"end_hour must be 0-23, got {self.end_hour}")

    def contains_hour(self, hour: int) -> bool:
        """Check if given hour falls within this TOU window."""
        if self.start_hour < self.end_hour:
            # Normal window (e.g., 17:00-22:00)
            return self.start_hour <= hour < self.end_hour
        else:
            # Window spans midnight (e.g., 22:00-06:00)
            return hour >= self.start_hour or hour < self.end_hour


@dataclass(frozen=True)
class TouConfig(ValueObject):
    """
    Complete TOU configuration for a site.

    Contains peak windows and timezone info.
    """
    peak_windows: List[TouWindow] = field(default_factory=list)
    timezone: str = "Asia/Karachi"

    def is_peak_hour(self, hour: int) -> bool:
        """Check if given hour is a peak hour."""
        return any(window.contains_hour(hour) for window in self.peak_windows)

    def is_off_peak_hour(self, hour: int) -> bool:
        """Check if given hour is an off-peak hour."""
        return not self.is_peak_hour(hour)

    @classmethod
    def default_pakistan(cls) -> "TouConfig":
        """Default TOU config for Pakistan (peak 17:00-22:00)."""
        return cls(
            peak_windows=[TouWindow(start_hour=17, end_hour=22)],
            timezone="Asia/Karachi"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "peak_windows": [
                {"start_hour": w.start_hour, "end_hour": w.end_hour}
                for w in self.peak_windows
            ],
            "timezone": self.timezone
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TouConfig":
        """Create from JSON dict."""
        windows = [
            TouWindow(start_hour=w["start_hour"], end_hour=w["end_hour"])
            for w in data.get("peak_windows", [])
        ]
        return cls(
            peak_windows=windows,
            timezone=data.get("timezone", "Asia/Karachi")
        )


@dataclass(frozen=True)
class BillingPrices(ValueObject):
    """
    All prices needed for billing calculations.

    Separates import prices from settlement prices.
    """
    # Import prices (buying from grid)
    price_offpeak_import: Decimal = Decimal("0")
    price_peak_import: Decimal = Decimal("0")

    # Settlement prices (selling expired credits at cycle end)
    price_offpeak_settlement: Decimal = Decimal("0")
    price_peak_settlement: Decimal = Decimal("0")

    # Fixed monthly charge
    fixed_charge_per_billing_month: Decimal = Decimal("0")

    # NEPRA surcharges (informational; already baked into import prices by resolver)
    fpa_per_kwh: Decimal = Decimal("0")
    qta_per_kwh: Decimal = Decimal("0")


@dataclass(frozen=True)
class CreditPool(ValueObject):
    """
    kWh credit pool for a TOU period within a cycle.

    Tracks credits generated, consumed, and remaining balance.
    """
    credits_kwh: Decimal = Decimal("0")  # Current balance

    def apply_credits(self, import_kwh: Decimal) -> tuple["CreditPool", Decimal]:
        """
        Apply credits to offset imports.

        Returns:
            Tuple of (new credit pool, net import after credits)
        """
        if import_kwh <= 0:
            # No import to offset
            return self, Decimal("0")

        if self.credits_kwh >= import_kwh:
            # Enough credits to cover all imports
            new_credits = self.credits_kwh - import_kwh
            return CreditPool(credits_kwh=new_credits), Decimal("0")
        else:
            # Partial coverage
            net_import = import_kwh - self.credits_kwh
            return CreditPool(credits_kwh=Decimal("0")), net_import

    def add_credits(self, export_kwh: Decimal) -> "CreditPool":
        """Add new export credits to the pool."""
        if export_kwh <= 0:
            return self
        return CreditPool(credits_kwh=self.credits_kwh + export_kwh)

    def settle(self, settlement_price: Decimal) -> Decimal:
        """Settle remaining credits to cash at cycle end."""
        return self.credits_kwh * settlement_price


@dataclass(kw_only=True)
class BillingConfig(Entity):
    """
    Per-site billing configuration.

    Stores anchor day, TOU windows, and pricing.
    """
    site_id: UUID

    # Billing month anchor (day of month, default 15)
    anchor_day: int = 15

    # TOU configuration
    tou_config: TouConfig = field(default_factory=TouConfig.default_pakistan)

    # Pricing
    prices: BillingPrices = field(default_factory=BillingPrices)

    # Fixed charge proration
    fixed_proration_mode: FixedProrationMode = FixedProrationMode.NONE

    # Net metering enabled
    net_metering_enabled: bool = True

    def get_billing_month_bounds(self, target_date: date) -> tuple[date, date]:
        """
        Get billing month start and end dates for a given date.

        Billing months run from anchor_day to anchor_day-1 of next month.
        Example (anchor=15): Jan 15 - Feb 14
        """
        year = target_date.year
        month = target_date.month
        day = target_date.day

        if day >= self.anchor_day:
            # We're in the period that starts this month
            start = date(year, month, self.anchor_day)
            # End is anchor_day - 1 of next month
            if month == 12:
                end = date(year + 1, 1, self.anchor_day - 1)
            else:
                end = date(year, month + 1, self.anchor_day - 1)
        else:
            # We're in the period that started last month
            if month == 1:
                start = date(year - 1, 12, self.anchor_day)
            else:
                start = date(year, month - 1, self.anchor_day)
            end = date(year, month, self.anchor_day - 1)

        return start, end

    def get_billing_month_number(self, target_date: date) -> int:
        """
        Get billing month number (1-12) for a given date.

        Month 1 starts from anchor_day of January.
        """
        start, _ = self.get_billing_month_bounds(target_date)
        return start.month

    def is_cycle_end_month(self, billing_month_number: int) -> bool:
        """Check if billing month is a cycle-end month (3, 6, 9, 12)."""
        return billing_month_number in (3, 6, 9, 12)

    def get_cycle_number(self, billing_month_number: int) -> int:
        """Get cycle number (1-4) for a billing month."""
        return ((billing_month_number - 1) // 3) + 1


@dataclass(kw_only=True)
class BillingCycle(Entity):
    """
    3-month netting cycle record.

    Tracks credit pools and settlement for a 3-month period.
    """
    site_id: UUID

    # Cycle identification
    cycle_number: int  # 1-4 within year
    year: int

    # Cycle period
    cycle_start_date: date
    cycle_end_date: date

    # Opening balances (from previous cycle settlement or zero)
    opening_credit_off_kwh: Decimal = Decimal("0")
    opening_credit_peak_kwh: Decimal = Decimal("0")
    opening_cash_credit_rs: Decimal = Decimal("0")

    # Cumulative energy during cycle
    total_import_off_kwh: Decimal = Decimal("0")
    total_export_off_kwh: Decimal = Decimal("0")
    total_import_peak_kwh: Decimal = Decimal("0")
    total_export_peak_kwh: Decimal = Decimal("0")

    # Credits generated/consumed during cycle
    credits_generated_off_kwh: Decimal = Decimal("0")
    credits_consumed_off_kwh: Decimal = Decimal("0")
    credits_generated_peak_kwh: Decimal = Decimal("0")
    credits_consumed_peak_kwh: Decimal = Decimal("0")

    # Closing credit balances (before settlement)
    closing_credit_off_kwh: Decimal = Decimal("0")
    closing_credit_peak_kwh: Decimal = Decimal("0")

    # Settlement amounts
    settlement_off_rs: Decimal = Decimal("0")
    settlement_peak_rs: Decimal = Decimal("0")
    total_settlement_rs: Decimal = Decimal("0")

    # Closing cash credit
    closing_cash_credit_rs: Decimal = Decimal("0")

    # Status
    status: BillingStatus = BillingStatus.ACTIVE

    # Audit
    config_hash: Optional[str] = None
    finalized_at: Optional[datetime] = None

    @property
    def is_finalized(self) -> bool:
        return self.status == BillingStatus.FINALIZED

    def finalize(
        self,
        prices: BillingPrices,
        off_credit_balance: Decimal,
        peak_credit_balance: Decimal,
    ) -> None:
        """
        Finalize the cycle by settling remaining credits.

        Converts remaining kWh credits to cash credits.
        """
        if self.is_finalized:
            raise ValueError("Cycle is already finalized")

        self.closing_credit_off_kwh = off_credit_balance
        self.closing_credit_peak_kwh = peak_credit_balance

        # Settle credits to cash
        self.settlement_off_rs = off_credit_balance * prices.price_offpeak_settlement
        self.settlement_peak_rs = peak_credit_balance * prices.price_peak_settlement
        self.total_settlement_rs = self.settlement_off_rs + self.settlement_peak_rs

        # Update closing cash credit
        self.closing_cash_credit_rs = self.opening_cash_credit_rs + self.total_settlement_rs

        self.status = BillingStatus.FINALIZED
        self.finalized_at = datetime.now(timezone.utc)
        self.mark_updated()


@dataclass(kw_only=True)
class BillingMonth(Entity):
    """
    Finalized monthly billing record.

    Contains all energy aggregates, credits applied, and final bill.
    """
    site_id: UUID

    # Cycle reference
    billing_cycle_id: Optional[UUID] = None

    # Month identification
    billing_month_number: int  # 1-12
    year: int

    # Billing period (anchor to anchor)
    period_start_date: date
    period_end_date: date

    # Raw energy aggregates
    import_off_kwh: Decimal = Decimal("0")
    export_off_kwh: Decimal = Decimal("0")
    import_peak_kwh: Decimal = Decimal("0")
    export_peak_kwh: Decimal = Decimal("0")

    # Informational totals
    solar_generation_kwh: Decimal = Decimal("0")
    load_consumption_kwh: Decimal = Decimal("0")

    # Net import after applying cycle credits
    net_import_off_kwh: Decimal = Decimal("0")
    net_import_peak_kwh: Decimal = Decimal("0")

    # Credits applied this month
    credits_applied_off_kwh: Decimal = Decimal("0")
    credits_applied_peak_kwh: Decimal = Decimal("0")

    # Credits generated this month
    credits_generated_off_kwh: Decimal = Decimal("0")
    credits_generated_peak_kwh: Decimal = Decimal("0")

    # Bill components
    bill_off_energy_rs: Decimal = Decimal("0")
    bill_peak_energy_rs: Decimal = Decimal("0")
    bill_fixed_rs: Decimal = Decimal("0")

    # Cycle settlement (only in cycle-end month)
    cycle_settlement_off_rs: Decimal = Decimal("0")
    cycle_settlement_peak_rs: Decimal = Decimal("0")

    # Bill totals
    bill_raw_rs: Decimal = Decimal("0")

    # Monetary carry-forward
    opening_credit_balance_rs: Decimal = Decimal("0")
    closing_credit_balance_rs: Decimal = Decimal("0")

    # Final payable amount
    bill_final_rs: Decimal = Decimal("0")

    # Status
    status: BillingStatus = BillingStatus.ACTIVE
    is_cycle_end_month: bool = False

    # Audit
    config_hash: Optional[str] = None
    finalized_at: Optional[datetime] = None

    @property
    def is_finalized(self) -> bool:
        return self.status == BillingStatus.FINALIZED

    @property
    def total_import_kwh(self) -> Decimal:
        return self.import_off_kwh + self.import_peak_kwh

    @property
    def total_export_kwh(self) -> Decimal:
        return self.export_off_kwh + self.export_peak_kwh

    @property
    def net_kwh(self) -> Decimal:
        """Net position: positive = surplus (export), negative = deficit (import)."""
        return self.total_export_kwh - self.total_import_kwh

    def calculate_bill(
        self,
        prices: BillingPrices,
        off_pool: CreditPool,
        peak_pool: CreditPool,
        opening_cash_balance: Decimal,
        include_cycle_settlement: bool = False,
        settlement_off_rs: Decimal = Decimal("0"),
        settlement_peak_rs: Decimal = Decimal("0"),
    ) -> tuple[CreditPool, CreditPool, Decimal]:
        """
        Calculate bill applying credit pools and monetary carry-forward.

        Returns:
            Tuple of (new off pool, new peak pool, closing cash balance)
        """
        # Calculate raw net for off-peak
        raw_net_off = self.import_off_kwh - self.export_off_kwh

        if raw_net_off > 0:
            # Net import - apply credits
            new_off_pool, self.net_import_off_kwh = off_pool.apply_credits(raw_net_off)
            self.credits_applied_off_kwh = raw_net_off - self.net_import_off_kwh
        else:
            # Net export - generate credits
            self.net_import_off_kwh = Decimal("0")
            new_off_pool = off_pool.add_credits(-raw_net_off)
            self.credits_generated_off_kwh = -raw_net_off

        # Calculate raw net for peak
        raw_net_peak = self.import_peak_kwh - self.export_peak_kwh

        if raw_net_peak > 0:
            # Net import - apply credits
            new_peak_pool, self.net_import_peak_kwh = peak_pool.apply_credits(raw_net_peak)
            self.credits_applied_peak_kwh = raw_net_peak - self.net_import_peak_kwh
        else:
            # Net export - generate credits
            self.net_import_peak_kwh = Decimal("0")
            new_peak_pool = peak_pool.add_credits(-raw_net_peak)
            self.credits_generated_peak_kwh = -raw_net_peak

        # Calculate energy charges
        self.bill_off_energy_rs = self.net_import_off_kwh * prices.price_offpeak_import
        self.bill_peak_energy_rs = self.net_import_peak_kwh * prices.price_peak_import
        self.bill_fixed_rs = prices.fixed_charge_per_billing_month

        # Include cycle settlement if this is cycle-end month
        if include_cycle_settlement:
            self.cycle_settlement_off_rs = -settlement_off_rs  # Negative = credit
            self.cycle_settlement_peak_rs = -settlement_peak_rs
            self.is_cycle_end_month = True

        # Calculate raw bill
        self.bill_raw_rs = (
            self.bill_off_energy_rs +
            self.bill_peak_energy_rs +
            self.bill_fixed_rs +
            self.cycle_settlement_off_rs +
            self.cycle_settlement_peak_rs
        )

        # Apply monetary carry-forward
        self.opening_credit_balance_rs = opening_cash_balance

        if self.bill_raw_rs > 0 and opening_cash_balance < 0:
            # Use credit to offset positive bill
            self.bill_final_rs = max(Decimal("0"), self.bill_raw_rs + opening_cash_balance)
            self.closing_credit_balance_rs = min(Decimal("0"), opening_cash_balance + self.bill_raw_rs)
        elif self.bill_raw_rs <= 0:
            # Negative bill adds to credit
            self.bill_final_rs = Decimal("0")
            self.closing_credit_balance_rs = opening_cash_balance + self.bill_raw_rs
        else:
            # No credit to apply
            self.bill_final_rs = self.bill_raw_rs
            self.closing_credit_balance_rs = Decimal("0")

        return new_off_pool, new_peak_pool, self.closing_credit_balance_rs

    def finalize(self) -> None:
        """Finalize the monthly record."""
        if self.is_finalized:
            raise ValueError("Month is already finalized")

        self.status = BillingStatus.FINALIZED
        self.finalized_at = datetime.now(timezone.utc)
        self.mark_updated()


@dataclass(kw_only=True)
class DailyBillingSnapshot(Entity):
    """
    Daily billing snapshot for running bill view.

    Shows to-date progress within the current billing month.
    """
    site_id: UUID
    date: date

    # Billing month reference
    billing_month_id: Optional[UUID] = None

    # Daily energy aggregates
    import_off_kwh: Decimal = Decimal("0")
    export_off_kwh: Decimal = Decimal("0")
    import_peak_kwh: Decimal = Decimal("0")
    export_peak_kwh: Decimal = Decimal("0")

    # Daily totals
    solar_generation_kwh: Decimal = Decimal("0")
    load_consumption_kwh: Decimal = Decimal("0")

    # Net import (running calculation)
    net_import_off_kwh: Decimal = Decimal("0")
    net_import_peak_kwh: Decimal = Decimal("0")

    # Credit pool balances (running state)
    credits_off_cycle_kwh_balance: Decimal = Decimal("0")
    credits_peak_cycle_kwh_balance: Decimal = Decimal("0")

    # Running bill components (to-date)
    bill_off_energy_rs: Decimal = Decimal("0")
    bill_peak_energy_rs: Decimal = Decimal("0")
    fixed_prorated_rs: Decimal = Decimal("0")

    # Expected cycle credit (preview)
    expected_cycle_credit_rs: Decimal = Decimal("0")

    # Running bill totals
    bill_raw_rs_to_date: Decimal = Decimal("0")
    bill_credit_balance_rs_to_date: Decimal = Decimal("0")
    bill_final_rs_to_date: Decimal = Decimal("0")

    # Position flags
    surplus_deficit_flag: SurplusDeficitFlag = SurplusDeficitFlag.NEUTRAL
    net_kwh_position: Decimal = Decimal("0")  # export - import for month to-date

    # Progress
    days_elapsed: int = 0
    total_days_in_month: int = 30

    # Timestamp
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def progress_percent(self) -> float:
        """Percentage of billing month elapsed."""
        if self.total_days_in_month <= 0:
            return 0.0
        return (self.days_elapsed / self.total_days_in_month) * 100

    @property
    def days_remaining(self) -> int:
        """Days remaining in billing month."""
        return max(0, self.total_days_in_month - self.days_elapsed)


@dataclass
class HourlyEnergyData:
    """
    Hourly energy data for billing aggregation.

    This is a simple data transfer object, not a persisted entity.
    """
    timestamp: datetime
    hour: int  # 0-23

    # Energy values
    load_kwh: Decimal = Decimal("0")
    solar_kwh: Decimal = Decimal("0")
    grid_import_kwh: Decimal = Decimal("0")
    grid_export_kwh: Decimal = Decimal("0")

    # TOU period (set during processing)
    is_peak: bool = False

    def set_tou_period(self, tou_config: TouConfig) -> None:
        """Determine and set the TOU period based on config."""
        self.is_peak = tou_config.is_peak_hour(self.hour)


@dataclass
class MonthlyEnergyAggregate:
    """
    Aggregated monthly energy data by TOU period.

    Result of aggregating hourly data for a billing month.
    """
    # Off-peak aggregates
    import_off_kwh: Decimal = Decimal("0")
    export_off_kwh: Decimal = Decimal("0")

    # Peak aggregates
    import_peak_kwh: Decimal = Decimal("0")
    export_peak_kwh: Decimal = Decimal("0")

    # Totals (informational)
    total_solar_kwh: Decimal = Decimal("0")
    total_load_kwh: Decimal = Decimal("0")

    @classmethod
    def from_hourly_data(
        cls,
        hourly_data: List[HourlyEnergyData],
        tou_config: TouConfig,
    ) -> "MonthlyEnergyAggregate":
        """
        Aggregate hourly data into monthly TOU buckets.
        """
        result = cls()

        for hour_data in hourly_data:
            hour_data.set_tou_period(tou_config)

            if hour_data.is_peak:
                result.import_peak_kwh += hour_data.grid_import_kwh
                result.export_peak_kwh += hour_data.grid_export_kwh
            else:
                result.import_off_kwh += hour_data.grid_import_kwh
                result.export_off_kwh += hour_data.grid_export_kwh

            result.total_solar_kwh += hour_data.solar_kwh
            result.total_load_kwh += hour_data.load_kwh

        return result
