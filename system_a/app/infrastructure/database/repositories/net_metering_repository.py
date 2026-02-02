"""
SQLAlchemy implementation of Net Metering Repository.

Handles CRUD operations for:
- BillingConfig
- BillingCycle
- BillingMonth
- BillingDaily
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import func, select, and_, or_, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.net_metering import (
    BillingConfig,
    BillingCycle,
    BillingMonth,
    DailyBillingSnapshot,
    CreditPool,
    BillingPrices,
    TouConfig,
    TouWindow,
    SurplusDeficitFlag,
    BillingStatus,
    FixedProrationMode,
)
from ..models.net_metering_model import (
    BillingConfigModel,
    BillingCycleModel,
    BillingMonthModel,
    BillingDailyModel,
)


class SQLAlchemyNetMeteringRepository:
    """SQLAlchemy implementation of net metering repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # Billing Config Methods
    # =========================================================================

    async def get_billing_config_by_site(self, site_id: UUID) -> Optional[BillingConfig]:
        """Get billing configuration for a site."""
        result = await self._session.execute(
            select(BillingConfigModel).where(BillingConfigModel.site_id == site_id)
        )
        model = result.scalar_one_or_none()
        return self._config_model_to_domain(model) if model else None

    async def create_billing_config(self, config: BillingConfig) -> BillingConfig:
        """Create billing configuration for a site."""
        model = self._config_domain_to_model(config)
        self._session.add(model)
        await self._session.flush()
        return self._config_model_to_domain(model)

    async def update_billing_config(self, config: BillingConfig) -> BillingConfig:
        """Update billing configuration."""
        result = await self._session.execute(
            select(BillingConfigModel).where(BillingConfigModel.site_id == config.site_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Billing config for site {config.site_id} not found")

        model.anchor_day = config.anchor_day
        model.tou_windows = config.tou_config.to_dict()
        model.fixed_charge_per_billing_month = config.prices.fixed_charge_per_billing_month
        model.price_offpeak_import = config.prices.price_offpeak_import
        model.price_peak_import = config.prices.price_peak_import
        model.price_offpeak_settlement = config.prices.price_offpeak_settlement
        model.price_peak_settlement = config.prices.price_peak_settlement
        model.fixed_proration_mode = config.fixed_proration_mode.value
        model.net_metering_enabled = config.net_metering_enabled
        model.version += 1

        await self._session.flush()
        return self._config_model_to_domain(model)

    async def upsert_billing_config(self, config: BillingConfig) -> BillingConfig:
        """Create or update billing configuration."""
        existing = await self.get_billing_config_by_site(config.site_id)
        if existing:
            return await self.update_billing_config(config)
        else:
            return await self.create_billing_config(config)

    # =========================================================================
    # Billing Cycle Methods
    # =========================================================================

    async def get_billing_cycle_by_id(self, cycle_id: UUID) -> Optional[BillingCycle]:
        """Get billing cycle by ID."""
        result = await self._session.execute(
            select(BillingCycleModel).where(BillingCycleModel.id == cycle_id)
        )
        model = result.scalar_one_or_none()
        return self._cycle_model_to_domain(model) if model else None

    async def get_active_billing_cycle(
        self,
        site_id: UUID,
        target_date: date,
    ) -> Optional[BillingCycle]:
        """Get active billing cycle for a site containing the target date."""
        result = await self._session.execute(
            select(BillingCycleModel).where(
                BillingCycleModel.site_id == site_id,
                BillingCycleModel.cycle_start_date <= target_date,
                BillingCycleModel.cycle_end_date >= target_date,
                BillingCycleModel.status == "active",
            )
        )
        model = result.scalar_one_or_none()
        return self._cycle_model_to_domain(model) if model else None

    async def get_billing_cycle_by_year_number(
        self,
        site_id: UUID,
        year: int,
        cycle_number: int,
    ) -> Optional[BillingCycle]:
        """Get billing cycle by site, year, and cycle number."""
        result = await self._session.execute(
            select(BillingCycleModel).where(
                BillingCycleModel.site_id == site_id,
                BillingCycleModel.year == year,
                BillingCycleModel.cycle_number == cycle_number,
            )
        )
        model = result.scalar_one_or_none()
        return self._cycle_model_to_domain(model) if model else None

    async def list_billing_cycles(
        self,
        site_id: UUID,
        year: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BillingCycle]:
        """List billing cycles for a site."""
        query = select(BillingCycleModel).where(
            BillingCycleModel.site_id == site_id
        )

        if year:
            query = query.where(BillingCycleModel.year == year)
        if status:
            query = query.where(BillingCycleModel.status == status)

        query = query.order_by(
            BillingCycleModel.year.desc(),
            BillingCycleModel.cycle_number.desc(),
        ).limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._cycle_model_to_domain(m) for m in models]

    async def create_billing_cycle(self, cycle: BillingCycle) -> BillingCycle:
        """Create a new billing cycle."""
        model = self._cycle_domain_to_model(cycle)
        self._session.add(model)
        await self._session.flush()
        return self._cycle_model_to_domain(model)

    async def update_billing_cycle(self, cycle: BillingCycle) -> BillingCycle:
        """Update an existing billing cycle."""
        result = await self._session.execute(
            select(BillingCycleModel).where(BillingCycleModel.id == cycle.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Billing cycle {cycle.id} not found")

        # Update all fields
        model.total_import_off_kwh = cycle.total_import_off_kwh
        model.total_export_off_kwh = cycle.total_export_off_kwh
        model.total_import_peak_kwh = cycle.total_import_peak_kwh
        model.total_export_peak_kwh = cycle.total_export_peak_kwh
        model.credits_generated_off_kwh = cycle.credits_generated_off_kwh
        model.credits_consumed_off_kwh = cycle.credits_consumed_off_kwh
        model.credits_generated_peak_kwh = cycle.credits_generated_peak_kwh
        model.credits_consumed_peak_kwh = cycle.credits_consumed_peak_kwh
        model.closing_credit_off_kwh = cycle.closing_credit_off_kwh
        model.closing_credit_peak_kwh = cycle.closing_credit_peak_kwh
        model.settlement_off_rs = cycle.settlement_off_rs
        model.settlement_peak_rs = cycle.settlement_peak_rs
        model.total_settlement_rs = cycle.total_settlement_rs
        model.closing_cash_credit_rs = cycle.closing_cash_credit_rs
        model.status = cycle.status.value
        model.config_hash = cycle.config_hash
        model.finalized_at = cycle.finalized_at
        model.version += 1

        await self._session.flush()
        return self._cycle_model_to_domain(model)

    async def finalize_billing_cycle(self, cycle_id: UUID) -> BillingCycle:
        """Finalize a billing cycle."""
        result = await self._session.execute(
            select(BillingCycleModel).where(BillingCycleModel.id == cycle_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Billing cycle {cycle_id} not found")

        model.status = BillingStatus.FINALIZED.value
        model.finalized_at = datetime.now()
        model.version += 1

        await self._session.flush()
        return self._cycle_model_to_domain(model)

    # =========================================================================
    # Billing Month Methods
    # =========================================================================

    async def get_billing_month_by_id(self, month_id: UUID) -> Optional[BillingMonth]:
        """Get billing month by ID."""
        result = await self._session.execute(
            select(BillingMonthModel).where(BillingMonthModel.id == month_id)
        )
        model = result.scalar_one_or_none()
        return self._month_model_to_domain(model) if model else None

    async def get_billing_month_by_date(
        self,
        site_id: UUID,
        target_date: date,
    ) -> Optional[BillingMonth]:
        """Get billing month containing the target date."""
        result = await self._session.execute(
            select(BillingMonthModel).where(
                BillingMonthModel.site_id == site_id,
                BillingMonthModel.period_start_date <= target_date,
                BillingMonthModel.period_end_date >= target_date,
            )
        )
        model = result.scalar_one_or_none()
        return self._month_model_to_domain(model) if model else None

    async def get_billing_month_by_year_number(
        self,
        site_id: UUID,
        year: int,
        billing_month_number: int,
    ) -> Optional[BillingMonth]:
        """Get billing month by site, year, and month number."""
        result = await self._session.execute(
            select(BillingMonthModel).where(
                BillingMonthModel.site_id == site_id,
                BillingMonthModel.year == year,
                BillingMonthModel.billing_month_number == billing_month_number,
            )
        )
        model = result.scalar_one_or_none()
        return self._month_model_to_domain(model) if model else None

    async def list_billing_months(
        self,
        site_id: UUID,
        year: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 24,
        offset: int = 0,
    ) -> List[BillingMonth]:
        """List billing months for a site."""
        query = select(BillingMonthModel).where(
            BillingMonthModel.site_id == site_id
        )

        if year:
            query = query.where(BillingMonthModel.year == year)
        if status:
            query = query.where(BillingMonthModel.status == status)

        query = query.order_by(
            BillingMonthModel.year.desc(),
            BillingMonthModel.billing_month_number.desc(),
        ).limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._month_model_to_domain(m) for m in models]

    async def create_billing_month(self, month: BillingMonth) -> BillingMonth:
        """Create a new billing month record."""
        model = self._month_domain_to_model(month)
        self._session.add(model)
        await self._session.flush()
        return self._month_model_to_domain(model)

    async def update_billing_month(self, month: BillingMonth) -> BillingMonth:
        """Update an existing billing month."""
        result = await self._session.execute(
            select(BillingMonthModel).where(BillingMonthModel.id == month.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Billing month {month.id} not found")

        # Update all fields
        model.import_off_kwh = month.import_off_kwh
        model.export_off_kwh = month.export_off_kwh
        model.import_peak_kwh = month.import_peak_kwh
        model.export_peak_kwh = month.export_peak_kwh
        model.solar_generation_kwh = month.solar_generation_kwh
        model.load_consumption_kwh = month.load_consumption_kwh
        model.net_import_off_kwh = month.net_import_off_kwh
        model.net_import_peak_kwh = month.net_import_peak_kwh
        model.credits_applied_off_kwh = month.credits_applied_off_kwh
        model.credits_applied_peak_kwh = month.credits_applied_peak_kwh
        model.credits_generated_off_kwh = month.credits_generated_off_kwh
        model.credits_generated_peak_kwh = month.credits_generated_peak_kwh
        model.bill_off_energy_rs = month.bill_off_energy_rs
        model.bill_peak_energy_rs = month.bill_peak_energy_rs
        model.bill_fixed_rs = month.bill_fixed_rs
        model.cycle_settlement_off_rs = month.cycle_settlement_off_rs
        model.cycle_settlement_peak_rs = month.cycle_settlement_peak_rs
        model.bill_raw_rs = month.bill_raw_rs
        model.opening_credit_balance_rs = month.opening_credit_balance_rs
        model.closing_credit_balance_rs = month.closing_credit_balance_rs
        model.bill_final_rs = month.bill_final_rs
        model.status = month.status.value
        model.is_cycle_end_month = month.is_cycle_end_month
        model.config_hash = month.config_hash
        model.finalized_at = month.finalized_at
        model.version += 1

        await self._session.flush()
        return self._month_model_to_domain(model)

    async def finalize_billing_month(self, month_id: UUID) -> BillingMonth:
        """Finalize a billing month."""
        result = await self._session.execute(
            select(BillingMonthModel).where(BillingMonthModel.id == month_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Billing month {month_id} not found")

        model.status = BillingStatus.FINALIZED.value
        model.finalized_at = datetime.now()
        model.version += 1

        await self._session.flush()
        return self._month_model_to_domain(model)

    # =========================================================================
    # Billing Daily Methods
    # =========================================================================

    async def get_daily_snapshot(
        self,
        site_id: UUID,
        target_date: date,
    ) -> Optional[DailyBillingSnapshot]:
        """Get daily billing snapshot for a site and date."""
        result = await self._session.execute(
            select(BillingDailyModel).where(
                BillingDailyModel.site_id == site_id,
                BillingDailyModel.date == target_date,
            )
        )
        model = result.scalar_one_or_none()
        return self._daily_model_to_domain(model) if model else None

    async def get_daily_snapshots_for_period(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[DailyBillingSnapshot]:
        """Get daily snapshots for a date range."""
        result = await self._session.execute(
            select(BillingDailyModel).where(
                BillingDailyModel.site_id == site_id,
                BillingDailyModel.date >= start_date,
                BillingDailyModel.date <= end_date,
            ).order_by(BillingDailyModel.date)
        )
        models = result.scalars().all()
        return [self._daily_model_to_domain(m) for m in models]

    async def get_latest_daily_snapshot(
        self,
        site_id: UUID,
    ) -> Optional[DailyBillingSnapshot]:
        """Get the most recent daily snapshot for a site."""
        result = await self._session.execute(
            select(BillingDailyModel).where(
                BillingDailyModel.site_id == site_id,
            ).order_by(BillingDailyModel.date.desc()).limit(1)
        )
        model = result.scalar_one_or_none()
        return self._daily_model_to_domain(model) if model else None

    async def upsert_daily_snapshot(
        self,
        snapshot: DailyBillingSnapshot,
    ) -> DailyBillingSnapshot:
        """Create or update daily billing snapshot (idempotent)."""
        stmt = insert(BillingDailyModel).values(
            id=snapshot.id,
            site_id=snapshot.site_id,
            date=snapshot.date,
            billing_month_id=snapshot.billing_month_id,
            import_off_kwh=snapshot.import_off_kwh,
            export_off_kwh=snapshot.export_off_kwh,
            import_peak_kwh=snapshot.import_peak_kwh,
            export_peak_kwh=snapshot.export_peak_kwh,
            solar_generation_kwh=snapshot.solar_generation_kwh,
            load_consumption_kwh=snapshot.load_consumption_kwh,
            net_import_off_kwh=snapshot.net_import_off_kwh,
            net_import_peak_kwh=snapshot.net_import_peak_kwh,
            credits_off_cycle_kwh_balance=snapshot.credits_off_cycle_kwh_balance,
            credits_peak_cycle_kwh_balance=snapshot.credits_peak_cycle_kwh_balance,
            bill_off_energy_rs=snapshot.bill_off_energy_rs,
            bill_peak_energy_rs=snapshot.bill_peak_energy_rs,
            fixed_prorated_rs=snapshot.fixed_prorated_rs,
            expected_cycle_credit_rs=snapshot.expected_cycle_credit_rs,
            bill_raw_rs_to_date=snapshot.bill_raw_rs_to_date,
            bill_credit_balance_rs_to_date=snapshot.bill_credit_balance_rs_to_date,
            bill_final_rs_to_date=snapshot.bill_final_rs_to_date,
            surplus_deficit_flag=snapshot.surplus_deficit_flag.value,
            net_kwh_position=snapshot.net_kwh_position,
            days_elapsed=snapshot.days_elapsed,
            total_days_in_month=snapshot.total_days_in_month,
            generated_at=snapshot.generated_at,
        ).on_conflict_do_update(
            index_elements=['site_id', 'date'],
            set_={
                'billing_month_id': snapshot.billing_month_id,
                'import_off_kwh': snapshot.import_off_kwh,
                'export_off_kwh': snapshot.export_off_kwh,
                'import_peak_kwh': snapshot.import_peak_kwh,
                'export_peak_kwh': snapshot.export_peak_kwh,
                'solar_generation_kwh': snapshot.solar_generation_kwh,
                'load_consumption_kwh': snapshot.load_consumption_kwh,
                'net_import_off_kwh': snapshot.net_import_off_kwh,
                'net_import_peak_kwh': snapshot.net_import_peak_kwh,
                'credits_off_cycle_kwh_balance': snapshot.credits_off_cycle_kwh_balance,
                'credits_peak_cycle_kwh_balance': snapshot.credits_peak_cycle_kwh_balance,
                'bill_off_energy_rs': snapshot.bill_off_energy_rs,
                'bill_peak_energy_rs': snapshot.bill_peak_energy_rs,
                'fixed_prorated_rs': snapshot.fixed_prorated_rs,
                'expected_cycle_credit_rs': snapshot.expected_cycle_credit_rs,
                'bill_raw_rs_to_date': snapshot.bill_raw_rs_to_date,
                'bill_credit_balance_rs_to_date': snapshot.bill_credit_balance_rs_to_date,
                'bill_final_rs_to_date': snapshot.bill_final_rs_to_date,
                'surplus_deficit_flag': snapshot.surplus_deficit_flag.value,
                'net_kwh_position': snapshot.net_kwh_position,
                'days_elapsed': snapshot.days_elapsed,
                'total_days_in_month': snapshot.total_days_in_month,
                'generated_at': snapshot.generated_at,
                'updated_at': func.now(),
            }
        )

        await self._session.execute(stmt)
        await self._session.flush()

        return await self.get_daily_snapshot(snapshot.site_id, snapshot.date)

    async def delete_daily_snapshots_for_period(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
    ) -> int:
        """Delete daily snapshots for a date range. Returns count deleted."""
        result = await self._session.execute(
            delete(BillingDailyModel).where(
                BillingDailyModel.site_id == site_id,
                BillingDailyModel.date >= start_date,
                BillingDailyModel.date <= end_date,
            )
        )
        await self._session.flush()
        return result.rowcount

    # =========================================================================
    # Aggregate Queries
    # =========================================================================

    async def get_yearly_billing_summary(
        self,
        site_id: UUID,
        year: int,
    ) -> Dict[str, Any]:
        """Get yearly billing summary for a site."""
        result = await self._session.execute(
            select(
                func.count().label("total_months"),
                func.sum(BillingMonthModel.bill_final_rs).label("total_bill"),
                func.sum(BillingMonthModel.import_off_kwh + BillingMonthModel.import_peak_kwh).label("total_import"),
                func.sum(BillingMonthModel.export_off_kwh + BillingMonthModel.export_peak_kwh).label("total_export"),
                func.sum(BillingMonthModel.solar_generation_kwh).label("total_solar"),
                func.sum(BillingMonthModel.load_consumption_kwh).label("total_load"),
            ).where(
                BillingMonthModel.site_id == site_id,
                BillingMonthModel.year == year,
            )
        )
        row = result.one()

        return {
            "year": year,
            "total_months": row.total_months or 0,
            "total_bill_rs": float(row.total_bill or 0),
            "total_import_kwh": float(row.total_import or 0),
            "total_export_kwh": float(row.total_export or 0),
            "total_solar_kwh": float(row.total_solar or 0),
            "total_load_kwh": float(row.total_load or 0),
        }

    async def get_billing_trend(
        self,
        site_id: UUID,
        months: int = 12,
    ) -> List[Dict[str, Any]]:
        """Get billing trend for the last N months."""
        result = await self._session.execute(
            select(BillingMonthModel).where(
                BillingMonthModel.site_id == site_id,
            ).order_by(
                BillingMonthModel.year.desc(),
                BillingMonthModel.billing_month_number.desc(),
            ).limit(months)
        )
        models = result.scalars().all()

        return [
            {
                "year": m.year,
                "month": m.billing_month_number,
                "period_start": m.period_start_date.isoformat(),
                "period_end": m.period_end_date.isoformat(),
                "import_off_kwh": float(m.import_off_kwh),
                "import_peak_kwh": float(m.import_peak_kwh),
                "export_off_kwh": float(m.export_off_kwh),
                "export_peak_kwh": float(m.export_peak_kwh),
                "bill_final_rs": float(m.bill_final_rs),
                "status": m.status,
            }
            for m in models
        ]

    # =========================================================================
    # Conversion Methods
    # =========================================================================

    def _config_model_to_domain(self, model: BillingConfigModel) -> BillingConfig:
        """Convert BillingConfigModel to domain entity."""
        tou_config = TouConfig.from_dict(model.tou_windows)

        prices = BillingPrices(
            price_offpeak_import=model.price_offpeak_import,
            price_peak_import=model.price_peak_import,
            price_offpeak_settlement=model.price_offpeak_settlement,
            price_peak_settlement=model.price_peak_settlement,
            fixed_charge_per_billing_month=model.fixed_charge_per_billing_month,
        )

        return BillingConfig(
            id=model.id,
            site_id=model.site_id,
            anchor_day=model.anchor_day,
            tou_config=tou_config,
            prices=prices,
            fixed_proration_mode=FixedProrationMode(model.fixed_proration_mode),
            net_metering_enabled=model.net_metering_enabled,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _config_domain_to_model(self, config: BillingConfig) -> BillingConfigModel:
        """Convert domain entity to BillingConfigModel."""
        return BillingConfigModel(
            id=config.id,
            site_id=config.site_id,
            anchor_day=config.anchor_day,
            tou_windows=config.tou_config.to_dict(),
            fixed_charge_per_billing_month=config.prices.fixed_charge_per_billing_month,
            price_offpeak_import=config.prices.price_offpeak_import,
            price_peak_import=config.prices.price_peak_import,
            price_offpeak_settlement=config.prices.price_offpeak_settlement,
            price_peak_settlement=config.prices.price_peak_settlement,
            fixed_proration_mode=config.fixed_proration_mode.value,
            net_metering_enabled=config.net_metering_enabled,
        )

    def _cycle_model_to_domain(self, model: BillingCycleModel) -> BillingCycle:
        """Convert BillingCycleModel to domain entity."""
        return BillingCycle(
            id=model.id,
            site_id=model.site_id,
            cycle_number=model.cycle_number,
            year=model.year,
            cycle_start_date=model.cycle_start_date,
            cycle_end_date=model.cycle_end_date,
            opening_credit_off_kwh=model.opening_credit_off_kwh,
            opening_credit_peak_kwh=model.opening_credit_peak_kwh,
            opening_cash_credit_rs=model.opening_cash_credit_rs,
            total_import_off_kwh=model.total_import_off_kwh,
            total_export_off_kwh=model.total_export_off_kwh,
            total_import_peak_kwh=model.total_import_peak_kwh,
            total_export_peak_kwh=model.total_export_peak_kwh,
            credits_generated_off_kwh=model.credits_generated_off_kwh,
            credits_consumed_off_kwh=model.credits_consumed_off_kwh,
            credits_generated_peak_kwh=model.credits_generated_peak_kwh,
            credits_consumed_peak_kwh=model.credits_consumed_peak_kwh,
            closing_credit_off_kwh=model.closing_credit_off_kwh,
            closing_credit_peak_kwh=model.closing_credit_peak_kwh,
            settlement_off_rs=model.settlement_off_rs,
            settlement_peak_rs=model.settlement_peak_rs,
            total_settlement_rs=model.total_settlement_rs,
            closing_cash_credit_rs=model.closing_cash_credit_rs,
            status=BillingStatus(model.status),
            config_hash=model.config_hash,
            finalized_at=model.finalized_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _cycle_domain_to_model(self, cycle: BillingCycle) -> BillingCycleModel:
        """Convert domain entity to BillingCycleModel."""
        return BillingCycleModel(
            id=cycle.id,
            site_id=cycle.site_id,
            cycle_number=cycle.cycle_number,
            year=cycle.year,
            cycle_start_date=cycle.cycle_start_date,
            cycle_end_date=cycle.cycle_end_date,
            opening_credit_off_kwh=cycle.opening_credit_off_kwh,
            opening_credit_peak_kwh=cycle.opening_credit_peak_kwh,
            opening_cash_credit_rs=cycle.opening_cash_credit_rs,
            total_import_off_kwh=cycle.total_import_off_kwh,
            total_export_off_kwh=cycle.total_export_off_kwh,
            total_import_peak_kwh=cycle.total_import_peak_kwh,
            total_export_peak_kwh=cycle.total_export_peak_kwh,
            credits_generated_off_kwh=cycle.credits_generated_off_kwh,
            credits_consumed_off_kwh=cycle.credits_consumed_off_kwh,
            credits_generated_peak_kwh=cycle.credits_generated_peak_kwh,
            credits_consumed_peak_kwh=cycle.credits_consumed_peak_kwh,
            closing_credit_off_kwh=cycle.closing_credit_off_kwh,
            closing_credit_peak_kwh=cycle.closing_credit_peak_kwh,
            settlement_off_rs=cycle.settlement_off_rs,
            settlement_peak_rs=cycle.settlement_peak_rs,
            total_settlement_rs=cycle.total_settlement_rs,
            closing_cash_credit_rs=cycle.closing_cash_credit_rs,
            status=cycle.status.value,
            config_hash=cycle.config_hash,
            finalized_at=cycle.finalized_at,
        )

    def _month_model_to_domain(self, model: BillingMonthModel) -> BillingMonth:
        """Convert BillingMonthModel to domain entity."""
        return BillingMonth(
            id=model.id,
            site_id=model.site_id,
            billing_cycle_id=model.billing_cycle_id,
            billing_month_number=model.billing_month_number,
            year=model.year,
            period_start_date=model.period_start_date,
            period_end_date=model.period_end_date,
            import_off_kwh=model.import_off_kwh,
            export_off_kwh=model.export_off_kwh,
            import_peak_kwh=model.import_peak_kwh,
            export_peak_kwh=model.export_peak_kwh,
            solar_generation_kwh=model.solar_generation_kwh,
            load_consumption_kwh=model.load_consumption_kwh,
            net_import_off_kwh=model.net_import_off_kwh,
            net_import_peak_kwh=model.net_import_peak_kwh,
            credits_applied_off_kwh=model.credits_applied_off_kwh,
            credits_applied_peak_kwh=model.credits_applied_peak_kwh,
            credits_generated_off_kwh=model.credits_generated_off_kwh,
            credits_generated_peak_kwh=model.credits_generated_peak_kwh,
            bill_off_energy_rs=model.bill_off_energy_rs,
            bill_peak_energy_rs=model.bill_peak_energy_rs,
            bill_fixed_rs=model.bill_fixed_rs,
            cycle_settlement_off_rs=model.cycle_settlement_off_rs,
            cycle_settlement_peak_rs=model.cycle_settlement_peak_rs,
            bill_raw_rs=model.bill_raw_rs,
            opening_credit_balance_rs=model.opening_credit_balance_rs,
            closing_credit_balance_rs=model.closing_credit_balance_rs,
            bill_final_rs=model.bill_final_rs,
            status=BillingStatus(model.status),
            is_cycle_end_month=model.is_cycle_end_month,
            config_hash=model.config_hash,
            finalized_at=model.finalized_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _month_domain_to_model(self, month: BillingMonth) -> BillingMonthModel:
        """Convert domain entity to BillingMonthModel."""
        return BillingMonthModel(
            id=month.id,
            site_id=month.site_id,
            billing_cycle_id=month.billing_cycle_id,
            billing_month_number=month.billing_month_number,
            year=month.year,
            period_start_date=month.period_start_date,
            period_end_date=month.period_end_date,
            import_off_kwh=month.import_off_kwh,
            export_off_kwh=month.export_off_kwh,
            import_peak_kwh=month.import_peak_kwh,
            export_peak_kwh=month.export_peak_kwh,
            solar_generation_kwh=month.solar_generation_kwh,
            load_consumption_kwh=month.load_consumption_kwh,
            net_import_off_kwh=month.net_import_off_kwh,
            net_import_peak_kwh=month.net_import_peak_kwh,
            credits_applied_off_kwh=month.credits_applied_off_kwh,
            credits_applied_peak_kwh=month.credits_applied_peak_kwh,
            credits_generated_off_kwh=month.credits_generated_off_kwh,
            credits_generated_peak_kwh=month.credits_generated_peak_kwh,
            bill_off_energy_rs=month.bill_off_energy_rs,
            bill_peak_energy_rs=month.bill_peak_energy_rs,
            bill_fixed_rs=month.bill_fixed_rs,
            cycle_settlement_off_rs=month.cycle_settlement_off_rs,
            cycle_settlement_peak_rs=month.cycle_settlement_peak_rs,
            bill_raw_rs=month.bill_raw_rs,
            opening_credit_balance_rs=month.opening_credit_balance_rs,
            closing_credit_balance_rs=month.closing_credit_balance_rs,
            bill_final_rs=month.bill_final_rs,
            status=month.status.value,
            is_cycle_end_month=month.is_cycle_end_month,
            config_hash=month.config_hash,
            finalized_at=month.finalized_at,
        )

    def _daily_model_to_domain(self, model: BillingDailyModel) -> DailyBillingSnapshot:
        """Convert BillingDailyModel to domain entity."""
        return DailyBillingSnapshot(
            id=model.id,
            site_id=model.site_id,
            date=model.date,
            billing_month_id=model.billing_month_id,
            import_off_kwh=model.import_off_kwh,
            export_off_kwh=model.export_off_kwh,
            import_peak_kwh=model.import_peak_kwh,
            export_peak_kwh=model.export_peak_kwh,
            solar_generation_kwh=model.solar_generation_kwh,
            load_consumption_kwh=model.load_consumption_kwh,
            net_import_off_kwh=model.net_import_off_kwh,
            net_import_peak_kwh=model.net_import_peak_kwh,
            credits_off_cycle_kwh_balance=model.credits_off_cycle_kwh_balance,
            credits_peak_cycle_kwh_balance=model.credits_peak_cycle_kwh_balance,
            bill_off_energy_rs=model.bill_off_energy_rs,
            bill_peak_energy_rs=model.bill_peak_energy_rs,
            fixed_prorated_rs=model.fixed_prorated_rs,
            expected_cycle_credit_rs=model.expected_cycle_credit_rs,
            bill_raw_rs_to_date=model.bill_raw_rs_to_date,
            bill_credit_balance_rs_to_date=model.bill_credit_balance_rs_to_date,
            bill_final_rs_to_date=model.bill_final_rs_to_date,
            surplus_deficit_flag=SurplusDeficitFlag(model.surplus_deficit_flag),
            net_kwh_position=model.net_kwh_position,
            days_elapsed=model.days_elapsed,
            total_days_in_month=model.total_days_in_month,
            generated_at=model.generated_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
