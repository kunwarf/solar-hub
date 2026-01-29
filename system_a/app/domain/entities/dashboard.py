"""
Dashboard preferences domain entities and value objects.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from .base import AggregateRoot, Entity, utc_now
from ..exceptions import ValidationException


class WidgetSize(str, Enum):
    """Widget size options."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class GridLayout(str, Enum):
    """Grid layout modes."""
    LIST = "list"
    GRID_2X2 = "2x2"
    GRID_3X3 = "3x3"


@dataclass(frozen=True)
class WidgetConfig:
    """Widget configuration (value object)."""
    id: str
    visible: bool
    size: WidgetSize
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'visible': self.visible,
            'size': self.size.value,
            'settings': self.settings
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WidgetConfig':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            visible=data['visible'],
            size=WidgetSize(data.get('size', 'medium')),
            settings=data.get('settings', {})
        )


@dataclass(frozen=True)
class PresetWidgetConfig:
    """Preset widget configuration (value object)."""
    id: str
    visible: bool
    size: WidgetSize

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'visible': self.visible,
            'size': self.size.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PresetWidgetConfig':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            visible=data['visible'],
            size=WidgetSize(data.get('size', 'medium'))
        )


@dataclass(kw_only=True)
class DashboardPreferences(AggregateRoot):
    """
    Dashboard preferences aggregate root.

    Stores user's dashboard customization including layout preset,
    grid layout mode, and widget configurations.
    """
    user_id: UUID
    layout_preset: str = "standard"
    grid_layout: GridLayout = GridLayout.LIST
    widget_layout: List[WidgetConfig] = field(default_factory=list)

    def __post_init__(self):
        """Validate entity after initialization."""
        super().__post_init__()
        if not self.user_id:
            raise ValidationException("user_id is required")
        if not self.layout_preset:
            raise ValidationException("layout_preset is required")

    def update_preset(self, preset_id: str) -> None:
        """Update the current layout preset."""
        if not preset_id:
            raise ValidationException("preset_id cannot be empty")
        object.__setattr__(self, 'layout_preset', preset_id)
        self._update_timestamp()

    def update_grid_layout(self, grid_layout: GridLayout) -> None:
        """Update the grid layout mode."""
        if not isinstance(grid_layout, GridLayout):
            raise ValidationException("Invalid grid_layout")
        object.__setattr__(self, 'grid_layout', grid_layout)
        self._update_timestamp()

    def update_widget_layout(self, widget_layout: List[WidgetConfig]) -> None:
        """Update the complete widget layout."""
        if not isinstance(widget_layout, list):
            raise ValidationException("widget_layout must be a list")
        object.__setattr__(self, 'widget_layout', widget_layout)
        self._update_timestamp()

    def update_widget_visibility(self, widget_id: str, visible: bool) -> None:
        """Update visibility of a specific widget."""
        updated = False
        new_layout = []
        for widget in self.widget_layout:
            if widget.id == widget_id:
                new_layout.append(WidgetConfig(
                    id=widget.id,
                    visible=visible,
                    size=widget.size,
                    settings=widget.settings
                ))
                updated = True
            else:
                new_layout.append(widget)

        if not updated:
            raise ValidationException(f"Widget {widget_id} not found")

        object.__setattr__(self, 'widget_layout', new_layout)
        self._update_timestamp()

    def update_widget_size(self, widget_id: str, size: WidgetSize) -> None:
        """Update size of a specific widget."""
        updated = False
        new_layout = []
        for widget in self.widget_layout:
            if widget.id == widget_id:
                new_layout.append(WidgetConfig(
                    id=widget.id,
                    visible=widget.visible,
                    size=size,
                    settings=widget.settings
                ))
                updated = True
            else:
                new_layout.append(widget)

        if not updated:
            raise ValidationException(f"Widget {widget_id} not found")

        object.__setattr__(self, 'widget_layout', new_layout)
        # When manually resizing, switch to custom preset
        object.__setattr__(self, 'layout_preset', 'custom')
        self._update_timestamp()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'user_id': str(self.user_id),
            'layout_preset': self.layout_preset,
            'grid_layout': self.grid_layout.value,
            'widget_layout': [w.to_dict() for w in self.widget_layout],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass(kw_only=True)
class CustomPreset(Entity):
    """
    Custom dashboard preset entity.

    Stores user-defined dashboard presets with widget configurations.
    """
    user_id: UUID
    name: str
    description: Optional[str] = None
    widget_config: List[PresetWidgetConfig] = field(default_factory=list)

    def __post_init__(self):
        """Validate entity after initialization."""
        super().__post_init__()
        if not self.user_id:
            raise ValidationException("user_id is required")
        if not self.name or not self.name.strip():
            raise ValidationException("name is required and cannot be empty")
        if len(self.name) > 100:
            raise ValidationException("name cannot exceed 100 characters")
        if self.description and len(self.description) > 500:
            raise ValidationException("description cannot exceed 500 characters")

    def update_name(self, name: str) -> None:
        """Update preset name."""
        if not name or not name.strip():
            raise ValidationException("name cannot be empty")
        if len(name) > 100:
            raise ValidationException("name cannot exceed 100 characters")
        object.__setattr__(self, 'name', name.strip())
        self._update_timestamp()

    def update_description(self, description: Optional[str]) -> None:
        """Update preset description."""
        if description and len(description) > 500:
            raise ValidationException("description cannot exceed 500 characters")
        object.__setattr__(self, 'description', description.strip() if description else None)
        self._update_timestamp()

    def update_widget_config(self, widget_config: List[PresetWidgetConfig]) -> None:
        """Update the widget configuration."""
        if not isinstance(widget_config, list):
            raise ValidationException("widget_config must be a list")
        object.__setattr__(self, 'widget_config', widget_config)
        self._update_timestamp()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'name': self.name,
            'description': self.description,
            'widget_config': [w.to_dict() for w in self.widget_config],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
