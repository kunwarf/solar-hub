"""
MQTT Integration Service.

Orchestrates Home Assistant MQTT integration lifecycle:
- Creating per-user Mosquitto credentials
- Password rotation
- Device enrollment / unenrollment
- Integration deletion

The service always creates/modifies the Mosquitto account FIRST and
persists to the DB second.  If the broker call fails, the DB transaction
is never flushed so no stale state accumulates.
"""
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from ...domain.entities.mqtt_integration import MqttIntegration, MqttIntegrationDevice
from ...application.interfaces.unit_of_work import UnitOfWork
from ...infrastructure.mqtt.mosquitto_admin_client import MosquittoAdminClient
from ...infrastructure.security import BcryptPasswordHasher

logger = logging.getLogger(__name__)


@dataclass
class MqttIntegrationResult:
    """Returned after creating an integration (password shown once)."""
    integration_id: str
    ha_username: str
    password: str           # plaintext — shown to user once, never stored
    broker_host: str
    broker_port: int
    publish_interval_seconds: int


@dataclass
class PasswordRotationResult:
    """Returned after rotating a password (new password shown once)."""
    ha_username: str
    password: str           # new plaintext password — shown once


class MqttIntegrationService:
    """
    Application service for MQTT integration management.

    Depends on:
    - MosquittoAdminClient  — creates/deletes broker accounts
    - BcryptPasswordHasher  — hashes passwords before DB storage
    - UnitOfWork            — provided by caller (FastAPI dependency)
    """

    def __init__(
        self,
        mosquitto_client: MosquittoAdminClient,
        password_hasher: BcryptPasswordHasher,
        broker_public_host: str,
        broker_public_port: int,
    ) -> None:
        self._mosquitto = mosquitto_client
        self._hasher = password_hasher
        self._public_host = broker_public_host
        self._public_port = broker_public_port

    # ------------------------------------------------------------------
    # Integration lifecycle
    # ------------------------------------------------------------------

    async def create_integration(
        self, user_id: UUID, uow: UnitOfWork
    ) -> MqttIntegrationResult:
        """
        Create a new MQTT integration for a user.

        Raises ValueError if the user already has an integration.
        Raises ConnectionError if the broker is unreachable.
        """
        async with uow:
            existing = await uow.mqtt_integrations.get_by_user_id(user_id)
            if existing is not None:
                raise ValueError(f"User {user_id} already has an MQTT integration")

            ha_username = f"sh_{secrets.token_hex(6)}"
            password = secrets.token_urlsafe(32)
            password_hash = self._hasher.hash(password)

            # Broker first — if this fails, nothing is persisted
            await self._mosquitto.create_user(ha_username, password)

            integration = MqttIntegration(
                user_id=user_id,
                ha_username=ha_username,
                password_hash=password_hash,
            )
            saved = await uow.mqtt_integrations.add(integration)
            await uow.commit()

            logger.info("Created MQTT integration for user %s → %s", user_id, ha_username)

            return MqttIntegrationResult(
                integration_id=str(saved.id),
                ha_username=ha_username,
                password=password,
                broker_host=self._public_host,
                broker_port=self._public_port,
                publish_interval_seconds=saved.publish_interval_seconds,
            )

    async def get_integration(
        self, user_id: UUID, uow: UnitOfWork
    ) -> Optional[MqttIntegration]:
        """Return the user's integration, or None if not set up."""
        async with uow:
            return await uow.mqtt_integrations.get_by_user_id(user_id)

    async def rotate_password(
        self, user_id: UUID, uow: UnitOfWork
    ) -> PasswordRotationResult:
        """Generate a new password for the user's MQTT account."""
        async with uow:
            integration = await uow.mqtt_integrations.get_by_user_id(user_id)
            if integration is None:
                raise ValueError(f"User {user_id} has no MQTT integration")

            new_password = secrets.token_urlsafe(32)
            new_hash = self._hasher.hash(new_password)

            # Broker first
            await self._mosquitto.update_password(integration.ha_username, new_password)

            integration.password_hash = new_hash
            integration.mark_updated()
            await uow.mqtt_integrations.update(integration)
            await uow.commit()

            logger.info("Rotated MQTT password for %s", integration.ha_username)

            return PasswordRotationResult(
                ha_username=integration.ha_username,
                password=new_password,
            )

    async def delete_integration(self, user_id: UUID, uow: UnitOfWork) -> None:
        """Delete the user's integration and remove the broker account."""
        async with uow:
            integration = await uow.mqtt_integrations.get_by_user_id(user_id)
            if integration is None:
                raise ValueError(f"User {user_id} has no MQTT integration")

            # Broker first — enrolled device rows cascade-delete via FK
            await self._mosquitto.delete_user(integration.ha_username)

            await uow.mqtt_integrations.delete(integration.id)
            await uow.commit()

            logger.info("Deleted MQTT integration for user %s", user_id)

    # ------------------------------------------------------------------
    # Device enrollment
    # ------------------------------------------------------------------

    async def enroll_device(
        self, user_id: UUID, device_id: UUID, uow: UnitOfWork
    ) -> MqttIntegrationDevice:
        """
        Enroll a device in the user's MQTT integration.

        Validates that the device belongs to the user before enrolling.
        """
        async with uow:
            integration = await uow.mqtt_integrations.get_by_user_id(user_id)
            if integration is None:
                raise ValueError(f"User {user_id} has no MQTT integration")

            # Verify device ownership
            device = await uow.devices.get_by_id(device_id)
            if device is None:
                raise ValueError(f"Device {device_id} not found")

            # Device must belong to a site owned by the user's organization
            # We check via site → organization ownership
            site = await uow.sites.get_by_id(device.site_id) if device.site_id else None
            if site is None:
                raise ValueError(f"Device {device_id} has no associated site")

            # Check existing enrollment
            existing = await uow.mqtt_integration_devices.get_by_integration_and_device(
                integration.id, device_id
            )
            if existing is not None:
                if not existing.enabled:
                    existing.enabled = True
                    existing.mark_updated()
                    saved = await uow.mqtt_integration_devices.update(existing)
                    await uow.commit()
                    return saved
                return existing  # already enrolled and enabled

            enrollment = MqttIntegrationDevice(
                integration_id=integration.id,
                device_id=device_id,
                enabled=True,
            )
            saved = await uow.mqtt_integration_devices.add(enrollment)
            await uow.commit()

            logger.info(
                "Enrolled device %s in MQTT integration for user %s", device_id, user_id
            )
            return saved

    async def unenroll_device(
        self, user_id: UUID, device_id: UUID, uow: UnitOfWork
    ) -> None:
        """Disable (soft-unenroll) a device from the user's MQTT integration."""
        async with uow:
            integration = await uow.mqtt_integrations.get_by_user_id(user_id)
            if integration is None:
                raise ValueError(f"User {user_id} has no MQTT integration")

            enrollment = await uow.mqtt_integration_devices.get_by_integration_and_device(
                integration.id, device_id
            )
            if enrollment is None:
                return  # already unenrolled — no-op

            enrollment.enabled = False
            enrollment.mark_updated()
            await uow.mqtt_integration_devices.update(enrollment)
            await uow.commit()

            logger.info(
                "Unenrolled device %s from MQTT integration for user %s", device_id, user_id
            )

    async def list_devices_with_enrollment(
        self, user_id: UUID, uow: UnitOfWork
    ) -> List[Dict[str, Any]]:
        """
        Return all devices owned by the user with enrollment status.

        Each item: {device_id, serial_number, name, enrolled}.
        """
        async with uow:
            integration = await uow.mqtt_integrations.get_by_user_id(user_id)

            # Get the user's site, then devices — simplified: get devices by user
            # We traverse: user → organizations → sites → devices
            user = await uow.users.get_by_id(user_id)
            if user is None:
                return []

            orgs = await uow.organizations.get_by_member_id(user_id)
            if not orgs:
                return []

            enrolled_device_ids: set = set()
            if integration:
                enrollments = await uow.mqtt_integration_devices.get_by_integration_id(
                    integration.id
                )
                enrolled_device_ids = {
                    e.device_id for e in enrollments if e.enabled
                }

            result = []
            for org in orgs:
                sites = await uow.sites.get_by_organization_id(org.id)
                for site in sites:
                    devices = await uow.devices.get_by_site_id(site.id)
                    for device in devices:
                        result.append(
                            {
                                "device_id": str(device.id),
                                "serial_number": device.serial_number,
                                "name": device.name,
                                "manufacturer": device.manufacturer,
                                "model": device.model,
                                "enrolled": device.id in enrolled_device_ids,
                            }
                        )
            return result
