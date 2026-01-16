"""
SQLAlchemy repository for telemetry data.

Queries aggregated telemetry summaries stored in System A.
Raw telemetry data is stored in System B (TimescaleDB).
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.telemetry_model import (
    TelemetryHourlySummaryModel,
    TelemetryDailySummaryModel,
    TelemetryMonthlySummaryModel,
    DeviceTelemetrySnapshotModel,
)

logger = logging.getLogger(__name__)


@dataclass
class SiteEnergyTotals:
    """Aggregated energy totals for a site."""
    site_id: UUID
    energy_generated_kwh: float
    energy_consumed_kwh: float
    energy_exported_kwh: float
    energy_imported_kwh: float
    peak_power_kw: float
    co2_avoided_kg: float
    estimated_savings_pkr: float


@dataclass
class OrgEnergyTotals:
    """Aggregated energy totals for an organization."""
    organization_id: UUID
    total_energy_generated_kwh: float
    total_energy_consumed_kwh: float
    total_energy_exported_kwh: float
    total_energy_imported_kwh: float
    total_current_power_kw: float
    site_count: int


@dataclass
class DailySummary:
    """Daily energy summary."""
    date: date
    energy_generated_kwh: float
    energy_consumed_kwh: float
    energy_exported_kwh: float
    energy_imported_kwh: float
    peak_power_kw: float
    peak_power_time: Optional[datetime]
    sunshine_hours: float
    performance_ratio: Optional[float]
    co2_avoided_kg: float


@dataclass
class MonthlySummary:
    """Monthly energy summary."""
    year: int
    month: int
    energy_generated_kwh: float
    energy_consumed_kwh: float
    energy_exported_kwh: float
    energy_imported_kwh: float
    avg_daily_generation_kwh: float
    peak_power_kw: float
    days_with_data: int
    performance_ratio: Optional[float]
    co2_avoided_kg: float


@dataclass
class DeviceSnapshot:
    """Current device telemetry snapshot."""
    device_id: UUID
    site_id: UUID
    timestamp: datetime
    current_power_kw: float
    energy_today_kwh: float
    energy_lifetime_kwh: float
    dc_voltage_v: Optional[float]
    dc_current_a: Optional[float]
    ac_voltage_v: Optional[float]
    ac_current_a: Optional[float]
    ac_frequency_hz: Optional[float]
    internal_temperature_c: Optional[float]
    battery_soc_percent: Optional[float]
    battery_power_kw: Optional[float]
    grid_import_power_kw: Optional[float]
    grid_export_power_kw: Optional[float]
    irradiance_w_m2: Optional[float]
    operating_state: Optional[str]
    error_code: Optional[str]


class SQLAlchemyTelemetryRepository:
    """
    Repository for querying telemetry summary data.

    This repository works with pre-aggregated data from System B.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # Device Snapshots (Real-time data)
    # =========================================================================

    async def get_device_snapshots(self, site_id: UUID) -> List[DeviceSnapshot]:
        """Get latest telemetry snapshots for all devices at a site."""
        query = (
            select(DeviceTelemetrySnapshotModel)
            .where(DeviceTelemetrySnapshotModel.site_id == site_id)
            .order_by(desc(DeviceTelemetrySnapshotModel.timestamp))
        )
        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._snapshot_to_dataclass(m) for m in models]

    async def get_device_snapshot(self, device_id: UUID) -> Optional[DeviceSnapshot]:
        """Get latest snapshot for a specific device."""
        query = select(DeviceTelemetrySnapshotModel).where(
            DeviceTelemetrySnapshotModel.device_id == device_id
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._snapshot_to_dataclass(model) if model else None

    async def get_site_current_power(self, site_id: UUID) -> float:
        """Get total current power for a site from device snapshots."""
        query = select(
            func.coalesce(func.sum(DeviceTelemetrySnapshotModel.current_power_kw), 0.0)
        ).where(
            and_(
                DeviceTelemetrySnapshotModel.site_id == site_id,
                DeviceTelemetrySnapshotModel.timestamp >= datetime.now(timezone.utc) - timedelta(minutes=5),
            )
        )
        result = await self._session.execute(query)
        return float(result.scalar() or 0.0)

    async def get_org_current_power(
        self,
        site_ids: List[UUID],
    ) -> float:
        """Get total current power across multiple sites."""
        if not site_ids:
            return 0.0

        query = select(
            func.coalesce(func.sum(DeviceTelemetrySnapshotModel.current_power_kw), 0.0)
        ).where(
            and_(
                DeviceTelemetrySnapshotModel.site_id.in_(site_ids),
                DeviceTelemetrySnapshotModel.timestamp >= datetime.now(timezone.utc) - timedelta(minutes=5),
            )
        )
        result = await self._session.execute(query)
        return float(result.scalar() or 0.0)

    # =========================================================================
    # Hourly Summaries
    # =========================================================================

    async def get_hourly_summaries(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        device_id: Optional[UUID] = None,
    ) -> List[TelemetryHourlySummaryModel]:
        """Get hourly summaries for a site within a time range."""
        conditions = [
            TelemetryHourlySummaryModel.site_id == site_id,
            TelemetryHourlySummaryModel.timestamp_hour >= start_time,
            TelemetryHourlySummaryModel.timestamp_hour < end_time,
        ]

        if device_id:
            conditions.append(TelemetryHourlySummaryModel.device_id == device_id)
        else:
            # Get site-level summaries (device_id is null)
            conditions.append(TelemetryHourlySummaryModel.device_id.is_(None))

        query = (
            select(TelemetryHourlySummaryModel)
            .where(and_(*conditions))
            .order_by(TelemetryHourlySummaryModel.timestamp_hour)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # Daily Summaries
    # =========================================================================

    async def get_daily_summaries(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
        device_id: Optional[UUID] = None,
    ) -> List[DailySummary]:
        """Get daily summaries for a site within a date range."""
        conditions = [
            TelemetryDailySummaryModel.site_id == site_id,
            TelemetryDailySummaryModel.summary_date >= start_date,
            TelemetryDailySummaryModel.summary_date <= end_date,
        ]

        if device_id:
            conditions.append(TelemetryDailySummaryModel.device_id == device_id)
        else:
            conditions.append(TelemetryDailySummaryModel.device_id.is_(None))

        query = (
            select(TelemetryDailySummaryModel)
            .where(and_(*conditions))
            .order_by(TelemetryDailySummaryModel.summary_date)
        )
        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._daily_to_dataclass(m) for m in models]

    async def get_today_energy(self, site_id: UUID) -> Dict[str, float]:
        """Get today's energy totals for a site."""
        today = date.today()
        query = select(TelemetryDailySummaryModel).where(
            and_(
                TelemetryDailySummaryModel.site_id == site_id,
                TelemetryDailySummaryModel.summary_date == today,
                TelemetryDailySummaryModel.device_id.is_(None),
            )
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        if model:
            return {
                "energy_generated_kwh": model.energy_generated_kwh,
                "energy_consumed_kwh": model.energy_consumed_kwh,
                "energy_exported_kwh": model.energy_exported_kwh,
                "energy_imported_kwh": model.energy_imported_kwh,
                "peak_power_kw": model.peak_power_kw,
            }
        return {
            "energy_generated_kwh": 0.0,
            "energy_consumed_kwh": 0.0,
            "energy_exported_kwh": 0.0,
            "energy_imported_kwh": 0.0,
            "peak_power_kw": 0.0,
        }

    # =========================================================================
    # Monthly Summaries
    # =========================================================================

    async def get_monthly_summaries(
        self,
        site_id: UUID,
        year: int,
        device_id: Optional[UUID] = None,
    ) -> List[MonthlySummary]:
        """Get all monthly summaries for a site for a given year."""
        conditions = [
            TelemetryMonthlySummaryModel.site_id == site_id,
            TelemetryMonthlySummaryModel.year == year,
        ]

        if device_id:
            conditions.append(TelemetryMonthlySummaryModel.device_id == device_id)
        else:
            conditions.append(TelemetryMonthlySummaryModel.device_id.is_(None))

        query = (
            select(TelemetryMonthlySummaryModel)
            .where(and_(*conditions))
            .order_by(TelemetryMonthlySummaryModel.month)
        )
        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._monthly_to_dataclass(m) for m in models]

    async def get_monthly_summary(
        self,
        site_id: UUID,
        year: int,
        month: int,
    ) -> Optional[MonthlySummary]:
        """Get a specific monthly summary for a site."""
        query = select(TelemetryMonthlySummaryModel).where(
            and_(
                TelemetryMonthlySummaryModel.site_id == site_id,
                TelemetryMonthlySummaryModel.year == year,
                TelemetryMonthlySummaryModel.month == month,
                TelemetryMonthlySummaryModel.device_id.is_(None),
            )
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._monthly_to_dataclass(model) if model else None

    async def get_this_month_energy(self, site_id: UUID) -> float:
        """Get total energy generated this month."""
        today = date.today()
        summary = await self.get_monthly_summary(site_id, today.year, today.month)
        return summary.energy_generated_kwh if summary else 0.0

    # =========================================================================
    # Aggregations
    # =========================================================================

    async def aggregate_site_totals(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
    ) -> SiteEnergyTotals:
        """Aggregate energy totals for a site over a date range."""
        query = select(
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_generated_kwh), 0.0).label("generated"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_consumed_kwh), 0.0).label("consumed"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_exported_kwh), 0.0).label("exported"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_imported_kwh), 0.0).label("imported"),
            func.coalesce(func.max(TelemetryDailySummaryModel.peak_power_kw), 0.0).label("peak"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.co2_avoided_kg), 0.0).label("co2"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.estimated_savings_pkr), 0.0).label("savings"),
        ).where(
            and_(
                TelemetryDailySummaryModel.site_id == site_id,
                TelemetryDailySummaryModel.summary_date >= start_date,
                TelemetryDailySummaryModel.summary_date <= end_date,
                TelemetryDailySummaryModel.device_id.is_(None),
            )
        )
        result = await self._session.execute(query)
        row = result.one()

        return SiteEnergyTotals(
            site_id=site_id,
            energy_generated_kwh=float(row.generated),
            energy_consumed_kwh=float(row.consumed),
            energy_exported_kwh=float(row.exported),
            energy_imported_kwh=float(row.imported),
            peak_power_kw=float(row.peak),
            co2_avoided_kg=float(row.co2),
            estimated_savings_pkr=float(row.savings),
        )

    async def aggregate_org_totals(
        self,
        site_ids: List[UUID],
    ) -> Dict[str, float]:
        """Aggregate today's energy totals across multiple sites."""
        if not site_ids:
            return {
                "energy_today_kwh": 0.0,
                "energy_month_kwh": 0.0,
                "current_power_kw": 0.0,
            }

        today = date.today()

        # Today's energy
        daily_query = select(
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_generated_kwh), 0.0)
        ).where(
            and_(
                TelemetryDailySummaryModel.site_id.in_(site_ids),
                TelemetryDailySummaryModel.summary_date == today,
                TelemetryDailySummaryModel.device_id.is_(None),
            )
        )
        daily_result = await self._session.execute(daily_query)
        energy_today = float(daily_result.scalar() or 0.0)

        # This month's energy
        monthly_query = select(
            func.coalesce(func.sum(TelemetryMonthlySummaryModel.energy_generated_kwh), 0.0)
        ).where(
            and_(
                TelemetryMonthlySummaryModel.site_id.in_(site_ids),
                TelemetryMonthlySummaryModel.year == today.year,
                TelemetryMonthlySummaryModel.month == today.month,
                TelemetryMonthlySummaryModel.device_id.is_(None),
            )
        )
        monthly_result = await self._session.execute(monthly_query)
        energy_month = float(monthly_result.scalar() or 0.0)

        # Current power from snapshots
        current_power = await self.get_org_current_power(site_ids)

        return {
            "energy_today_kwh": energy_today,
            "energy_month_kwh": energy_month,
            "current_power_kw": current_power,
        }

    async def get_lifetime_energy(self, site_id: UUID) -> float:
        """Get total lifetime energy generated for a site."""
        query = select(
            func.coalesce(func.sum(TelemetryMonthlySummaryModel.energy_generated_kwh), 0.0)
        ).where(
            and_(
                TelemetryMonthlySummaryModel.site_id == site_id,
                TelemetryMonthlySummaryModel.device_id.is_(None),
            )
        )
        result = await self._session.execute(query)
        return float(result.scalar() or 0.0)

    # =========================================================================
    # Performance Metrics
    # =========================================================================

    async def get_site_performance_metrics(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Get performance metrics for a site."""
        query = select(
            func.avg(TelemetryDailySummaryModel.performance_ratio).label("avg_pr"),
            func.avg(TelemetryDailySummaryModel.capacity_factor).label("avg_cf"),
            func.sum(TelemetryDailySummaryModel.sunshine_hours).label("total_sunshine"),
            func.sum(TelemetryDailySummaryModel.production_hours).label("total_production"),
            func.sum(TelemetryDailySummaryModel.grid_outage_minutes).label("total_outage"),
        ).where(
            and_(
                TelemetryDailySummaryModel.site_id == site_id,
                TelemetryDailySummaryModel.summary_date >= start_date,
                TelemetryDailySummaryModel.summary_date <= end_date,
                TelemetryDailySummaryModel.device_id.is_(None),
            )
        )
        result = await self._session.execute(query)
        row = result.one()

        return {
            "avg_performance_ratio": float(row.avg_pr) if row.avg_pr else None,
            "avg_capacity_factor": float(row.avg_cf) if row.avg_cf else None,
            "total_sunshine_hours": float(row.total_sunshine) if row.total_sunshine else 0.0,
            "total_production_hours": float(row.total_production) if row.total_production else 0.0,
            "total_grid_outage_minutes": int(row.total_outage) if row.total_outage else 0,
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _snapshot_to_dataclass(self, model: DeviceTelemetrySnapshotModel) -> DeviceSnapshot:
        """Convert snapshot model to dataclass."""
        return DeviceSnapshot(
            device_id=model.device_id,
            site_id=model.site_id,
            timestamp=model.timestamp,
            current_power_kw=model.current_power_kw,
            energy_today_kwh=model.energy_today_kwh,
            energy_lifetime_kwh=model.energy_lifetime_kwh,
            dc_voltage_v=model.dc_voltage_v,
            dc_current_a=model.dc_current_a,
            ac_voltage_v=model.ac_voltage_v,
            ac_current_a=model.ac_current_a,
            ac_frequency_hz=model.ac_frequency_hz,
            internal_temperature_c=model.internal_temperature_c,
            battery_soc_percent=model.battery_soc_percent,
            battery_power_kw=model.battery_power_kw,
            grid_import_power_kw=model.grid_import_power_kw,
            grid_export_power_kw=model.grid_export_power_kw,
            irradiance_w_m2=model.irradiance_w_m2,
            operating_state=model.operating_state,
            error_code=model.error_code,
        )

    def _daily_to_dataclass(self, model: TelemetryDailySummaryModel) -> DailySummary:
        """Convert daily summary model to dataclass."""
        return DailySummary(
            date=model.summary_date,
            energy_generated_kwh=model.energy_generated_kwh,
            energy_consumed_kwh=model.energy_consumed_kwh,
            energy_exported_kwh=model.energy_exported_kwh,
            energy_imported_kwh=model.energy_imported_kwh,
            peak_power_kw=model.peak_power_kw,
            peak_power_time=model.peak_power_time,
            sunshine_hours=model.sunshine_hours,
            performance_ratio=model.performance_ratio,
            co2_avoided_kg=model.co2_avoided_kg,
        )

    def _monthly_to_dataclass(self, model: TelemetryMonthlySummaryModel) -> MonthlySummary:
        """Convert monthly summary model to dataclass."""
        return MonthlySummary(
            year=model.year,
            month=model.month,
            energy_generated_kwh=model.energy_generated_kwh,
            energy_consumed_kwh=model.energy_consumed_kwh,
            energy_exported_kwh=model.energy_exported_kwh,
            energy_imported_kwh=model.energy_imported_kwh,
            avg_daily_generation_kwh=model.average_daily_generation_kwh,
            peak_power_kw=model.peak_power_kw,
            days_with_data=model.days_with_data,
            performance_ratio=model.performance_ratio,
            co2_avoided_kg=model.co2_avoided_kg,
        )
