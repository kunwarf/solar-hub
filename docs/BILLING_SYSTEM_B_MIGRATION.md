# Billing Module Migration to System B

**Status:** Phase 1 Complete (Infrastructure Ready)
**Date:** 2026-02-02
**Authors:** Development Team

## Executive Summary

The billing module has been updated to support reading telemetry data directly from System B's TimescaleDB continuous aggregates instead of System A's PostgreSQL summary tables. This migration eliminates data duplication, reduces sync lag, and improves billing accuracy.

## Architecture Changes

### Previous Architecture (Deprecated)
```
System B (TimescaleDB)
  ↓ Sync Job (hourly)
System A PostgreSQL - telemetry_hourly_summary, telemetry_daily_summary
  ↓ Query
Billing Module
```

### New Architecture (Current)
```
System B (TimescaleDB) - telemetry_hourly, telemetry_daily (continuous aggregates)
  ↓ HTTP API
System A Billing Module - SystemBTelemetryRepository (adapter)
  ↓ Calculate
Billing Snapshots (billing_daily, billing_months, billing_cycles)
```

## Key Changes

### 1. New Components

**System B Client Extension** (`system_a/app/infrastructure/external/system_b_client.py`)
- Added `get_hourly_energy_summary()` method for billing-specific queries
- Fetches hourly energy data from System B's energy-chart endpoint

**SystemBTelemetryRepository** (`system_a/app/infrastructure/database/repositories/telemetry_system_b_repository.py`)
- Adapter that implements the same interface as `SQLAlchemyTelemetryRepository`
- Transparently queries System B via HTTP instead of local PostgreSQL
- Maps System B response format to System A domain models

**Feature Flags** (`system_a/app/config.py`)
- `use_system_b_for_billing` (default: False) - Enable System B for billing telemetry
- `validate_system_b_data` (default: False) - Enable dual-read validation
- `system_b_rollout_percentage` (default: 100) - Gradual rollout control

### 2. Updated Components

**BillingSchedulerService** (`system_a/app/application/services/billing_scheduler_service.py`)
- Updated `_get_hourly_telemetry_for_period()` to support three modes:
  1. System A only (default, legacy)
  2. System B only (after migration)
  3. Dual-read with validation (transition period)
- Added `_validate_data_consistency()` method for dual-read validation
- Accepts optional `system_b_telemetry_repo` parameter

**System B Energy Chart Endpoint** (`system_b/app/api/v1/telemetry.py`)
- Added support for `period=custom` with custom `start_time`, `end_time`, `bucket_interval`
- Enables precise time range queries for billing calculations

### 3. New Tools

**Backfill Script** (`system_a/scripts/backfill_billing_from_system_b.py`)
- Recalculates historical billing using System B data
- Supports single site or bulk processing
- Dry-run mode for validation
- Progress tracking and error reporting

**Unit Tests** (`system_a/tests/unit/infrastructure/external/test_system_b_billing.py`)
- Comprehensive tests for System B client and repository adapter
- Mock-based unit tests for fast feedback
- Integration tests for end-to-end validation

**Database Migration** (`system_a/alembic/versions/20260202_0012_012_drop_telemetry_summary_tables.py`)
- Drops System A summary tables after migration complete
- Includes backup instructions and rollback procedure

## Feature Flags Configuration

### Environment Variables

```bash
# Enable System B for billing (set to true when ready to migrate)
USE_SYSTEM_B_FOR_BILLING=false

# Enable dual-read validation (recommended during transition)
VALIDATE_SYSTEM_B_DATA=false

# Gradual rollout percentage (0-100)
SYSTEM_B_ROLLOUT_PERCENTAGE=100

# System B connection settings
SYSTEM_B_URL=http://localhost:8001
SYSTEM_B_API_KEY=your-api-key-here
SYSTEM_B_TIMEOUT=30.0
```

### Feature Flag Behavior

| Flag | Effect |
|------|--------|
| `USE_SYSTEM_B_FOR_BILLING=false` | Billing uses System A (current behavior, no changes) |
| `USE_SYSTEM_B_FOR_BILLING=true` + `VALIDATE_SYSTEM_B_DATA=false` | Billing uses System B only (after migration) |
| `USE_SYSTEM_B_FOR_BILLING=true` + `VALIDATE_SYSTEM_B_DATA=true` | Dual-read: System B primary, System A for validation |

## Migration Phases

### Phase 1: Infrastructure Setup ✅ COMPLETE
- [x] Extend System B client with billing methods
- [x] Create SystemBTelemetryRepository adapter
- [x] Add feature flags
- [x] Implement dual-read validation logic
- [x] Create backfill script
- [x] Write unit tests
- [x] Create database migration

### Phase 2: Testing & Validation (Next Steps)
- [ ] Run integration tests against real System B
- [ ] Run E2E tests for complete billing cycle
- [ ] Performance benchmarking (100 sites, target <5min)
- [ ] Load testing with System B

### Phase 3: Gradual Rollout
- [ ] Deploy to staging with `USE_SYSTEM_B_FOR_BILLING=true` + `VALIDATE_SYSTEM_B_DATA=true`
- [ ] Monitor for 7 days, check discrepancies
- [ ] Deploy to production with 10% rollout
- [ ] Monitor for 48 hours
- [ ] Increase to 50%, monitor for 1 week
- [ ] Increase to 100%

