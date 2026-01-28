"""
Telemetry Sync Service.

Pulls aggregated telemetry data from System B (TimescaleDB) and
upserts it into System A's summary tables (PostgreSQL).

This service is the bridge between System B's time-series aggregates
and System A's dashboard-oriented summary tables.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from ...infrastructure.external.system_b_client import (
    SystemBClient,
    SystemBClientError,
    TelemetryAggregate,
)
from ...infrastructure.database.repositories.telemetry_repository import (
    SQLAlchemyTelemetryRepository,
)
from ...infrastructure.database.repositories.site_repository import SQLAlchemySiteRepository
from ...infrastructure.database.repositories.device_repository import SQLAlchemyDeviceRepository

logger = logging.getLogger(__name__)

# Key metrics to sync from System B
POWER_METRICS = [
    "pv_power_w",
    "load_power_w",
    "grid_power_w",
    "battery_power_w",
]

ENERGY_METRICS = [
    "energy_today_kwh",
    "energy_import_kwh",
    "energy_export_kwh",
]

ENVIRONMENTAL_METRICS = [
    "battery_soc_pct",
    "grid_voltage_v",
    "grid_frequency_hz",
    "temperature_ambient",
]


@dataclass
class SyncResult:
    """Result of a telemetry sync operation."""
    success: bool = True
    records_upserted: int = 0
    errors: List[str] = field(default_factory=list)


class TelemetrySyncService:
    """
    Coordinates telemetry data sync from System B to System A.

    Pulls aggregated data via SystemBClient and upserts into
    System A's hourly, daily, and monthly summary tables.
    """

    def __init__(
        self,
        system_b_client: SystemBClient,
        telemetry_repository: SQLAlchemyTelemetryRepository,
        site_repository: SQLAlchemySiteRepository,
        device_repository: SQLAlchemyDeviceRepository,
    ):
        self._system_b = system_b_client
        self._telemetry_repo = telemetry_repository
        self._site_repo = site_repository
        self._device_repo = device_repository
        # Cache for serial_number -> System B device_id mapping
        self._device_id_cache: Dict[str, UUID] = {}

    async def _get_system_b_device_id(self, serial_number: str) -> Optional[UUID]:
        """Look up System B device ID by serial number, with caching."""
        if serial_number in self._device_id_cache:
            return self._device_id_cache[serial_number]

        try:
            device_info = await self._system_b.get_device_by_serial(serial_number)
            if device_info:
                self._device_id_cache[serial_number] = device_info.id
                return device_info.id
        except SystemBClientError as e:
            logger.warning("Failed to look up System B device for %s: %s", serial_number, e)

        return None

    # =========================================================================
    # Hourly Sync
    # =========================================================================

    async def sync_hourly_for_site(
        self,
        site_id: UUID,
        hours_back: int = 2,
    ) -> SyncResult:
        """
        Sync hourly aggregates from System B for a site.

        Pulls hourly data for each device, upserts per-device rows,
        then computes and upserts site-level rollup.

        Args:
            site_id: System A site UUID
            hours_back: Number of hours to sync backward from now
        """
        result = SyncResult()
        now = datetime.now(timezone.utc)
        # Align to hour boundaries
        end_time = now.replace(minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=hours_back)

        # Get devices for this site
        devices = await self._device_repo.get_by_site_id(site_id)
        if not devices:
            logger.info("No devices found for site %s, skipping sync", site_id)
            return result

        # Per-hour accumulators for site-level rollup
        # Key: hour timestamp -> accumulated metric values
        site_hourly: Dict[datetime, Dict[str, float]] = {}

        for device in devices:
            sys_b_id = await self._get_system_b_device_id(device.serial_number)
            if not sys_b_id:
                result.errors.append(f"Device {device.serial_number}: not found in System B")
                continue

            try:
                device_hourly = await self._fetch_device_hourly(
                    sys_b_device_id=sys_b_id,
                    start_time=start_time,
                    end_time=end_time,
                )

                for hour_ts, metrics in device_hourly.items():
                    # Upsert per-device hourly row
                    await self._telemetry_repo.upsert_hourly_summary(
                        site_id=site_id,
                        device_id=device.id,
                        timestamp_hour=hour_ts,
                        data=metrics,
                    )
                    result.records_upserted += 1

                    # Accumulate for site-level rollup
                    if hour_ts not in site_hourly:
                        site_hourly[hour_ts] = self._empty_hourly_metrics()
                    self._accumulate_metrics(site_hourly[hour_ts], metrics)

            except SystemBClientError as e:
                error_msg = f"Device {device.serial_number}: System B error: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Upsert site-level rollup (device_id=None)
        for hour_ts, metrics in site_hourly.items():
            await self._telemetry_repo.upsert_hourly_summary(
                site_id=site_id,
                device_id=None,
                timestamp_hour=hour_ts,
                data=metrics,
            )
            result.records_upserted += 1

        if result.errors:
            result.success = len(result.errors) < len(devices)

        logger.info(
            "Hourly sync for site %s: %d records upserted, %d errors",
            site_id, result.records_upserted, len(result.errors),
        )
        return result

    async def _fetch_device_hourly(
        self,
        sys_b_device_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[datetime, Dict[str, Any]]:
        """
        Fetch hourly aggregates for a device from System B.

        Queries multiple metrics and combines them into hourly buckets.
        """
        hourly_data: Dict[datetime, Dict[str, Any]] = {}

        # Fetch power metrics (W) and convert to energy (kWh per hour)
        for metric_name in POWER_METRICS:
            aggregates = await self._system_b.get_device_aggregates(
                device_id=sys_b_device_id,
                metric_name=metric_name,
                start_time=start_time,
                end_time=end_time,
                bucket_interval="1 hour",
            )

            for agg in aggregates:
                if agg.bucket not in hourly_data:
                    hourly_data[agg.bucket] = self._empty_hourly_metrics()

                data = hourly_data[agg.bucket]
                avg_w = agg.avg or 0.0
                energy_kwh = avg_w / 1000.0  # W to kW, and 1 hour bucket

                if metric_name == "pv_power_w":
                    data["energy_generated_kwh"] += energy_kwh
                    data["peak_power_kw"] = max(data["peak_power_kw"], (agg.max or 0.0) / 1000.0)
                    data["average_power_kw"] = avg_w / 1000.0
                elif metric_name == "load_power_w":
                    data["energy_consumed_kwh"] += energy_kwh
                elif metric_name == "grid_power_w":
                    if avg_w > 0:
                        data["energy_imported_kwh"] += energy_kwh
                    else:
                        data["energy_exported_kwh"] += abs(energy_kwh)
                elif metric_name == "battery_power_w":
                    if avg_w > 0:
                        data["energy_stored_kwh"] += energy_kwh
                    else:
                        data["energy_discharged_kwh"] += abs(energy_kwh)

                data["sample_count"] = max(data["sample_count"], agg.sample_count)
                data["data_quality_percent"] = min(
                    data["data_quality_percent"], agg.quality_percent
                )

        # Fetch environmental metrics
        for metric_name in ENVIRONMENTAL_METRICS:
            try:
                aggregates = await self._system_b.get_device_aggregates(
                    device_id=sys_b_device_id,
                    metric_name=metric_name,
                    start_time=start_time,
                    end_time=end_time,
                    bucket_interval="1 hour",
                )

                for agg in aggregates:
                    if agg.bucket not in hourly_data:
                        hourly_data[agg.bucket] = self._empty_hourly_metrics()

                    data = hourly_data[agg.bucket]
                    if metric_name == "battery_soc_pct":
                        data["avg_battery_soc_percent"] = agg.avg
                        data["min_battery_soc_percent"] = agg.min
                        data["max_battery_soc_percent"] = agg.max
                    elif metric_name == "grid_voltage_v":
                        data["avg_grid_voltage_v"] = agg.avg
                    elif metric_name == "grid_frequency_hz":
                        data["avg_grid_frequency_hz"] = agg.avg
                    elif metric_name == "temperature_ambient":
                        data["avg_temperature_c"] = agg.avg
                        data["max_temperature_c"] = agg.max
                        data["min_temperature_c"] = agg.min

            except SystemBClientError:
                # Environmental metrics are optional, skip on error
                pass

        return hourly_data

    @staticmethod
    def _empty_hourly_metrics() -> Dict[str, Any]:
        """Return a zeroed-out hourly metrics dict."""
        return {
            "energy_generated_kwh": 0.0,
            "energy_consumed_kwh": 0.0,
            "energy_exported_kwh": 0.0,
            "energy_imported_kwh": 0.0,
            "energy_stored_kwh": 0.0,
            "energy_discharged_kwh": 0.0,
            "peak_power_kw": 0.0,
            "average_power_kw": 0.0,
            "sample_count": 0,
            "data_quality_percent": 100.0,
        }

    @staticmethod
    def _accumulate_metrics(
        target: Dict[str, Any],
        source: Dict[str, Any],
    ) -> None:
        """Accumulate source metrics into target (for site-level rollup)."""
        additive_keys = [
            "energy_generated_kwh", "energy_consumed_kwh",
            "energy_exported_kwh", "energy_imported_kwh",
            "energy_stored_kwh", "energy_discharged_kwh",
            "average_power_kw",
        ]
        for key in additive_keys:
            target[key] = target.get(key, 0.0) + source.get(key, 0.0)

        # Peak power: take max across devices
        target["peak_power_kw"] = max(
            target.get("peak_power_kw", 0.0),
            source.get("peak_power_kw", 0.0),
        )
        # Sample count: take max
        target["sample_count"] = max(
            target.get("sample_count", 0),
            source.get("sample_count", 0),
        )
        # Quality: take min
        target["data_quality_percent"] = min(
            target.get("data_quality_percent", 100.0),
            source.get("data_quality_percent", 100.0),
        )

    # =========================================================================
    # Daily Sync
    # =========================================================================

    async def sync_daily_for_site(
        self,
        site_id: UUID,
        days_back: int = 1,
    ) -> SyncResult:
        """
        Aggregate hourly summaries into daily summaries for a site.

        Rolls up data already in System A's hourly summary table.
        """
        result = SyncResult()
        today = date.today()

        devices = await self._device_repo.get_by_site_id(site_id)

        for day_offset in range(days_back):
            target_date = today - timedelta(days=day_offset)

            # Aggregate per-device daily summaries
            for device in devices:
                try:
                    daily_data = await self._telemetry_repo.aggregate_hourly_to_daily(
                        site_id=site_id,
                        device_id=device.id,
                        target_date=target_date,
                    )
                    if daily_data.get("hours_with_data", 0) > 0:
                        await self._telemetry_repo.upsert_daily_summary(
                            site_id=site_id,
                            device_id=device.id,
                            summary_date=target_date,
                            data=daily_data,
                        )
                        result.records_upserted += 1
                except Exception as e:
                    error_msg = f"Daily rollup for device {device.serial_number} on {target_date}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            # Aggregate site-level daily summary (from hourly site-level rows)
            try:
                site_daily = await self._telemetry_repo.aggregate_hourly_to_daily(
                    site_id=site_id,
                    device_id=None,
                    target_date=target_date,
                )
                if site_daily.get("hours_with_data", 0) > 0:
                    await self._telemetry_repo.upsert_daily_summary(
                        site_id=site_id,
                        device_id=None,
                        summary_date=target_date,
                        data=site_daily,
                    )
                    result.records_upserted += 1
            except Exception as e:
                error_msg = f"Daily site rollup for {site_id} on {target_date}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        if result.errors:
            result.success = False

        logger.info(
            "Daily sync for site %s: %d records, %d errors",
            site_id, result.records_upserted, len(result.errors),
        )
        return result

    # =========================================================================
    # Monthly Sync
    # =========================================================================

    async def sync_monthly_for_site(
        self,
        site_id: UUID,
        months_back: int = 1,
    ) -> SyncResult:
        """
        Aggregate daily summaries into monthly summaries for a site.

        Rolls up data already in System A's daily summary table.
        """
        result = SyncResult()
        today = date.today()

        devices = await self._device_repo.get_by_site_id(site_id)

        for month_offset in range(months_back):
            # Calculate target month
            target_date = today - timedelta(days=30 * month_offset)
            year = target_date.year
            month = target_date.month

            # Per-device monthly rollup
            for device in devices:
                try:
                    monthly_data = await self._telemetry_repo.aggregate_daily_to_monthly(
                        site_id=site_id,
                        device_id=device.id,
                        year=year,
                        month=month,
                    )
                    if monthly_data.get("days_with_data", 0) > 0:
                        await self._telemetry_repo.upsert_monthly_summary(
                            site_id=site_id,
                            device_id=device.id,
                            year=year,
                            month=month,
                            data=monthly_data,
                        )
                        result.records_upserted += 1
                except Exception as e:
                    error_msg = f"Monthly rollup for device {device.serial_number} {year}-{month}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            # Site-level monthly rollup
            try:
                site_monthly = await self._telemetry_repo.aggregate_daily_to_monthly(
                    site_id=site_id,
                    device_id=None,
                    year=year,
                    month=month,
                )
                if site_monthly.get("days_with_data", 0) > 0:
                    await self._telemetry_repo.upsert_monthly_summary(
                        site_id=site_id,
                        device_id=None,
                        year=year,
                        month=month,
                        data=site_monthly,
                    )
                    result.records_upserted += 1
            except Exception as e:
                error_msg = f"Monthly site rollup for {site_id} {year}-{month}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        if result.errors:
            result.success = False

        logger.info(
            "Monthly sync for site %s: %d records, %d errors",
            site_id, result.records_upserted, len(result.errors),
        )
        return result

    # =========================================================================
    # Sync All Sites
    # =========================================================================

    async def sync_all_sites(
        self,
        site_ids: Optional[List[UUID]] = None,
    ) -> Dict[UUID, SyncResult]:
        """
        Sync hourly data for multiple sites.

        Args:
            site_ids: Specific site IDs to sync. If None, fetches all
                      sites from all organizations.
        """
        results = {}

        if site_ids is None:
            # Get all sites from all organizations via site repository
            all_sites = await self._site_repo.get_by_organization_id(
                organization_id=None,  # type: ignore
                limit=1000,
            )
            site_ids = [s.id for s in all_sites] if all_sites else []

        for sid in site_ids:
            try:
                result = await self.sync_hourly_for_site(sid)
                results[sid] = result
            except Exception as e:
                logger.error("Failed to sync site %s: %s", sid, e)
                results[sid] = SyncResult(
                    success=False,
                    errors=[str(e)],
                )

        return results

    # =========================================================================
    # Backfill
    # =========================================================================

    async def backfill(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
    ) -> SyncResult:
        """
        Backfill historical data for a site from System B.

        Fetches hourly aggregates for the full date range, then
        rolls up to daily and monthly summaries.
        """
        result = SyncResult()

        # Sync hourly data for each day in range
        current = start_date
        while current <= end_date:
            start_time = datetime.combine(current, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = start_time + timedelta(days=1)

            devices = await self._device_repo.get_by_site_id(site_id)
            site_hourly: Dict[datetime, Dict[str, Any]] = {}

            for device in devices:
                sys_b_id = await self._get_system_b_device_id(device.serial_number)
                if not sys_b_id:
                    continue

                try:
                    device_hourly = await self._fetch_device_hourly(
                        sys_b_device_id=sys_b_id,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    for hour_ts, metrics in device_hourly.items():
                        await self._telemetry_repo.upsert_hourly_summary(
                            site_id=site_id,
                            device_id=device.id,
                            timestamp_hour=hour_ts,
                            data=metrics,
                        )
                        result.records_upserted += 1

                        if hour_ts not in site_hourly:
                            site_hourly[hour_ts] = self._empty_hourly_metrics()
                        self._accumulate_metrics(site_hourly[hour_ts], metrics)

                except SystemBClientError as e:
                    result.errors.append(f"Backfill {device.serial_number} {current}: {e}")

            # Site-level rollup for this day
            for hour_ts, metrics in site_hourly.items():
                await self._telemetry_repo.upsert_hourly_summary(
                    site_id=site_id,
                    device_id=None,
                    timestamp_hour=hour_ts,
                    data=metrics,
                )
                result.records_upserted += 1

            current += timedelta(days=1)

        # Roll up to daily and monthly
        daily_result = await self.sync_daily_for_site(
            site_id, days_back=(end_date - start_date).days + 1
        )
        result.records_upserted += daily_result.records_upserted
        result.errors.extend(daily_result.errors)

        monthly_result = await self.sync_monthly_for_site(site_id, months_back=2)
        result.records_upserted += monthly_result.records_upserted
        result.errors.extend(monthly_result.errors)

        if result.errors:
            result.success = False

        logger.info(
            "Backfill for site %s (%s to %s): %d records, %d errors",
            site_id, start_date, end_date, result.records_upserted, len(result.errors),
        )
        return result
