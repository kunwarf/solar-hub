"""
Billing domain entities.

Handles tariff plans and billing simulations for Pakistan DISCOs.
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID

from .base import Entity


class DiscoProvider(str, Enum):
    """Pakistan electricity distribution companies (DISCOs)."""
    LESCO = "lesco"      # Lahore Electric Supply Company
    FESCO = "fesco"      # Faisalabad Electric Supply Company
    IESCO = "iesco"      # Islamabad Electric Supply Company
    GEPCO = "gepco"      # Gujranwala Electric Power Company
    MEPCO = "mepco"      # Multan Electric Power Company
    PESCO = "pesco"      # Peshawar Electric Supply Company
    HESCO = "hesco"      # Hyderabad Electric Supply Company
    SEPCO = "sepco"      # Sukkur Electric Power Company
    QESCO = "qesco"      # Quetta Electric Supply Company
    TESCO = "tesco"      # Tribal Areas Electricity Supply Company
    KELECTRIC = "kelectric"  # K-Electric (Karachi)


class TariffCategory(str, Enum):
    """Tariff categories for different consumer types."""
    # Residential
    RESIDENTIAL_PROTECTED = "residential_protected"  # Protected consumers
    RESIDENTIAL_UNPROTECTED = "residential_unprotected"

    # Commercial
    COMMERCIAL_A1 = "commercial_a1"  # Small commercial
    COMMERCIAL_A2 = "commercial_a2"  # Medium commercial
    COMMERCIAL_A3 = "commercial_a3"  # Large commercial

    # Industrial
    INDUSTRIAL_B1 = "industrial_b1"  # Small industrial
    INDUSTRIAL_B2 = "industrial_b2"  # Medium industrial
    INDUSTRIAL_B3 = "industrial_b3"  # Large industrial
    INDUSTRIAL_B4 = "industrial_b4"  # Peak/off-peak industrial

    # Agricultural
    AGRICULTURAL_TUBE_WELL = "agricultural_tube_well"
    AGRICULTURAL_SCARP = "agricultural_scarp"

    # Bulk
    BULK_SUPPLY = "bulk_supply"

    # Time of Use
    TOU_INDUSTRIAL = "tou_industrial"
    TOU_COMMERCIAL = "tou_commercial"


class TimeOfUse(str, Enum):
    """Time of use periods for TOU tariffs."""
    PEAK = "peak"          # Peak hours (usually 6-10 PM)
    OFF_PEAK = "off_peak"  # Off-peak hours
    NORMAL = "normal"      # Normal/flat rate


@dataclass
class TariffSlab:
    """
    Energy consumption slab with associated rate.

    Used for slab-based billing (common in residential tariffs).
    """
    min_units: int  # Minimum kWh for this slab
    max_units: Optional[int]  # Maximum kWh (None = unlimited)
    rate_per_kwh: Decimal  # PKR per kWh
    fixed_charges: Decimal = Decimal("0")  # Fixed monthly charges for this slab

    def applies_to(self, units: int) -> bool:
        """Check if this slab applies to given consumption."""
        if self.max_units is None:
            return units >= self.min_units
        return self.min_units <= units <= self.max_units

    def calculate_cost(self, units_in_slab: int) -> Decimal:
        """Calculate cost for units in this slab."""
        return Decimal(str(units_in_slab)) * self.rate_per_kwh


@dataclass
class TariffRates:
    """
    Complete tariff rate structure.

    Supports slab-based, flat, and time-of-use tariffs.
    """
    # Base rates
    energy_charge_per_kwh: Decimal  # Base energy charge (PKR/kWh)

    # Slabs (for residential/commercial)
    slabs: List[TariffSlab] = field(default_factory=list)

    # Time of Use rates (for TOU tariffs)
    peak_rate_per_kwh: Optional[Decimal] = None
    off_peak_rate_per_kwh: Optional[Decimal] = None

    # Fixed charges
    fixed_charges_per_month: Decimal = Decimal("0")
    meter_rent: Decimal = Decimal("0")

    # Additional charges
    fuel_price_adjustment: Decimal = Decimal("0")  # FPA per kWh
    quarterly_tariff_adjustment: Decimal = Decimal("0")  # QTA per kWh
    electricity_duty_percent: Decimal = Decimal("1.5")  # ED %
    gst_percent: Decimal = Decimal("17")  # GST %
    tv_fee: Decimal = Decimal("35")  # PTV fee

    # Net metering
    export_rate_per_kwh: Optional[Decimal] = None  # Rate for exported energy

    # Demand charges (for industrial)
    demand_charge_per_kw: Optional[Decimal] = None  # PKR per kW of demand

    def is_slab_based(self) -> bool:
        """Check if tariff uses slab-based pricing."""
        return len(self.slabs) > 0

    def is_tou_based(self) -> bool:
        """Check if tariff uses time-of-use pricing."""
        return self.peak_rate_per_kwh is not None


@dataclass(kw_only=True)
class TariffPlan(Entity):
    """
    Tariff plan for a DISCO and category.

    Stores the complete tariff structure including rates, slabs, and additional charges.
    """
    disco_provider: DiscoProvider
    category: TariffCategory
    name: str
    description: Optional[str] = None

    # Validity period
    effective_from: date = field(default_factory=date.today)
    effective_to: Optional[date] = None  # None = currently active

    # Rates structure (stored as JSON in DB)
    rates: TariffRates = field(default_factory=lambda: TariffRates(energy_charge_per_kwh=Decimal("0")))

    # Features
    supports_net_metering: bool = True
    supports_tou: bool = False

    # Metadata
    source_url: Optional[str] = None  # URL to official tariff document
    notes: Optional[str] = None

    def is_active(self, check_date: Optional[date] = None) -> bool:
        """Check if tariff is active on given date."""
        check_date = check_date or date.today()
        if check_date < self.effective_from:
            return False
        if self.effective_to and check_date > self.effective_to:
            return False
        return True


@dataclass
class EnergyConsumption:
    """Energy consumption data for billing calculation."""
    total_consumed_kwh: Decimal
    total_generated_kwh: Decimal = Decimal("0")
    total_exported_kwh: Decimal = Decimal("0")
    total_imported_kwh: Decimal = Decimal("0")

    # Time of Use breakdown (optional)
    peak_consumed_kwh: Optional[Decimal] = None
    off_peak_consumed_kwh: Optional[Decimal] = None

    # Demand (for industrial)
    peak_demand_kw: Optional[Decimal] = None

    @property
    def net_consumed_kwh(self) -> Decimal:
        """Net consumption after accounting for export."""
        return self.total_imported_kwh - self.total_exported_kwh


@dataclass
class BillBreakdown:
    """Detailed breakdown of a billing simulation."""
    # Energy charges
    energy_charges: Decimal = Decimal("0")
    slab_breakdown: List[Dict[str, Any]] = field(default_factory=list)

    # Fixed charges
    fixed_charges: Decimal = Decimal("0")
    meter_rent: Decimal = Decimal("0")

    # Adjustments
    fuel_price_adjustment: Decimal = Decimal("0")
    quarterly_tariff_adjustment: Decimal = Decimal("0")

    # Taxes and duties
    electricity_duty: Decimal = Decimal("0")
    gst: Decimal = Decimal("0")
    tv_fee: Decimal = Decimal("0")

    # Net metering credit
    export_credit: Decimal = Decimal("0")

    # Demand charges (industrial)
    demand_charges: Decimal = Decimal("0")

    # Totals
    subtotal: Decimal = Decimal("0")
    total_taxes: Decimal = Decimal("0")
    total_bill: Decimal = Decimal("0")

    def calculate_totals(self) -> None:
        """Calculate subtotal and total."""
        self.subtotal = (
            self.energy_charges +
            self.fixed_charges +
            self.meter_rent +
            self.fuel_price_adjustment +
            self.quarterly_tariff_adjustment +
            self.demand_charges -
            self.export_credit
        )
        self.total_taxes = self.electricity_duty + self.gst + self.tv_fee
        self.total_bill = self.subtotal + self.total_taxes


@dataclass
class SavingsBreakdown:
    """Breakdown of savings from solar generation."""
    # What bill would have been without solar
    bill_without_solar: Decimal = Decimal("0")

    # Actual bill with solar
    bill_with_solar: Decimal = Decimal("0")

    # Savings
    total_savings: Decimal = Decimal("0")
    savings_percent: Decimal = Decimal("0")

    # Export income (if net metering)
    export_income: Decimal = Decimal("0")

    # Environmental impact
    co2_avoided_kg: Decimal = Decimal("0")
    trees_equivalent: Decimal = Decimal("0")

    def calculate(self) -> None:
        """Calculate savings metrics."""
        self.total_savings = self.bill_without_solar - self.bill_with_solar + self.export_income
        if self.bill_without_solar > 0:
            self.savings_percent = (self.total_savings / self.bill_without_solar) * 100


@dataclass(kw_only=True)
class BillingSimulation(Entity):
    """
    Simulated electricity bill for a site.

    Calculates estimated bills based on energy consumption and tariff plans.
    """
    site_id: UUID
    tariff_plan_id: UUID

    # Billing period
    period_start: date
    period_end: date

    # Energy data
    energy_consumed_kwh: Decimal = Decimal("0")
    energy_generated_kwh: Decimal = Decimal("0")
    energy_exported_kwh: Decimal = Decimal("0")
    energy_imported_kwh: Decimal = Decimal("0")

    # Peak demand (for industrial)
    peak_demand_kw: Optional[Decimal] = None

    # Calculated bill
    bill_breakdown: BillBreakdown = field(default_factory=BillBreakdown)

    # Savings analysis
    savings_breakdown: SavingsBreakdown = field(default_factory=SavingsBreakdown)

    # Totals (convenience fields)
    estimated_bill_pkr: Decimal = Decimal("0")
    estimated_savings_pkr: Decimal = Decimal("0")

    # Status
    is_actual: bool = False  # True if based on actual meter readings
    notes: Optional[str] = None

    @property
    def billing_days(self) -> int:
        """Number of days in billing period."""
        return (self.period_end - self.period_start).days + 1

    @property
    def daily_average_consumption(self) -> Decimal:
        """Average daily consumption in kWh."""
        if self.billing_days <= 0:
            return Decimal("0")
        return self.energy_consumed_kwh / self.billing_days

    @property
    def self_consumption_percent(self) -> Decimal:
        """Percentage of generated energy used on-site."""
        if self.energy_generated_kwh <= 0:
            return Decimal("0")
        self_consumed = self.energy_generated_kwh - self.energy_exported_kwh
        return (self_consumed / self.energy_generated_kwh) * 100
