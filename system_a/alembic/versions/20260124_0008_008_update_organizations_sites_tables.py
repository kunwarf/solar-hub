"""Update organizations and sites tables to match models.

Revision ID: 008
Revises: 007
Create Date: 2026-01-24

Updates:
- Create organization_status enum
- Change organizations.status from String to Enum
- Add organizations.site_count column
- Update site_status enum with new values
- Create site_type enum
- Add site_type column to sites
- Add missing site columns (device_ids, notes, contact_*)
- Update organization_members table structure
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create organization_status enum
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'organization_status') THEN
                CREATE TYPE organization_status AS ENUM ('active', 'suspended', 'deactivated');
            END IF;
        END $$;
    """))

    # 2. Create membership_status enum
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'membership_status') THEN
                CREATE TYPE membership_status AS ENUM ('pending', 'active', 'removed');
            END IF;
        END $$;
    """))

    # 2b. Add super_admin to org_member_role enum if not exists
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'super_admin' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'org_member_role')) THEN
                ALTER TYPE org_member_role ADD VALUE 'super_admin';
            END IF;
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """))

    # 3. Create site_type enum
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'site_type') THEN
                CREATE TYPE site_type AS ENUM ('residential', 'commercial', 'industrial', 'utility', 'agricultural');
            END IF;
        END $$;
    """))

    # 4. Add new values to site_status enum if they don't exist
    # Note: We use IF NOT EXISTS and handle in separate connection commits
    # PostgreSQL requires enum values to be committed before use
    connection = op.get_bind()

    # Check and add enum values one by one with commits
    # Using raw connection to enable autocommit for enum additions
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'pending_setup' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'site_status')) THEN
                ALTER TYPE site_status ADD VALUE 'pending_setup';
            END IF;
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """))

    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'commissioning' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'site_status')) THEN
                ALTER TYPE site_status ADD VALUE 'commissioning';
            END IF;
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """))

    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'offline' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'site_status')) THEN
                ALTER TYPE site_status ADD VALUE 'offline';
            END IF;
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """))

    # 5. Add site_count column to organizations
    op.add_column('organizations', sa.Column('site_count', sa.Integer(), server_default='0', nullable=False))

    # 6. Convert organizations.status from String to Enum
    # First add a temporary column
    op.add_column('organizations', sa.Column(
        'status_new',
        sa.Enum('active', 'suspended', 'deactivated', name='organization_status', create_type=False),
        nullable=True
    ))

    # Copy data, mapping old string values to new enum values
    op.execute(sa.text("""
        UPDATE organizations
        SET status_new = CASE
            WHEN status = 'active' THEN 'active'::organization_status
            WHEN status = 'suspended' THEN 'suspended'::organization_status
            WHEN status = 'deactivated' THEN 'deactivated'::organization_status
            ELSE 'active'::organization_status
        END
    """))

    # Make status_new not nullable
    op.alter_column('organizations', 'status_new', nullable=False)

    # Drop old column and rename new one
    op.drop_column('organizations', 'status')
    op.alter_column('organizations', 'status_new', new_column_name='status')

    # Create index on status
    op.create_index('ix_organizations_status', 'organizations', ['status'])

    # 7. Add site_type column to sites
    op.add_column('sites', sa.Column(
        'site_type',
        sa.Enum('residential', 'commercial', 'industrial', 'utility', 'agricultural', name='site_type', create_type=False),
        server_default='residential',
        nullable=False
    ))
    op.create_index('ix_sites_site_type', 'sites', ['site_type'])

    # 8. Add missing columns to sites
    op.add_column('sites', sa.Column('device_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default='{}', nullable=False))
    op.add_column('sites', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('sites', sa.Column('contact_name', sa.String(200), nullable=True))
    op.add_column('sites', sa.Column('contact_phone', sa.String(20), nullable=True))
    op.add_column('sites', sa.Column('contact_email', sa.String(254), nullable=True))

    # 9. Note: 'inactive' -> 'offline' mapping would require a separate migration
    # because PostgreSQL requires new enum values to be committed before use.
    # If there are sites with 'inactive' status, run this after the migration:
    # UPDATE sites SET status = 'offline' WHERE status = 'inactive';

    # 10. Update organization_members table
    # Add status column
    op.add_column('organization_members', sa.Column(
        'status',
        sa.Enum('pending', 'active', 'removed', name='membership_status', create_type=False),
        nullable=True
    ))

    # Add invited_at column
    op.add_column('organization_members', sa.Column('invited_at', sa.DateTime(timezone=True), nullable=True))

    # Add accepted_at column
    op.add_column('organization_members', sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True))

    # Migrate data from old columns to new ones
    op.execute(sa.text("""
        UPDATE organization_members
        SET status = CASE
            WHEN invitation_accepted = true THEN 'active'::membership_status
            ELSE 'pending'::membership_status
        END,
        invited_at = COALESCE(created_at, NOW()),
        accepted_at = CASE
            WHEN invitation_accepted = true THEN joined_at
            ELSE NULL
        END
    """))

    # Make status and invited_at not nullable
    op.alter_column('organization_members', 'status', nullable=False)
    op.alter_column('organization_members', 'invited_at', nullable=False)

    # Drop old columns
    op.drop_column('organization_members', 'invitation_token')
    op.drop_column('organization_members', 'invitation_expires')
    op.drop_column('organization_members', 'invitation_accepted')
    op.drop_column('organization_members', 'joined_at')


def downgrade() -> None:
    # Restore organization_members columns
    op.add_column('organization_members', sa.Column('invitation_token', sa.String(255), nullable=True))
    op.add_column('organization_members', sa.Column('invitation_expires', sa.DateTime(timezone=True), nullable=True))
    op.add_column('organization_members', sa.Column('invitation_accepted', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('organization_members', sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True))

    # Migrate data back
    op.execute(sa.text("""
        UPDATE organization_members
        SET invitation_accepted = CASE
            WHEN status = 'active' THEN true
            ELSE false
        END,
        joined_at = accepted_at
    """))

    op.drop_column('organization_members', 'status')
    op.drop_column('organization_members', 'invited_at')
    op.drop_column('organization_members', 'accepted_at')

    # Drop site columns
    op.drop_column('sites', 'contact_email')
    op.drop_column('sites', 'contact_phone')
    op.drop_column('sites', 'contact_name')
    op.drop_column('sites', 'notes')
    op.drop_column('sites', 'device_ids')
    op.drop_index('ix_sites_site_type', 'sites')
    op.drop_column('sites', 'site_type')

    # Restore organizations.status as String
    op.add_column('organizations', sa.Column('status_old', sa.String(50), nullable=True))
    op.execute(sa.text("""
        UPDATE organizations SET status_old = status::text
    """))
    op.alter_column('organizations', 'status_old', nullable=False)
    op.drop_index('ix_organizations_status', 'organizations')
    op.drop_column('organizations', 'status')
    op.alter_column('organizations', 'status_old', new_column_name='status')

    # Drop site_count
    op.drop_column('organizations', 'site_count')

    # Note: We don't drop enum types in downgrade as they might be used elsewhere
