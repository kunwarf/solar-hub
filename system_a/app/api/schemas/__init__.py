"""
Pydantic request/response schemas for API endpoints.
"""
# Auth schemas
from .auth_schemas import (
    AuthResponse,
    ChangePasswordRequest,
    ErrorResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse as AuthUserResponse,
)

# User schemas
from .user_schemas import (
    UserDetailResponse,
    UserListResponse,
    UserPreferencesSchema,
    UserPreferencesUpdate,
    UserProfileUpdate,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)

# Organization schemas
from .organization_schemas import (
    InviteMemberRequest,
    OrganizationCreate,
    OrganizationDetailResponse,
    OrganizationListResponse,
    OrganizationMemberResponse,
    OrganizationResponse,
    OrganizationSettingsSchema,
    OrganizationUpdate,
    TransferOwnershipRequest,
    UpdateMemberRoleRequest,
)

# Site schemas
from .site_schemas import (
    AddressSchema,
    GeoLocationSchema,
    SiteConfigurationSchema,
    SiteCreate,
    SiteDetailResponse,
    SiteListResponse,
    SiteResponse,
    SiteStatusUpdate,
    SiteSummaryResponse,
    SiteUpdate,
)

# Device schemas
from .device_schemas import (
    ConnectionConfigSchema,
    DeviceCommandRequest,
    DeviceCommandResponse,
    DeviceCreate,
    DeviceDetailResponse,
    DeviceListResponse,
    DeviceMetricsSchema,
    DeviceResponse,
    DeviceStatusUpdate,
    DeviceSummaryResponse,
    DeviceUpdate,
)

# Dashboard schemas
from .dashboard_schemas import (
    DailyEnergyStats,
    DashboardWidgetData,
    EnergyChartData,
    EnergyDataPoint,
    EnvironmentalImpactResponse,
    MonthlyEnergyStats,
    OrganizationOverviewResponse,
    PowerChartData,
    PowerDataPoint,
    SiteComparisonItem,
    SiteComparisonResponse,
    SiteOverviewResponse,
    WeatherData,
)

# Alert schemas
from .alert_schemas import (
    AlertAcknowledgeRequest,
    AlertConditionSchema,
    AlertListResponse,
    AlertResolveRequest,
    AlertResponse,
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleToggleRequest,
    AlertRuleUpdate,
    AlertSummary,
)

__all__ = [
    # Auth
    'AuthResponse',
    'ChangePasswordRequest',
    'ErrorResponse',
    'ForgotPasswordRequest',
    'LoginRequest',
    'MessageResponse',
    'RefreshTokenRequest',
    'RegisterRequest',
    'ResetPasswordRequest',
    'TokenResponse',
    'AuthUserResponse',
    # User
    'UserDetailResponse',
    'UserListResponse',
    'UserPreferencesSchema',
    'UserPreferencesUpdate',
    'UserProfileUpdate',
    'UserResponse',
    'UserRoleUpdate',
    'UserStatusUpdate',
    # Organization
    'InviteMemberRequest',
    'OrganizationCreate',
    'OrganizationDetailResponse',
    'OrganizationListResponse',
    'OrganizationMemberResponse',
    'OrganizationResponse',
    'OrganizationSettingsSchema',
    'OrganizationUpdate',
    'TransferOwnershipRequest',
    'UpdateMemberRoleRequest',
    # Site
    'AddressSchema',
    'GeoLocationSchema',
    'SiteConfigurationSchema',
    'SiteCreate',
    'SiteDetailResponse',
    'SiteListResponse',
    'SiteResponse',
    'SiteStatusUpdate',
    'SiteSummaryResponse',
    'SiteUpdate',
    # Device
    'ConnectionConfigSchema',
    'DeviceCommandRequest',
    'DeviceCommandResponse',
    'DeviceCreate',
    'DeviceDetailResponse',
    'DeviceListResponse',
    'DeviceMetricsSchema',
    'DeviceResponse',
    'DeviceStatusUpdate',
    'DeviceSummaryResponse',
    'DeviceUpdate',
    # Dashboard
    'DailyEnergyStats',
    'DashboardWidgetData',
    'EnergyChartData',
    'EnergyDataPoint',
    'EnvironmentalImpactResponse',
    'MonthlyEnergyStats',
    'OrganizationOverviewResponse',
    'PowerChartData',
    'PowerDataPoint',
    'SiteComparisonItem',
    'SiteComparisonResponse',
    'SiteOverviewResponse',
    'WeatherData',
    # Alert
    'AlertAcknowledgeRequest',
    'AlertConditionSchema',
    'AlertListResponse',
    'AlertResolveRequest',
    'AlertResponse',
    'AlertRuleCreate',
    'AlertRuleListResponse',
    'AlertRuleResponse',
    'AlertRuleToggleRequest',
    'AlertRuleUpdate',
    'AlertSummary',
]
