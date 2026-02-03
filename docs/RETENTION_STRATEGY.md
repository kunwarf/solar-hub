# Retention Strategy and Long-Term Data Management

## Overview

This document explains how to manage telemetry data storage costs while preserving historical queryability through hierarchical continuous aggregates and retention policies.

---

## The Problem

**Without retention policies:**
- Hourly data grows forever: ~100 GB/year for 100 sites
- After 5 years: ~500 GB just for hourly aggregates
- Storage costs increase linearly with time

**But we need historical data for:**
- Year-over-year comparisons
- Multi-year trend analysis
- Customer billing history
- Regulatory compliance (energy records)

---

## The Solution: Hierarchical Retention

Store data at different granularities based on age:

```
Recent Data (Hot)     →  High detail (hourly)   →  90 days
Medium Age (Warm)     →  Medium detail (daily)   →  2 years
Old Data (Cold)       →  Low detail (monthly)    →  Forever
```

### Storage Impact

**Before (no retention):**
```
Hourly forever: ~100 GB/year × 5 years = 500 GB
```

**After (hierarchical retention):**
```
Hourly (90 days):    ~2.5 GB
Daily (2 years):     ~2.0 GB
Monthly (5 years):   ~0.5 GB
Total:               ~5 GB
```

**Savings: 99% storage reduction** 🎉

---

## Implementation Phases

### Phase 1: Current State ✅ (Done)

**What we have:**
- `telemetry_hourly_local` continuous aggregate
- No retention policy (keeping all data)
- Runtime aggregation for daily/monthly/yearly queries

**Works well for:**
- Migration period
- Testing and validation
- Small data volumes (<1 year)

**Status:** This is where you are now

---

### Phase 2: Add Hierarchical Aggregates (Future)

**When to do this:** After 3-6 months, or when hourly data exceeds 50 GB

**Steps:**

1. **Run migration 0008** (creates daily + monthly aggregates):
   ```bash
   cd system_b
   alembic upgrade head
   ```

2. **Backfill daily aggregates** from hourly data:
   ```bash
   python scripts/backfill_daily_aggregate.py --all-history
   ```

3. **Backfill monthly aggregates** from daily data:
   ```bash
   python scripts/backfill_monthly_aggregate.py --all-history
   ```

4. **Validate** the aggregates contain complete data:
   ```sql
   -- Check daily coverage
   SELECT
     MIN(bucket::date) as earliest_daily,
     MAX(bucket::date) as latest_daily,
     COUNT(*) as total_daily_records
   FROM telemetry_daily_local;

   -- Check monthly coverage
   SELECT
     MIN(bucket::date) as earliest_monthly,
     MAX(bucket::date) as latest_monthly,
     COUNT(*) as total_monthly_records
   FROM telemetry_monthly_local;
   ```

**Duration:** ~1 day for backfilling (depending on data volume)

---

### Phase 3: Enable Retention Policies (Future)

⚠️ **ONLY run this after Phase 2 is complete and validated!**

**Prerequisites:**
- ✅ Daily and monthly aggregates exist
- ✅ All historical data backfilled into those aggregates
- ✅ Query router implemented in application code
- ✅ Validated aggregates have complete data

**Steps:**

1. **Deploy smart query router** in application:
   ```python
   # Update TelemetryService to use appropriate aggregate based on date range
   ```

2. **Run migration 0009** (enables retention policies):
   ```bash
   cd system_b
   alembic upgrade head
   ```

3. **Monitor the first cleanup cycle**:
   ```sql
   -- Check retention policy status
   SELECT * FROM timescaledb_information.jobs
   WHERE proc_name = 'policy_retention';
   ```

**What happens:**
- Old hourly data (>90 days) will be deleted automatically
- Old daily data (>2 years) will be deleted automatically
- Monthly data is kept forever

**WARNING:** Deleted data cannot be recovered! Make sure backfill is complete first.

---

## Query Strategy

### Smart Query Router

The application automatically selects the right aggregate based on date range:

