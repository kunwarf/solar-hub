"""Add report and report schedule tables

Revision ID: 004
Revises: 003
Create Date: 2026-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # REPORT SCHEDULES (create first due to FK from reports)
    # =========================================================================
    op.create_table(
        'report_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Ownership
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),

        # Schedule definition
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Report template
        sa.Column('report_type', sa.String(50), nullable=False, index=True),
        sa.Column('parameters', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('format', sa.String(20), nullable=False, server_default='pdf'),

        # Scheduling
        sa.Column('frequency', sa.String(20), nullable=False, server_default='monthly'),

        # Time settings
        sa.Column('run_time', sa.Time(), nullable=False, server_default='06:00:00'),
        sa.Column('day_of_week', sa.Integer(), nullable=True),  # 0=Monday
        sa.Column('day_of_month', sa.Integer(), nullable=True),  # 1-28

        # Timezone
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Karachi'),

        # Active period
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),

        # Delivery configuration (JSON)
        sa.Column('delivery_config', postgresql.JSONB(), nullable=False, server_default='{}'),

        # Tracking
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('last_report_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Statistics
        sa.Column('total_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_runs', sa.Integer(), nullable=False, server_default='0'),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )

    # Indexes for report_schedules
    op.create_index('idx_schedules_org_active', 'report_schedules', ['organization_id', 'is_active'])
    op.create_index('idx_schedules_next_run', 'report_schedules', ['is_active', 'next_run_at'])

    # =========================================================================
    # REPORTS
    # =========================================================================
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Ownership
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),

        # Report definition
        sa.Column('report_type', sa.String(50), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Parameters (JSON)
        sa.Column('parameters', postgresql.JSONB(), nullable=False, server_default='{}'),

        # Output format
        sa.Column('format', sa.String(20), nullable=False, server_default='pdf'),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', index=True),

        # Generation tracking
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        # Result
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),

        # Error handling
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),

        # Delivery configuration (JSON)
        sa.Column('delivery_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),

        # Expiration
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, index=True),

        # Schedule reference
        sa.Column('schedule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('report_schedules.id', ondelete='SET NULL'), nullable=True, index=True),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )

    # Indexes for reports
    op.create_index('idx_reports_org_type', 'reports', ['organization_id', 'report_type'])
    op.create_index('idx_reports_status_requested', 'reports', ['status', 'requested_at'])
    op.create_index('idx_reports_org_status', 'reports', ['organization_id', 'status'])

    # =========================================================================
    # REPORT TEMPLATES
    # =========================================================================
    op.create_table(
        'report_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Ownership
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),

        # Template info
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(50), nullable=False, index=True),

        # Branding (JSON)
        sa.Column('branding', postgresql.JSONB(), nullable=False, server_default='{}'),

        # Content sections (JSON array)
        sa.Column('sections', postgresql.JSONB(), nullable=False, server_default='[]'),

        # Default parameters
        sa.Column('default_parameters', postgresql.JSONB(), nullable=False, server_default='{}'),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),

        # Usage tracking
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )

    # Indexes for report_templates
    op.create_index('idx_templates_org_type', 'report_templates', ['organization_id', 'report_type'])
    op.create_index('idx_templates_org_default', 'report_templates', ['organization_id', 'is_default'])


def downgrade() -> None:
    # Drop report_templates
    op.drop_index('idx_templates_org_default', 'report_templates')
    op.drop_index('idx_templates_org_type', 'report_templates')
    op.drop_table('report_templates')

    # Drop reports
    op.drop_index('idx_reports_org_status', 'reports')
    op.drop_index('idx_reports_status_requested', 'reports')
    op.drop_index('idx_reports_org_type', 'reports')
    op.drop_table('reports')

    # Drop report_schedules
    op.drop_index('idx_schedules_next_run', 'report_schedules')
    op.drop_index('idx_schedules_org_active', 'report_schedules')
    op.drop_table('report_schedules')
