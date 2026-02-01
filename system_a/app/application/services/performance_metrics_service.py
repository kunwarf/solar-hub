"""
Performance Metrics Calculation Service

Calculates and stores derived performance metrics like:
- Inverter efficiency
- Self-sufficiency (energy independence)
- Performance ratio
- Capacity factor

These metrics are calculated from raw telemetry data and stored
in hourly/daily summary tables for efficient querying.
"""
import logging
from datetime import datetime, timedelta, timezone, date as date_type
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.database.models.telemetry_model import (
    TelemetryHourlySummaryModel,
    TelemetryDailySummaryModel,
)

logger = logging.getLogger(__name__)


class PerformanceMetricsService:
    """Service for calculating and storing performance metrics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def calculate_efficiency(
        energy_generated_kwh: float,
        energy_consumed_kwh: float,
        energy_exported_kwh: float,
        energy_stored_kwh: float,
    ) -> Optional[float]:
        """
        Calculate inverter efficiency.

        Efficiency = (AC Output / DC Input) × 100
        Where:
        - DC Input = PV energy generated
        - AC Output = Energy consumed + exported + stored in battery

        Args:
            energy_generated_kwh: Total PV energy generated (DC input)
            energy_consumed_kwh: Energy consumed by loads
            energy_exported_kwh: Energy exported to grid
            energy_stored_kwh: Energy stored in battery

        Returns:
            Efficiency percentage (0-100) or None if cannot calculate
        """
        if energy_generated_kwh <= 0:
            return None

        # AC output is everything that left the inverter
        ac_output_kwh = energy_consumed_kwh + energy_exported_kwh + energy_stored_kwh

        # Efficiency = (AC / DC) × 100
        efficiency = (ac_output_kwh / energy_generated_kwh) * 100

        # Clamp to reasonable range (inverters can't exceed 100% efficiency)
        # If >100%, it means battery is discharging or there's measurement error
        efficiency = min(efficiency, 100.0)

        return round(efficiency, 2)

    @staticmethod
    def calculate_self_sufficiency(
        energy_consumed_kwh: float,
        energy_imported_kwh: float,
    ) -> Optional[float]:
        """
        Calculate self-sufficiency (energy independence).

        Self-Sufficiency = ((Load - Grid Import) / Load) × 100
        Or equivalently: (1 - (Grid Import / Load)) × 100

        This shows what percentage of consumed energy came from
        solar/battery rather than the grid.

        Args:
            energy_consumed_kwh: Total energy consumed by loads
            energy_imported_kwh: Energy imported from grid

        Returns:
            Self-sufficiency percentage (0-100) or None if cannot calculate

        Examples:
            - Load=10kWh, Import=2kWh -> 80% (80% from solar, 20% from grid)
            - Load=10kWh, Import=0kWh -> 100% (fully self-sufficient)
            - Load=10kWh, Import=10kWh -> 0% (all from grid)
        """
        if energy_consumed_kwh <= 0:
            return None

        # Self-sufficiency = how much we DIDN'T need from the grid
        self_sufficiency = (1 - (energy_imported_kwh / energy_consumed_kwh)) * 100

        # Clamp to 0-100 range
        self_sufficiency = max(0.0, min(self_sufficiency, 100.0))

        return round(self_sufficiency, 2)

    async def calculate_hourly_metrics(
        self,
        site_id: Optional[UUID] = None,
        device_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Calculate and update efficiency and self-sufficiency for hourly summaries.

        Args:
            site_id: Optional site filter
            device_id: Optional device filter
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Number of records updated
        """
        # Build query
        query = select(TelemetryHourlySummaryModel)

        if site_id:
            query = query.where(TelemetryHourlySummaryModel.site_id == site_id)
        if device_id:
            query = query.where(TelemetryHourlySummaryModel.device_id == device_id)
        if start_time:
            query = query.where(TelemetryHourlySummaryModel.timestamp_hour >= start_time)
        if end_time:
            query = query.where(TelemetryHourlySummaryModel.timestamp_hour < end_time)

        result = await self.session.execute(query)
        records = result.scalars().all()

        updated_count = 0
        for record in records:
            # Calculate efficiency
            efficiency = self.calculate_efficiency(
                energy_generated_kwh=record.energy_generated_kwh,
                energy_consumed_kwh=record.energy_consumed_kwh,
                energy_exported_kwh=record.energy_exported_kwh,
                energy_stored_kwh=record.energy_stored_kwh,
            )

            # Calculate self-sufficiency
            self_sufficiency = self.calculate_self_sufficiency(
                energy_consumed_kwh=record.energy_consumed_kwh,
                energy_imported_kwh=record.energy_imported_kwh,
            )

            # Update if calculated
            if efficiency is not None or self_sufficiency is not None:
                record.efficiency_pct = efficiency
                record.self_sufficiency_pct = self_sufficiency
                updated_count += 1

        await self.session.flush()
        logger.info(f"Updated {updated_count} hourly records with performance metrics")
        return updated_count

    async def calculate_daily_metrics(
        self,
        site_id: Optional[UUID] = None,
        device_id: Optional[UUID] = None,
        start_date: Optional[date_type] = None,
        end_date: Optional[date_type] = None,
    ) -> int:
        """
        Calculate and update efficiency and self-sufficiency for daily summaries.

        Args:
            site_id: Optional site filter
            device_id: Optional device filter
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Number of records updated
        """
        # Build query
        query = select(TelemetryDailySummaryModel)

        if site_id:
            query = query.where(TelemetryDailySummaryModel.site_id == site_id)
        if device_id:
            query = query.where(TelemetryDailySummaryModel.device_id == device_id)
        if start_date:
            query = query.where(TelemetryDailySummaryModel.summary_date >= start_date)
        if end_date:
            query = query.where(TelemetryDailySummaryModel.summary_date < end_date)

        result = await self.session.execute(query)
        records = result.scalars().all()

        updated_count = 0
        for record in records:
            # Calculate efficiency
            efficiency = self.calculate_efficiency(
                energy_generated_kwh=record.energy_generated_kwh,
                energy_consumed_kwh=record.energy_consumed_kwh,
                energy_exported_kwh=record.energy_exported_kwh,
                energy_stored_kwh=record.energy_stored_kwh,
            )

            # Calculate self-sufficiency
            self_sufficiency = self.calculate_self_sufficiency(
                energy_consumed_kwh=record.energy_consumed_kwh,
                energy_imported_kwh=record.energy_imported_kwh,
            )

            # Update if calculated
            if efficiency is not None or self_sufficiency is not None:
                record.efficiency_pct = efficiency
                record.self_sufficiency_pct = self_sufficiency
                updated_count += 1

        await self.session.flush()
        logger.info(f"Updated {updated_count} daily records with performance metrics")
        return updated_count

    async def calculate_previous_day_metrics(
        self,
        site_id: Optional[UUID] = None,
    ) -> dict:
        """
        Calculate metrics for the previous day.

        This is meant to be called daily (e.g., at midnight or 1am)
        to calculate yesterday's performance metrics.

        Args:
            site_id: Optional site filter

        Returns:
            Dictionary with counts of updated records
        """
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        yesterday_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
        yesterday_end = yesterday_start + timedelta(days=1)

        # Calculate hourly metrics for yesterday
        hourly_count = await self.calculate_hourly_metrics(
            site_id=site_id,
            start_time=yesterday_start,
            end_time=yesterday_end,
        )

        # Calculate daily metric for yesterday
        daily_count = await self.calculate_daily_metrics(
            site_id=site_id,
            start_date=yesterday,
            end_date=yesterday + timedelta(days=1),
        )

        await self.session.commit()

        result = {
            "date": yesterday.isoformat(),
            "hourly_records_updated": hourly_count,
            "daily_records_updated": daily_count,
        }

        logger.info(f"Calculated previous day metrics: {result}")
        return result

    async def backfill_metrics(
        self,
        days: int = 30,
        site_id: Optional[UUID] = None,
    ) -> dict:
        """
        Backfill performance metrics for historical data.

        Useful for calculating metrics on existing data that
        was created before this feature was implemented.

        Args:
            days: Number of days to backfill
            site_id: Optional site filter

        Returns:
            Dictionary with counts of updated records
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        # Calculate hourly metrics
        hourly_count = await self.calculate_hourly_metrics(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Calculate daily metrics
        daily_count = await self.calculate_daily_metrics(
            site_id=site_id,
            start_date=start_date,
            end_date=end_date,
        )

        await self.session.commit()

        result = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days_backfilled": days,
            "hourly_records_updated": hourly_count,
            "daily_records_updated": daily_count,
        }

        logger.info(f"Backfilled metrics: {result}")
        return result
