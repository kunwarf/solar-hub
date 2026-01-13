"""
Pydantic schemas for site endpoints.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AddressSchema(BaseModel):
    """Physical address."""
    street: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = Field(default="Pakistan")


class GeoLocationSchema(BaseModel):
    """Geographic coordinates."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class SiteConfigurationSchema(BaseModel):
    """Solar site configuration."""
    system_capacity_kw: float = Field(..., gt=0, description="Total system capacity in kW")
    panel_count: int = Field(..., gt=0, description="Number of solar panels")
    panel_wattage: float = Field(..., gt=0, description="Wattage per panel")
    inverter_capacity_kw: float = Field(..., gt=0, description="Inverter capacity in kW")
    inverter_count: int = Field(default=1, ge=1)
    battery_capacity_kwh: Optional[float] = Field(None, ge=0, description="Battery storage capacity")
    battery_count: int = Field(default=0, ge=0)
    grid_connection_type: str = Field(default="on_grid")
    net_metering_enabled: bool = Field(default=False)
    disco_provider: Optional[str] = Field(None, description="DISCO provider (LESCO, FESCO, etc.)")
    tariff_category: Optional[str] = Field(None, description="Tariff category")
    reference_number: Optional[str] = Field(None, description="DISCO reference/account number")

    @field_validator('grid_connection_type')
    @classmethod
    def validate_grid_type(cls, v: str) -> str:
        valid_types = ['on_grid', 'off_grid', 'hybrid']
        if v.lower() not in valid_types:
            raise ValueError(f'Grid connection type must be one of: {", ".join(valid_types)}')
        return v.lower()

    @field_validator('disco_provider')
    @classmethod
    def validate_disco(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid_discos = ['lesco', 'fesco', 'iesco', 'gepco', 'mepco', 'pesco', 'hesco', 'sepco', 'qesco', 'tesco', 'kelectric']
        if v.lower() not in valid_discos:
            raise ValueError(f'DISCO provider must be one of: {", ".join(valid_discos)}')
        return v.lower()


class SiteCreate(BaseModel):
    """Request to create a site."""
    organization_id: UUID
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    address: AddressSchema
    geo_location: GeoLocationSchema
    timezone: str = Field(default="Asia/Karachi")
    configuration: SiteConfigurationSchema

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()


class SiteUpdate(BaseModel):
    """Request to update a site."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    address: Optional[AddressSchema] = None
    geo_location: Optional[GeoLocationSchema] = None
    timezone: Optional[str] = None
    configuration: Optional[SiteConfigurationSchema] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class SiteResponse(BaseModel):
    """Site response."""
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str]
    address: AddressSchema
    geo_location: GeoLocationSchema
    timezone: str
    status: str
    site_type: str
    configuration: SiteConfigurationSchema
    commissioned_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class SiteDetailResponse(SiteResponse):
    """Detailed site response with device counts."""
    device_count: int = 0
    online_device_count: int = 0
    alert_count: int = 0


class SiteListResponse(BaseModel):
    """Paginated list of sites."""
    items: List[SiteResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SiteStatusUpdate(BaseModel):
    """Request to update site status."""
    status: str = Field(..., description="New status for the site")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = ['active', 'inactive', 'maintenance', 'decommissioned']
        if v.lower() not in valid_statuses:
            raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v.lower()


class SiteSummaryResponse(BaseModel):
    """Site summary for dashboard."""
    id: UUID
    name: str
    status: str
    device_count: int
    online_devices: int
    current_power_kw: float = 0.0
    daily_energy_kwh: float = 0.0
    monthly_energy_kwh: float = 0.0
