"""Update devices table with missing columns

Revision ID: 006
Revises: 005
Create Date: 2026-01-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to devices table
    # Note: This migration assumes the devices table exists from migration 001
    # If the table doesn't exist, run migration 001 first
    
    # Check if devices table exists
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'devices' not in tables:
        # Table doesn't exist - this migration will fail
        # User needs to run earlier migrations first
        raise Exception("devices table does not exist. Please run earlier migrations first.")
    
    # Get existing columns
    columns = [col['name'] for col in inspector.get_columns('devices')]
    
    # Add last_error_at if it doesn't exist
    if 'last_error_at' not in columns:
        op.add_column('devices', sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True))
    
    # Handle last_error_message: rename last_error if it exists, otherwise add it
    if 'last_error' in columns and 'last_error_message' not in columns:
        # Rename existing last_error column to last_error_message
        op.alter_column('devices', 'last_error', new_column_name='last_error_message')
    elif 'last_error_message' not in columns:
        # Add last_error_message if it doesn't exist and last_error doesn't exist either
        op.add_column('devices', sa.Column('last_error_message', sa.Text(), nullable=True))
    
    # Add latest_metrics if it doesn't exist
    if 'latest_metrics' not in columns:
        op.add_column('devices', sa.Column('latest_metrics', postgresql.JSONB(), nullable=True))
    
    # Add tags if it doesn't exist
    if 'tags' not in columns:
        op.add_column('devices', sa.Column('tags', postgresql.ARRAY(sa.String()), default=[], nullable=False, server_default='{}'))
    
    # Add total_messages_received if it doesn't exist
    if 'total_messages_received' not in columns:
        op.add_column('devices', sa.Column('total_messages_received', sa.Integer(), default=0, nullable=False, server_default='0'))
    
    # Add total_errors if it doesn't exist
    if 'total_errors' not in columns:
        op.add_column('devices', sa.Column('total_errors', sa.Integer(), default=0, nullable=False, server_default='0'))
    
    # Add uptime_percentage if it doesn't exist
    if 'uptime_percentage' not in columns:
        op.add_column('devices', sa.Column('uptime_percentage', sa.Float(), default=0.0, nullable=False, server_default='0.0'))
    
    # Update manufacturer and model to be NOT NULL if they're currently nullable
    # Note: This will fail if there are NULL values, so we set defaults first
    if 'manufacturer' in columns:
        op.execute("UPDATE devices SET manufacturer = 'Unknown' WHERE manufacturer IS NULL")
        op.alter_column('devices', 'manufacturer', nullable=False, existing_type=sa.String(100))
    
    if 'model' in columns:
        op.execute("UPDATE devices SET model = 'Unknown' WHERE model IS NULL")
        op.alter_column('devices', 'model', nullable=False, existing_type=sa.String(100))
    
    # Add index on last_seen_at if it doesn't exist
    indexes = [idx['name'] for idx in inspector.get_indexes('devices')]
    if 'idx_devices_last_seen_at' not in indexes:
        op.create_index('idx_devices_last_seen_at', 'devices', ['last_seen_at'])


def downgrade() -> None:
    # Remove added columns
    op.drop_index('idx_devices_last_seen_at', 'devices', if_exists=True)
    op.drop_column('devices', 'uptime_percentage')
    op.drop_column('devices', 'total_errors')
    op.drop_column('devices', 'total_messages_received')
    op.drop_column('devices', 'tags')
    op.drop_column('devices', 'latest_metrics')
    op.drop_column('devices', 'last_error_message')
    op.drop_column('devices', 'last_error_at')
    
    # Revert manufacturer and model to nullable
    op.alter_column('devices', 'manufacturer', nullable=True, existing_type=sa.String(100))
    op.alter_column('devices', 'model', nullable=True, existing_type=sa.String(100))
