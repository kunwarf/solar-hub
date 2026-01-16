"""
Billing Calculator Domain Service.

Calculates electricity bills based on Pakistan DISCO tariff structures.
Supports slab-based, flat-rate, and time-of-use tariffs.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple

from ..entities.billing import (
    TariffPlan,
    TariffRates,
    TariffSlab,
    EnergyConsumption,
    BillBreakdown,
    SavingsBreakdown,
)


class BillingCalculator:
    """
    Pure domain service for calculating electricity bills.

    Implements Pakistan DISCO billing logic including:
    - Slab-based progressive tariffs
    - Flat rate tariffs
    - Time-of-use (TOU) tariffs
    - Fuel Price Adjustment (FPA)
    - Quarterly Tariff Adjustment (QTA)
    - Electricity Duty, GST, and TV fee
    - Net metering export credits
    - Demand charges for industrial consumers
    """

    # Constants for environmental impact calculations
    CO2_KG_PER_KWH = Decimal("0.7")  # kg CO2 per kWh (Pakistan grid average)
    TREES_PER_TON_CO2 = Decimal("40")  # Trees needed to absorb 1 ton CO2/year

    def calculate_bill(
        self,
        consumption: EnergyConsumption,
        tariff: TariffPlan,
    ) -> BillBreakdown:
        """
        Calculate complete electricity bill.

        Args:
            consumption: Energy consumption data for the period
            tariff: Applicable tariff plan

        Returns:
            BillBreakdown with all charges and totals
        """
        breakdown = BillBreakdown()
        rates = tariff.rates

        # Step 1: Calculate energy charges
        if rates.is_slab_based():
            energy_charges, slab_breakdown = self._calculate_slab_charges(
                units=int(consumption.net_consumed_kwh),
                slabs=rates.slabs,
            )
            breakdown.energy_charges = energy_charges
            breakdown.slab_breakdown = slab_breakdown
        elif rates.is_tou_based():
            breakdown.energy_charges = self._calculate_tou_charges(
                peak_kwh=consumption.peak_consumed_kwh or Decimal("0"),
                off_peak_kwh=consumption.off_peak_consumed_kwh or Decimal("0"),
                rates=rates,
            )
        else:
            # Flat rate
            breakdown.energy_charges = (
                consumption.net_consumed_kwh * rates.energy_charge_per_kwh
            )

        # Step 2: Fixed charges and meter rent
        breakdown.fixed_charges = rates.fixed_charges_per_month
        breakdown.meter_rent = rates.meter_rent

        # Step 3: Surcharges (FPA and QTA)
        breakdown.fuel_price_adjustment = (
            consumption.net_consumed_kwh * rates.fuel_price_adjustment
        )
        breakdown.quarterly_tariff_adjustment = (
            consumption.net_consumed_kwh * rates.quarterly_tariff_adjustment
        )

        # Step 4: Demand charges (for industrial consumers)
        if consumption.peak_demand_kw and rates.demand_charge_per_kw:
            breakdown.demand_charges = (
                consumption.peak_demand_kw * rates.demand_charge_per_kw
            )

        # Step 5: Calculate taxes
        tax_breakdown = self._calculate_taxes(
            energy_charges=breakdown.energy_charges,
            surcharges=breakdown.fuel_price_adjustment + breakdown.quarterly_tariff_adjustment,
            fixed_charges=breakdown.fixed_charges + breakdown.meter_rent,
            demand_charges=breakdown.demand_charges,
            rates=rates,
        )
        breakdown.electricity_duty = tax_breakdown["electricity_duty"]
        breakdown.gst = tax_breakdown["gst"]
        breakdown.tv_fee = tax_breakdown["tv_fee"]

        # Step 6: Net metering export credit
        if consumption.total_exported_kwh > 0 and rates.export_rate_per_kwh:
            breakdown.export_credit = self._calculate_net_metering_credit(
                exported_kwh=consumption.total_exported_kwh,
                export_rate=rates.export_rate_per_kwh,
            )

        # Step 7: Calculate totals
        breakdown.calculate_totals()

        return breakdown

    def _calculate_slab_charges(
        self,
        units: int,
        slabs: List[TariffSlab],
    ) -> Tuple[Decimal, List[Dict[str, Any]]]:
        """
        Calculate energy charges using progressive slab rates.

        Pakistan residential tariffs use progressive slabs where
        higher consumption attracts higher rates.

        Args:
            units: Total units consumed (kWh)
            slabs: List of tariff slabs sorted by min_units

        Returns:
            Tuple of (total_charges, slab_breakdown)
        """
        total_charges = Decimal("0")
        slab_breakdown = []
        remaining_units = units

        # Sort slabs by min_units
        sorted_slabs = sorted(slabs, key=lambda s: s.min_units)

        for slab in sorted_slabs:
            if remaining_units <= 0:
                break

            # Calculate units in this slab
            slab_max = slab.max_units or float('inf')
            slab_range = int(slab_max - slab.min_units) if slab.max_units else remaining_units

            units_in_slab = min(remaining_units, slab_range + 1) if slab.min_units == 0 else min(remaining_units, slab_range)

            if units >= slab.min_units:
                # Calculate if total consumption falls within this slab's eligibility
                slab_charges = slab.calculate_cost(units_in_slab)
                total_charges += slab_charges

                slab_breakdown.append({
                    "slab": f"{slab.min_units}-{slab.max_units or 'above'}",
                    "units": units_in_slab,
                    "rate": float(slab.rate_per_kwh),
                    "amount": float(slab_charges),
                })

                remaining_units -= units_in_slab

        # Add fixed charges from applicable slab
        for slab in reversed(sorted_slabs):
            if slab.applies_to(units) and slab.fixed_charges > 0:
                total_charges += slab.fixed_charges
                slab_breakdown.append({
                    "slab": "fixed",
                    "description": f"Fixed charges for {slab.min_units}-{slab.max_units or 'above'} slab",
                    "amount": float(slab.fixed_charges),
                })
                break

        return total_charges, slab_breakdown

    def _calculate_tou_charges(
        self,
        peak_kwh: Decimal,
        off_peak_kwh: Decimal,
        rates: TariffRates,
    ) -> Decimal:
        """
        Calculate time-of-use energy charges.

        TOU tariffs charge different rates for peak and off-peak hours.

        Args:
            peak_kwh: Energy consumed during peak hours
            off_peak_kwh: Energy consumed during off-peak hours
            rates: Tariff rates including TOU rates

        Returns:
            Total TOU energy charges
        """
        peak_charges = peak_kwh * (rates.peak_rate_per_kwh or rates.energy_charge_per_kwh)
        off_peak_charges = off_peak_kwh * (rates.off_peak_rate_per_kwh or rates.energy_charge_per_kwh)

        return peak_charges + off_peak_charges

    def _calculate_taxes(
        self,
        energy_charges: Decimal,
        surcharges: Decimal,
        fixed_charges: Decimal,
        demand_charges: Decimal,
        rates: TariffRates,
    ) -> Dict[str, Decimal]:
        """
        Calculate taxes and duties.

        Pakistan electricity bills include:
        - Electricity Duty (ED): Applied on energy charges only
        - GST: Applied on subtotal (energy + surcharges + fixed + demand)
        - TV Fee: Flat fee (if applicable)

        Args:
            energy_charges: Total energy charges
            surcharges: FPA + QTA
            fixed_charges: Fixed charges + meter rent
            demand_charges: Demand charges (industrial)
            rates: Tariff rates with tax percentages

        Returns:
            Dict with electricity_duty, gst, and tv_fee
        """
        # Electricity Duty is calculated on energy charges only
        electricity_duty = (energy_charges * rates.electricity_duty_percent / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Subtotal for GST calculation
        subtotal_for_gst = (
            energy_charges +
            surcharges +
            fixed_charges +
            demand_charges +
            electricity_duty
        )

        # GST on subtotal
        gst = (subtotal_for_gst * rates.gst_percent / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # TV fee (fixed amount)
        tv_fee = rates.tv_fee

        return {
            "electricity_duty": electricity_duty,
            "gst": gst,
            "tv_fee": tv_fee,
        }

    def _calculate_net_metering_credit(
        self,
        exported_kwh: Decimal,
        export_rate: Decimal,
    ) -> Decimal:
        """
        Calculate net metering export credit.

        Solar installations with net metering can export excess
        energy to the grid and receive credits.

        Args:
            exported_kwh: Energy exported to grid
            export_rate: Rate per kWh for exported energy

        Returns:
            Export credit amount
        """
        return (exported_kwh * export_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def calculate_savings(
        self,
        bill_with_solar: BillBreakdown,
        consumption: EnergyConsumption,
        tariff: TariffPlan,
    ) -> SavingsBreakdown:
        """
        Calculate savings from solar generation.

        Compares actual bill with what bill would have been
        without solar generation.

        Args:
            bill_with_solar: Calculated bill with solar
            consumption: Energy consumption data
            tariff: Applicable tariff plan

        Returns:
            SavingsBreakdown with savings metrics
        """
        savings = SavingsBreakdown()

        # Calculate what bill would have been without solar
        consumption_without_solar = EnergyConsumption(
            total_consumed_kwh=consumption.total_consumed_kwh,
            total_generated_kwh=Decimal("0"),
            total_exported_kwh=Decimal("0"),
            total_imported_kwh=consumption.total_consumed_kwh,
            peak_consumed_kwh=consumption.peak_consumed_kwh,
            off_peak_consumed_kwh=consumption.off_peak_consumed_kwh,
            peak_demand_kw=consumption.peak_demand_kw,
        )

        bill_without_solar = self.calculate_bill(consumption_without_solar, tariff)

        savings.bill_without_solar = bill_without_solar.total_bill
        savings.bill_with_solar = bill_with_solar.total_bill
        savings.export_income = bill_with_solar.export_credit

        # Environmental impact
        energy_offset = consumption.total_generated_kwh
        savings.co2_avoided_kg = (energy_offset * self.CO2_KG_PER_KWH).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        savings.trees_equivalent = (
            savings.co2_avoided_kg / 1000 * self.TREES_PER_TON_CO2
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

        # Calculate totals
        savings.calculate()

        return savings

    def calculate_bill_with_savings(
        self,
        consumption: EnergyConsumption,
        tariff: TariffPlan,
    ) -> Tuple[BillBreakdown, SavingsBreakdown]:
        """
        Calculate bill and savings in one call.

        Convenience method that returns both bill breakdown
        and savings analysis.

        Args:
            consumption: Energy consumption data
            tariff: Applicable tariff plan

        Returns:
            Tuple of (BillBreakdown, SavingsBreakdown)
        """
        bill = self.calculate_bill(consumption, tariff)
        savings = self.calculate_savings(bill, consumption, tariff)

        return bill, savings
