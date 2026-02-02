# Timezone-Aware Hourly Aggregate Migration

## Overview

This document tracks the migration from UTC-based continuous aggregates to timezone-aware aggregates for global expansion.

**Status:** 🚧 Phase 1 - Infrastructure Created

**Goal:** Enable correct daily boundary calculations for sites across multiple timezones.

---

## Background

### Problem
The current `telemetry_hourly` aggregate uses UTC time buckets:
```sql
time_bucket('1 hour', time) AS bucket
```

This causes issues:
1. **Wrong daily boundaries**: A "day" in PKT timezone spans from 19:00 UTC (previous day) to 18:59 UTC (same day)
2. **Incorrect TOU classification**: Peak/off-peak hours determined by UTC hour instead of local hour
3. **Global expansion blocker**: Cannot accurately report daily totals for users in different timezones

### Solution
Create timezone-aware hourly aggregate using site's timezone:
```sql
time_bucket('1 hour', time AT TIME ZONE sites.timezone) AS bucket_local
```

This enables:
- Correct daily boundary calculations per timezone
- Accurate TOU classification
- Simple aggregation hierarchy: Hourly (local) → Daily → Monthly → Yearly
- Multi-timezone support for global expansion

---

## Migration Phases

### ✅ Phase 1: Infrastructure (Weeks 1-2) - COMPLETED

**Status:** DONE

**Deliverables:**
- [x] Create `telemetry_hourly_local` continuous aggregate
- [x] Add timezone utility functions (`timezone_utils.py`)
- [x] Write comprehensive unit tests (39 tests, all passing)
- [x] Create backfill script
- [x] Add indexes for performance

**Files Created:**
- `system_b/alembic/versions/20260203_0006_add_timezone_aware_hourly_aggregate.py`
- `system_a/app/domain/services/timezone_utils.py`
- `system_a/tests/unit/domain/services/test_timezone_utils.py`
- `system_b/scripts/backfill_timezone_aware_aggregate.py`

**Database Changes:**
- Created materialized view: `telemetry_hourly_local`
- Added indexes:
  - `idx_telemetry_hourly_local_site_bucket`
  - `idx_telemetry_hourly_local_site_device_bucket`
  - `idx_telemetry_hourly_local_site_metric_bucket`
- Set refresh policy: Every 1 hour

**Next Steps:**
1. Apply migration: `cd system_b && alembic upgrade head`
2. Backfill recent data: `python scripts/backfill_timezone_aware_aggregate.py --days 30`
3. Move to Phase 2 for validation

---

### 📋 Phase 2: Validation (Week 3) - PENDING

**Goal:** Validate data accuracy with dual-calculation approach

**Tasks:**
- [ ] Backfill last 30 days of data
- [ ] Create validation queries comparing UTC vs timezone-aware aggregates
- [ ] Run daily comparison for 1 week to verify accuracy
- [ ] Monitor query performance
- [ ] Create dashboard for monitoring data quality
- [ ] Document any discrepancies and root causes

**Validation Queries:**
```sql
-- Compare daily totals: UTC-based vs timezone-aware
WITH utc_daily AS (
  SELECT
    site_id,
    time_bucket('1 day', bucket)::date as day_utc,
    SUM(total_energy) as energy_utc
  FROM telemetry_hourly
  WHERE metric_name = 'pv_energy_kwh'
  GROUP BY site_id, day_utc
),
local_daily AS (
  SELECT
    site_id,
    bucket_local::date as day_local,
    SUM(total_energy) as energy_local
  FROM telemetry_hourly_local
  WHERE metric_name = 'pv_energy_kwh'
  GROUP BY site_id, day_local
)
SELECT
  u.site_id,
  u.day_utc,
  l.day_local,
  u.energy_utc,
  l.energy_local,
  ABS(u.energy_utc - l.energy_local) as difference,
  CASE
    WHEN u.energy_utc > 0 THEN
      ABS(u.energy_utc - l.energy_local) / u.energy_utc * 100
    ELSE 0
  END as pct_difference
FROM utc_daily u
FULL OUTER JOIN local_daily l
  ON u.site_id = l.site_id
  AND u.day_utc = l.day_local
WHERE ABS(u.energy_utc - l.energy_local) > 0.01
ORDER BY difference DESC;
```

