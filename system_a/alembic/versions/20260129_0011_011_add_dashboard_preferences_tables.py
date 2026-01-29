"""Add dashboard preferences tables.

Revision ID: 011
Revises: 010
Create Date: 2026-01-29

Adds tables for user dashboard customization:
- user_dashboard_preferences (layout preset, grid layout, widget configuration)
- user_custom_presets (saved custom presets)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_dashboard_preferences table
    op.create_table(
        'user_dashboard_preferences',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('layout_preset', sa.String(length=50), nullable=False, server_default='standard'),
        sa.Column('grid_layout', sa.String(length=10), nullable=False, server_default='list'),
        sa.Column('widget_layout', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Create index on user_id for faster lookups
    op.create_index(
        'ix_user_dashboard_preferences_user_id',
        'user_dashboard_preferences',
        ['user_id'],
        unique=True
    )

    # Create user_custom_presets table
    op.create_table(
        'user_custom_presets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('widget_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Create indexes for faster lookups
    op.create_index(
        'ix_user_custom_presets_id',
        'user_custom_presets',
        ['id'],
        unique=True
    )
    op.create_index(
        'ix_user_custom_presets_user_id',
        'user_custom_presets',
        ['user_id'],
        unique=False
    )

    # Create trigger to auto-update updated_at timestamp
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_dashboard_preferences_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))

    op.execute(sa.text("""
        CREATE TRIGGER user_dashboard_preferences_updated_at
        BEFORE UPDATE ON user_dashboard_preferences
        FOR EACH ROW
        EXECUTE FUNCTION update_dashboard_preferences_updated_at();
    """))

    op.execute(sa.text("""
        CREATE TRIGGER user_custom_presets_updated_at
        BEFORE UPDATE ON user_custom_presets
        FOR EACH ROW
        EXECUTE FUNCTION update_dashboard_preferences_updated_at();
    """))


def downgrade() -> None:
    # Drop triggers
    op.execute(sa.text('DROP TRIGGER IF EXISTS user_custom_presets_updated_at ON user_custom_presets'))
    op.execute(sa.text('DROP TRIGGER IF EXISTS user_dashboard_preferences_updated_at ON user_dashboard_preferences'))
    op.execute(sa.text('DROP FUNCTION IF EXISTS update_dashboard_preferences_updated_at()'))

    # Drop indexes
    op.drop_index('ix_user_custom_presets_user_id', table_name='user_custom_presets')
    op.drop_index('ix_user_custom_presets_id', table_name='user_custom_presets')
    op.drop_index('ix_user_dashboard_preferences_user_id', table_name='user_dashboard_preferences')

    # Drop tables
    op.drop_table('user_custom_presets')
    op.drop_table('user_dashboard_preferences')
