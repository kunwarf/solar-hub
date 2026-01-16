"""Add billing and tariff tables

Revision ID: 003
Revises: 002
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # TARIFF PLANS
    # =========================================================================
    op.create_table(
        'tariff_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # DISCO and category
        sa.Column('disco_provider', sa.String(50), nullable=False, index=True),
        sa.Column('category', sa.String(100), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Validity period
        sa.Column('effective_from', sa.Date(), nullable=False, index=True),
        sa.Column('effective_to', sa.Date(), nullable=True),

        # Rates structure (JSON)
        # Structure: {
        #   "energy_charge_per_kwh": "25.00",
        #   "slabs": [
        #     {"min_units": 0, "max_units": 100, "rate_per_kwh": "7.74", "fixed_charges": "0"},
        #     {"min_units": 101, "max_units": 200, "rate_per_kwh": "10.06", "fixed_charges": "0"},
        #     ...
        #   ],
        #   "peak_rate_per_kwh": "30.00",
        #   "off_peak_rate_per_kwh": "18.00",
        #   "fixed_charges_per_month": "150.00",
        #   "meter_rent": "25.00",
        #   "fuel_price_adjustment": "3.50",
        #   "quarterly_tariff_adjustment": "1.20",
        #   "electricity_duty_percent": "1.5",
        #   "gst_percent": "17",
        #   "tv_fee": "35",
        #   "export_rate_per_kwh": "19.32",
        #   "demand_charge_per_kw": "400.00"
        # }
        sa.Column('rates', postgresql.JSONB(), nullable=False),

        # Features
        sa.Column('supports_net_metering', sa.Boolean(), default=True, nullable=False),
        sa.Column('supports_tou', sa.Boolean(), default=False, nullable=False),

        # Metadata
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Indexes for tariff_plans
    op.create_index('idx_tariff_disco_category', 'tariff_plans', ['disco_provider', 'category'])
    op.create_index('idx_tariff_active', 'tariff_plans', ['disco_provider', 'category', 'effective_from', 'effective_to'])

    # =========================================================================
    # BILLING SIMULATIONS
    # =========================================================================
    op.create_table(
        'billing_simulations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Foreign keys
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('tariff_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tariff_plans.id', ondelete='SET NULL'), nullable=True, index=True),

        # Billing period
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),

        # Energy consumption data
        sa.Column('energy_consumed_kwh', sa.Numeric(12, 3), default=0, nullable=False),
        sa.Column('energy_generated_kwh', sa.Numeric(12, 3), default=0, nullable=False),
        sa.Column('energy_exported_kwh', sa.Numeric(12, 3), default=0, nullable=False),
        sa.Column('energy_imported_kwh', sa.Numeric(12, 3), default=0, nullable=False),

        # Peak demand (for industrial tariffs)
        sa.Column('peak_demand_kw', sa.Numeric(10, 2), nullable=True),

        # Bill breakdown (JSON)
        # Structure: {
        #   "energy_charges": "5000.00",
        #   "slab_breakdown": [
        #     {"slab": "0-100", "units": 100, "rate": "7.74", "amount": "774.00"},
        #     ...
        #   ],
        #   "fixed_charges": "150.00",
        #   "meter_rent": "25.00",
        #   "fuel_price_adjustment": "350.00",
        #   "quarterly_tariff_adjustment": "120.00",
        #   "electricity_duty": "75.00",
        #   "gst": "850.00",
        #   "tv_fee": "35.00",
        #   "export_credit": "500.00",
        #   "demand_charges": "0.00",
        #   "subtotal": "5500.00",
        #   "total_taxes": "960.00",
        #   "total_bill": "6460.00"
        # }
        sa.Column('bill_breakdown', postgresql.JSONB(), nullable=False, server_default='{}'),

        # Savings analysis (JSON)
        # Structure: {
        #   "bill_without_solar": "10000.00",
        #   "bill_with_solar": "6460.00",
        #   "total_savings": "3540.00",
        #   "savings_percent": "35.4",
        #   "export_income": "500.00",
        #   "co2_avoided_kg": "250.00",
        #   "trees_equivalent": "12.5"
        # }
        sa.Column('savings_breakdown', postgresql.JSONB(), nullable=False, server_default='{}'),

        # Totals (convenience fields for querying)
        sa.Column('estimated_bill_pkr', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('estimated_savings_pkr', sa.Numeric(12, 2), default=0, nullable=False),

        # Status
        sa.Column('is_actual', sa.Boolean(), default=False, nullable=False),  # True if based on actual readings
        sa.Column('notes', sa.Text(), nullable=True),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Indexes for billing_simulations
    op.create_index('idx_billing_site_period', 'billing_simulations', ['site_id', 'period_start', 'period_end'])
    op.create_index('idx_billing_period', 'billing_simulations', ['period_start', 'period_end'])


def downgrade() -> None:
    # Drop billing_simulations table
    op.drop_index('idx_billing_period', 'billing_simulations')
    op.drop_index('idx_billing_site_period', 'billing_simulations')
    op.drop_table('billing_simulations')

    # Drop tariff_plans table
    op.drop_index('idx_tariff_active', 'tariff_plans')
    op.drop_index('idx_tariff_disco_category', 'tariff_plans')
    op.drop_table('tariff_plans')
