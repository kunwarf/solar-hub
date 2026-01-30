"""add_device_settings_table

Revision ID: dcf3f785fbc8
Revises: 5b5dc1009fb8
Create Date: 2026-01-30 07:57:42.758223+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcf3f785fbc8'
down_revision: Union[str, None] = '5b5dc1009fb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create device_settings table
    op.create_table(
        'device_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.UUID(), nullable=False),
        sa.Column('device_type', sa.String(50), nullable=False),
        sa.Column('manufacturer', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    )

    # Create indexes for efficient lookups
    op.create_index('ix_device_settings_device_id', 'device_settings', ['device_id'], unique=True)
    op.create_index('ix_device_settings_device_type', 'device_settings', ['device_type'])
    op.create_index('ix_device_settings_manufacturer_model', 'device_settings', ['manufacturer', 'model'])

    # Create updated_at trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_device_settings_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER device_settings_updated_at_trigger
        BEFORE UPDATE ON device_settings
        FOR EACH ROW
        EXECUTE FUNCTION update_device_settings_updated_at();
    """)


def downgrade() -> None:
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS device_settings_updated_at_trigger ON device_settings")
    op.execute("DROP FUNCTION IF EXISTS update_device_settings_updated_at()")

    # Drop indexes
    op.drop_index('ix_device_settings_manufacturer_model', table_name='device_settings')
    op.drop_index('ix_device_settings_device_type', table_name='device_settings')
    op.drop_index('ix_device_settings_device_id', table_name='device_settings')

    # Drop table
    op.drop_table('device_settings')
