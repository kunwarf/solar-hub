"""
Pydantic schemas for dashboard preferences and custom presets.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class WidgetConfigSchema(BaseModel):
    """Widget configuration schema."""
    id: str
    visible: bool
    size: str = Field(..., pattern="^(small|medium|large)$")
    settings: Dict[str, Any] = Field(default_factory=dict)


class PresetWidgetConfigSchema(BaseModel):
    """Preset widget configuration schema (simplified)."""
    id: str
    visible: bool
    size: str = Field(..., pattern="^(small|medium|large)$")


class DashboardPreferencesResponse(BaseModel):
    """Dashboard preferences response schema."""
    user_id: UUID
    layout_preset: str
    grid_layout: str = Field(..., pattern="^(list|2x2|3x3)$")
    widget_layout: List[WidgetConfigSchema]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DashboardPreferencesUpdate(BaseModel):
    """Dashboard preferences update schema."""
    layout_preset: Optional[str] = None
    grid_layout: Optional[str] = Field(None, pattern="^(list|2x2|3x3)$")
    widget_layout: Optional[List[WidgetConfigSchema]] = None

    @validator('widget_layout', pre=True)
    def validate_widget_layout(cls, v):
        """Ensure widget_layout items have correct structure."""
        if v is not None:
            for widget in v:
                if isinstance(widget, dict):
                    if 'id' not in widget or 'visible' not in widget or 'size' not in widget:
                        raise ValueError("Each widget must have 'id', 'visible', and 'size' fields")
        return v


class CustomPresetResponse(BaseModel):
    """Custom preset response schema."""
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str] = None
    widget_config: List[PresetWidgetConfigSchema]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomPresetListResponse(BaseModel):
    """List of custom presets."""
    presets: List[CustomPresetResponse]
    total: int


class CustomPresetCreate(BaseModel):
    """Create custom preset request schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    widget_config: List[PresetWidgetConfigSchema]

    @validator('name')
    def validate_name(cls, v):
        """Ensure name is not just whitespace."""
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()

    @validator('widget_config')
    def validate_widget_config(cls, v):
        """Ensure widget_config is not empty."""
        if not v:
            raise ValueError("Widget config cannot be empty")
        return v


class CustomPresetUpdate(BaseModel):
    """Update custom preset request schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    widget_config: Optional[List[PresetWidgetConfigSchema]] = None

    @validator('name')
    def validate_name(cls, v):
        """Ensure name is not just whitespace if provided."""
        if v is not None and not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip() if v else None
