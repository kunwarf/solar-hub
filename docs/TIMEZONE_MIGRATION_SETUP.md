# Timezone Migration Setup Guide

## Overview

This guide walks you through setting up the timezone-aware hourly aggregates with automatic site replication to System B.

---

## Architecture

**Problem:** TimescaleDB continuous aggregates can't join across databases.
- `telemetry_raw` is in System B (`solar_hub_telemetry`)
- `sites` table is in System A (`solar_hub`)

**Solution:** Create `sites_metadata` lookup table in System B with minimal site data (id + timezone).

**Auto-sync:** Site create/update/delete operations automatically replicate to System B.

---

## Step-by-Step Implementation

### Step 1: Update .env File

Ensure `USE_TIMESCALEDB=true` in System B's `.env` file:

```bash
# On server
cd /opt/solarhub/app/solar-hub/system_b

# Check current setting
cat .env | grep USE_TIMESCALEDB

# If it's false or missing, update it
sed -i 's/USE_TIMESCALEDB=.*/USE_TIMESCALEDB=true/' .env

# If the line doesn't exist, add it
grep -q "USE_TIMESCALEDB" .env || echo "USE_TIMESCALEDB=true" >> .env

# Verify
cat .env | grep USE_TIMESCALEDB
# Should show: USE_TIMESCALEDB=true
```

### Step 2: Create Migration 0007 (sites_metadata table)

Create a new migration file:

```bash
cd /opt/solarhub/app/solar-hub/system_b
source /opt/solarhub/venv/bin/activate

# Create migration
alembic revision -m "add_sites_metadata_table"
```

This creates a file like: `alembic/versions/20260203_XXXX_add_sites_metadata_table.py`

Edit that file and replace its contents with:

```python
"""add sites metadata lookup table

Revision ID: 0007
Revises: 0005
Create Date: 2026-02-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision: str = "0007"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sites_metadata lookup table."""

    # Create sites_metadata table
    op.execute("""
        CREATE TABLE IF NOT EXISTS sites_metadata (
            id UUID PRIMARY KEY,
            timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Karachi',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Create index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sites_metadata_timezone
        ON sites_metadata (timezone);
    """)

    print("✓ Created sites_metadata lookup table")


def downgrade() -> None:
    """Remove sites_metadata table."""
    op.execute("DROP TABLE IF EXISTS sites_metadata CASCADE;")
    print("✓ Dropped sites_metadata table")
```

**IMPORTANT:** Make sure `down_revision` is set to the ID of your latest migration (probably `0005`). Check with:

```bash
alembic history | head -5
```

### Step 3: Update Migration 0006 to use sites_metadata

Edit the existing migration file:

```bash
nano /opt/solarhub/app/solar-hub/system_b/alembic/versions/20260203_0006_add_timezone_aware_hourly_aggregate.py
```

Find this line (around line 69):
```python
FROM telemetry_raw tr
INNER JOIN sites s ON tr.site_id = s.id
```

Replace with:
```python
FROM telemetry_raw tr
INNER JOIN sites_metadata s ON tr.site_id = s.id
```

Save the file (Ctrl+O, Enter, Ctrl+X).

### Step 4: Run Migrations

```bash
cd /opt/solarhub/app/solar-hub/system_b
source /opt/solarhub/venv/bin/activate

# Run migrations
alembic upgrade head
```

You should see:
```
INFO  [alembic.runtime.migration] Running upgrade 0005 -> 0007, add sites metadata lookup table
✓ Created sites_metadata lookup table
INFO  [alembic.runtime.migration] Running upgrade 0007 -> 0006, Add timezone-aware hourly continuous aggregate for global expansion.
Creating timezone-aware hourly continuous aggregate...
✓ Created telemetry_hourly_local materialized view
✓ Added refresh policy (hourly)
✓ Created indexes for query performance
```

### Step 5: Verify Migration

```bash
psql -U solarhub_telemetry -d solar_hub_telemetry << 'EOF'
-- Check sites_metadata table exists
\d sites_metadata

-- Check timezone-aware aggregate exists
SELECT
  view_name,
  materialized_only,
  compression_enabled
FROM timescaledb_information.continuous_aggregates
WHERE view_name = 'telemetry_hourly_local';

-- Check indexes
SELECT indexname
FROM pg_indexes
WHERE tablename = 'sites_metadata'
ORDER BY indexname;
EOF
```

Expected output:
- sites_metadata table with columns: id, timezone, updated_at
- telemetry_hourly_local aggregate exists
- Index: idx_sites_metadata_timezone

### Step 6: Sync Existing Sites

Run the sync script to copy existing sites from System A to System B:

```bash
cd /opt/solarhub/app/solar-hub/system_b
source /opt/solarhub/venv/bin/activate

python scripts/sync_sites_metadata.py
```

You should see:
```
2026-02-03 12:00:00 - INFO - Connecting to databases...
2026-02-03 12:00:00 - INFO - ✓ Connected to both databases
2026-02-03 12:00:00 - INFO - Fetching sites from System A...
2026-02-03 12:00:00 - INFO - Found 5 sites to sync
2026-02-03 12:00:00 - INFO - Progress: 5/5 sites synced
============================================================
Sync Summary:
  Total sites: 5
  ✓ Synced: 5
============================================================

Verification:
  System A sites: 5
  System B sites_metadata: 5
✓ Counts match - sync successful!
```

