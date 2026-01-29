"""fix_dashboard_preferences_add_id_and_version_columns

Revision ID: 5b5dc1009fb8
Revises: 011
Create Date: 2026-01-29 14:32:01.798265+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b5dc1009fb8'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing id and version columns to dashboard tables."""

    # Add id and version columns to user_dashboard_preferences
    # For existing rows, use user_id as the id value
    op.add_column('user_dashboard_preferences',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.execute("""
        UPDATE user_dashboard_preferences
        SET id = user_id
        WHERE id IS NULL
    """)
    op.alter_column('user_dashboard_preferences', 'id', nullable=False)

    op.add_column('user_dashboard_preferences',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1')
    )

    # Add id and version columns to user_custom_presets (id already exists from default)
    # But ensure version is there
    op.add_column('user_custom_presets',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1')
    )


def downgrade() -> None:
    """Remove id and version columns from dashboard tables."""

    # Remove version column from both tables
    op.drop_column('user_custom_presets', 'version')
    op.drop_column('user_dashboard_preferences', 'version')
    op.drop_column('user_dashboard_preferences', 'id')
