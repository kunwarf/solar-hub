"""Initial schema - Create all tables

Revision ID: 001
Revises:
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE user_role AS ENUM ('super_admin', 'owner', 'admin', 'manager', 'viewer', 'installer')")
    op.execute("CREATE TYPE org_member_role AS ENUM ('owner', 'admin', 'manager', 'viewer', 'installer')")
    op.execute("CREATE TYPE site_status AS ENUM ('active', 'inactive', 'maintenance', 'decommissioned')")
    op.execute("CREATE TYPE device_type AS ENUM ('inverter', 'meter', 'battery', 'weather_station', 'sensor', 'gateway')")
    op.execute("CREATE TYPE device_status AS ENUM ('online', 'offline', 'error', 'maintenance', 'unknown')")
    op.execute("CREATE TYPE protocol_type AS ENUM ('modbus_tcp', 'modbus_rtu', 'mqtt', 'http', 'custom')")
    op.execute("CREATE TYPE alert_severity AS ENUM ('info', 'warning', 'critical')")
    op.execute("CREATE TYPE alert_status AS ENUM ('active', 'acknowledged', 'resolved', 'expired')")

    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('phone', sa.String(20), nullable=True, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('role', sa.Enum('super_admin', 'owner', 'admin', 'manager', 'viewer', 'installer', name='user_role', create_type=False), default='viewer', nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_verified', sa.Boolean(), default=False, nullable=False),
        sa.Column('verification_token', sa.String(255), nullable=True),
        sa.Column('reset_token', sa.String(255), nullable=True),
        sa.Column('reset_token_expires', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('preferences', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='active', nullable=False),
        sa.Column('settings', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Organization members table
    op.create_table(
        'organization_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.Enum('owner', 'admin', 'manager', 'viewer', 'installer', name='org_member_role', create_type=False), default='viewer', nullable=False),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('invitation_token', sa.String(255), nullable=True),
        sa.Column('invitation_expires', sa.DateTime(timezone=True), nullable=True),
        sa.Column('invitation_accepted', sa.Boolean(), default=False, nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_member'),
    )

    # Sites table
    op.create_table(
        'sites',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'maintenance', 'decommissioned', name='site_status', create_type=False), default='active', nullable=False, index=True),
        sa.Column('address', postgresql.JSONB(), nullable=True),
        sa.Column('latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('timezone', sa.String(50), default='Asia/Karachi', nullable=False),
        sa.Column('configuration', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Create index for site geo queries
    op.create_index('idx_sites_location', 'sites', ['latitude', 'longitude'])

    # Devices table
    op.create_table(
        'devices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('device_type', sa.Enum('inverter', 'meter', 'battery', 'weather_station', 'sensor', 'gateway', name='device_type', create_type=False), nullable=False, index=True),
        sa.Column('manufacturer', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('serial_number', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('firmware_version', sa.String(50), nullable=True),
        sa.Column('protocol', sa.Enum('modbus_tcp', 'modbus_rtu', 'mqtt', 'http', 'custom', name='protocol_type', create_type=False), nullable=True),
        sa.Column('connection_config', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.Enum('online', 'offline', 'error', 'maintenance', 'unknown', name='device_status', create_type=False), default='unknown', nullable=False, index=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Alert rules table
    op.create_table(
        'alert_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('condition', postgresql.JSONB(), nullable=False),
        sa.Column('severity', sa.Enum('info', 'warning', 'critical', name='alert_severity', create_type=False), default='warning', nullable=False),
        sa.Column('notification_channels', postgresql.ARRAY(sa.String(50)), default=[], nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('cooldown_minutes', sa.Integer(), default=15, nullable=False),
        sa.Column('auto_resolve', sa.Boolean(), default=True, nullable=False),
        sa.Column('notify_on_trigger', sa.Boolean(), default=True, nullable=False),
        sa.Column('notify_on_resolve', sa.Boolean(), default=True, nullable=False),
        sa.Column('escalation_minutes', sa.Integer(), nullable=True),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alert_rules.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('devices.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('severity', sa.Enum('info', 'warning', 'critical', name='alert_severity', create_type=False), default='warning', nullable=False),
        sa.Column('status', sa.Enum('active', 'acknowledged', 'resolved', 'expired', name='alert_status', create_type=False), default='active', nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=True),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('notifications_sent', postgresql.ARRAY(sa.String(255)), default=[], nullable=False),
        sa.Column('escalated', sa.Boolean(), default=False, nullable=False),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Create index for alert queries
    op.create_index('idx_alerts_triggered', 'alerts', ['triggered_at'])
    op.create_index('idx_alerts_status_severity', 'alerts', ['status', 'severity'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_alerts_status_severity', 'alerts')
    op.drop_index('idx_alerts_triggered', 'alerts')
    op.drop_table('alerts')
    op.drop_table('alert_rules')
    op.drop_table('devices')
    op.drop_index('idx_sites_location', 'sites')
    op.drop_table('sites')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    op.drop_table('users')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS alert_status')
    op.execute('DROP TYPE IF EXISTS alert_severity')
    op.execute('DROP TYPE IF EXISTS protocol_type')
    op.execute('DROP TYPE IF EXISTS device_status')
    op.execute('DROP TYPE IF EXISTS device_type')
    op.execute('DROP TYPE IF EXISTS site_status')
    op.execute('DROP TYPE IF EXISTS org_member_role')
    op.execute('DROP TYPE IF EXISTS user_role')
