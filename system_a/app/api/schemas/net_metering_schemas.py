"""
Pydantic schemas for net metering billing endpoints.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# =========================================================================
# TOU Window Schemas
# =========================================================================

class TouWindowSchema(BaseModel):
    """Time-of-Use window definition."""
    start_hour: int = Field(..., ge=0, le=23, description="Start hour (0-23)")
    end_hour: int = Field(..., ge=0, le=23, description="End hour (0-23, exclusive)")


class TouConfigSchema(BaseModel):
    """TOU configuration."""
    peak_windows: List[TouWindowSchema] = Field(
        default=[TouWindowSchema(start_hour=17, end_hour=22)],
        description="Peak hour windows"
    )
    timezone: str = Field(default="Asia/Karachi", description="Timezone for TOU")


# =========================================================================
# Billing Config Schemas
# =========================================================================

class BillingPricesSchema(BaseModel):
    """Billing prices configuration."""
    price_offpeak_import: float = Field(..., ge=0, description="Off-peak import price per kWh")
    price_peak_import: float = Field(..., ge=0, description="Peak import price per kWh")
    price_offpeak_settlement: float = Field(..., ge=0, description="Off-peak credit settlement price")
    price_peak_settlement: float = Field(..., ge=0, description="Peak credit settlement price")
    fixed_charge_per_billing_month: float = Field(..., ge=0, description="Fixed monthly charge")


class BillingConfigCreate(BaseModel):
    """Request to create/update billing configuration."""
    site_id: UUID = Field(..., description="Site ID")
    anchor_day: int = Field(default=15, ge=1, le=28, description="Billing month anchor day")
    tou_config: TouConfigSchema = Field(default_factory=TouConfigSchema, description="TOU configuration")
    prices: BillingPricesSchema = Field(..., description="Pricing configuration")
    fixed_proration_mode: str = Field(default="none", description="Fixed charge proration: none or linear_by_day")
    net_metering_enabled: bool = Field(default=True, description="Enable net metering")


class BillingConfigResponse(BaseModel):
    """Billing configuration response."""
    id: UUID
    site_id: UUID
    anchor_day: int
    tou_config: TouConfigSchema
    prices: BillingPricesSchema
    fixed_proration_mode: str
    net_metering_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# =========================================================================
# Running Bill Schemas
# =========================================================================

class RunningBillResponse(BaseModel):
    """Running bill (to-date) response."""
    site_id: UUID
    date: date
    billing_month_id: Optional[UUID]

    # Period info
    billing_period_start: date
    billing_period_end: date
    days_elapsed: int
    total_days_in_month: int
    progress_percent: float

    # Energy aggregates (month to-date)
    import_off_kwh: float
    export_off_kwh: float
    import_peak_kwh: float
    export_peak_kwh: float
    solar_generation_kwh: float
    load_consumption_kwh: float

    # Net import after credits
    net_import_off_kwh: float
    net_import_peak_kwh: float

    # Credit pools
    credits_off_cycle_kwh_balance: float
    credits_peak_cycle_kwh_balance: float

    # Bill components (to-date)
    bill_off_energy_rs: float
    bill_peak_energy_rs: float
    fixed_prorated_rs: float

    # Expected settlement (preview)
    expected_cycle_credit_rs: float

    # Bill totals (to-date)
    bill_raw_rs_to_date: float
    bill_credit_balance_rs_to_date: float
    bill_final_rs_to_date: float

    # Position
    surplus_deficit_flag: str  # SURPLUS, DEFICIT, NEUTRAL
    net_kwh_position: float

    generated_at: datetime


class DailySnapshotResponse(BaseModel):
    """Daily billing snapshot response."""
    id: UUID
    site_id: UUID
    date: date
    billing_month_id: Optional[UUID]

    # Daily energy
    import_off_kwh: float
    export_off_kwh: float
    import_peak_kwh: float
    export_peak_kwh: float
    solar_generation_kwh: float
    load_consumption_kwh: float

    # Running totals
    bill_final_rs_to_date: float
    surplus_deficit_flag: str
    net_kwh_position: float

    generated_at: datetime


class DailySnapshotsListResponse(BaseModel):
    """List of daily snapshots."""
    snapshots: List[DailySnapshotResponse]
    total: int


# =========================================================================
# Billing Month Schemas
# =========================================================================

class BillingMonthResponse(BaseModel):
    """Finalized billing month response."""
    id: UUID
    site_id: UUID
    billing_cycle_id: Optional[UUID]
    billing_month_number: int
    year: int

    # Period
    period_start_date: date
    period_end_date: date

    # Energy aggregates
    import_off_kwh: float
    export_off_kwh: float
    import_peak_kwh: float
    export_peak_kwh: float
    solar_generation_kwh: float
    load_consumption_kwh: float

    # Net after credits
    net_import_off_kwh: float
    net_import_peak_kwh: float

    # Credits applied/generated
    credits_applied_off_kwh: float
    credits_applied_peak_kwh: float
    credits_generated_off_kwh: float
    credits_generated_peak_kwh: float

    # Bill components
    bill_off_energy_rs: float
    bill_peak_energy_rs: float
    bill_fixed_rs: float
    cycle_settlement_off_rs: float
    cycle_settlement_peak_rs: float

    # Totals
    bill_raw_rs: float
    opening_credit_balance_rs: float
    closing_credit_balance_rs: float
    bill_final_rs: float

    # Status
    status: str
    is_cycle_end_month: bool
    finalized_at: Optional[datetime]

    created_at: datetime
    updated_at: Optional[datetime]


class BillingMonthListResponse(BaseModel):
    """List of billing months."""
    months: List[BillingMonthResponse]
    total: int


# =========================================================================
# Billing Cycle Schemas
# =========================================================================

class BillingCycleResponse(BaseModel):
    """Billing cycle response."""
    id: UUID
    site_id: UUID
    cycle_number: int
    year: int

    # Period
    cycle_start_date: date
    cycle_end_date: date

    # Opening balances
    opening_credit_off_kwh: float
    opening_credit_peak_kwh: float
    opening_cash_credit_rs: float

    # Cumulative energy
    total_import_off_kwh: float
    total_export_off_kwh: float
    total_import_peak_kwh: float
    total_export_peak_kwh: float

    # Credits
    credits_generated_off_kwh: float
    credits_consumed_off_kwh: float
    credits_generated_peak_kwh: float
    credits_consumed_peak_kwh: float
    closing_credit_off_kwh: float
    closing_credit_peak_kwh: float

    # Settlement
    settlement_off_rs: float
    settlement_peak_rs: float
    total_settlement_rs: float
    closing_cash_credit_rs: float

    # Status
    status: str
    finalized_at: Optional[datetime]

    created_at: datetime
    updated_at: Optional[datetime]


class BillingCycleListResponse(BaseModel):
    """List of billing cycles."""
    cycles: List[BillingCycleResponse]
    total: int


# =========================================================================
# Billing Summary Schemas
# =========================================================================

class BillingSummaryResponse(BaseModel):
    """Current billing month summary."""
    billing_month: int
    year: int
    billing_period_start: date
    billing_period_end: date

    # Energy
    import_off_kwh: float
    import_peak_kwh: float
    export_off_kwh: float
    export_peak_kwh: float

    # Bill
    fixed_charge: float
    bill_amount: float
    credit_balance: float

    # Status
    days_elapsed: int
    days_remaining: int
    progress_percent: float

    # Savings
    estimated_savings_month: float = Field(default=0.0, description="Estimated monthly savings in PKR")
    total_savings_since_install: float = Field(default=0.0, description="Total lifetime savings in PKR")


class BillingTrendItem(BaseModel):
    """Single month in billing trend."""
    year: int
    month: int
    period_start: str
    period_end: str
    import_off_kwh: float
    import_peak_kwh: float
    export_off_kwh: float
    export_peak_kwh: float
    bill_final_rs: float
    status: str


class BillingTrendResponse(BaseModel):
    """Billing trend response."""
    trend: List[BillingTrendItem]
    months: int


class YearlyBillingSummaryResponse(BaseModel):
    """Yearly billing summary."""
    year: int
    total_months: int
    total_bill_rs: float
    total_import_kwh: float
    total_export_kwh: float
    total_solar_kwh: float
    total_load_kwh: float


# =========================================================================
# Capacity Analysis Schemas
# =========================================================================

class CapacityStatusResponse(BaseModel):
    """Capacity analysis response."""
    site_id: UUID
    installed_kw: float
    required_kw_for_zero_bill: float
    deficit_kw: float
    status: str  # under-capacity, over-capacity, balanced

    # Supporting data
    annual_bill_rs: float
    annual_import_kwh: float
    annual_export_kwh: float
    annual_solar_kwh: float
    months_with_positive_bill: int


# =========================================================================
# Admin Schemas
# =========================================================================

class ForceCycleCloseRequest(BaseModel):
    """Request to force-close a billing cycle."""
    cycle_id: UUID = Field(..., description="Cycle ID to close")


class ForceCycleCloseResponse(BaseModel):
    """Response after force-closing a cycle."""
    success: bool
    cycle_id: UUID
    settlement_total_rs: float
    message: str


class BackfillRequest(BaseModel):
    """Request to backfill billing data."""
    site_id: UUID = Field(..., description="Site to backfill")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")


class BackfillResponse(BaseModel):
    """Backfill operation response."""
    site_id: UUID
    start_date: date
    end_date: date
    days_processed: int
    days_successful: int
    days_failed: int
