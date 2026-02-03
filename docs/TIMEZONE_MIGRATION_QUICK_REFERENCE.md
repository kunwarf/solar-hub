# Timezone Migration - Quick Reference

Quick commands and queries for managing timezone-aware aggregates.

---

## Quick Commands

### Sync Sites (One-Time or Manual)
```bash
cd /opt/solarhub/app/solar-hub/system_b
source /opt/solarhub/venv/bin/activate
python scripts/sync_sites_metadata.py
```

### Backfill Aggregate Data
```bash
# Last 7 days
python scripts/backfill_timezone_aware_aggregate.py --days 7 --validate

# Specific date range
python scripts/backfill_timezone_aware_aggregate.py \
  --start-date 2026-01-01 \
  --end-date 2026-02-03 \
  --validate

# Dry run (show what would be done)
python scripts/backfill_timezone_aware_aggregate.py --days 7 --dry-run
```

### Check Migration Status
```bash
cd /opt/solarhub/app/solar-hub/system_b
alembic current  # Current migration version
alembic history  # All migrations
```

### Restart System A (Enable Auto-Sync)
```bash
# Using systemd
sudo systemctl restart solarhub-system-a

# Using supervisor
sudo supervisorctl restart solarhub-system-a
```

---

## Quick Queries

### Check Sites Synchronization
```sql
-- Connect to System B
psql -U solarhub_telemetry -d solar_hub_telemetry

-- View synced sites
SELECT id, timezone, updated_at
FROM sites_metadata
ORDER BY updated_at DESC;

-- Count sites
SELECT COUNT(*) FROM sites_metadata;
```

### Check Aggregate Status
```sql
-- Verify aggregate exists
SELECT view_name, materialized_only, compression_enabled
FROM timescaledb_information.continuous_aggregates
WHERE view_name = 'telemetry_hourly_local';

-- View sample data
SELECT bucket, site_timezone, site_id, metric_name, avg_value
FROM telemetry_hourly_local
ORDER BY bucket DESC
LIMIT 10;

-- Count buckets
SELECT COUNT(*) FROM telemetry_hourly_local;

-- Count by date
SELECT bucket::date, COUNT(*)
FROM telemetry_hourly_local
GROUP BY bucket::date
ORDER BY bucket::date DESC
LIMIT 7;
```

### Check Refresh Policy
```sql
-- View refresh policy status
SELECT
    j.job_id,
    j.schedule_interval,
    js.last_run_status,
    js.last_successful_finish,
    js.next_start
FROM timescaledb_information.jobs j
JOIN timescaledb_information.job_stats js ON j.job_id = js.job_id
WHERE j.proc_name = 'policy_refresh_continuous_aggregate'
  AND j.hypertable_name = 'telemetry_hourly_local';
```

### Check Storage Usage
```sql
-- Size of each aggregate
SELECT
    hypertable_name,
    pg_size_pretty(hypertable_size) as size,
    pg_size_pretty(total_bytes) as total_with_indexes
FROM timescaledb_information.hypertables
WHERE hypertable_name LIKE 'telemetry_%'
ORDER BY hypertable_name;
```

### Manually Refresh Aggregate
```sql
-- Refresh specific date range
CALL refresh_continuous_aggregate(
    'telemetry_hourly_local',
    '2026-01-01 00:00:00+00'::timestamptz,
    '2026-02-03 23:59:59+00'::timestamptz
);
```

---

## Troubleshooting

### Site Not Syncing
```bash
# Check System A logs
tail -f /var/log/solarhub/system_a.log | grep "Synced site timezone"

# Manual sync
python scripts/sync_sites_metadata.py

# Verify counts match
psql -U solarhub -d solar_hub -c "SELECT COUNT(*) FROM sites;"
psql -U solarhub_telemetry -d solar_hub_telemetry -c "SELECT COUNT(*) FROM sites_metadata;"
```

### Aggregate Not Updating
```sql
-- Check last refresh
SELECT last_successful_finish
FROM timescaledb_information.job_stats
WHERE job_id = (
    SELECT job_id FROM timescaledb_information.jobs
    WHERE proc_name = 'policy_refresh_continuous_aggregate'
    AND hypertable_name = 'telemetry_hourly_local'
);

-- Force immediate refresh
CALL refresh_continuous_aggregate('telemetry_hourly_local', NOW() - INTERVAL '24 hours', NOW());
```

### Missing Data in Aggregate
```bash
# Backfill missing date range
python scripts/backfill_timezone_aware_aggregate.py \
  --start-date 2026-01-01 \
  --end-date 2026-01-31 \
  --validate
```

---