**Success Criteria:**
- Daily totals match within 0.1 kWh (accounting for timestamp boundary differences)
- TOU classification shows expected differences (peak hours shift to correct local time)
- Query performance is acceptable (< 100ms for typical dashboard queries)
- No data quality issues in continuous aggregate

---

### 📋 Phase 3: Cutover (Week 4) - PENDING

**Goal:** Switch application code to use timezone-aware aggregate

**Tasks:**
- [ ] Update billing scheduler to query from `telemetry_hourly_local`
- [ ] Update dashboard APIs to use timezone-aware queries
- [ ] Update report generation to use local time buckets
- [ ] Add feature flag for gradual rollout
- [ ] Update API documentation
- [ ] Create rollback plan

**Code Changes Needed:**

1. **Billing Scheduler** (`billing_scheduler_service.py`):
```python
# OLD (UTC-based):
SELECT * FROM telemetry_hourly
WHERE site_id = ? AND bucket >= ? AND bucket < ?

# NEW (Timezone-aware):
SELECT * FROM telemetry_hourly_local
WHERE site_id = ?
  AND bucket_local >= ?  -- Local date boundaries
  AND bucket_local < ?
  AND bucket_timezone = ?  -- Validate timezone
```

2. **Daily Aggregation Queries**:
```python
# Use timezone utilities for date boundaries
from app.domain.services.timezone_utils import get_local_date_range

start_utc, end_utc = get_local_date_range(local_date, site.timezone)

# Query hourly buckets for the local date
hourly_data = await query_telemetry_hourly_local(
    site_id=site.id,
    start=start_utc,
    end=end_utc,
    timezone=site.timezone
)
```

**Rollback Plan:**
- Keep UTC-based aggregate running in parallel
- Use feature flag to toggle between aggregates
- Monitor error rates and performance
- Can instantly rollback by disabling feature flag

---

### 📋 Phase 4: Historical Backfill (Weeks 5-8) - PENDING

**Goal:** Backfill all historical data

**Tasks:**
- [ ] Create background job for incremental backfill
- [ ] Backfill data in monthly chunks (oldest to newest)
- [ ] Monitor database performance during backfill
- [ ] Validate each month after backfill
- [ ] Update progress tracking dashboard

**Backfill Strategy:**
```bash
# Backfill in monthly chunks to manage load
for year in {2024..2025}; do
  for month in {1..12}; do
    python backfill_timezone_aware_aggregate.py \
      --start-date ${year}-${month}-01 \
      --end-date ${year}-${month}-31 \
      --validate
    sleep 60  # Pause between months
  done
done
```

**Monitoring:**
- Track backfill progress (months completed / total months)
- Monitor database CPU and memory usage
- Alert if backfill falls behind or fails
- Validate data quality after each chunk

---

### 📋 Phase 5: Cleanup (Week 9) - PENDING

**Goal:** Complete migration and deprecate UTC aggregate

**Tasks:**
- [ ] Verify 100% of queries use timezone-aware aggregate
- [ ] Remove feature flag
- [ ] Remove code that queries UTC-based aggregate
- [ ] Update retention policies
- [ ] Create new migration to drop `telemetry_hourly` (UTC version)
- [ ] Update documentation
- [ ] Announce migration completion

---

## Rollout Checklist

### Pre-Migration
- [x] Create timezone-aware continuous aggregate
- [x] Write timezone utility functions
- [x] Create comprehensive tests
- [ ] Review and approve architecture (approved: Option B)
- [ ] Set up monitoring and alerting
- [ ] Create rollback procedures

### Migration
- [ ] Phase 1: Infrastructure ✅ COMPLETED
- [ ] Phase 2: Validation (1 week)
- [ ] Phase 3: Cutover (1 week)
- [ ] Phase 4: Backfill (4 weeks)
- [ ] Phase 5: Cleanup (1 week)

### Post-Migration
- [ ] Monitor query performance for 2 weeks
- [ ] Verify billing calculations are correct
- [ ] Update user documentation
- [ ] Train support team on timezone handling
- [ ] Document lessons learned

---

## Key Decisions

### Architecture Decision: Option B (Timezone-Aware Hourly Buckets)

**Rationale:**
- Simplest query logic: `WHERE bucket_local::date = '2024-01-15'`
- Best performance: Direct date filtering on indexed column
- Clean aggregation hierarchy: Hourly → Daily → Monthly → Yearly
- Future-proof: Ready for multi-timezone expansion
- Industry standard: Similar to how other global systems handle timezones

