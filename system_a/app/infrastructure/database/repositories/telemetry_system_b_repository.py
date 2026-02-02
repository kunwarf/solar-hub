"""
Repository adapter for querying telemetry data from System B.

This adapter implements the same interface as SQLAlchemyTelemetryRepository
but queries System B's TimescaleDB via HTTP API instead of System A's PostgreSQL.
"""
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from ...external.system_b_client import SystemBClient, SystemBClientError
from ..models.telemetry_model import TelemetryHourlySummaryModel

logger = logging.getLogger(__name__)


class SystemBTelemetryRepository:
    """
    Repository adapter for System B telemetry data.

    Provides the same interface as SQLAlchemyTelemetryRepository but
    fetches data from System B's TimescaleDB continuous aggregates
    via HTTP API.

    This enables the billing module to transparently switch between
    System A (PostgreSQL) and System B (TimescaleDB) data sources.
    """

    def __init__(self, system_b_client: SystemBClient):
        """
        Initialize repository with System B client.

        Args:
            system_b_client: HTTP client for System B API
        """
        self._client = system_b_client

    async def get_hourly_summaries(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        device_id: Optional[UUID] = None,
    ) -> List[TelemetryHourlySummaryModel]:
        """
        Get hourly telemetry summaries for a site from System B.

        Args:
            site_id: Site UUID
            start_time: Start of time range (inclusive)
            end_time: End of time range (exclusive)
            device_id: Optional device filter (not supported in System B - site-level only)

        Returns:
            List of TelemetryHourlySummaryModel objects compatible with System A

        Raises:
            SystemBClientError: On API errors or connection failures
        """
        if device_id is not None:
            logger.warning(
                "Device-level filtering not supported in System B adapter. "
                "Fetching site-level data for site_id=%s",
                site_id
            )

        logger.info(
            "Fetching hourly summaries from System B: site=%s, start=%s, end=%s",
            site_id, start_time, end_time
        )

        try:
            # Fetch hourly energy data from System B
            data_points = await self._client.get_hourly_energy_summary(
                site_id=site_id,
                start_time=start_time,
                end_time=end_time,
            )

            # Map System B response to System A domain models
            summaries = []
            for point in data_points:
                summary = self._map_to_hourly_summary_model(
                    site_id=site_id,
                    device_id=None,  # System B returns site-level aggregates
                    data_point=point,
                )
                summaries.append(summary)

            logger.info(
                "Retrieved %d hourly summaries from System B for site %s",
                len(summaries), site_id
            )

            return summaries

        except SystemBClientError as e:
            logger.error(
                "Failed to fetch hourly summaries from System B: %s",
                e, exc_info=True
            )
            raise

    def _map_to_hourly_summary_model(
        self,
        site_id: UUID,
        device_id: Optional[UUID],
        data_point: dict,
    ) -> TelemetryHourlySummaryModel:
        """
        Map System B energy chart data point to System A hourly summary model.

        System B returns:
            - timestamp: ISO datetime string
            - pv_kwh: float (solar generation)
            - load_kwh: float (consumption)
            - grid_import_kwh: float
            - grid_export_kwh: float
            - battery_charge_kwh: float (optional)
            - battery_discharge_kwh: float (optional)

        System A expects:
            - timestamp_hour: datetime
            - energy_generated_kwh: Decimal
            - energy_consumed_kwh: Decimal
            - energy_imported_kwh: Decimal
            - energy_exported_kwh: Decimal
            - energy_stored_kwh: Decimal
            - energy_discharged_kwh: Decimal

        Args:
            site_id: Site UUID
            device_id: Device UUID (None for site-level)
            data_point: Dict from System B API

        Returns:
            TelemetryHourlySummaryModel compatible with System A
        """
        # Parse timestamp - handle both string and datetime objects
        timestamp = data_point["timestamp"]
        if isinstance(timestamp, str):
            timestamp_hour = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            timestamp_hour = timestamp

        # Ensure timezone-aware
        if timestamp_hour.tzinfo is None:
            timestamp_hour = timestamp_hour.replace(tzinfo=timezone.utc)

        # Map energy fields with proper type conversion (float -> Decimal)
        # System B uses kWh values, System A also uses kWh, so no unit conversion
        model = TelemetryHourlySummaryModel(
            site_id=site_id,
            device_id=device_id,
            timestamp_hour=timestamp_hour,
            energy_generated_kwh=Decimal(str(data_point.get("pv_kwh", 0.0))),
            energy_consumed_kwh=Decimal(str(data_point.get("load_kwh", 0.0))),
            energy_imported_kwh=Decimal(str(data_point.get("grid_import_kwh", 0.0))),
            energy_exported_kwh=Decimal(str(data_point.get("grid_export_kwh", 0.0))),
            energy_stored_kwh=Decimal(str(data_point.get("battery_charge_kwh", 0.0))),
            energy_discharged_kwh=Decimal(str(data_point.get("battery_discharge_kwh", 0.0))),
            # Optional fields - System B may not provide these
            peak_power_kw=None,
            average_power_kw=None,
            avg_irradiance_w_m2=None,
            avg_temperature_c=data_point.get("temperature_c"),
            max_temperature_c=None,
            min_temperature_c=None,
            avg_battery_soc_percent=None,
            avg_grid_voltage_v=None,
            avg_power_factor=None,
            sample_count=1,  # System B aggregates don't expose sample count
        )

        return model

    async def close(self) -> None:
        """
        Close the underlying HTTP client.

        Called during cleanup to release resources.
        """
        await self._client.close()

    # =========================================================================
    # Optional: Other repository methods (if needed by billing)
    # =========================================================================

    async def get_daily_summaries(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
        device_id: Optional[UUID] = None,
    ):
        """
        Get daily summaries from System B.

        Not currently used by billing module, but included for completeness.
        """
        logger.warning(
            "get_daily_summaries() called on SystemBTelemetryRepository. "
            "This method is not fully implemented yet."
        )
        # TODO: Implement if needed for other modules
        return []
