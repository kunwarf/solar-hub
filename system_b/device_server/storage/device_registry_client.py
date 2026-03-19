"""
Device Registry Client for the Device Server.

Provides async database access to query the device registry
for linking Modbus-identified devices with self-registered data loggers.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ..config import DeviceServerSettings, get_device_server_settings

logger = logging.getLogger(__name__)


class DeviceRegistryClient:
    """
    Async client for querying the device registry database.

    Used by the device server to link Modbus-identified devices
    (with inverter serial) back to self-registered data loggers
    (with data logger serial).
    """

    def __init__(self, settings: Optional[DeviceServerSettings] = None):
        self.settings = settings or get_device_server_settings()
        self._engine = None
        self._session_factory = None

    async def connect(self) -> None:
        """Connect to the device registry database."""
        db_url = self.settings.device_registry_db.url
        logger.info(f"Connecting to device registry database at {self.settings.device_registry_db.host}")

        self._engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )

        self._session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Test connection
        try:
            async with self._engine.begin():
                pass
            logger.info("Device registry database connected")
        except Exception as e:
            logger.error(f"Failed to connect to device registry database: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Device registry database disconnected")

    async def get_recently_connected_serial(
        self,
        device_type: str,
        within_minutes: int = 10,
    ) -> Optional[str]:
        """
        Find the data logger serial for a recently connected device.

        When a data logger connects via TCP and is identified via Modbus,
        we need to find its original self-registration serial (printed on device)
        to use for telemetry caching.

        Args:
            device_type: Device type from Modbus identification (e.g., "inverter").
            within_minutes: Look for devices connected within this time window.

        Returns:
            The data logger serial number if found, None otherwise.
        """
        if not self._session_factory:
            logger.warning("Device registry client not connected")
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)

        try:
            async with self._session_factory() as session:
                # Query for recently connected device of matching type
                # Uses last_connected_at to match devices that just reconnected
                # Does not filter by status - works for both orphan and claimed devices
                result = await session.execute(
                    text("""
                    SELECT serial_number
                    FROM device_registry
                    WHERE device_type = CAST(:device_type AS text)
                      AND last_connected_at >= CAST(:cutoff AS timestamptz)
                      AND (metadata IS NULL OR metadata->>'inverter_serial' IS NULL)
                    ORDER BY last_connected_at DESC
                    LIMIT 1
                    """),
                    {"device_type": device_type, "cutoff": cutoff},
                )
                row = result.fetchone()

                if row:
                    serial = row[0]
                    logger.debug(f"Found data logger serial for {device_type}: {serial}")
                    return serial

                logger.debug(f"No recently connected device found for type {device_type}")
                return None

        except Exception as e:
            logger.error(f"Error querying device registry: {e}")
            return None

    async def update_inverter_serial(
        self,
        data_logger_serial: str,
        inverter_serial: str,
    ) -> bool:
        """
        Update device metadata with the Modbus-identified inverter serial.

        Args:
            data_logger_serial: The data logger serial (from self-registration).
            inverter_serial: The inverter serial (from Modbus identification).

        Returns:
            True if updated, False otherwise.
        """
        if not self._session_factory:
            logger.warning("Device registry client not connected")
            return False

        try:
            async with self._session_factory() as session:
                # Update metadata with inverter serial
                result = await session.execute(
                    text("""
                    UPDATE device_registry
                    SET metadata = CASE
                            WHEN metadata IS NULL OR jsonb_typeof(metadata) != 'object'
                            THEN jsonb_build_object('inverter_serial', CAST(:inverter_serial AS text))
                            ELSE metadata || jsonb_build_object('inverter_serial', CAST(:inverter_serial AS text))
                        END,
                        updated_at = CAST(:now AS timestamptz)
                    WHERE serial_number = CAST(:data_logger_serial AS text)
                    """),
                    {
                        "data_logger_serial": data_logger_serial,
                        "inverter_serial": inverter_serial,
                        "now": datetime.now(timezone.utc),
                    },
                )
                await session.commit()

                if result.rowcount > 0:
                    logger.info(
                        f"Updated device {data_logger_serial} with inverter serial {inverter_serial}"
                    )
                    return True

                return False

        except Exception as e:
            logger.error(f"Error updating device registry: {e}")
            return False

    async def get_device_by_inverter_serial(
        self,
        inverter_serial: str,
    ) -> Optional[str]:
        """
        Find data logger serial by inverter serial.

        Used when a device reconnects and we need to find its data logger serial.

        Args:
            inverter_serial: The Modbus-identified inverter serial.

        Returns:
            The data logger serial if found, None otherwise.
        """
        if not self._session_factory:
            return None

        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    text("""
                    SELECT serial_number
                    FROM device_registry
                    WHERE metadata->>'inverter_serial' = CAST(:inverter_serial AS text)
                    LIMIT 1
                    """),
                    {"inverter_serial": inverter_serial},
                )
                row = result.fetchone()

                if row:
                    return row[0]

                return None

        except Exception as e:
            logger.error(f"Error querying by inverter serial: {e}")
            return None

    async def get_registration_by_serial(
        self,
        serial_number: str,
    ) -> Optional[dict]:
        """
        Get full registration info for a serial bridge HELLO identification.

        Returns device_type, manufacturer, model, firmware_version, and the
        optional protocol_id stored in metadata (set during self-registration).

        Args:
            serial_number: The data logger serial number from the HELLO frame.

        Returns:
            Dict with registration fields, or None if not found.
        """
        if not self._session_factory:
            logger.warning("Device registry client not connected")
            return None

        try:
            async with self._session_factory() as session:
                # Only select columns that definitely exist in all schema versions.
                # manufacturer/model/firmware_version were added in migration 0003 and
                # may be absent on older deployments — a missing column would silently
                # cause the whole query to fail and return None, breaking HELLO lookup.
                result = await session.execute(
                    text("""
                    SELECT device_type, protocol
                    FROM device_registry
                    WHERE serial_number = CAST(:serial_number AS text)
                    LIMIT 1
                    """),
                    {"serial_number": serial_number},
                )
                row = result.fetchone()

                if not row:
                    logger.debug(
                        f"No registration found for serial {serial_number}"
                    )
                    return None

                device_type, protocol_id = row
                logger.debug(
                    f"Registration for {serial_number}: device_type={device_type!r}, "
                    f"protocol={protocol_id!r}"
                )

                return {
                    "device_type": device_type,
                    "protocol_id": protocol_id,
                }

        except Exception as e:
            logger.error(f"Error querying registration for {serial_number}: {e}")
            return None

    async def get_device_by_serial(
        self,
        serial_number: str,
    ) -> Optional[dict]:
        """
        Get device info (device_id, site_id) by serial number.

        Used to get the data logger's device_id for telemetry writes.

        Args:
            serial_number: The device serial number.

        Returns:
            Dict with device_id and site_id if found, None otherwise.
        """
        if not self._session_factory:
            return None

        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    text("""
                    SELECT device_id, site_id
                    FROM device_registry
                    WHERE serial_number = :serial_number
                    LIMIT 1
                    """),
                    {"serial_number": serial_number},
                )
                row = result.fetchone()

                if row:
                    return {
                        "device_id": row[0],
                        "site_id": row[1]
                    }

                return None

        except Exception as e:
            logger.error(f"Error querying device by serial: {e}")
            return None
