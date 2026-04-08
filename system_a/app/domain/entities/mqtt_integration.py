"""
MQTT Integration domain entities.

Represents a user's Home Assistant MQTT integration — the per-user
Mosquitto account and the list of enrolled devices to publish.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from .base import AggregateRoot, Entity


@dataclass(kw_only=True)
class MqttIntegration(AggregateRoot):
    """
    A user's Home Assistant MQTT integration.

    One per user.  Holds the per-user Mosquitto credentials and
    top-level settings for the HA publisher.
    """
    user_id: UUID
    ha_username: str               # e.g. "sh_a1b2c3" — unique across the broker
    password_hash: str             # bcrypt hash; the plaintext is shown once on creation
    enabled: bool = True
    publish_interval_seconds: int = 30


@dataclass(kw_only=True)
class MqttIntegrationDevice(Entity):
    """
    A device enrolled in a user's MQTT integration.

    Controls whether System B publishes telemetry for this specific
    device to the HA broker.
    """
    integration_id: UUID
    device_id: UUID
    enabled: bool = True
    enrolled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
