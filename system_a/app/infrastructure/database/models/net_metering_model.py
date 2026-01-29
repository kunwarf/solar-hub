"""
SQLAlchemy ORM models for net metering billing.

Tables:
- billing_config: Per-site billing configuration
- billing_cycles: 3-month netting cycle records
- billing_months: Finalized monthly billing records
- billing_daily: Daily billing snapshots
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import BaseModel, Base, TimestampMixin, UUIDMixin


class BillingConfigModel(BaseModel):
    """
    Per-site billing configuration.

    Stores anchor day, TOU windows, and pricing.
    """
    __tablename__ = "billing_config"

    # Site reference (unique - one config per site)
    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Billing month anchor (day of month, default 15)
    anchor_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")

    # TOU windows configuration
    # Structure: {
    #   "peak_windows": [{"start_hour": 17, "end_hour": 22}],
    #   "timezone": "Asia/Karachi"
    # }
    tou_windows: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default='{"peak_windows": [{"start_hour": 17, "end_hour": 22}], "timezone": "Asia/Karachi"}',
    )

    # Fixed charges
    fixed_charge_per_billing_month: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )

    # Import prices (buying from grid)
    price_offpeak_import: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default="0"
    )
    price_peak_import: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default="0"
    )

    # Settlement prices (selling expired credits at cycle end)
    price_offpeak_settlement: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default="0"
    )
    price_peak_settlement: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default="0"
    )

    # Fixed charge proration mode: 'none' or 'linear_by_day'
    fixed_proration_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="none"
    )

    # Net metering enabled
    net_metering_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Relationships
    site: Mapped["SiteModel"] = relationship("SiteModel", back_populates="billing_config")

    __table_args__ = (
        Index("idx_billing_config_site", "site_id"),
    )


class BillingCycleModel(BaseModel):
    """
    3-month netting cycle record.

    Tracks credit pools and settlement for a 3-month period.
    """
    __tablename__ = "billing_cycles"

    # Site reference
    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Cycle identification
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-4 within year
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Cycle period
    cycle_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    cycle_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Opening balances
    opening_credit_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    opening_credit_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    opening_cash_credit_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Cumulative energy during cycle
    total_import_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    total_export_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    total_import_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    total_export_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Credits generated/consumed during cycle
    credits_generated_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    credits_consumed_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    credits_generated_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    credits_consumed_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Closing credit balances (before settlement)
    closing_credit_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    closing_credit_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Settlement amounts
    settlement_off_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    settlement_peak_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    total_settlement_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Closing cash credit
    closing_cash_credit_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )

    # Audit hash
    config_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Finalization timestamp
    finalized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    site: Mapped["SiteModel"] = relationship("SiteModel", back_populates="billing_cycles")
    billing_months: Mapped[List["BillingMonthModel"]] = relationship(
        "BillingMonthModel",
        back_populates="billing_cycle",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("idx_billing_cycles_site_year", "site_id", "year", "cycle_number"),
        Index("idx_billing_cycles_period", "site_id", "cycle_start_date", "cycle_end_date"),
    )


class BillingMonthModel(BaseModel):
    """
    Finalized monthly billing record.

    Contains all energy aggregates, credits applied, and final bill.
    """
    __tablename__ = "billing_months"

    # Site reference
    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Cycle reference
    billing_cycle_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing_cycles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Month identification
    billing_month_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Billing period
    period_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Raw energy aggregates
    import_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    export_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    import_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    export_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Informational totals
    solar_generation_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    load_consumption_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Net import after credits
    net_import_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    net_import_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Credits applied/generated
    credits_applied_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    credits_applied_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    credits_generated_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    credits_generated_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Bill components
    bill_off_energy_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    bill_peak_energy_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    bill_fixed_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Cycle settlement (cycle-end month only)
    cycle_settlement_off_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    cycle_settlement_peak_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Bill totals
    bill_raw_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Monetary carry-forward
    opening_credit_balance_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    closing_credit_balance_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Final payable amount
    bill_final_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    is_cycle_end_month: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Audit hash
    config_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Finalization timestamp
    finalized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    site: Mapped["SiteModel"] = relationship("SiteModel", back_populates="billing_months")
    billing_cycle: Mapped[Optional["BillingCycleModel"]] = relationship(
        "BillingCycleModel", back_populates="billing_months"
    )
    daily_snapshots: Mapped[List["BillingDailyModel"]] = relationship(
        "BillingDailyModel",
        back_populates="billing_month",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("idx_billing_months_site_period", "site_id", "period_start_date", "period_end_date"),
        Index("idx_billing_months_site_year", "site_id", "year", "billing_month_number"),
    )


class BillingDailyModel(Base, UUIDMixin, TimestampMixin):
    """
    Daily billing snapshot.

    Shows to-date progress within the current billing month.
    """
    __tablename__ = "billing_daily"

    # Site reference
    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Date
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Billing month reference
    billing_month_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing_months.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Daily energy aggregates
    import_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    export_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    import_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    export_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Solar and load totals
    solar_generation_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    load_consumption_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Net import (running calculation)
    net_import_off_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    net_import_peak_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Credit pool balances (running state)
    credits_off_cycle_kwh_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    credits_peak_cycle_kwh_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Running bill components (to-date)
    bill_off_energy_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    bill_peak_energy_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    fixed_prorated_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Expected cycle credit (preview)
    expected_cycle_credit_rs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Running bill totals (to-date)
    bill_raw_rs_to_date: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    bill_credit_balance_rs_to_date: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    bill_final_rs_to_date: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Surplus/deficit flag
    surplus_deficit_flag: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="NEUTRAL"
    )

    # Net kWh position
    net_kwh_position: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )

    # Days progress
    days_elapsed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_days_in_month: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")

    # Generation timestamp
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    site: Mapped["SiteModel"] = relationship("SiteModel", back_populates="billing_daily")
    billing_month: Mapped[Optional["BillingMonthModel"]] = relationship(
        "BillingMonthModel", back_populates="daily_snapshots"
    )

    __table_args__ = (
        Index("idx_billing_daily_site_date", "site_id", "date"),
        Index("idx_billing_daily_date", "date"),
        Index("idx_billing_daily_month", "billing_month_id"),
    )


# Import for type hints (avoid circular imports)
from .site_model import SiteModel
