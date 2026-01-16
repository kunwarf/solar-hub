"""Add protocol_definitions table

Revision ID: 005
Revises: 004
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create protocol_definitions table
    op.create_table(
        'protocol_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('protocol_id', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('device_type', sa.Enum('inverter', 'meter', 'battery', 'weather_station',
                                         'sensor', 'gateway', name='device_type',
                                         create_type=False), nullable=False, index=True),
        sa.Column('protocol_type', sa.Enum('modbus_tcp', 'modbus_rtu', 'mqtt', 'http',
                                           'custom', name='protocol_type',
                                           create_type=False), nullable=False, index=True),
        sa.Column('priority', sa.Integer(), nullable=False, default=100),
        sa.Column('manufacturer', sa.String(100), nullable=True),
        sa.Column('model_pattern', sa.String(200), nullable=True),
        sa.Column('adapter_class', sa.String(200), nullable=False),
        sa.Column('register_map_file', sa.String(200), nullable=True),

        # Configuration as JSONB
        sa.Column('identification_config', postgresql.JSONB(), nullable=True),
        sa.Column('serial_number_config', postgresql.JSONB(), nullable=True),
        sa.Column('polling_config', postgresql.JSONB(), nullable=True),
        sa.Column('modbus_config', postgresql.JSONB(), nullable=True),
        sa.Column('command_config', postgresql.JSONB(), nullable=True),
        sa.Column('default_connection_config', postgresql.JSONB(), nullable=True),

        # Metadata
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, default=False),

        # Standard timestamps
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )

    # Create indexes for common queries
    op.create_index('idx_protocol_definitions_priority', 'protocol_definitions', ['priority'])
    op.create_index('idx_protocol_definitions_is_active', 'protocol_definitions', ['is_active'])
    op.create_index('idx_protocol_definitions_device_protocol',
                    'protocol_definitions', ['device_type', 'protocol_type'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_protocol_definitions_device_protocol', 'protocol_definitions')
    op.drop_index('idx_protocol_definitions_is_active', 'protocol_definitions')
    op.drop_index('idx_protocol_definitions_priority', 'protocol_definitions')

    # Drop table
    op.drop_table('protocol_definitions')
