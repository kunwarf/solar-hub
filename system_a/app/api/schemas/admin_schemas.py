"""
Pydantic schemas for admin portal API.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from ...domain.entities.admin import (
    BillingScheduleStatus,
    ProviderStatus,
    TariffCategory,
    TariffStatus,
    TariffType,
)
from ...domain.entities.user import UserRole, UserStatus


# ---------------------------------------------------------------------------
# Admin Auth Schemas
# ---------------------------------------------------------------------------

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AdminPermissions(BaseModel):
    manage_providers: bool = False
    manage_tariffs: bool = False
    manage_load_shedding: bool = False
    manage_users: bool = False
    view_users: bool = False
    manage_firmware: bool = False
    manage_devices: bool = False
    view_audit_log: bool = False
    manage_system: bool = False

    @classmethod
    def for_role(cls, role: UserRole) -> "AdminPermissions":
        """Derive permissions from role."""
        if role == UserRole.SUPER_ADMIN:
            return cls(
                manage_providers=True, manage_tariffs=True,
                manage_load_shedding=True, manage_users=True,
                view_users=True, manage_firmware=True,
                manage_devices=True, view_audit_log=True,
                manage_system=True,
            )
        if role == UserRole.OPS_ADMIN:
            return cls(
                manage_providers=True, manage_tariffs=True,
                manage_load_shedding=True, view_users=True,
                view_audit_log=True,
            )
        if role == UserRole.BILLING_ADMIN:
            return cls(manage_tariffs=True, view_audit_log=True)
        if role == UserRole.DEVICE_ADMIN:
            return cls(manage_devices=True, view_audit_log=True)
        if role == UserRole.FIRMWARE_ADMIN:
            return cls(manage_firmware=True, view_audit_log=True)
        return cls()


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    status: UserStatus
    permissions: AdminPermissions
    last_login_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AdminUserResponse


# ---------------------------------------------------------------------------
# Electricity Provider Schemas
# ---------------------------------------------------------------------------

class ProviderCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    short_name: str = Field(min_length=2, max_length=20)
    region: str = Field(min_length=2, max_length=100)

    @field_validator("short_name")
    @classmethod
    def upper_short_name(cls, v: str) -> str:
        return v.upper()


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    short_name: Optional[str] = Field(None, min_length=2, max_length=20)
    region: Optional[str] = Field(None, min_length=2, max_length=100)
    status: Optional[ProviderStatus] = None

    @field_validator("short_name")
    @classmethod
    def upper_short_name(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v


class ProviderResponse(BaseModel):
    id: UUID
    name: str
    short_name: str
    region: str
    status: ProviderStatus
    tariff_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ProviderListResponse(BaseModel):
    items: List[ProviderResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Electricity Tariff Schemas
# ---------------------------------------------------------------------------

class TariffCreate(BaseModel):
    provider_id: UUID
    name: str = Field(min_length=2, max_length=200)
    category: TariffCategory
    type: TariffType
    rates: Dict[str, Any] = Field(description="Tariff rate structure (depends on type)")
    fixed_charges: float = Field(0.0, ge=0)
    effective_from: date
    effective_to: Optional[date] = None
    description: Optional[str] = None


class TariffUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    category: Optional[TariffCategory] = None
    type: Optional[TariffType] = None
    rates: Optional[Dict[str, Any]] = None
    fixed_charges: Optional[float] = Field(None, ge=0)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    description: Optional[str] = None
    status: Optional[TariffStatus] = None


class TariffResponse(BaseModel):
    id: UUID
    provider_id: UUID
    name: str
    category: TariffCategory
    type: TariffType
    rates: Dict[str, Any]
    fixed_charges: float
    effective_from: date
    effective_to: Optional[date]
    status: TariffStatus
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TariffListResponse(BaseModel):
    items: List[TariffResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Load Shedding Schemas
# ---------------------------------------------------------------------------

class LoadSheddingCreate(BaseModel):
    area_name: str = Field(min_length=2, max_length=200)
    region: str = Field(min_length=2, max_length=100)
    feeder_code: Optional[str] = Field(None, max_length=50)
    schedule: Dict[str, Any] = Field(
        description="Weekly schedule: {monday: [{start: '06:00', end: '08:00'}], ...}"
    )
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class LoadSheddingUpdate(BaseModel):
    area_name: Optional[str] = Field(None, min_length=2, max_length=200)
    region: Optional[str] = Field(None, min_length=2, max_length=100)
    feeder_code: Optional[str] = Field(None, max_length=50)
    schedule: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class LoadSheddingResponse(BaseModel):
    id: UUID
    area_name: str
    region: str
    feeder_code: Optional[str]
    schedule: Dict[str, Any]
    is_active: bool
    effective_from: Optional[date]
    effective_to: Optional[date]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class LoadSheddingListResponse(BaseModel):
    items: List[LoadSheddingResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Admin Audit Log Schemas
# ---------------------------------------------------------------------------

class AuditLogResponse(BaseModel):
    id: UUID
    admin_user_id: UUID
    admin_email: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Admin User Management Schemas
# ---------------------------------------------------------------------------

class AdminUserListItem(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    status: UserStatus
    last_login_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: List[AdminUserListItem]
    total: int
    limit: int
    offset: int


class AdminUserUpdate(BaseModel):
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None


# ---------------------------------------------------------------------------
# Public provider / tariff schemas (read-only, no auth required)
# ---------------------------------------------------------------------------

class PublicProviderResponse(BaseModel):
    id: UUID
    name: str
    short_name: str
    region: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Provider Billing Schedule Schemas
# ---------------------------------------------------------------------------

class BillingScheduleCreate(BaseModel):
    provider_id: UUID
    tariff_category: str = Field(min_length=1, max_length=50, description="e.g. 'residential', 'A-1'")
    price_offpeak_import: float = Field(..., ge=0, description="Off-peak import price per kWh")
    price_peak_import: float = Field(..., ge=0, description="Peak import price per kWh")
    price_offpeak_settlement: float = Field(..., ge=0, description="Off-peak settlement price")
    price_peak_settlement: float = Field(..., ge=0, description="Peak settlement price")
    fixed_charge: float = Field(0.0, ge=0, description="Fixed monthly charge")
    fuel_price_adjustment: float = Field(0.0, ge=0, description="NEPRA Fuel Price Adjustment surcharge per kWh")
    quarterly_tariff_adjustment: float = Field(0.0, ge=0, description="NEPRA Quarterly Tariff Adjustment surcharge per kWh")
    tou_windows: Dict[str, Any] = Field(
        default={"peak_windows": [{"start_hour": 17, "end_hour": 22}], "timezone": "Asia/Karachi"},
        description='TOU windows: {"peak_windows": [{"start_hour": 17, "end_hour": 22}], "timezone": "Asia/Karachi"}',
    )
    default_anchor_day: int = Field(15, ge=1, le=28)
    currency: str = Field("PKR", max_length=10)
    net_metering_enabled: bool = True
    status: BillingScheduleStatus = BillingScheduleStatus.ACTIVE
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    description: Optional[str] = None


class BillingScheduleUpdate(BaseModel):
    tariff_category: Optional[str] = Field(None, min_length=1, max_length=50)
    price_offpeak_import: Optional[float] = Field(None, ge=0)
    price_peak_import: Optional[float] = Field(None, ge=0)
    price_offpeak_settlement: Optional[float] = Field(None, ge=0)
    price_peak_settlement: Optional[float] = Field(None, ge=0)
    fixed_charge: Optional[float] = Field(None, ge=0)
    fuel_price_adjustment: Optional[float] = Field(None, ge=0)
    quarterly_tariff_adjustment: Optional[float] = Field(None, ge=0)
    tou_windows: Optional[Dict[str, Any]] = None
    default_anchor_day: Optional[int] = Field(None, ge=1, le=28)
    currency: Optional[str] = Field(None, max_length=10)
    net_metering_enabled: Optional[bool] = None
    status: Optional[BillingScheduleStatus] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    description: Optional[str] = None


class BillingScheduleResponse(BaseModel):
    id: UUID
    provider_id: UUID
    tariff_category: str
    price_offpeak_import: float
    price_peak_import: float
    price_offpeak_settlement: float
    price_peak_settlement: float
    fixed_charge: float
    fuel_price_adjustment: float
    quarterly_tariff_adjustment: float
    tou_windows: Dict[str, Any]
    default_anchor_day: int
    currency: str
    net_metering_enabled: bool
    status: BillingScheduleStatus
    effective_from: date
    effective_to: Optional[date]
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class BillingScheduleListResponse(BaseModel):
    items: List[BillingScheduleResponse]
    total: int
    limit: int
    offset: int


class PublicTariffResponse(BaseModel):
    id: UUID
    provider_id: UUID
    name: str
    category: TariffCategory
    type: TariffType
    rates: Dict[str, Any]
    fixed_charges: float
    effective_from: date
    effective_to: Optional[date]

    model_config = {"from_attributes": True}
