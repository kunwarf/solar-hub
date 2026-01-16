"""
SQLAlchemy ORM models for billing and tariff management.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any
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
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base, BaseModel


class TariffPlanModel(Base, BaseModel):
    """
    Tariff plan for a DISCO and category.

    Stores tariff rates including slabs, TOU rates, and additional charges.
    """
    __tablename__ = "tariff_plans"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())

    # DISCO and category
    disco_provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Validity period
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Rates structure (JSON)
    # Structure: {
    #   "energy_charge_per_kwh": "25.00",
    #   "slabs": [
    #     {"min_units": 0, "max_units": 100, "rate_per_kwh": "7.74", "fixed_charges": "0"},
    #     {"min_units": 101, "max_units": 200, "rate_per_kwh": "10.06", "fixed_charges": "0"},
    #     ...
    #   ],
    #   "peak_rate_per_kwh": "30.00",
    #   "off_peak_rate_per_kwh": "18.00",
    #   "fixed_charges_per_month": "150.00",
    #   "meter_rent": "25.00",
    #   "fuel_price_adjustment": "3.50",
    #   "quarterly_tariff_adjustment": "1.20",
    #   "electricity_duty_percent": "1.5",
    #   "gst_percent": "17",
    #   "tv_fee": "35",
    #   "export_rate_per_kwh": "19.32",
    #   "demand_charge_per_kw": "400.00"
    # }
    rates: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Features
    supports_net_metering: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_tou: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    billing_simulations: Mapped[list["BillingSimulationModel"]] = relationship(
        "BillingSimulationModel",
        back_populates="tariff_plan",
        lazy="dynamic"
    )

    # Indexes
    __table_args__ = (
        Index("idx_tariff_disco_category", "disco_provider", "category"),
        Index("idx_tariff_active", "disco_provider", "category", "effective_from", "effective_to"),
    )


class BillingSimulationModel(Base, BaseModel):
    """
    Simulated electricity bill for a site.

    Calculates estimated bills based on energy consumption and tariff plans.
    """
    __tablename__ = "billing_simulations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())

    # Foreign keys
    site_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    tariff_plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tariff_plans.id", ondelete="SET NULL"), nullable=True, index=True)

    # Billing period
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Energy consumption data
    energy_consumed_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    energy_generated_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    energy_exported_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    energy_imported_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)

    # Peak demand (for industrial tariffs)
    peak_demand_kw: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Bill breakdown (JSON)
    # Structure: {
    #   "energy_charges": "5000.00",
    #   "slab_breakdown": [
    #     {"slab": "0-100", "units": 100, "rate": "7.74", "amount": "774.00"},
    #     ...
    #   ],
    #   "fixed_charges": "150.00",
    #   "meter_rent": "25.00",
    #   "fuel_price_adjustment": "350.00",
    #   "quarterly_tariff_adjustment": "120.00",
    #   "electricity_duty": "75.00",
    #   "gst": "850.00",
    #   "tv_fee": "35.00",
    #   "export_credit": "500.00",
    #   "demand_charges": "0.00",
    #   "subtotal": "5500.00",
    #   "total_taxes": "960.00",
    #   "total_bill": "6460.00"
    # }
    bill_breakdown: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Savings analysis (JSON)
    # Structure: {
    #   "bill_without_solar": "10000.00",
    #   "bill_with_solar": "6460.00",
    #   "total_savings": "3540.00",
    #   "savings_percent": "35.4",
    #   "export_income": "500.00",
    #   "co2_avoided_kg": "250.00",
    #   "trees_equivalent": "12.5"
    # }
    savings_breakdown: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Totals (convenience fields for querying)
    estimated_bill_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    estimated_savings_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    # Status
    is_actual: Mapped[bool] = mapped_column(Boolean, default=False)  # True if based on actual readings
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    site: Mapped["SiteModel"] = relationship("SiteModel", back_populates="billing_simulations")
    tariff_plan: Mapped[Optional["TariffPlanModel"]] = relationship("TariffPlanModel", back_populates="billing_simulations")

    # Indexes
    __table_args__ = (
        Index("idx_billing_site_period", "site_id", "period_start", "period_end"),
        Index("idx_billing_period", "period_start", "period_end"),
    )


# Import for type hints (avoid circular imports)
from .site_model import SiteModel
