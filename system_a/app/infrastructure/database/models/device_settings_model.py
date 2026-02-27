"""
Device Settings Model

Stores device-specific configuration settings that vary by device type and manufacturer.
Supports inverter, battery, and meter settings with flexible JSON storage.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Index,
)
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID
from sqlalchemy.orm import relationship

from .base import Base


class DeviceSettings(Base):
    """Device Settings model for storing device-specific configurations"""

    __tablename__ = "device_settings"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    device_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    created_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Device identification
    device_type = Column(String(50), nullable=False, index=True)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)

    # Settings storage (flexible JSON)
    settings = Column(JSON, nullable=False, server_default="{}")

    # Flags
    is_default = Column(Boolean, nullable=False, server_default="false")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
        onupdate=datetime.utcnow,
    )

    # Relationships
    device = relationship("DeviceModel", back_populates="settings")
    creator = relationship("UserModel", foreign_keys=[created_by])
    updater = relationship("UserModel", foreign_keys=[updated_by])

    # Composite index for manufacturer + model lookups
    __table_args__ = (
        Index("ix_device_settings_manufacturer_model", "manufacturer", "model"),
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceSettings("
            f"id={self.id}, "
            f"device_id={self.device_id}, "
            f"type={self.device_type}, "
            f"manufacturer={self.manufacturer}"
            f")>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary representation"""
        return {
            "id": str(self.id),
            "device_id": str(self.device_id),
            "device_type": self.device_type,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "settings": self.settings,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": str(self.created_by) if self.created_by else None,
            "updated_by": str(self.updated_by) if self.updated_by else None,
        }


# Default settings by device type
DEFAULT_INVERTER_SETTINGS = {
    "power_limits": {
        "max_charge_power_w": 5000,
        "max_discharge_power_w": 5000,
        "max_grid_export_power_w": 5000,
    },
    "grid_settings": {
        "grid_voltage_upper_limit_v": 253,
        "grid_voltage_lower_limit_v": 207,
        "grid_frequency_upper_limit_hz": 52,
        "grid_frequency_lower_limit_hz": 47,
    },
    "protection": {
        "over_voltage_protection_enabled": True,
        "under_voltage_protection_enabled": True,
        "over_frequency_protection_enabled": True,
        "under_frequency_protection_enabled": True,
        "anti_islanding_enabled": True,
    },
    "tou_windows": [],
}

DEFAULT_BATTERY_SETTINGS = {
    "general": {
        "device_id": "",
        "device_name": "",
        "array_id": "array1",
    },
    "adapter": {
        "type": "generic",
        "transport": "rtu",
        "serial_port": "/dev/ttyUSB0",
        "baudrate": 9600,
        "parity": "N",
        "stopbits": 1,
        "bytesize": 8,
        "host": "192.168.1.100",
        "port": 502,
        "batteries": 1,
        "cells_per_battery": 16,
        "dev_name": "battery",
        "manufacturer": "Generic",
        "model": "Generic BMS",
    },
    "soc_limits": {
        "min_soc_pct": 10,
        "max_soc_pct": 95,
        "target_soc_pct": 80,
    },
    "charging": {
        "max_charge_current_a": 50,
        "max_discharge_current_a": 50,
        "cell_voltage_limit_v": 3.65,
        "temperature_limit_c": 45,
    },
    "protection": {
        "over_voltage_protection_enabled": True,
        "under_voltage_protection_enabled": True,
        "over_current_protection_enabled": True,
        "over_temperature_protection_enabled": True,
    },
}

DEFAULT_METER_SETTINGS = {
    "metering": {
        "meter_type": "bidirectional",
        "ct_ratio": 100,
        "voltage_ratio": 1,
        "phase_configuration": "3P4W",
    },
    "direction": {
        "reverse_current_detection": True,
        "import_export_tracking": True,
    },
    "demand": {
        "demand_calculation_enabled": True,
        "demand_window_minutes": 15,
        "demand_threshold_kw": 10,
    },
    "communication": {
        "protocol": "modbus_rtu",
        "address": 1,
        "baudrate": 9600,
        "parity": "N",
        "stopbits": 1,
    },
}


# Manufacturer-specific inverter setting overrides
# These are merged on top of DEFAULT_INVERTER_SETTINGS
_MANUFACTURER_INVERTER_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "powdrive": {
        "power_limits": {
            "max_charge_power_w": 3500,
            "max_discharge_power_w": 3500,
            "max_grid_export_power_w": 3500,
        },
        "telemetry": {
            # Powdrive uses negative values for battery charging (opposite convention)
            "battery_power_sign_convention": "negative_charging",
        },
    },
    "senergy": {
        "power_limits": {
            "max_charge_power_w": 5000,
            "max_discharge_power_w": 5000,
            "max_grid_export_power_w": 5000,
        },
        "telemetry": {
            "battery_power_sign_convention": "positive_charging",
        },
    },
}


def get_default_settings(device_type: str, manufacturer: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Get default settings for a device type, with optional manufacturer/model-specific overrides.
    """
    import copy
    defaults = {
        "inverter": DEFAULT_INVERTER_SETTINGS,
        "battery": DEFAULT_BATTERY_SETTINGS,
        "meter": DEFAULT_METER_SETTINGS,
    }

    base_settings = copy.deepcopy(defaults.get(device_type.lower(), {}))

    # Apply manufacturer-specific overrides for inverters
    if device_type.lower() == "inverter" and manufacturer:
        overrides = _MANUFACTURER_INVERTER_OVERRIDES.get(manufacturer.lower())
        if overrides:
            for section_key, section_values in overrides.items():
                if section_key in base_settings and isinstance(base_settings[section_key], dict):
                    base_settings[section_key].update(section_values)
                else:
                    base_settings[section_key] = section_values

    return base_settings
