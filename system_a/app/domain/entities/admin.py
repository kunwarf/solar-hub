"""
Admin portal domain entities.

Entities for electricity providers, tariffs, load shedding schedules, and audit logs.
All are simple CRUD aggregates managed exclusively by portal staff.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from .base import AggregateRoot, utc_now


class ProviderStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class TariffCategory(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    AGRICULTURAL = "agricultural"


class TariffType(str, Enum):
    SLAB = "slab"          # Progressive slab-based billing
    FLAT = "flat"          # Single flat rate per unit
    TOU = "tou"            # Time-of-use rate


class TariffStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


# ---------------------------------------------------------------------------
# Electricity Provider
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class ElectricityProvider(AggregateRoot):
    """
    Electricity distribution company (DISCO) managed by portal admins.

    Examples: LESCO, GEPCO, HESCO, SEPCO, PESCO, QESCO, IESCO, MEPCO, FESCO
    """
    name: str            # Full name e.g. "Lahore Electric Supply Company"
    short_name: str      # Abbreviation e.g. "LESCO"
    region: str          # e.g. "Punjab", "Sindh", "KPK", "Balochistan"
    status: ProviderStatus = ProviderStatus.ACTIVE
    tariff_count: int = 0  # Denormalised count for display

    @classmethod
    def create(
        cls,
        name: str,
        short_name: str,
        region: str,
        created_by: UUID,
    ) -> "ElectricityProvider":
        provider = cls(
            name=name.strip(),
            short_name=short_name.strip().upper(),
            region=region.strip(),
        )
        return provider

    def update(self, name: str, short_name: str, region: str) -> None:
        self.name = name.strip()
        self.short_name = short_name.strip().upper()
        self.region = region.strip()
        self.mark_updated()

    def activate(self) -> None:
        self.status = ProviderStatus.ACTIVE
        self.mark_updated()

    def deactivate(self) -> None:
        self.status = ProviderStatus.INACTIVE
        self.mark_updated()


# ---------------------------------------------------------------------------
# Electricity Tariff
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class ElectricityTariff(AggregateRoot):
    """
    Tariff plan belonging to an electricity provider.

    The `rates` field holds the tariff structure as a JSON-compatible dict:

    For SLAB type:
        {"slabs": [{"min_units": 0, "max_units": 100, "rate_per_kwh": 7.74}, ...]}

    For FLAT type:
        {"rate_per_kwh": 25.0}

    For TOU type:
        {"peak_rate": 35.0, "off_peak_rate": 18.0,
         "peak_hours_start": 18, "peak_hours_end": 22}
    """
    provider_id: UUID
    name: str
    category: TariffCategory
    type: TariffType
    rates: Dict[str, Any]          # JSON structure, varies by type
    fixed_charges: float = 0.0    # Monthly fixed charge in PKR
    effective_from: date = field(default_factory=date.today)
    effective_to: Optional[date] = None
    status: TariffStatus = TariffStatus.ACTIVE
    description: Optional[str] = None

    @classmethod
    def create(
        cls,
        provider_id: UUID,
        name: str,
        category: TariffCategory,
        type: TariffType,
        rates: Dict[str, Any],
        fixed_charges: float = 0.0,
        effective_from: Optional[date] = None,
        effective_to: Optional[date] = None,
        description: Optional[str] = None,
    ) -> "ElectricityTariff":
        return cls(
            provider_id=provider_id,
            name=name.strip(),
            category=category,
            type=type,
            rates=rates,
            fixed_charges=fixed_charges,
            effective_from=effective_from or date.today(),
            effective_to=effective_to,
            description=description,
        )

    def update(
        self,
        name: str,
        category: TariffCategory,
        type: TariffType,
        rates: Dict[str, Any],
        fixed_charges: float,
        effective_from: date,
        effective_to: Optional[date],
        description: Optional[str],
    ) -> None:
        self.name = name.strip()
        self.category = category
        self.type = type
        self.rates = rates
        self.fixed_charges = fixed_charges
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.description = description
        self.mark_updated()

    def activate(self) -> None:
        self.status = TariffStatus.ACTIVE
        self.mark_updated()

    def deactivate(self) -> None:
        self.status = TariffStatus.INACTIVE
        self.mark_updated()


# ---------------------------------------------------------------------------
# Load Shedding Schedule
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class LoadSheddingSchedule(AggregateRoot):
    """
    Load shedding schedule for an area / feeder.

    The `schedule` field holds the weekly schedule as a JSON-compatible dict:
        {
            "monday": [{"start": "06:00", "end": "08:00"}, ...],
            "tuesday": [...],
            ...
        }
    """
    area_name: str       # e.g. "DHA Phase 5"
    region: str          # e.g. "Punjab"
    feeder_code: Optional[str] = None   # e.g. "F-101"
    schedule: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None

    @classmethod
    def create(
        cls,
        area_name: str,
        region: str,
        schedule: Dict[str, Any],
        feeder_code: Optional[str] = None,
        effective_from: Optional[date] = None,
        effective_to: Optional[date] = None,
    ) -> "LoadSheddingSchedule":
        return cls(
            area_name=area_name.strip(),
            region=region.strip(),
            feeder_code=feeder_code,
            schedule=schedule,
            effective_from=effective_from,
            effective_to=effective_to,
        )

    def update(
        self,
        area_name: str,
        region: str,
        schedule: Dict[str, Any],
        feeder_code: Optional[str],
        effective_from: Optional[date],
        effective_to: Optional[date],
    ) -> None:
        self.area_name = area_name.strip()
        self.region = region.strip()
        self.schedule = schedule
        self.feeder_code = feeder_code
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.mark_updated()

    def activate(self) -> None:
        self.is_active = True
        self.mark_updated()

    def deactivate(self) -> None:
        self.is_active = False
        self.mark_updated()


# ---------------------------------------------------------------------------
# Admin Audit Log
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class AdminAuditLog(AggregateRoot):
    """
    Immutable audit log entry for admin portal actions.

    Written once, never updated or deleted by the application.
    """
    admin_user_id: UUID
    admin_email: str
    action: str           # e.g. "create", "update", "delete", "login", "logout"
    resource_type: str    # e.g. "provider", "tariff", "load_shedding", "user"
    resource_id: Optional[str] = None  # UUID or name of the affected resource
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    @classmethod
    def record(
        cls,
        admin_user_id: UUID,
        admin_email: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> "AdminAuditLog":
        return cls(
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
        )


# ---------------------------------------------------------------------------
# Provider Billing Schedule
# ---------------------------------------------------------------------------

class BillingScheduleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


@dataclass(kw_only=True)
class ProviderBillingSchedule(AggregateRoot):
    """
    Admin-managed billing schedule for a DISCO + tariff category combination.

    When a site's disco_provider + tariff_category match an active schedule,
    the billing engine uses these rates instead of per-site billing_config.

    The tou_windows field stores a JSON dict compatible with TouConfig.from_dict():
        {"peak_windows": [{"start_hour": 17, "end_hour": 22}], "timezone": "Asia/Karachi"}
    """
    provider_id: UUID
    tariff_category: str            # e.g. "residential", "A-1", "commercial"

    # Import prices (buying from grid)
    price_offpeak_import: Decimal
    price_peak_import: Decimal

    # Settlement prices (selling expired credits at cycle end)
    price_offpeak_settlement: Decimal
    price_peak_settlement: Decimal

    # Fixed monthly charge
    fixed_charge: Decimal = field(default_factory=lambda: Decimal("0"))

    # NEPRA-mandated surcharges (admin-configurable)
    fuel_price_adjustment: Decimal = field(default_factory=lambda: Decimal("0"))
    quarterly_tariff_adjustment: Decimal = field(default_factory=lambda: Decimal("0"))

    # TOU configuration as JSON dict (same format as TouConfig)
    tou_windows: Dict[str, Any] = field(default_factory=lambda: {
        "peak_windows": [{"start_hour": 17, "end_hour": 22}],
        "timezone": "Asia/Karachi",
    })

    # Defaults applied to new sites
    default_anchor_day: int = 15
    currency: str = "PKR"
    net_metering_enabled: bool = True

    # Status and validity dates
    status: BillingScheduleStatus = BillingScheduleStatus.ACTIVE
    effective_from: date = field(default_factory=date.today)
    effective_to: Optional[date] = None
    description: Optional[str] = None

    @classmethod
    def create(
        cls,
        provider_id: UUID,
        tariff_category: str,
        price_offpeak_import: Decimal,
        price_peak_import: Decimal,
        price_offpeak_settlement: Decimal,
        price_peak_settlement: Decimal,
        fixed_charge: Decimal = Decimal("0"),
        fuel_price_adjustment: Decimal = Decimal("0"),
        quarterly_tariff_adjustment: Decimal = Decimal("0"),
        tou_windows: Optional[Dict[str, Any]] = None,
        default_anchor_day: int = 15,
        currency: str = "PKR",
        net_metering_enabled: bool = True,
        status: BillingScheduleStatus = BillingScheduleStatus.ACTIVE,
        effective_from: Optional[date] = None,
        effective_to: Optional[date] = None,
        description: Optional[str] = None,
    ) -> "ProviderBillingSchedule":
        return cls(
            provider_id=provider_id,
            tariff_category=tariff_category.strip().lower(),
            price_offpeak_import=price_offpeak_import,
            price_peak_import=price_peak_import,
            price_offpeak_settlement=price_offpeak_settlement,
            price_peak_settlement=price_peak_settlement,
            fixed_charge=fixed_charge,
            fuel_price_adjustment=fuel_price_adjustment,
            quarterly_tariff_adjustment=quarterly_tariff_adjustment,
            tou_windows=tou_windows or {
                "peak_windows": [{"start_hour": 17, "end_hour": 22}],
                "timezone": "Asia/Karachi",
            },
            default_anchor_day=default_anchor_day,
            currency=currency,
            net_metering_enabled=net_metering_enabled,
            status=status,
            effective_from=effective_from or date.today(),
            effective_to=effective_to,
            description=description,
        )

    def update(
        self,
        tariff_category: str,
        price_offpeak_import: Decimal,
        price_peak_import: Decimal,
        price_offpeak_settlement: Decimal,
        price_peak_settlement: Decimal,
        fixed_charge: Decimal,
        fuel_price_adjustment: Decimal,
        quarterly_tariff_adjustment: Decimal,
        tou_windows: Dict[str, Any],
        default_anchor_day: int,
        currency: str,
        net_metering_enabled: bool,
        status: BillingScheduleStatus,
        effective_from: date,
        effective_to: Optional[date],
        description: Optional[str],
    ) -> None:
        self.tariff_category = tariff_category.strip().lower()
        self.price_offpeak_import = price_offpeak_import
        self.price_peak_import = price_peak_import
        self.price_offpeak_settlement = price_offpeak_settlement
        self.price_peak_settlement = price_peak_settlement
        self.fixed_charge = fixed_charge
        self.fuel_price_adjustment = fuel_price_adjustment
        self.quarterly_tariff_adjustment = quarterly_tariff_adjustment
        self.tou_windows = tou_windows
        self.default_anchor_day = default_anchor_day
        self.currency = currency
        self.net_metering_enabled = net_metering_enabled
        self.status = status
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.description = description
        self.mark_updated()

    def activate(self) -> None:
        self.status = BillingScheduleStatus.ACTIVE
        self.mark_updated()

    def deactivate(self) -> None:
        self.status = BillingScheduleStatus.INACTIVE
        self.mark_updated()