### Step 7: Restart System A (to load new code)

The site repository now includes automatic sync to System B. Restart System A to load the changes:

```bash
# If using systemd
sudo systemctl restart solarhub-system-a

# Or if using supervisor
sudo supervisorctl restart solarhub-system-a

# Or if running manually, restart the process
```

### Step 8: Test Site Creation

Test that new sites automatically sync:

```bash
# Create a test site via API or frontend
# Then verify it appears in System B:

psql -U solarhub_telemetry -d solar_hub_telemetry -c "
SELECT id, timezone, updated_at
FROM sites_metadata
ORDER BY updated_at DESC
LIMIT 5;
"
```

### Step 9: Backfill Telemetry Data (Optional)

If you want to populate the timezone-aware aggregate with historical data:

```bash
cd /opt/solarhub/app/solar-hub/system_b

# Backfill last 30 days
python scripts/backfill_timezone_aware_aggregate.py --days 30 --validate

# Or backfill specific date range
python scripts/backfill_timezone_aware_aggregate.py \
  --start-date 2024-01-01 \
  --end-date 2026-02-03 \
  --validate
```

---

## Verification Queries

### Check Sync Status

```sql
-- Compare counts
SELECT
  (SELECT COUNT(*) FROM solar_hub.public.sites) as system_a_sites,
  (SELECT COUNT(*) FROM sites_metadata) as system_b_sites_metadata;
```

### View Site Timezones

```sql
SELECT id, timezone, updated_at
FROM sites_metadata
ORDER BY updated_at DESC;
```

### Check Continuous Aggregate

```sql
SELECT
  view_name,
  materialized_only,
  compression_enabled
FROM timescaledb_information.continuous_aggregates
WHERE view_name IN ('telemetry_hourly', 'telemetry_hourly_local')
ORDER BY view_name;
```

### Sample Hourly Data

```sql
SELECT
  bucket_local,
  bucket_timezone,
  site_id,
  metric_name,
  local_hour,
  avg_value
FROM telemetry_hourly_local
WHERE metric_name = 'pv_power_kw'
ORDER BY bucket_local DESC
LIMIT 10;
```

---

## Auto-Sync Behavior

Once setup is complete, sites will automatically sync to System B:

### On Site Creation
- User registers → Default "My Home" site created → Auto-synced to System B
- User creates site via API → Auto-synced to System B

### On Site Update
- User updates site timezone → Auto-synced to System B

### On Site Deletion
- User deletes site → Removed from System B

### Monitoring
Check System A logs for sync messages:
```bash
tail -f /var/log/solarhub/system_a.log | grep "Synced site timezone"
```

---

## Troubleshooting

### Migration Failed: "relation sites does not exist"

**Cause:** Migration 0006 ran before migration 0007 (order issue)

**Fix:**
```bash
# Rollback to 0005
alembic downgrade 0005

# Run 0007 first (creates sites_metadata)
alembic upgrade +1

# Then run 0006 (creates aggregate using sites_metadata)
alembic upgrade head
```

### sites_metadata Table Empty After Migration

**Cause:** Migrations don't copy existing data

**Fix:** Run the sync script:
```bash
python scripts/sync_sites_metadata.py
```

### Site Created But Not in System B

**Possible causes:**
1. System A not restarted after code deployment
2. TimescaleDB connection failed
3. USE_TIMESCALEDB=false

**Check logs:**
```bash
grep "Failed to sync site timezone" /var/log/solarhub/system_a.log
```

**Manual sync:**
```bash
python scripts/sync_sites_metadata.py
```

### Continuous Aggregate Not Created

**Cause:** USE_TIMESCALEDB=false in .env

**Fix:**
```bash
# Update .env
echo "USE_TIMESCALEDB=true" >> /opt/solarhub/app/solar-hub/system_b/.env

# Rollback and re-run
alembic downgrade -1
alembic upgrade head
```

---

## Next Steps

After successful setup:

1. **Phase 2: Validation**
   - Run comparison queries (in TIMEZONE_MIGRATION.md)
   - Verify daily totals match expectations
   - Monitor for 1 week

2. **Phase 3: Cutover**
   - Update application code to use `telemetry_hourly_local`
   - Deploy with feature flag
   - Gradually roll out

3. **Phase 4: Historical Backfill**
   - Backfill all historical data in monthly chunks
   - Monitor database performance

4. **Phase 5: Cleanup**
   - Deprecate `telemetry_hourly` (UTC version)
   - Remove old code paths

---

## Summary

✅ **What was implemented:**
1. `sites_metadata` lookup table in System B
2. Automatic sync service that replicates site timezone on create/update/delete
3. Timezone-aware continuous aggregate using the lookup table
4. Backfill scripts for existing sites and telemetry data

✅ **What happens automatically:**
- Every time a site is created → Timezone synced to System B
- Every time a site timezone is updated → Synced to System B
- Every time a site is deleted → Removed from System B

✅ **Manual steps required:**
1. Update .env file (one time)
2. Run migrations (one time)
3. Sync existing sites (one time)
4. Restart System A (one time)
5. Optional: Backfill historical telemetry data

---

For questions or issues, refer to:
- Main migration doc: `docs/TIMEZONE_MIGRATION.md`
- Validation queries in migration doc
- Troubleshooting section above