```python
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

async def get_telemetry_stats(
    site_id: UUID,
    start_date: date,
    end_date: date,
    metric_name: str
) -> dict:
    """
    Smart query router that selects optimal data source.

    Query strategy:
    - Recent (< 90 days): Use hourly aggregate (runtime aggregation)
    - Medium (90 days - 2 years): Use daily aggregate
    - Old (> 2 years): Use monthly aggregate
    """

    days_ago = (date.today() - end_date).days

    if days_ago < 90:
        # Recent: Query hourly, aggregate at runtime
        return await _query_from_hourly(site_id, start_date, end_date, metric_name)

    elif days_ago < 730:  # 2 years
        # Medium age: Query daily aggregate (pre-materialized)
        return await _query_from_daily(site_id, start_date, end_date, metric_name)

    else:
        # Old: Query monthly aggregate (pre-materialized)
        return await _query_from_monthly(site_id, start_date, end_date, metric_name)


async def _query_from_hourly(
    site_id: UUID,
    start_date: date,
    end_date: date,
    metric_name: str
) -> dict:
    """Query hourly aggregates and compute daily/monthly/yearly at runtime."""

    # Convert local date range to UTC
    from system_b.app.utils.timezone_utils import local_date_to_utc_range

    site_tz = await get_site_timezone(site_id)
    start_utc, end_utc = local_date_to_utc_range(start_date, end_date, site_tz)

    # Query hourly buckets
    query = """
        SELECT
            bucket,
            site_timezone,
            avg_value,
            min_value,
            max_value,
            sample_count,
            total_energy
        FROM telemetry_hourly_local
        WHERE site_id = $1
          AND metric_name = $2
          AND bucket >= $3
          AND bucket <= $4
        ORDER BY bucket
    """

    rows = await db.fetch(query, site_id, metric_name, start_utc, end_utc)

    # Aggregate in Python (group by local day/month/year)
    return aggregate_hourly_to_daily(rows, site_tz)


async def _query_from_daily(
    site_id: UUID,
    start_date: date,
    end_date: date,
    metric_name: str
) -> dict:
    """Query pre-materialized daily aggregates."""

    site_tz = await get_site_timezone(site_id)
    start_utc, end_utc = local_date_to_utc_range(start_date, end_date, site_tz)

    query = """
        SELECT
            bucket,
            site_timezone,
            avg_value,
            min_value,
            max_value,
            sample_count,
            total_energy
        FROM telemetry_daily_local
        WHERE site_id = $1
          AND metric_name = $2
          AND bucket >= $3
          AND bucket <= $4
        ORDER BY bucket
    """

    rows = await db.fetch(query, site_id, metric_name, start_utc, end_utc)

    # Already daily, just convert bucket to local time
    return format_daily_results(rows, site_tz)


async def _query_from_monthly(
    site_id: UUID,
    start_date: date,
    end_date: date,
    metric_name: str
) -> dict:
    """Query pre-materialized monthly aggregates."""

    site_tz = await get_site_timezone(site_id)
    start_utc, end_utc = local_date_to_utc_range(start_date, end_date, site_tz)

    query = """
        SELECT
            bucket,
            site_timezone,
            avg_value,
            min_value,
            max_value,
            sample_count,
            total_energy
        FROM telemetry_monthly_local
        WHERE site_id = $1
          AND metric_name = $2
          AND bucket >= $3
          AND bucket <= $4
        ORDER BY bucket
    """

    rows = await db.fetch(query, site_id, metric_name, start_utc, end_utc)

    # Already monthly, just convert bucket to local time
    return format_monthly_results(rows, site_tz)
```

### Performance Characteristics

| Query Type | Data Source | Query Time | Use Case |
|------------|-------------|------------|----------|
| Today's data | Hourly (24 buckets) | ~20ms | Dashboard |
| Last week | Hourly (168 buckets) | ~50ms | Weekly report |
| Last month | Hourly (720 buckets) | ~100ms | Monthly report |
| Last 3 months | Daily (90 records) | ~30ms | Quarterly report |
| Last year | Daily (365 records) | ~80ms | Annual report |
| Last 5 years | Monthly (60 records) | ~20ms | Historical trends |

---

## Maintenance and Monitoring

### Check Retention Policy Status

```sql
-- View all retention policies
SELECT
    hypertable_name,
    older_than,
    schedule_interval,
    last_run,
    next_scheduled_run
FROM timescaledb_information.jobs j
JOIN timescaledb_information.job_stats js ON j.job_id = js.job_id
WHERE proc_name = 'policy_retention'
ORDER BY hypertable_name;
```

### Monitor Storage Usage

```sql
-- Check size of each aggregate
SELECT
    hypertable_name,
    pg_size_pretty(hypertable_size) as size,
    pg_size_pretty(total_bytes) as total_with_indexes
FROM timescaledb_information.hypertables
WHERE hypertable_name LIKE 'telemetry_%'
ORDER BY hypertable_name;
```

### Verify Data Coverage