### Phase 4: Cutover
- [ ] Disable telemetry sync service
- [ ] Monitor for 30 days
- [ ] Create database backup
- [ ] Run migration to drop System A summary tables

## Running the Backfill Script

### Backfill Single Site
```bash
cd system_a

# Dry run (no database changes)
python -m scripts.backfill_billing_from_system_b \
  --site-id 271edc3f-f8e8-4aac-acae-78ffd8bf4643 \
  --days 30 \
  --dry-run

# Actual backfill with validation
python -m scripts.backfill_billing_from_system_b \
  --site-id 271edc3f-f8e8-4aac-acae-78ffd8bf4643 \
  --days 30 \
  --validate
```

### Backfill All Sites
```bash
# Backfill last 7 days for all sites
python -m scripts.backfill_billing_from_system_b \
  --all-sites \
  --days 7 \
  --dry-run

# Backfill specific date range
python -m scripts.backfill_billing_from_system_b \
  --all-sites \
  --start-date 2026-01-01 \
  --end-date 2026-01-31
```

## Testing

### Run Unit Tests
```bash
cd system_a
pytest tests/unit/infrastructure/external/test_system_b_billing.py -v
```

### Run Integration Tests (requires System B running)
```bash
docker-compose up -d system-b-db
export TEST_SYSTEM_B_INTEGRATION=1
pytest tests/unit/infrastructure/external/test_system_b_billing.py::test_real_system_b_client_energy_summary -v
```

### Run E2E Tests
```bash
# TODO: Implement E2E tests (Task #8)
pytest tests/e2e/test_billing_system_b.py -v
```

## Monitoring & Alerts

### Key Metrics to Monitor

1. **Billing Job Success Rate**
   - Target: >99% success rate
   - Alert if: <95% over 24 hours

2. **Data Discrepancy Rate**
   - Target: <1% during dual-read validation
   - Alert if: >5% discrepancies

3. **Query Latency**
   - Target: <2 seconds for hourly data fetch
   - Alert if: >5 seconds

4. **System B Availability**
   - Target: >99.9% uptime
   - Alert if: down for >5 minutes

### Log Messages to Watch

```
# Success
INFO - Using System B for billing telemetry (site=..., validation=True)
INFO - Data validation passed for site ...: All ... points within tolerance

# Warnings
WARNING - Data discrepancy at ... for site ...: solar(A=10.5, B=10.3, diff=0.2)
WARNING - System B fetch failed for site .... Falling back to System A.

# Errors
ERROR - System B billing energy error: ...
ERROR - Failed to fetch hourly summaries from System B: ...
```

## Rollback Procedure

If issues occur after enabling System B:

### Immediate Rollback (Environment Variable)
```bash
# Set environment variable
export USE_SYSTEM_B_FOR_BILLING=false

# Restart services
systemctl restart billing-scheduler.service
```

### Rollback After Table Drop (Requires Backup)
```bash
# 1. Stop all services
systemctl stop billing-scheduler.service

# 2. Rollback migration
cd system_a
alembic downgrade -1

# 3. Restore data from backup
psql -h localhost -U postgres -d solar_hub_a < backup_system_a_summaries_2026-02-02.sql

# 4. Re-enable telemetry sync
# (uncomment sync job in telemetry_jobs.py)

# 5. Set environment variable
export USE_SYSTEM_B_FOR_BILLING=false

# 6. Restart services
systemctl start billing-scheduler.service
```

## Known Limitations

1. **Device-Level Filtering Not Supported**
   - System B adapter only supports site-level aggregates
   - Device-level billing queries will log a warning and return site data

2. **Performance Considerations**
   - Cross-system HTTP queries add ~50-100ms latency vs local PostgreSQL
   - Mitigated by caching (future enhancement)

3. **System B Dependency**
   - Billing becomes dependent on System B availability
   - Fallback to System A available during transition period

## FAQ

### Q: When will the migration be complete?
**A:** Phase 1 (Infrastructure) is complete. Phase 2-4 will take approximately 6-8 weeks with gradual rollout and 30-day monitoring period before dropping System A tables.

### Q: Will existing billing data be affected?
**A:** No. Existing billing records in `billing_daily`, `billing_months`, and `billing_cycles` tables remain unchanged. The migration only affects the data source for new billing calculations.

### Q: What happens if System B is down?
**A:** During the transition period (when `VALIDATE_SYSTEM_B_DATA=true`), the system will automatically fall back to System A. After full migration, billing will fail if System B is unavailable (alert will be triggered).

### Q: How do I test the migration locally?
**A:** See "Testing" section above. Set `USE_SYSTEM_B_FOR_BILLING=true` and run the backfill script in dry-run mode.

### Q: Can I run billing from both systems simultaneously?
**A:** Yes, during dual-read validation mode (`VALIDATE_SYSTEM_B_DATA=true`). The system will fetch from both and log discrepancies.

## Support & Contact

For issues or questions:
- Create an issue in the repository
- Contact the development team
- Review logs: `logs/billing_scheduler.log`

## References

- [Billing Module Architecture Analysis](./BILLING_SYSTEM_B_MIGRATION_ANALYSIS.md)
- [System B TimescaleDB Schema](../system_b/docs/timescale_schema.sql)
- [Billing Scheduler Service](../system_a/app/application/services/billing_scheduler_service.py)
- [System B Client](../system_a/app/infrastructure/external/system_b_client.py)
