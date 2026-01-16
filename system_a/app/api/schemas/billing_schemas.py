"""
Pydantic schemas for billing endpoints.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# =========================================================================
# Tariff Schemas
# =========================================================================

class TariffSlabSchema(BaseModel):
    """Tariff slab definition."""
    min_units: int = Field(..., ge=0, description="Minimum units for this slab")
    max_units: Optional[int] = Field(None, ge=0, description="Maximum units (None for unlimited)")
    rate_per_kwh: str = Field(..., description="Rate per kWh in PKR")
    fixed_charges: str = Field(default="0", description="Fixed charges for this slab")


class TariffRatesSchema(BaseModel):
    """Complete tariff rates structure."""
    energy_charge_per_kwh: str = Field(..., description="Base energy charge per kWh")
    slabs: Optional[List[TariffSlabSchema]] = Field(default=None, description="Slab rates for progressive tariffs")
    peak_rate_per_kwh: Optional[str] = Field(None, description="Peak hour rate (TOU)")
    off_peak_rate_per_kwh: Optional[str] = Field(None, description="Off-peak rate (TOU)")
    fixed_charges_per_month: str = Field(default="0", description="Monthly fixed charges")
    meter_rent: str = Field(default="0", description="Monthly meter rent")
    fuel_price_adjustment: str = Field(default="0", description="FPA per kWh")
    quarterly_tariff_adjustment: str = Field(default="0", description="QTA per kWh")
    electricity_duty_percent: str = Field(default="1.5", description="ED percentage")
    gst_percent: str = Field(default="17", description="GST percentage")
    tv_fee: str = Field(default="35", description="TV license fee")
    export_rate_per_kwh: Optional[str] = Field(None, description="Net metering export rate")
    demand_charge_per_kw: Optional[str] = Field(None, description="Demand charge per kW")


class TariffPlanCreate(BaseModel):
    """Request to create a tariff plan."""
    disco_provider: str = Field(..., description="DISCO provider code")
    category: str = Field(..., description="Tariff category code")
    name: str = Field(..., min_length=1, max_length=255, description="Tariff plan name")
    description: Optional[str] = Field(None, description="Plan description")
    effective_from: Optional[date] = Field(None, description="Effective from date")
    effective_to: Optional[date] = Field(None, description="Effective to date")
    rates: TariffRatesSchema = Field(..., description="Rate structure")
    supports_net_metering: bool = Field(default=True, description="Supports net metering")
    supports_tou: bool = Field(default=False, description="Time-of-use tariff")
    source_url: Optional[str] = Field(None, description="URL to official tariff document")
    notes: Optional[str] = Field(None, description="Additional notes")


class TariffPlanResponse(BaseModel):
    """Tariff plan response."""
    id: UUID
    disco_provider: str
    category: str
    name: str
    description: Optional[str]
    effective_from: date
    effective_to: Optional[date]
    rates: Dict[str, Any]
    supports_net_metering: bool
    supports_tou: bool
    source_url: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TariffListResponse(BaseModel):
    """List of tariff plans."""
    tariffs: List[TariffPlanResponse]
    total: int


class DiscoWithCategoriesResponse(BaseModel):
    """DISCO with available categories."""
    disco_provider: str
    categories: List[str]


class DiscosListResponse(BaseModel):
    """List of DISCOs with categories."""
    discos: List[DiscoWithCategoriesResponse]


# =========================================================================
# Billing Simulation Schemas
# =========================================================================

class SlabBreakdownItem(BaseModel):
    """Breakdown of charges for a single slab."""
    slab: str
    units: Optional[int] = None
    rate: Optional[float] = None
    amount: float
    description: Optional[str] = None


class BillBreakdownSchema(BaseModel):
    """Detailed bill breakdown."""
    energy_charges: float
    slab_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    fixed_charges: float
    meter_rent: float
    fuel_price_adjustment: float
    quarterly_tariff_adjustment: float
    electricity_duty: float
    gst: float
    tv_fee: float
    export_credit: float
    demand_charges: float
    subtotal: float
    total_taxes: float
    total_bill: float


class SavingsBreakdownSchema(BaseModel):
    """Savings analysis breakdown."""
    bill_without_solar: float
    bill_with_solar: float
    total_savings: float
    savings_percent: float
    export_income: float
    co2_avoided_kg: float
    trees_equivalent: float


class SimulationRequest(BaseModel):
    """Request to create a billing simulation."""
    site_id: UUID = Field(..., description="Site ID")
    period_start: date = Field(..., description="Billing period start")
    period_end: date = Field(..., description="Billing period end")
    tariff_plan_id: Optional[UUID] = Field(None, description="Tariff plan ID (optional)")
    energy_consumed_kwh: float = Field(..., ge=0, description="Total energy consumed in kWh")
    energy_generated_kwh: float = Field(default=0, ge=0, description="Solar energy generated")
    energy_exported_kwh: float = Field(default=0, ge=0, description="Energy exported to grid")
    energy_imported_kwh: Optional[float] = Field(None, ge=0, description="Energy imported from grid")
    peak_demand_kw: Optional[float] = Field(None, ge=0, description="Peak demand in kW")
    peak_consumed_kwh: Optional[float] = Field(None, ge=0, description="Peak hours consumption")
    off_peak_consumed_kwh: Optional[float] = Field(None, ge=0, description="Off-peak consumption")
    notes: Optional[str] = Field(None, description="Additional notes")


class SimulationResponse(BaseModel):
    """Billing simulation response."""
    id: UUID
    site_id: UUID
    tariff_plan_id: Optional[UUID]
    period_start: date
    period_end: date
    energy_consumed_kwh: float
    energy_generated_kwh: float
    energy_exported_kwh: float
    energy_imported_kwh: float
    peak_demand_kw: Optional[float]
    bill_breakdown: BillBreakdownSchema
    savings_breakdown: SavingsBreakdownSchema
    estimated_bill_pkr: float
    estimated_savings_pkr: float
    is_actual: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class SimulationListResponse(BaseModel):
    """List of billing simulations."""
    simulations: List[SimulationResponse]
    total: int


class YearlySummaryResponse(BaseModel):
    """Yearly billing summary."""
    year: int
    total_simulations: int
    total_bills_pkr: float
    total_savings_pkr: float
    total_consumed_kwh: float
    total_generated_kwh: float
    total_exported_kwh: float


# =========================================================================
# Tariff Comparison Schemas
# =========================================================================

class TariffComparisonRequest(BaseModel):
    """Request to compare tariff plans."""
    tariff_ids: List[UUID] = Field(..., min_length=2, max_length=5, description="Tariff IDs to compare")
    energy_consumed_kwh: float = Field(..., ge=0, description="Energy consumed")
    energy_generated_kwh: float = Field(default=0, ge=0, description="Energy generated")
    energy_exported_kwh: float = Field(default=0, ge=0, description="Energy exported")


class TariffComparisonItem(BaseModel):
    """Single tariff comparison result."""
    tariff_id: str
    tariff_name: str
    disco_provider: str
    category: str
    total_bill: float
    energy_charges: float
    total_taxes: float
    export_credit: float
    total_savings: float
    savings_percent: float


class TariffComparisonResponse(BaseModel):
    """Tariff comparison results."""
    comparisons: List[TariffComparisonItem]
    best_tariff_id: str
    potential_savings: float = Field(description="Savings vs worst tariff")
