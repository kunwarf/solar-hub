"""
Pydantic schemas for organization endpoints.
"""
import re
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class OrganizationSettingsSchema(BaseModel):
    """Organization settings."""
    max_sites: int = Field(default=10, ge=1)
    max_users: int = Field(default=20, ge=1)
    alert_email_enabled: bool = Field(default=True)
    alert_sms_enabled: bool = Field(default=False)
    report_frequency: str = Field(default="weekly")
    default_dashboard: str = Field(default="overview")


class OrganizationCreate(BaseModel):
    """Request to create an organization."""
    name: str = Field(..., min_length=2, max_length=255, description="Organization name")
    slug: Optional[str] = Field(None, min_length=2, max_length=100, description="URL-friendly slug")
    description: Optional[str] = Field(None, max_length=1000)
    settings: Optional[OrganizationSettingsSchema] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.lower().strip()
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', v) and len(v) > 2:
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v


class OrganizationUpdate(BaseModel):
    """Request to update an organization."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    settings: Optional[OrganizationSettingsSchema] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class OrganizationMemberResponse(BaseModel):
    """Organization member response."""
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: str
    status: str
    invited_by: Optional[UUID]
    invited_at: datetime
    accepted_at: Optional[datetime]

    # User details
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class OrganizationResponse(BaseModel):
    """Organization response."""
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    owner_id: UUID
    status: str
    settings: OrganizationSettingsSchema
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class OrganizationDetailResponse(OrganizationResponse):
    """Detailed organization response with members."""
    members: List[OrganizationMemberResponse]
    site_count: int = 0
    device_count: int = 0


class OrganizationListResponse(BaseModel):
    """Paginated list of organizations."""
    items: List[OrganizationResponse]
    total: int
    page: int
    page_size: int
    pages: int


class InviteMemberRequest(BaseModel):
    """Request to invite a member to an organization."""
    email: EmailStr = Field(..., description="Email of user to invite")
    role: str = Field(default="viewer", description="Role for the invited user")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ['viewer', 'installer', 'manager', 'admin']
        if v.lower() not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v.lower()


class UpdateMemberRoleRequest(BaseModel):
    """Request to update a member's role."""
    role: str = Field(..., description="New role for the member")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ['viewer', 'installer', 'manager', 'admin']
        if v.lower() not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v.lower()


class TransferOwnershipRequest(BaseModel):
    """Request to transfer organization ownership."""
    new_owner_id: UUID = Field(..., description="ID of the new owner")
