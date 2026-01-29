"""
SQLAlchemy models for Dashboard entities.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from .base import BaseModel
from ....domain.entities.dashboard import (
    DashboardPreferences,
    CustomPreset,
    GridLayout,
    WidgetConfig,
    PresetWidgetConfig,
)


class DashboardPreferencesModel(BaseModel):
    """SQLAlchemy model for user_dashboard_preferences table."""

    __tablename__ = 'user_dashboard_preferences'

    # Override id column to use user_id as primary key
    user_id = Column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, nullable=False)

    # Dashboard configuration
    layout_preset = Column(String(50), default='standard', nullable=False)
    grid_layout = Column(String(10), default='list', nullable=False)
    widget_layout = Column(JSONB, default=list, nullable=False)

    # Relationships
    user = relationship('UserModel', foreign_keys=[user_id])

    def to_domain(self) -> DashboardPreferences:
        """Convert ORM model to domain entity."""
        # Convert JSON widget layout to WidgetConfig objects
        widget_configs = [
            WidgetConfig.from_dict(w) for w in (self.widget_layout or [])
        ]

        prefs = DashboardPreferences(
            id=self.id if hasattr(self, 'id') and self.id else self.user_id,  # Use user_id as id
            user_id=self.user_id,
            layout_preset=self.layout_preset,
            grid_layout=GridLayout(self.grid_layout),
            widget_layout=widget_configs,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version
        )
        prefs._domain_events = []  # Clear events loaded from DB
        return prefs

    @classmethod
    def from_domain(cls, prefs: DashboardPreferences) -> 'DashboardPreferencesModel':
        """Create ORM model from domain entity."""
        # Convert WidgetConfig objects to JSON
        widget_layout_json = [w.to_dict() for w in prefs.widget_layout]

        return cls(
            user_id=prefs.user_id,
            layout_preset=prefs.layout_preset,
            grid_layout=prefs.grid_layout.value,
            widget_layout=widget_layout_json,
            created_at=prefs.created_at,
            updated_at=prefs.updated_at,
            version=prefs.version
        )

    def update_from_domain(self, prefs: DashboardPreferences) -> None:
        """Update ORM model from domain entity."""
        widget_layout_json = [w.to_dict() for w in prefs.widget_layout]

        self.layout_preset = prefs.layout_preset
        self.grid_layout = prefs.grid_layout.value
        self.widget_layout = widget_layout_json
        self.updated_at = prefs.updated_at
        self.version = prefs.version


class CustomPresetModel(BaseModel):
    """SQLAlchemy model for user_custom_presets table."""

    __tablename__ = 'user_custom_presets'

    user_id = Column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    widget_config = Column(JSONB, nullable=False)

    # Relationships
    user = relationship('UserModel', foreign_keys=[user_id])

    def to_domain(self) -> CustomPreset:
        """Convert ORM model to domain entity."""
        # Convert JSON widget config to PresetWidgetConfig objects
        widget_configs = [
            PresetWidgetConfig.from_dict(w) for w in (self.widget_config or [])
        ]

        preset = CustomPreset(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            description=self.description,
            widget_config=widget_configs,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version
        )
        preset._domain_events = []  # Clear events loaded from DB
        return preset

    @classmethod
    def from_domain(cls, preset: CustomPreset) -> 'CustomPresetModel':
        """Create ORM model from domain entity."""
        # Convert PresetWidgetConfig objects to JSON
        widget_config_json = [w.to_dict() for w in preset.widget_config]

        return cls(
            id=preset.id,
            user_id=preset.user_id,
            name=preset.name,
            description=preset.description,
            widget_config=widget_config_json,
            created_at=preset.created_at,
            updated_at=preset.updated_at,
            version=preset.version
        )

    def update_from_domain(self, preset: CustomPreset) -> None:
        """Update ORM model from domain entity."""
        widget_config_json = [w.to_dict() for w in preset.widget_config]

        self.name = preset.name
        self.description = preset.description
        self.widget_config = widget_config_json
        self.updated_at = preset.updated_at
        self.version = preset.version
