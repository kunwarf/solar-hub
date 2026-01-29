"""Add net metering billing tables

Adds tables for 3-month netting cycle billing:
- billing_config: Per-site billing configuration (anchor day, TOU windows, settlement prices)
- billing_daily: Daily billing snapshots for running bill view
- billing_months: Finalized monthly billing records
- billing_cycles: 3-month netting cycle summaries

Revision ID: 010
Revises: 009
Create Date: 2026-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # BILLING CONFIG - Per-site billing configuration
    # =========================================================================
    op.create_table(
        'billing_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Site reference
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, unique=True),

        # Billing month anchor (day of month when billing cycle starts, default 15)
        sa.Column('anchor_day', sa.Integer(), nullable=False, server_default='15'),

        # Time-of-Use windows configuration
        # Structure: {
        #   "peak_windows": [
        #     {"start_hour": 17, "end_hour": 22}
        #   ],
        #   "timezone": "Asia/Karachi"
        # }
        sa.Column('tou_windows', postgresql.JSONB(), nullable=False, server_default='{"peak_windows": [{"start_hour": 17, "end_hour": 22}], "timezone": "Asia/Karachi"}'),

        # Fixed charges
        sa.Column('fixed_charge_per_billing_month', sa.Numeric(10, 2), nullable=False, server_default='0'),

        # Import prices (buying from grid)
        sa.Column('price_offpeak_import', sa.Numeric(8, 4), nullable=False, server_default='0'),
        sa.Column('price_peak_import', sa.Numeric(8, 4), nullable=False, server_default='0'),

        # Settlement prices (selling expired credits at cycle end)
        sa.Column('price_offpeak_settlement', sa.Numeric(8, 4), nullable=False, server_default='0'),
        sa.Column('price_peak_settlement', sa.Numeric(8, 4), nullable=False, server_default='0'),

        # Fixed charge proration mode: 'none' or 'linear_by_day'
        sa.Column('fixed_proration_mode', sa.String(20), nullable=False, server_default='none'),

        # Whether net metering is enabled for this site
        sa.Column('net_metering_enabled', sa.Boolean(), nullable=False, server_default='true'),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    )

    op.create_index('idx_billing_config_site', 'billing_config', ['site_id'])

    # =========================================================================
    # BILLING CYCLES - 3-month netting cycle records
    # =========================================================================
    op.create_table(
        'billing_cycles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Site reference
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),

        # Cycle identification
        sa.Column('cycle_number', sa.Integer(), nullable=False),  # 1-4 within a year
        sa.Column('year', sa.Integer(), nullable=False),

        # Cycle period
        sa.Column('cycle_start_date', sa.Date(), nullable=False),
        sa.Column('cycle_end_date', sa.Date(), nullable=False),

        # Credit pools at cycle start (carried from previous cycle settlement)
        sa.Column('opening_credit_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('opening_credit_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('opening_cash_credit_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Cumulative energy during cycle
        sa.Column('total_import_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('total_export_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('total_import_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('total_export_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Credits generated/consumed during cycle
        sa.Column('credits_generated_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('credits_consumed_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('credits_generated_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('credits_consumed_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Credits remaining at cycle end (before settlement)
        sa.Column('closing_credit_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('closing_credit_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Settlement amounts (credits converted to cash at cycle end)
        sa.Column('settlement_off_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('settlement_peak_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total_settlement_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Closing cash credit (opening + settlement - used)
        sa.Column('closing_cash_credit_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),  # active, finalized

        # Audit hash for tariff/config snapshot
        sa.Column('config_hash', sa.String(64), nullable=True),

        # Audit
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    )

    op.create_index('idx_billing_cycles_site_year', 'billing_cycles', ['site_id', 'year', 'cycle_number'])
    op.create_index('idx_billing_cycles_period', 'billing_cycles', ['site_id', 'cycle_start_date', 'cycle_end_date'])
    op.create_unique_constraint('uq_billing_cycles_site_year_num', 'billing_cycles', ['site_id', 'year', 'cycle_number'])

    # =========================================================================
    # BILLING MONTHS - Finalized monthly billing records
    # =========================================================================
    op.create_table(
        'billing_months',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Site reference
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),

        # Cycle reference
        sa.Column('billing_cycle_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('billing_cycles.id', ondelete='SET NULL'), nullable=True),

        # Month identification
        sa.Column('billing_month_number', sa.Integer(), nullable=False),  # 1-12 within cycle year
        sa.Column('year', sa.Integer(), nullable=False),

        # Billing period (anchor to anchor)
        sa.Column('period_start_date', sa.Date(), nullable=False),
        sa.Column('period_end_date', sa.Date(), nullable=False),

        # Raw energy aggregates
        sa.Column('import_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('export_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('import_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('export_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Total solar and load (informational)
        sa.Column('solar_generation_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('load_consumption_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Net import after applying cycle credits
        sa.Column('net_import_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('net_import_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Credits applied from cycle pool this month
        sa.Column('credits_applied_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('credits_applied_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Credits generated this month (added to cycle pool)
        sa.Column('credits_generated_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('credits_generated_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Bill components
        sa.Column('bill_off_energy_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('bill_peak_energy_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('bill_fixed_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Cycle settlement (only non-zero in cycle-end month)
        sa.Column('cycle_settlement_off_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('cycle_settlement_peak_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Bill totals
        sa.Column('bill_raw_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Monetary carry-forward
        sa.Column('opening_credit_balance_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('closing_credit_balance_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Final payable amount
        sa.Column('bill_final_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),  # active, finalized
        sa.Column('is_cycle_end_month', sa.Boolean(), nullable=False, server_default='false'),

        # Audit hash for config snapshot
        sa.Column('config_hash', sa.String(64), nullable=True),

        # Audit
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    )

    op.create_index('idx_billing_months_site_period', 'billing_months', ['site_id', 'period_start_date', 'period_end_date'])
    op.create_index('idx_billing_months_site_year', 'billing_months', ['site_id', 'year', 'billing_month_number'])
    op.create_unique_constraint('uq_billing_months_site_year_num', 'billing_months', ['site_id', 'year', 'billing_month_number'])

    # =========================================================================
    # BILLING DAILY - Daily billing snapshots
    # =========================================================================
    op.create_table(
        'billing_daily',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Site reference
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),

        # Date
        sa.Column('date', sa.Date(), nullable=False),

        # Billing month reference
        sa.Column('billing_month_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('billing_months.id', ondelete='SET NULL'), nullable=True),

        # Daily energy aggregates (from hourly telemetry)
        sa.Column('import_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('export_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('import_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('export_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Solar and load totals
        sa.Column('solar_generation_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('load_consumption_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Net import after applying cycle credits (running calculation)
        sa.Column('net_import_off_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('net_import_peak_kwh', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Credit pool balances (running state)
        sa.Column('credits_off_cycle_kwh_balance', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('credits_peak_cycle_kwh_balance', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Running bill components (to-date within billing month)
        sa.Column('bill_off_energy_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('bill_peak_energy_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('fixed_prorated_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Expected cycle credit (preview, not actual until cycle end)
        sa.Column('expected_cycle_credit_rs', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Running bill totals (to-date)
        sa.Column('bill_raw_rs_to_date', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('bill_credit_balance_rs_to_date', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('bill_final_rs_to_date', sa.Numeric(12, 2), nullable=False, server_default='0'),

        # Surplus/deficit flag for the billing month to-date
        sa.Column('surplus_deficit_flag', sa.String(10), nullable=False, server_default='NEUTRAL'),  # SURPLUS, DEFICIT, NEUTRAL

        # Net kWh position (export - import for the month to-date)
        sa.Column('net_kwh_position', sa.Numeric(12, 3), nullable=False, server_default='0'),

        # Days elapsed in billing month
        sa.Column('days_elapsed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_days_in_month', sa.Integer(), nullable=False, server_default='30'),

        # Timestamp when this snapshot was generated
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Primary lookup: site + date
    op.create_index('idx_billing_daily_site_date', 'billing_daily', ['site_id', 'date'])
    op.create_unique_constraint('uq_billing_daily_site_date', 'billing_daily', ['site_id', 'date'])

    # For time-series queries
    op.create_index('idx_billing_daily_date', 'billing_daily', ['date'])
    op.create_index('idx_billing_daily_month', 'billing_daily', ['billing_month_id'])


def downgrade() -> None:
    # Drop billing_daily
    op.drop_index('idx_billing_daily_month', 'billing_daily')
    op.drop_index('idx_billing_daily_date', 'billing_daily')
    op.drop_constraint('uq_billing_daily_site_date', 'billing_daily', type_='unique')
    op.drop_index('idx_billing_daily_site_date', 'billing_daily')
    op.drop_table('billing_daily')

    # Drop billing_months
    op.drop_constraint('uq_billing_months_site_year_num', 'billing_months', type_='unique')
    op.drop_index('idx_billing_months_site_year', 'billing_months')
    op.drop_index('idx_billing_months_site_period', 'billing_months')
    op.drop_table('billing_months')

    # Drop billing_cycles
    op.drop_constraint('uq_billing_cycles_site_year_num', 'billing_cycles', type_='unique')
    op.drop_index('idx_billing_cycles_period', 'billing_cycles')
    op.drop_index('idx_billing_cycles_site_year', 'billing_cycles')
    op.drop_table('billing_cycles')

    # Drop billing_config
    op.drop_index('idx_billing_config_site', 'billing_config')
    op.drop_table('billing_config')
