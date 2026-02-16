"""add OTA firmware management

Revision ID: 20260216_0011
Revises: 20260203_1300
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260216_0011'
down_revision = '20260203_1300'
branch_labels = None
depends_on = None


def upgrade():
    # Firmware versions table - stores firmware metadata
    op.create_table(
        'firmware_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('version', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('device_type', sa.String(50), nullable=False, server_default='datalogger'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )
    op.create_index('ix_firmware_versions_version', 'firmware_versions', ['version'])
    op.create_index('ix_firmware_versions_device_type', 'firmware_versions', ['device_type'])

    # Firmware files table - stores actual file content
    op.create_table(
        'firmware_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('firmware_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content', sa.Text, nullable=False),  # Base64 encoded for binary, plain text for .py
        sa.Column('file_size', sa.Integer, nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),  # SHA256 hash
        sa.Column('file_type', sa.String(20), nullable=False, server_default='python'),  # python, config, binary
        sa.Column('is_required', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['firmware_version_id'], ['firmware_versions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_firmware_files_version_id', 'firmware_files', ['firmware_version_id'])
    op.create_index('ix_firmware_files_filename', 'firmware_files', ['filename'])

    # Device firmware status table - tracks what each device is running
    op.create_table(
        'device_firmware_status',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('device_serial', sa.String(50), nullable=False),
        sa.Column('current_version', sa.String(50), nullable=True),
        sa.Column('target_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('update_status', sa.String(20), nullable=False, server_default='up_to_date'),
        # Status: up_to_date, pending, downloading, applying, success, failed, rollback
        sa.Column('update_progress', sa.Integer, nullable=False, server_default='0'),  # 0-100
        sa.Column('last_check_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('update_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('update_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),  # Device info, memory, etc.
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['target_version_id'], ['firmware_versions.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_device_firmware_status_device_serial', 'device_firmware_status', ['device_serial'], unique=True)
    op.create_index('ix_device_firmware_status_update_status', 'device_firmware_status', ['update_status'])

    # Update campaigns table - for managing rollouts
    op.create_table(
        'firmware_update_campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('firmware_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_devices', postgresql.ARRAY(sa.String), nullable=True),  # Specific device serials
        sa.Column('target_filter', postgresql.JSONB, nullable=True),  # Filter criteria (e.g., current_version, site_id)
        sa.Column('rollout_strategy', sa.String(20), nullable=False, server_default='immediate'),
        # Strategies: immediate, staged, canary, scheduled
        sa.Column('rollout_percentage', sa.Integer, nullable=False, server_default='100'),  # For staged rollouts
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        # Status: draft, active, paused, completed, cancelled
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.ForeignKeyConstraint(['firmware_version_id'], ['firmware_versions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_firmware_update_campaigns_status', 'firmware_update_campaigns', ['status'])

    # Update history table - audit log
    op.create_table(
        'firmware_update_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('device_serial', sa.String(50), nullable=False),
        sa.Column('from_version', sa.String(50), nullable=True),
        sa.Column('to_version', sa.String(50), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),  # success, failed, rollback
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['firmware_update_campaigns.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_firmware_update_history_device_serial', 'firmware_update_history', ['device_serial'])
    op.create_index('ix_firmware_update_history_started_at', 'firmware_update_history', ['started_at'])


def downgrade():
    op.drop_table('firmware_update_history')
    op.drop_table('firmware_update_campaigns')
    op.drop_table('device_firmware_status')
    op.drop_table('firmware_files')
    op.drop_table('firmware_versions')
