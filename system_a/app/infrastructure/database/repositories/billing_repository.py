"""
SQLAlchemy implementation of BillingRepository.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.billing import (
    TariffPlan,
    TariffRates,
    TariffSlab,
    BillingSimulation,
    BillBreakdown,
    SavingsBreakdown,
    DiscoProvider,
    TariffCategory,
)
from ..models.billing_model import TariffPlanModel, BillingSimulationModel


class SQLAlchemyBillingRepository:
    """SQLAlchemy implementation of billing repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # Tariff Plan Methods
    # =========================================================================

    async def get_tariff_plan_by_id(self, id: UUID) -> Optional[TariffPlan]:
        """Get tariff plan by ID."""
        result = await self._session.execute(
            select(TariffPlanModel).where(TariffPlanModel.id == id)
        )
        model = result.scalar_one_or_none()
        return self._tariff_model_to_domain(model) if model else None

    async def get_active_tariff(
        self,
        disco_provider: str,
        category: str,
        check_date: Optional[date] = None,
    ) -> Optional[TariffPlan]:
        """
        Get active tariff plan for a DISCO and category.

        Returns the most recent active tariff for the given date.
        """
        check_date = check_date or date.today()

        result = await self._session.execute(
            select(TariffPlanModel).where(
                TariffPlanModel.disco_provider == disco_provider,
                TariffPlanModel.category == category,
                TariffPlanModel.effective_from <= check_date,
                (TariffPlanModel.effective_to == None) | (TariffPlanModel.effective_to >= check_date),
            ).order_by(TariffPlanModel.effective_from.desc()).limit(1)
        )
        model = result.scalar_one_or_none()
        return self._tariff_model_to_domain(model) if model else None

    async def list_tariff_plans(
        self,
        disco_provider: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TariffPlan]:
        """List tariff plans with optional filters."""
        query = select(TariffPlanModel)

        if disco_provider:
            query = query.where(TariffPlanModel.disco_provider == disco_provider)
        if category:
            query = query.where(TariffPlanModel.category == category)
        if active_only:
            today = date.today()
            query = query.where(
                TariffPlanModel.effective_from <= today,
                (TariffPlanModel.effective_to == None) | (TariffPlanModel.effective_to >= today),
            )

        query = query.order_by(
            TariffPlanModel.disco_provider,
            TariffPlanModel.category,
            TariffPlanModel.effective_from.desc()
        ).limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._tariff_model_to_domain(m) for m in models]

    async def get_discos_with_tariffs(self) -> List[Dict[str, Any]]:
        """
        Get list of DISCOs with their available tariff categories.

        Returns:
            List of dicts with disco_provider and categories
        """
        today = date.today()
        result = await self._session.execute(
            select(
                TariffPlanModel.disco_provider,
                func.array_agg(func.distinct(TariffPlanModel.category)).label("categories")
            ).where(
                TariffPlanModel.effective_from <= today,
                (TariffPlanModel.effective_to == None) | (TariffPlanModel.effective_to >= today),
            ).group_by(TariffPlanModel.disco_provider)
        )
        rows = result.all()
        return [
            {"disco_provider": row.disco_provider, "categories": row.categories}
            for row in rows
        ]

    async def create_tariff_plan(self, tariff: TariffPlan) -> TariffPlan:
        """Create a new tariff plan."""
        model = self._tariff_domain_to_model(tariff)
        self._session.add(model)
        await self._session.flush()
        return self._tariff_model_to_domain(model)

    async def update_tariff_plan(self, tariff: TariffPlan) -> TariffPlan:
        """Update an existing tariff plan."""
        result = await self._session.execute(
            select(TariffPlanModel).where(TariffPlanModel.id == tariff.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Tariff plan {tariff.id} not found")

        # Update fields
        model.name = tariff.name
        model.description = tariff.description
        model.effective_from = tariff.effective_from
        model.effective_to = tariff.effective_to
        model.rates = self._rates_to_json(tariff.rates)
        model.supports_net_metering = tariff.supports_net_metering
        model.supports_tou = tariff.supports_tou
        model.source_url = tariff.source_url
        model.notes = tariff.notes
        model.version += 1

        await self._session.flush()
        return self._tariff_model_to_domain(model)

    # =========================================================================
    # Billing Simulation Methods
    # =========================================================================

    async def get_simulation_by_id(self, id: UUID) -> Optional[BillingSimulation]:
        """Get billing simulation by ID."""
        result = await self._session.execute(
            select(BillingSimulationModel).where(BillingSimulationModel.id == id)
        )
        model = result.scalar_one_or_none()
        return self._simulation_model_to_domain(model) if model else None

    async def list_simulations_by_site(
        self,
        site_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BillingSimulation]:
        """List billing simulations for a site."""
        query = select(BillingSimulationModel).where(
            BillingSimulationModel.site_id == site_id
        )

        if start_date:
            query = query.where(BillingSimulationModel.period_start >= start_date)
        if end_date:
            query = query.where(BillingSimulationModel.period_end <= end_date)

        query = query.order_by(
            BillingSimulationModel.period_start.desc()
        ).limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._simulation_model_to_domain(m) for m in models]

    async def create_simulation(self, simulation: BillingSimulation) -> BillingSimulation:
        """Create a new billing simulation."""
        model = self._simulation_domain_to_model(simulation)
        self._session.add(model)
        await self._session.flush()
        return self._simulation_model_to_domain(model)

    async def get_simulation_summary(
        self,
        site_id: UUID,
        year: int,
    ) -> Dict[str, Any]:
        """
        Get yearly billing summary for a site.

        Returns aggregated totals for the year.
        """
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        result = await self._session.execute(
            select(
                func.count().label("total_simulations"),
                func.sum(BillingSimulationModel.estimated_bill_pkr).label("total_bills"),
                func.sum(BillingSimulationModel.estimated_savings_pkr).label("total_savings"),
                func.sum(BillingSimulationModel.energy_consumed_kwh).label("total_consumed"),
                func.sum(BillingSimulationModel.energy_generated_kwh).label("total_generated"),
                func.sum(BillingSimulationModel.energy_exported_kwh).label("total_exported"),
            ).where(
                BillingSimulationModel.site_id == site_id,
                BillingSimulationModel.period_start >= start_date,
                BillingSimulationModel.period_end <= end_date,
            )
        )
        row = result.one()

        return {
            "year": year,
            "total_simulations": row.total_simulations or 0,
            "total_bills_pkr": float(row.total_bills or 0),
            "total_savings_pkr": float(row.total_savings or 0),
            "total_consumed_kwh": float(row.total_consumed or 0),
            "total_generated_kwh": float(row.total_generated or 0),
            "total_exported_kwh": float(row.total_exported or 0),
        }

    # =========================================================================
    # Conversion Methods
    # =========================================================================

    def _tariff_model_to_domain(self, model: TariffPlanModel) -> TariffPlan:
        """Convert TariffPlanModel to domain entity."""
        rates_json = model.rates
        rates = self._json_to_rates(rates_json)

        return TariffPlan(
            id=model.id,
            disco_provider=DiscoProvider(model.disco_provider),
            category=TariffCategory(model.category),
            name=model.name,
            description=model.description,
            effective_from=model.effective_from,
            effective_to=model.effective_to,
            rates=rates,
            supports_net_metering=model.supports_net_metering,
            supports_tou=model.supports_tou,
            source_url=model.source_url,
            notes=model.notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _tariff_domain_to_model(self, tariff: TariffPlan) -> TariffPlanModel:
        """Convert domain entity to TariffPlanModel."""
        return TariffPlanModel(
            id=tariff.id,
            disco_provider=tariff.disco_provider.value,
            category=tariff.category.value,
            name=tariff.name,
            description=tariff.description,
            effective_from=tariff.effective_from,
            effective_to=tariff.effective_to,
            rates=self._rates_to_json(tariff.rates),
            supports_net_metering=tariff.supports_net_metering,
            supports_tou=tariff.supports_tou,
            source_url=tariff.source_url,
            notes=tariff.notes,
        )

    def _json_to_rates(self, rates_json: Dict[str, Any]) -> TariffRates:
        """Convert JSON rates to TariffRates object."""
        slabs = []
        for slab_data in rates_json.get("slabs", []):
            slabs.append(TariffSlab(
                min_units=slab_data["min_units"],
                max_units=slab_data.get("max_units"),
                rate_per_kwh=Decimal(str(slab_data["rate_per_kwh"])),
                fixed_charges=Decimal(str(slab_data.get("fixed_charges", "0"))),
            ))

        return TariffRates(
            energy_charge_per_kwh=Decimal(str(rates_json.get("energy_charge_per_kwh", "0"))),
            slabs=slabs,
            peak_rate_per_kwh=Decimal(str(rates_json["peak_rate_per_kwh"])) if rates_json.get("peak_rate_per_kwh") else None,
            off_peak_rate_per_kwh=Decimal(str(rates_json["off_peak_rate_per_kwh"])) if rates_json.get("off_peak_rate_per_kwh") else None,
            fixed_charges_per_month=Decimal(str(rates_json.get("fixed_charges_per_month", "0"))),
            meter_rent=Decimal(str(rates_json.get("meter_rent", "0"))),
            fuel_price_adjustment=Decimal(str(rates_json.get("fuel_price_adjustment", "0"))),
            quarterly_tariff_adjustment=Decimal(str(rates_json.get("quarterly_tariff_adjustment", "0"))),
            electricity_duty_percent=Decimal(str(rates_json.get("electricity_duty_percent", "1.5"))),
            gst_percent=Decimal(str(rates_json.get("gst_percent", "17"))),
            tv_fee=Decimal(str(rates_json.get("tv_fee", "35"))),
            export_rate_per_kwh=Decimal(str(rates_json["export_rate_per_kwh"])) if rates_json.get("export_rate_per_kwh") else None,
            demand_charge_per_kw=Decimal(str(rates_json["demand_charge_per_kw"])) if rates_json.get("demand_charge_per_kw") else None,
        )

    def _rates_to_json(self, rates: TariffRates) -> Dict[str, Any]:
        """Convert TariffRates object to JSON."""
        result = {
            "energy_charge_per_kwh": str(rates.energy_charge_per_kwh),
            "fixed_charges_per_month": str(rates.fixed_charges_per_month),
            "meter_rent": str(rates.meter_rent),
            "fuel_price_adjustment": str(rates.fuel_price_adjustment),
            "quarterly_tariff_adjustment": str(rates.quarterly_tariff_adjustment),
            "electricity_duty_percent": str(rates.electricity_duty_percent),
            "gst_percent": str(rates.gst_percent),
            "tv_fee": str(rates.tv_fee),
        }

        if rates.slabs:
            result["slabs"] = [
                {
                    "min_units": s.min_units,
                    "max_units": s.max_units,
                    "rate_per_kwh": str(s.rate_per_kwh),
                    "fixed_charges": str(s.fixed_charges),
                }
                for s in rates.slabs
            ]

        if rates.peak_rate_per_kwh:
            result["peak_rate_per_kwh"] = str(rates.peak_rate_per_kwh)
        if rates.off_peak_rate_per_kwh:
            result["off_peak_rate_per_kwh"] = str(rates.off_peak_rate_per_kwh)
        if rates.export_rate_per_kwh:
            result["export_rate_per_kwh"] = str(rates.export_rate_per_kwh)
        if rates.demand_charge_per_kw:
            result["demand_charge_per_kw"] = str(rates.demand_charge_per_kw)

        return result

    def _simulation_model_to_domain(self, model: BillingSimulationModel) -> BillingSimulation:
        """Convert BillingSimulationModel to domain entity."""
        bill_json = model.bill_breakdown or {}
        savings_json = model.savings_breakdown or {}

        bill_breakdown = BillBreakdown(
            energy_charges=Decimal(str(bill_json.get("energy_charges", "0"))),
            slab_breakdown=bill_json.get("slab_breakdown", []),
            fixed_charges=Decimal(str(bill_json.get("fixed_charges", "0"))),
            meter_rent=Decimal(str(bill_json.get("meter_rent", "0"))),
            fuel_price_adjustment=Decimal(str(bill_json.get("fuel_price_adjustment", "0"))),
            quarterly_tariff_adjustment=Decimal(str(bill_json.get("quarterly_tariff_adjustment", "0"))),
            electricity_duty=Decimal(str(bill_json.get("electricity_duty", "0"))),
            gst=Decimal(str(bill_json.get("gst", "0"))),
            tv_fee=Decimal(str(bill_json.get("tv_fee", "0"))),
            export_credit=Decimal(str(bill_json.get("export_credit", "0"))),
            demand_charges=Decimal(str(bill_json.get("demand_charges", "0"))),
            subtotal=Decimal(str(bill_json.get("subtotal", "0"))),
            total_taxes=Decimal(str(bill_json.get("total_taxes", "0"))),
            total_bill=Decimal(str(bill_json.get("total_bill", "0"))),
        )

        savings_breakdown = SavingsBreakdown(
            bill_without_solar=Decimal(str(savings_json.get("bill_without_solar", "0"))),
            bill_with_solar=Decimal(str(savings_json.get("bill_with_solar", "0"))),
            total_savings=Decimal(str(savings_json.get("total_savings", "0"))),
            savings_percent=Decimal(str(savings_json.get("savings_percent", "0"))),
            export_income=Decimal(str(savings_json.get("export_income", "0"))),
            co2_avoided_kg=Decimal(str(savings_json.get("co2_avoided_kg", "0"))),
            trees_equivalent=Decimal(str(savings_json.get("trees_equivalent", "0"))),
        )

        return BillingSimulation(
            id=model.id,
            site_id=model.site_id,
            tariff_plan_id=model.tariff_plan_id,
            period_start=model.period_start,
            period_end=model.period_end,
            energy_consumed_kwh=model.energy_consumed_kwh,
            energy_generated_kwh=model.energy_generated_kwh,
            energy_exported_kwh=model.energy_exported_kwh,
            energy_imported_kwh=model.energy_imported_kwh,
            peak_demand_kw=model.peak_demand_kw,
            bill_breakdown=bill_breakdown,
            savings_breakdown=savings_breakdown,
            estimated_bill_pkr=model.estimated_bill_pkr,
            estimated_savings_pkr=model.estimated_savings_pkr,
            is_actual=model.is_actual,
            notes=model.notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _simulation_domain_to_model(self, simulation: BillingSimulation) -> BillingSimulationModel:
        """Convert domain entity to BillingSimulationModel."""
        bill_json = {
            "energy_charges": str(simulation.bill_breakdown.energy_charges),
            "slab_breakdown": simulation.bill_breakdown.slab_breakdown,
            "fixed_charges": str(simulation.bill_breakdown.fixed_charges),
            "meter_rent": str(simulation.bill_breakdown.meter_rent),
            "fuel_price_adjustment": str(simulation.bill_breakdown.fuel_price_adjustment),
            "quarterly_tariff_adjustment": str(simulation.bill_breakdown.quarterly_tariff_adjustment),
            "electricity_duty": str(simulation.bill_breakdown.electricity_duty),
            "gst": str(simulation.bill_breakdown.gst),
            "tv_fee": str(simulation.bill_breakdown.tv_fee),
            "export_credit": str(simulation.bill_breakdown.export_credit),
            "demand_charges": str(simulation.bill_breakdown.demand_charges),
            "subtotal": str(simulation.bill_breakdown.subtotal),
            "total_taxes": str(simulation.bill_breakdown.total_taxes),
            "total_bill": str(simulation.bill_breakdown.total_bill),
        }

        savings_json = {
            "bill_without_solar": str(simulation.savings_breakdown.bill_without_solar),
            "bill_with_solar": str(simulation.savings_breakdown.bill_with_solar),
            "total_savings": str(simulation.savings_breakdown.total_savings),
            "savings_percent": str(simulation.savings_breakdown.savings_percent),
            "export_income": str(simulation.savings_breakdown.export_income),
            "co2_avoided_kg": str(simulation.savings_breakdown.co2_avoided_kg),
            "trees_equivalent": str(simulation.savings_breakdown.trees_equivalent),
        }

        return BillingSimulationModel(
            id=simulation.id,
            site_id=simulation.site_id,
            tariff_plan_id=simulation.tariff_plan_id,
            period_start=simulation.period_start,
            period_end=simulation.period_end,
            energy_consumed_kwh=simulation.energy_consumed_kwh,
            energy_generated_kwh=simulation.energy_generated_kwh,
            energy_exported_kwh=simulation.energy_exported_kwh,
            energy_imported_kwh=simulation.energy_imported_kwh,
            peak_demand_kw=simulation.peak_demand_kw,
            bill_breakdown=bill_json,
            savings_breakdown=savings_json,
            estimated_bill_pkr=simulation.estimated_bill_pkr,
            estimated_savings_pkr=simulation.estimated_savings_pkr,
            is_actual=simulation.is_actual,
            notes=simulation.notes,
        )
