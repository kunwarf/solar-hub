"""Update users table to match model.

Revision ID: 007
Revises: 006
Create Date: 2026-01-24

Adds missing columns:
- status (enum)
- email_verified_at
- failed_login_attempts
- locked_until

Removes deprecated columns:
- is_active
- is_verified
- verification_token
- reset_token
- reset_token_expires
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_status enum type if it doesn't exist
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_status') THEN
                CREATE TYPE user_status AS ENUM ('active', 'pending', 'suspended', 'deactivated');
            END IF;
        END $$;
    """))

    # Add new columns
    op.add_column('users', sa.Column(
        'status',
        sa.Enum('active', 'pending', 'suspended', 'deactivated', name='user_status', create_type=False),
        nullable=True
    ))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))

    # Migrate data: set status based on is_active and is_verified
    op.execute(sa.text("""
        UPDATE users
        SET status = CASE
            WHEN is_active = false THEN 'deactivated'::user_status
            WHEN is_verified = false THEN 'pending'::user_status
            ELSE 'active'::user_status
        END,
        email_verified_at = CASE
            WHEN is_verified = true THEN created_at
            ELSE NULL
        END
    """))

    # Make status non-nullable after migration
    op.alter_column('users', 'status', nullable=False)

    # Create index on status
    op.create_index('ix_users_status', 'users', ['status'])

    # Drop old columns
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'verification_token')
    op.drop_column('users', 'reset_token')
    op.drop_column('users', 'reset_token_expires')


def downgrade() -> None:
    # Add back old columns
    op.add_column('users', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('verification_token', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('reset_token', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('reset_token_expires', sa.DateTime(timezone=True), nullable=True))

    # Migrate data back
    op.execute(sa.text("""
        UPDATE users
        SET is_active = CASE
            WHEN status = 'deactivated' THEN false
            ELSE true
        END,
        is_verified = CASE
            WHEN email_verified_at IS NOT NULL THEN true
            ELSE false
        END
    """))

    # Drop new columns and index
    op.drop_index('ix_users_status', 'users')
    op.drop_column('users', 'status')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'locked_until')

    # Note: We don't drop the user_status enum type in downgrade
    # as it might be used elsewhere or cause issues