**Trade-offs:**
- Requires one-time migration effort (9 weeks)
- Temporary dual-aggregate overhead during migration
- Historical data needs backfilling

**Alternatives Considered:**
- Option A: Query UTC buckets across day boundaries (complex, slower)
- Option C: Future-only approach (leaves historical data with issue)

**Approved by:** User on 2026-02-03

---

## Testing Strategy

### Unit Tests
- ✅ Timezone conversion functions (39 tests)
- [ ] Billing calculations with timezone-aware data
- [ ] TOU classification with local hours
- [ ] Edge cases (DST, midnight boundaries, month boundaries)

### Integration Tests
- [ ] End-to-end daily billing calculation
- [ ] Dashboard queries with timezone-aware aggregate
- [ ] Cross-timezone data consistency
- [ ] Performance benchmarks

### E2E Tests
- [ ] User views correct daily totals in their timezone
- [ ] Peak hours display correctly in billing breakdown
- [ ] Historical data migration maintains accuracy
- [ ] Multi-site scenarios with different timezones

---

## Performance Metrics

### Baseline (UTC-based aggregate)
- Daily query time: ~50-100ms
- Monthly query time: ~200-500ms
- Hourly aggregate size: ~X GB
- Query complexity: Medium (requires join with sites table)

### Target (Timezone-aware aggregate)
- Daily query time: < 100ms (direct date filter)
- Monthly query time: < 500ms
- Hourly aggregate size: ~X GB (similar, includes timezone column)
- Query complexity: Low (simple date range filter)

### To Be Measured
- [ ] Aggregate refresh time
- [ ] Storage overhead
- [ ] Query performance with large datasets
- [ ] Backfill speed

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Data loss during migration | Keep UTC aggregate running in parallel; validate before cutover |
| Performance degradation | Monitor query times; optimize indexes; rollback if needed |
| Incorrect billing calculations | Extensive validation in Phase 2; manual verification of sample bills |
| Timezone changes by sites | Store `bucket_timezone` for auditing; handle timezone updates gracefully |
| Backfill fails or takes too long | Chunked processing; resume capability; background job with monitoring |
| User confusion during transition | Clear communication; gradual rollout; support documentation |

---

## Communication Plan

### Internal Team
- [x] Architecture decision documented and approved
- [ ] Migration plan reviewed by team
- [ ] Daily standup updates during migration
- [ ] Post-migration retrospective

### Support Team
- [ ] Training on timezone handling
- [ ] FAQ document for user questions
- [ ] Escalation procedures

### Users
- [ ] Announcement of upcoming migration
- [ ] Expected changes in behavior
- [ ] Support contact information

---

## Useful Commands

### Apply Migration
```bash
cd system_b
alembic upgrade head
```

### Backfill Recent Data (Phase 1)
```bash
python scripts/backfill_timezone_aware_aggregate.py --days 30 --validate
```

### Backfill Historical Data (Phase 4)
```bash
# Last 90 days
python scripts/backfill_timezone_aware_aggregate.py --days 90

# Specific date range
python scripts/backfill_timezone_aware_aggregate.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --validate
```

### Monitor Aggregate Size
```sql
SELECT
  pg_size_pretty(pg_total_relation_size('telemetry_hourly_local')) as size,
  COUNT(*) as row_count
FROM telemetry_hourly_local;
```

### Check Refresh Status
```sql
SELECT
  view_name,
  last_run_status,
  last_successful_finish,
  total_runs,
  total_successes
FROM timescaledb_information.job_stats
WHERE view_name = 'telemetry_hourly_local';
```

---

## References

- [TimescaleDB Continuous Aggregates Docs](https://docs.timescale.com/use-timescale/latest/continuous-aggregates/)
- [PostgreSQL Timezone Handling](https://www.postgresql.org/docs/current/datatype-datetime.html#DATATYPE-TIMEZONES)
- [pytz Documentation](https://pythonhosted.org/pytz/)
- Migration: `system_b/alembic/versions/20260203_0006_add_timezone_aware_hourly_aggregate.py`
- Utilities: `system_a/app/domain/services/timezone_utils.py`
- Tests: `system_a/tests/unit/domain/services/test_timezone_utils.py`

---

## Contact

For questions or issues during migration:
- Technical Lead: [Name]
- Database Admin: [Name]
- Project Manager: [Name]

---

**Last Updated:** 2026-02-03
**Next Review:** After Phase 2 completion
