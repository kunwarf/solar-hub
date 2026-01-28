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
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    # Upsert Methods (for Telemetry Sync Pipeline)
    # =========================================================================

    async def upsert_hourly_summary(
        self,
        site_id: UUID,
        device_id: Optional[UUID],
        timestamp_hour: datetime,
        data: Dict[str, Any],
    ) -> None:
        """
        Insert or update an hourly telemetry summary row.

        Uses PostgreSQL ON CONFLICT DO UPDATE for idempotent upserts.
        For site-level rows (device_id=None), uses partial unique index.
        """
        values = {
            "id": uuid4(),
            "site_id": site_id,
            "device_id": device_id,
            "timestamp_hour": timestamp_hour,
            **data,
        }

        stmt = pg_insert(TelemetryHourlySummaryModel).values(**values)

        # Use different conflict targets based on device_id presence
        update_fields = {k: stmt.excluded[k] for k in data.keys()}
        if device_id is not None:
            stmt = stmt.on_conflict_do_update(
                constraint="uq_hourly_site_device_time",
                set_=update_fields,
            )
        else:
            stmt = stmt.on_conflict_do_update(
                index_elements=["site_id", "timestamp_hour"],
                index_where=TelemetryHourlySummaryModel.device_id.is_(None),
                set_=update_fields,
            )

        await self._session.execute(stmt)
        await self._session.flush()

    async def upsert_daily_summary(
        self,
        site_id: UUID,
        device_id: Optional[UUID],
        summary_date: date,
        data: Dict[str, Any],
    ) -> None:
        """
        Insert or update a daily telemetry summary row.

        Uses PostgreSQL ON CONFLICT DO UPDATE for idempotent upserts.
        """
        values = {
            "id": uuid4(),
            "site_id": site_id,
            "device_id": device_id,
            "summary_date": summary_date,
            **data,
        }

        stmt = pg_insert(TelemetryDailySummaryModel).values(**values)

        update_fields = {k: stmt.excluded[k] for k in data.keys()}
        update_fields["updated_at"] = datetime.now(timezone.utc)

        if device_id is not None:
            stmt = stmt.on_conflict_do_update(
                constraint="uq_daily_site_device_date",
                set_=update_fields,
            )
        else:
            stmt = stmt.on_conflict_do_update(
                index_elements=["site_id", "summary_date"],
                index_where=TelemetryDailySummaryModel.device_id.is_(None),
                set_=update_fields,
            )

        await self._session.execute(stmt)
        await self._session.flush()

    async def upsert_monthly_summary(
        self,
        site_id: UUID,
        device_id: Optional[UUID],
        year: int,
        month: int,
        data: Dict[str, Any],
    ) -> None:
        """
        Insert or update a monthly telemetry summary row.

        Uses PostgreSQL ON CONFLICT DO UPDATE for idempotent upserts.
        """
        values = {
            "id": uuid4(),
            "site_id": site_id,
            "device_id": device_id,
            "year": year,
            "month": month,
            **data,
        }

        stmt = pg_insert(TelemetryMonthlySummaryModel).values(**values)

        update_fields = {k: stmt.excluded[k] for k in data.keys()}
        update_fields["updated_at"] = datetime.now(timezone.utc)

        if device_id is not None:
            stmt = stmt.on_conflict_do_update(
                constraint="uq_monthly_site_device_period",
                set_=update_fields,
            )
        else:
            stmt = stmt.on_conflict_do_update(
                index_elements=["site_id", "year", "month"],
                index_where=TelemetryMonthlySummaryModel.device_id.is_(None),
                set_=update_fields,
            )

        await self._session.execute(stmt)
        await self._session.flush()

    async def aggregate_hourly_to_daily(
        self,
        site_id: UUID,
        device_id: Optional[UUID],
        target_date: date,
    ) -> Dict[str, Any]:
        """
        Aggregate hourly summaries into daily values for a specific date.

        Returns a dict suitable for upsert_daily_summary().
        """
        start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)

        conditions = [
            TelemetryHourlySummaryModel.site_id == site_id,
            TelemetryHourlySummaryModel.timestamp_hour >= start_time,
            TelemetryHourlySummaryModel.timestamp_hour < end_time,
        ]
        if device_id is not None:
            conditions.append(TelemetryHourlySummaryModel.device_id == device_id)
        else:
            conditions.append(TelemetryHourlySummaryModel.device_id.is_(None))

        query = select(
            func.coalesce(func.sum(TelemetryHourlySummaryModel.energy_generated_kwh), 0.0).label("energy_generated_kwh"),
            func.coalesce(func.sum(TelemetryHourlySummaryModel.energy_consumed_kwh), 0.0).label("energy_consumed_kwh"),
            func.coalesce(func.sum(TelemetryHourlySummaryModel.energy_exported_kwh), 0.0).label("energy_exported_kwh"),
            func.coalesce(func.sum(TelemetryHourlySummaryModel.energy_imported_kwh), 0.0).label("energy_imported_kwh"),
            func.coalesce(func.sum(TelemetryHourlySummaryModel.energy_stored_kwh), 0.0).label("energy_stored_kwh"),
            func.coalesce(func.sum(TelemetryHourlySummaryModel.energy_discharged_kwh), 0.0).label("energy_discharged_kwh"),
            func.coalesce(func.max(TelemetryHourlySummaryModel.peak_power_kw), 0.0).label("peak_power_kw"),
            func.avg(TelemetryHourlySummaryModel.average_power_kw).label("average_power_kw"),
            func.avg(TelemetryHourlySummaryModel.avg_irradiance_w_m2).label("avg_irradiance_w_m2"),
            func.avg(TelemetryHourlySummaryModel.avg_temperature_c).label("avg_temperature_c"),
            func.max(TelemetryHourlySummaryModel.max_temperature_c).label("max_temperature_c"),
            func.min(TelemetryHourlySummaryModel.min_temperature_c).label("min_temperature_c"),
            func.avg(TelemetryHourlySummaryModel.avg_battery_soc_percent).label("avg_battery_soc_percent"),
            func.avg(TelemetryHourlySummaryModel.avg_grid_voltage_v).label("avg_grid_voltage_v"),
            func.avg(TelemetryHourlySummaryModel.avg_power_factor).label("avg_power_factor"),
            func.coalesce(func.sum(TelemetryHourlySummaryModel.sample_count), 0).label("total_samples"),
            func.count().label("hours_with_data"),
        ).where(and_(*conditions))

        result = await self._session.execute(query)
        row = result.one()

        generated = float(row.energy_generated_kwh)
        consumed = float(row.energy_consumed_kwh)
        exported = float(row.energy_exported_kwh)
        imported = float(row.energy_imported_kwh)
        hours = int(row.hours_with_data)

        return {
            "energy_generated_kwh": generated,
            "energy_consumed_kwh": consumed,
            "energy_exported_kwh": exported,
            "energy_imported_kwh": imported,
            "energy_stored_kwh": float(row.energy_stored_kwh),
            "energy_discharged_kwh": float(row.energy_discharged_kwh),
            "net_energy_kwh": generated - consumed,
            "peak_power_kw": float(row.peak_power_kw),
            "average_power_kw": float(row.average_power_kw or 0.0),
            "sunshine_hours": max(0.0, float(hours)),
            "production_hours": max(0.0, float(hours)),
            "avg_irradiance_w_m2": float(row.avg_irradiance_w_m2) if row.avg_irradiance_w_m2 else None,
            "avg_temperature_c": float(row.avg_temperature_c) if row.avg_temperature_c else None,
            "max_temperature_c": float(row.max_temperature_c) if row.max_temperature_c else None,
            "min_temperature_c": float(row.min_temperature_c) if row.min_temperature_c else None,
            "avg_battery_soc_percent": float(row.avg_battery_soc_percent) if row.avg_battery_soc_percent else None,
            "avg_grid_voltage_v": float(row.avg_grid_voltage_v) if row.avg_grid_voltage_v else None,
            "avg_power_factor": float(row.avg_power_factor) if row.avg_power_factor else None,
            "co2_avoided_kg": generated * 0.475,  # Pakistan grid emission factor
            "estimated_savings_pkr": generated * 25.0,  # Average PKR/kWh rate
            "hours_with_data": hours,
            "data_completeness_percent": (hours / 24.0) * 100.0 if hours > 0 else 0.0,
        }

    async def aggregate_daily_to_monthly(
        self,
        site_id: UUID,
        device_id: Optional[UUID],
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """
        Aggregate daily summaries into monthly values.

        Returns a dict suitable for upsert_monthly_summary().
        """
        # Calculate date range for the month
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        conditions = [
            TelemetryDailySummaryModel.site_id == site_id,
            TelemetryDailySummaryModel.summary_date >= month_start,
            TelemetryDailySummaryModel.summary_date <= month_end,
        ]
        if device_id is not None:
            conditions.append(TelemetryDailySummaryModel.device_id == device_id)
        else:
            conditions.append(TelemetryDailySummaryModel.device_id.is_(None))

        query = select(
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_generated_kwh), 0.0).label("energy_generated_kwh"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_consumed_kwh), 0.0).label("energy_consumed_kwh"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_exported_kwh), 0.0).label("energy_exported_kwh"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_imported_kwh), 0.0).label("energy_imported_kwh"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_stored_kwh), 0.0).label("energy_stored_kwh"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.energy_discharged_kwh), 0.0).label("energy_discharged_kwh"),
            func.coalesce(func.max(TelemetryDailySummaryModel.peak_power_kw), 0.0).label("peak_power_kw"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.sunshine_hours), 0.0).label("total_sunshine_hours"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.production_hours), 0.0).label("total_production_hours"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.grid_outage_minutes), 0).label("total_grid_outage_minutes"),
            func.avg(TelemetryDailySummaryModel.avg_temperature_c).label("avg_temperature_c"),
            func.avg(TelemetryDailySummaryModel.performance_ratio).label("performance_ratio"),
            func.avg(TelemetryDailySummaryModel.capacity_factor).label("capacity_factor"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.co2_avoided_kg), 0.0).label("co2_avoided_kg"),
            func.coalesce(func.sum(TelemetryDailySummaryModel.estimated_savings_pkr), 0.0).label("estimated_savings_pkr"),
            func.count().label("days_with_data"),
        ).where(and_(*conditions))

        result = await self._session.execute(query)
        row = result.one()

        generated = float(row.energy_generated_kwh)
        consumed = float(row.energy_consumed_kwh)
        days = int(row.days_with_data)

        return {
            "energy_generated_kwh": generated,
            "energy_consumed_kwh": consumed,
            "energy_exported_kwh": float(row.energy_exported_kwh),
            "energy_imported_kwh": float(row.energy_imported_kwh),
            "energy_stored_kwh": float(row.energy_stored_kwh),
            "energy_discharged_kwh": float(row.energy_discharged_kwh),
            "net_energy_kwh": generated - consumed,
            "peak_power_kw": float(row.peak_power_kw),
            "average_daily_generation_kwh": generated / days if days > 0 else 0.0,
            "total_sunshine_hours": float(row.total_sunshine_hours),
            "total_production_hours": float(row.total_production_hours),
            "total_grid_outage_minutes": int(row.total_grid_outage_minutes),
            "avg_temperature_c": float(row.avg_temperature_c) if row.avg_temperature_c else None,
            "performance_ratio": float(row.performance_ratio) if row.performance_ratio else None,
            "capacity_factor": float(row.capacity_factor) if row.capacity_factor else None,
            "co2_avoided_kg": float(row.co2_avoided_kg),
            "trees_equivalent": float(row.co2_avoided_kg) / 1000 * 45,  # Trees per ton CO2
            "estimated_revenue_pkr": float(row.estimated_savings_pkr),
            "estimated_savings_pkr": float(row.estimated_savings_pkr),
            "days_with_data": days,
            "data_completeness_percent": (days / month_end.day) * 100.0 if days > 0 else 0.0,
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