```sql
-- Check coverage for each layer
SELECT
    'hourly' as layer,
    MIN(bucket) as earliest,
    MAX(bucket) as latest,
    AGE(NOW(), MIN(bucket)) as oldest_data
FROM telemetry_hourly_local

UNION ALL

SELECT
    'daily' as layer,
    MIN(bucket),
    MAX(bucket),
    AGE(NOW(), MIN(bucket))
FROM telemetry_daily_local

UNION ALL

SELECT
    'monthly' as layer,
    MIN(bucket),
    MAX(bucket),
    AGE(NOW(), MIN(bucket))
FROM telemetry_monthly_local

ORDER BY layer;
```

---

## Cost Analysis

### Storage Costs (Example: 100 Sites, 5 Years)

**No retention (keep all hourly forever):**
```
Year 1: 20 GB   → $1/month
Year 2: 40 GB   → $2/month
Year 3: 60 GB   → $3/month
Year 4: 80 GB   → $4/month
Year 5: 100 GB  → $5/month
Total cost: $180 over 5 years
```

**With hierarchical retention:**
```
Year 1-5: ~5 GB → $0.25/month
Total cost: $15 over 5 years
```

**Savings: ~$165 over 5 years** (92% cost reduction)

### Query Performance Impact

- 95% of queries are for recent data → No change (still using hourly)
- 4% of queries are for medium-age data → Faster (daily pre-aggregated)
- 1% of queries are for old data → Much faster (monthly pre-aggregated)

**Overall: Better performance AND lower costs** ✅

---

## Rollback Plan

If you need to rollback after enabling retention:

⚠️ **WARNING:** Data deleted by retention policies cannot be recovered!

### Remove retention policies (stop deleting data):

```bash
cd system_b
alembic downgrade 0008  # Removes retention policies
```

This will:
- Stop automatic deletion of old data
- Keep existing data at all levels
- Preserve daily and monthly aggregates

**Note:** You cannot recover data that was already deleted by retention policies. You would need to restore from a backup taken before the retention policies ran.

---

## FAQ

### Q: When should I implement retention policies?

**A:** Implement when:
- Hourly data exceeds 50 GB
- Storage costs become significant
- You have >6 months of data to backfill into daily/monthly aggregates

**Don't rush:** Keep it simple during first 6 months, focus on application features.

### Q: What if I need hourly detail for data older than 90 days?

**A:** Options:
1. Increase retention from 90 to 180 days (costs more)
2. Keep backups/exports of old hourly data for rare deep-dives
3. Accept that old data is only available at daily granularity

**Recommendation:** 90 days is sufficient for 99% of use cases. Users rarely need hourly detail for data >3 months old.

### Q: Can I change retention periods later?

**A:** Yes! You can adjust retention periods anytime:

```sql
-- Change hourly retention from 90 to 180 days
SELECT remove_retention_policy('telemetry_hourly_local');
SELECT add_retention_policy('telemetry_hourly_local', INTERVAL '180 days');
```

### Q: What happens during timezone changes?

**A:** With this architecture, timezone changes are handled gracefully:

1. **Hourly data:** Stored with timezone metadata, converted at query time
2. **Daily aggregates:** Re-aggregate hourly data after timezone change
3. **Monthly aggregates:** Re-aggregate daily data after timezone change

The smart query router handles this automatically.

### Q: How do I backfill if I enable retention too early?

**A:** If you enabled retention before backfilling:

1. Restore hourly data from backup (before retention deleted it)
2. Backfill daily and monthly aggregates
3. Re-enable retention

**Prevention:** Always backfill BEFORE enabling retention (follow the phases in order).

---

## Summary

### Current State (Phase 1) ✅
- Hourly aggregates with no retention
- Runtime aggregation for all queries
- Simple, works well for <1 year of data

### Future (Phase 2+3) 📅
- Hierarchical aggregates (hourly → daily → monthly)
- Smart query router based on data age
- Retention policies for cost optimization
- 95% storage reduction
- Better query performance

### When to Move to Phase 2
- After 3-6 months of operation
- When hourly data exceeds 50 GB
- When you have proven the current system works
- When storage costs justify the engineering effort

**Recommendation:** Stay in Phase 1 for now, implement Phase 2 when storage becomes an issue (probably 6-12 months from now).

---

## Related Documentation

- [Timezone Migration Guide](./TIMEZONE_MIGRATION.md)
- [Setup Instructions](./TIMEZONE_MIGRATION_SETUP.md)
- [TimescaleDB Retention Policies](https://docs.timescale.com/api/latest/data-retention/add_retention_policy/)
- [Continuous Aggregates](https://docs.timescale.com/use-timescale/latest/continuous-aggregates/)
