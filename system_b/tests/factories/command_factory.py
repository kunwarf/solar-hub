"""
Command-related test data factories.
"""
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from uuid import uuid4

import factory


class CommandFactory(factory.Factory):
    """
    Factory for creating command data dictionaries.

    Usage:
        command = CommandFactory()
        command = CommandFactory(command_type="set_battery_mode")
    """

    class Meta:
        model = dict

    command_id = factory.LazyFunction(uuid4)
    device_id = factory.LazyFunction(uuid4)
    site_id = factory.LazyFunction(uuid4)
    command_type = factory.Iterator([
        "set_battery_mode",
        "set_charge_current",
        "set_discharge_current",
        "set_grid_charge",
        "set_time_of_use",
        "restart_device",
        "update_firmware",
    ])
    status = "pending"
    priority = factory.LazyFunction(lambda: random.randint(1, 10))
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    scheduled_at = None
    sent_at = None
    acknowledged_at = None
    completed_at = None
    expires_at = factory.LazyAttribute(
        lambda o: o.created_at + timedelta(hours=1)
    )
    retry_count = 0
    max_retries = 3
    result = None
    error_message = None
    created_by = None

    @factory.lazy_attribute
    def command_params(self) -> Dict[str, Any]:
        params_by_type = {
            "set_battery_mode": {"mode": random.choice(["charge", "discharge", "auto"])},
            "set_charge_current": {"current_a": random.randint(10, 50)},
            "set_discharge_current": {"current_a": random.randint(10, 50)},
            "set_grid_charge": {"enabled": random.choice([True, False])},
            "set_time_of_use": {
                "periods": [
                    {"start": "06:00", "end": "09:00", "mode": "charge"},
                    {"start": "17:00", "end": "21:00", "mode": "discharge"},
                ]
            },
            "restart_device": {},
            "update_firmware": {"version": "1.2.4", "url": "https://example.com/fw.bin"},
        }
        return params_by_type.get(self.command_type, {})


class PendingCommandFactory(CommandFactory):
    """Factory for pending commands."""

    status = "pending"


class SentCommandFactory(CommandFactory):
    """Factory for commands that have been sent to device."""

    status = "sent"
    sent_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class AcknowledgedCommandFactory(CommandFactory):
    """Factory for commands acknowledged by device."""

    status = "acknowledged"
    sent_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) - timedelta(seconds=5)
    )
    acknowledged_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class CompletedCommandFactory(CommandFactory):
    """Factory for completed commands."""

    status = "completed"
    sent_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) - timedelta(seconds=10)
    )
    acknowledged_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) - timedelta(seconds=5)
    )
    completed_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))

    @factory.lazy_attribute
    def result(self) -> Dict[str, Any]:
        return {"success": True, "message": "Command executed successfully"}


class FailedCommandFactory(CommandFactory):
    """Factory for failed commands."""

    status = "failed"
    sent_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) - timedelta(seconds=10)
    )
    completed_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    error_message = factory.LazyFunction(
        lambda: random.choice([
            "Device not responding",
            "Invalid parameter value",
            "Command timeout",
            "Device rejected command",
        ])
    )


class ExpiredCommandFactory(CommandFactory):
    """Factory for expired commands."""

    status = "expired"
    expires_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) - timedelta(minutes=5)
    )


class SetBatteryModeCommandFactory(CommandFactory):
    """Factory for set_battery_mode commands."""

    command_type = "set_battery_mode"

    @factory.lazy_attribute
    def command_params(self) -> Dict[str, Any]:
        return {
            "mode": random.choice(["charge", "discharge", "auto", "standby"]),
            "power_limit_w": random.choice([None, 2000, 3000, 5000]),
        }


class SetChargeCurrentCommandFactory(CommandFactory):
    """Factory for set_charge_current commands."""

    command_type = "set_charge_current"

    @factory.lazy_attribute
    def command_params(self) -> Dict[str, Any]:
        return {
            "current_a": random.randint(10, 100),
        }
