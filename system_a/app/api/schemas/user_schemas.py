"""
Pydantic schemas for user endpoints.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserPreferencesSchema(BaseModel):
    """User preferences."""
    timezone: str = Field(default="Asia/Karachi")
    language: str = Field(default="en")
    currency: str = Field(default="PKR")
    date_format: str = Field(default="DD/MM/YYYY")
    notifications_enabled: bool = Field(default=True)
    email_notifications: bool = Field(default=True)
    sms_notifications: bool = Field(default=True)
    dashboard_refresh_interval: int = Field(default=30, ge=5, le=300)


class UserProfileUpdate(BaseModel):
    """Request to update user profile."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None)

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class UserPreferencesUpdate(BaseModel):
    """Request to update user preferences."""
    timezone: Optional[str] = None
    language: Optional[str] = None
    currency: Optional[str] = None
    date_format: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    dashboard_refresh_interval: Optional[int] = Field(None, ge=5, le=300)


class UserResponse(BaseModel):
    """User response."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    role: str
    status: str
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Detailed user response with preferences."""
    preferences: UserPreferencesSchema
    last_login_at: Optional[datetime]
    failed_login_attempts: int = 0


class UserListResponse(BaseModel):
    """Paginated list of users."""
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int


class UserRoleUpdate(BaseModel):
    """Request to update user role (admin only)."""
    role: str = Field(..., description="New role for the user")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ['viewer', 'installer', 'manager', 'admin']
        if v.lower() not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v.lower()


class UserStatusUpdate(BaseModel):
    """Request to update user status (admin only)."""
    status: str = Field(..., description="New status for the user")
    reason: Optional[str] = Field(None, description="Reason for status change")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = ['active', 'suspended', 'deactivated']
        if v.lower() not in valid_statuses:
            raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v.lower()