## File Locations

### System A (Main Application)
```
/opt/solarhub/app/solar-hub/system_a/
├── app/infrastructure/database/repositories/site_repository.py
└── app/infrastructure/external/system_b_timezone_sync.py
```

### System B (Telemetry Database)
```
/opt/solarhub/app/solar-hub/system_b/
├── alembic/versions/
│   ├── 20260203_0007_add_sites_metadata_table.py
│   └── 20260203_0006_add_timezone_aware_hourly_aggregate.py
└── scripts/
    ├── sync_sites_metadata.py
    └── backfill_timezone_aware_aggregate.py
```

### Documentation
```
/opt/solarhub/app/solar-hub/docs/
├── TIMEZONE_MIGRATION.md               # Overall strategy
├── TIMEZONE_MIGRATION_SETUP.md         # Setup guide
├── TIMEZONE_MIGRATION_COMPLETED.md     # What was done
├── RETENTION_STRATEGY.md               # Long-term planning
└── TIMEZONE_MIGRATION_QUICK_REFERENCE.md  # This file
```

---

## Environment Variables

### System B Required Variables
```bash
# .env file location: /opt/solarhub/app/solar-hub/system_b/.env

# TimescaleDB
USE_TIMESCALEDB=true
TIMESCALE_HOST=127.0.0.1
TIMESCALE_PORT=5432
TIMESCALE_USER=solarhub_telemetry
TIMESCALE_PASSWORD=<password>
TIMESCALE_DATABASE=solar_hub_telemetry

# System A database (for sync script)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=solarhub
DB_PASSWORD=<password>
DB_NAME=solar_hub
```

---

## Key Tables

### sites_metadata (System B)
```sql
CREATE TABLE sites_metadata (
    id UUID PRIMARY KEY,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Karachi',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### telemetry_hourly_local (System B)
```sql
-- Continuous aggregate columns:
bucket          TIMESTAMPTZ  -- UTC hour bucket
site_timezone   VARCHAR      -- Site's timezone (e.g., 'Asia/Karachi')
site_id         UUID
device_id       UUID
metric_name     VARCHAR
avg_value       DOUBLE PRECISION
min_value       DOUBLE PRECISION
max_value       DOUBLE PRECISION
stddev_value    DOUBLE PRECISION
sample_count    BIGINT
good_samples    BIGINT
total_energy    DOUBLE PRECISION  -- For energy metrics only
```

---

## Testing Checklist

After any changes, run through this checklist:

- [ ] Sites sync successfully: `python scripts/sync_sites_metadata.py`
- [ ] Counts match: System A sites = System B sites_metadata
- [ ] Aggregate exists: Query `timescaledb_information.continuous_aggregates`
- [ ] Aggregate has data: `SELECT COUNT(*) FROM telemetry_hourly_local`
- [ ] Refresh policy is running: Query `timescaledb_information.jobs`
- [ ] Indexes exist: `\d telemetry_hourly_local`
- [ ] System A restarted: Auto-sync enabled
- [ ] Test site creation: New site appears in sites_metadata

---

## Performance Benchmarks

Expected query performance (single site):

| Query Type | Buckets | Time | Use Case |
|------------|---------|------|----------|
| Today | 24 | 10-50ms | Dashboard |
| Last week | 168 | 30-100ms | Weekly report |
| Last month | 720 | 50-200ms | Monthly report |
| Last 3 months | 2,160 | 200-500ms | Quarterly |
| Last year | 8,760 | 500ms-2s | Annual report |

If queries are slower than this, check:
1. Indexes exist
2. ANALYZE has run: `ANALYZE telemetry_hourly_local;`
3. Consider adding application caching
4. For yearly queries, consider Phase 2 (daily/monthly aggregates)

---

## Migration Timeline

- **2026-02-03:** Phase 1 completed ✅
  - Migration 0007: sites_metadata table
  - Migration 0006: timezone-aware hourly aggregate
  - Auto-sync service implemented
  - Backfill completed for last 8 days

- **Next: Enable auto-sync** (restart System A)
- **Future: Phase 2** (when storage >50 GB)
  - Migration 0008: Daily and monthly aggregates
- **Future: Phase 3** (after Phase 2 complete)
  - Migration 0009: Retention policies

---

## Support

For detailed information, see:
- **TIMEZONE_MIGRATION_COMPLETED.md** - What was implemented
- **TIMEZONE_MIGRATION_SETUP.md** - How to set up
- **RETENTION_STRATEGY.md** - Long-term strategy
- **TIMEZONE_MIGRATION.md** - Overall architecture

**Last Updated:** 2026-02-03
