# Timezone Migration - Testing Plan

**Date:** 2026-02-03
**Phase:** Ready to Deploy
**Status:** Code changes complete, testing required before restart

---

## ✅ Pre-Restart Checklist

### Database Validation (Completed)
- [x] Migration 0007 (sites_metadata) applied successfully
- [x] Migration 0006 (telemetry_hourly_local) applied successfully
- [x] Sites synced to System B (1 site verified)
- [x] Aggregate backfilled (9,801 buckets verified)
- [x] Indexes created and working (3 indexes verified)
- [x] Refresh policy running (hourly, 100% success rate)
- [x] Timezone conversion correct (+5:00 offset for Asia/Karachi)
- [x] Data quality 100% (all samples good)

### Code Changes (Completed)
- [x] System A: Auto-sync service implemented (SiteRepository)
- [x] System B: Updated to query `telemetry_hourly_local` instead of `telemetry_hourly`
- [x] All changes committed and pushed to main

### Ready to Deploy
- [ ] Pull latest code on server
- [ ] Restart System A (enable auto-sync)
- [ ] Restart System B (use new aggregate)
- [ ] Run test suite
- [ ] Verify billing calculations
- [ ] Verify graphs display correctly

---

## 🔧 Deployment Steps

### Step 1: Pull Latest Code on Server

```bash
# On production server
cd /opt/solarhub/app/solar-hub

# Pull latest changes
git pull origin main

# Verify you have the latest commit
git log --oneline -5

# Should show:
# f468ae0 fix: update System B to query telemetry_hourly_local
# 60c1728 docs: add comprehensive migration documentation
# 290ce29 fix: use sites_metadata instead of sites in validation
```

### Step 2: Restart System A (Enable Auto-Sync)

System A needs restart to load the new `SystemBTimezoneSyncService`.

**Check which service manager:**
```bash
# Systemd
systemctl list-units | grep solarhub

# Supervisor
supervisorctl status | grep solarhub

# Docker
docker ps | grep solarhub
```

**Restart System A:**
```bash
# If using systemd
sudo systemctl restart solarhub-system-a
sudo systemctl status solarhub-system-a

# If using supervisor
sudo supervisorctl restart solarhub-system-a
sudo supervisorctl status solarhub-system-a

# If using docker
docker restart solarhub-system-a
docker logs -f solarhub-system-a | head -50
```

**Verify System A started successfully:**
```bash
# Check logs for startup
tail -100 /var/log/solarhub/system_a.log

# Look for:
# ✅ "Application startup complete"
# ✅ No errors about SystemBTimezoneSyncService
# ✅ Database connections established
```

### Step 3: Restart System B (Use New Aggregate)

System B needs restart to load the updated repository code.

**Restart System B:**
```bash
# If using systemd
sudo systemctl restart solarhub-system-b
sudo systemctl status solarhub-system-b

# If using supervisor
sudo supervisorctl restart solarhub-system-b
sudo supervisorctl status solarhub-system-b

# If using docker
docker restart solarhub-system-b
docker logs -f solarhub-system-b | head -50
```

**Verify System B started successfully:**
```bash
# Check logs for startup
tail -100 /var/log/solarhub/system_b.log

# Look for:
# ✅ "Application startup complete"
# ✅ "Connected to TimescaleDB"
# ✅ No errors about telemetry_hourly_local
```

---

## 🧪 Testing Plan

### Test 1: Auto-Sync Verification

**Purpose:** Verify new sites automatically sync to System B

**Steps:**
1. Create a new test site via frontend or API
2. Immediately check System B:
   ```bash
   psql -U solarhub_telemetry -d solar_hub_telemetry -c "
   SELECT id, timezone, updated_at,
          AGE(NOW(), updated_at) as age
   FROM sites_metadata
   ORDER BY updated_at DESC
   LIMIT 3;
   "
   ```
3. Verify the new site appears within seconds (age < 1 minute)
4. Check System A logs for sync message:
   ```bash
   tail -100 /var/log/solarhub/system_a.log | grep -i "sync"
   ```

**Expected Result:**
- ✅ New site appears in sites_metadata immediately
- ✅ Log shows: "Synced site timezone to System B: <site_id>"

**If it fails:**
- Check System A logs for errors
- Verify TimescaleDB connection in System A .env
- Manually run: `python system_b/scripts/sync_sites_metadata.py`

---

### Test 2: Telemetry API Query

**Purpose:** Verify System B API returns data from new aggregate

**Steps:**
1. Query System B API for energy chart:
   ```bash
   curl -X GET "http://localhost:8001/api/v1/telemetry/energy-chart/271edc3f-f8e8-4aac-acae-78ffd8bf4643?period=week" \
     -H "Accept: application/json"
   ```

2. Check System B logs for table selection:
   ```bash
   tail -100 /var/log/solarhub/system_b.log | grep -i "selected"
   ```

3. Should see: "Auto-selected telemetry_hourly_local with 1 hour bucket"

**Expected Result:**
- ✅ API returns data successfully (HTTP 200)
- ✅ Logs show querying `telemetry_hourly_local` (not `telemetry_hourly`)
- ✅ Data includes timezone information

**If it fails:**
- Check System B logs for SQL errors
- Verify `telemetry_hourly_local` exists:
  ```sql
  SELECT view_name FROM timescaledb_information.continuous_aggregates
  WHERE view_name = 'telemetry_hourly_local';
  ```

---

### Test 3: Billing Calculation Verification

**Purpose:** Verify billing uses local time boundaries for TOU classification

**Test Data:**
```
Site: 271edc3f-f8e8-4aac-acae-78ffd8bf4643
Timezone: Asia/Karachi (UTC+5)
Date: 2026-02-02 (full day of data available)
```

**Manual Calculation (Expected):**

Peak hours in Asia/Karachi: 6 PM - 10 PM (18:00 - 22:00 local time)
In UTC, this is: 1 PM - 5 PM (13:00 - 17:00 UTC)

**Query for verification:**
```sql
-- Get hourly energy for Feb 2 with timezone conversion
SELECT
    bucket AT TIME ZONE 'Asia/Karachi' as local_hour,
    bucket AT TIME ZONE 'UTC' as utc_hour,
    EXTRACT(HOUR FROM (bucket AT TIME ZONE 'Asia/Karachi')) as local_hour_of_day,
    CASE
        WHEN EXTRACT(HOUR FROM (bucket AT TIME ZONE 'Asia/Karachi')) BETWEEN 18 AND 21
        THEN 'peak'
        ELSE 'off-peak'
    END as tou_period,
    metric_name,
    ROUND(total_energy::numeric, 2) as energy_kwh
FROM telemetry_hourly_local
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643'
  AND bucket::date = '2026-02-02'
  AND metric_name = 'load_energy_total_kwh'
ORDER BY bucket;
```

**Sum peak and off-peak:**
```sql
-- Total energy by TOU period
SELECT
    CASE
        WHEN EXTRACT(HOUR FROM (bucket AT TIME ZONE 'Asia/Karachi')) BETWEEN 18 AND 21
        THEN 'peak'
        ELSE 'off-peak'
    END as tou_period,
    SUM(total_energy) as total_kwh,
    COUNT(*) as hours
FROM telemetry_hourly_local
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643'
  AND bucket::date = '2026-02-02'
  AND metric_name LIKE '%load_energy%'
GROUP BY tou_period;
```

**Steps:**
1. Run billing calculation via API or admin panel for Feb 2
2. Compare API result with manual SQL calculation
3. Verify peak hours match local time (18:00-22:00 Karachi), not UTC

**Expected Result:**
- ✅ Peak hours: 6 PM - 10 PM Karachi time (not UTC)
- ✅ Daily total matches sum of hourly values
- ✅ Billing amount reflects correct TOU rates

**If it fails:**
- Verify billing code queries System B API (not System A)
- Check timezone is correctly set on site
- Verify TOU rate configuration

---

### Test 4: Energy Graph Display

**Purpose:** Verify graphs show data with correct local time boundaries

**Steps:**
1. Open frontend dashboard for site 271edc3f-f8e8-4aac-acae-78ffd8bf4643
2. View energy graph for "Last 7 Days"
3. Check that:
   - Day boundaries align with midnight Karachi time (not UTC)
   - Daily totals match database query
   - Hourly data shows local hours (not UTC hours)

**Database verification:**
```sql
-- Get daily totals for last 7 days (local time)
SELECT
    (bucket AT TIME ZONE 'Asia/Karachi')::date as local_date,
    SUM(total_energy) as total_kwh
FROM telemetry_hourly_local
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643'
  AND metric_name = 'pv_energy_total_kwh'
  AND bucket >= NOW() - INTERVAL '7 days'
GROUP BY local_date
ORDER BY local_date DESC;
```

**Expected Result:**
- ✅ Graph shows daily bars aligned to local midnight
- ✅ Daily totals match SQL query
- ✅ No data split across wrong days

**If it fails:**
- Check frontend is using System B API
- Verify API response includes timezone information
- Check frontend timezone handling code

---

### Test 5: Multi-Site Timezone Handling (Future)

**Purpose:** Verify system handles multiple timezones correctly

**Steps:**
1. Create a test site with different timezone (e.g., "America/New_York" UTC-5)
2. Verify site syncs to System B with correct timezone
3. Query energy data for both sites
4. Verify each site uses its own timezone for calculations

**Expected Result:**
- ✅ Each site has its own timezone in sites_metadata
- ✅ Daily boundaries differ by timezone offset
- ✅ Peak hours use local time for each site independently

---

## 🔥 Smoke Test (Quick Validation)

Run this quick test after restart to verify everything works:

```bash
# 1. Check services are running
sudo systemctl status solarhub-system-a
sudo systemctl status solarhub-system-b

# 2. Quick API health check
curl http://localhost:8000/health  # System A
curl http://localhost:8001/health  # System B

# 3. Check database aggregate is being used
psql -U solarhub_telemetry -d solar_hub_telemetry << 'EOF'
-- Verify aggregate has recent data (last hour)
SELECT
    COUNT(*) as recent_buckets,
    MAX(bucket) as latest_bucket,
    AGE(NOW(), MAX(bucket)) as age_of_latest
FROM telemetry_hourly_local
WHERE bucket >= NOW() - INTERVAL '1 hour';
EOF

# Expected: recent_buckets > 0, age_of_latest < 1 hour

# 4. Quick timezone test
psql -U solarhub_telemetry -d solar_hub_telemetry << 'EOF'
-- Verify timezone conversion works
SELECT
    bucket,
    bucket AT TIME ZONE 'Asia/Karachi' as local_time,
    (bucket AT TIME ZONE 'Asia/Karachi') - (bucket AT TIME ZONE 'UTC') as offset
FROM telemetry_hourly_local
ORDER BY bucket DESC
LIMIT 1;
EOF

# Expected: offset = 05:00:00
```

If all 4 checks pass, basic functionality is working! ✅

---

## 🚨 Rollback Plan

If tests fail and you need to rollback:

### Option 1: Rollback Code Only (Keep Database)

```bash
# Revert to previous commit
cd /opt/solarhub/app/solar-hub
git log --oneline -5  # Find previous commit
git checkout <previous-commit-hash>

# Restart services
sudo systemctl restart solarhub-system-a
sudo systemctl restart solarhub-system-b

# This reverts code but keeps:
# ✅ telemetry_hourly_local aggregate (no harm)
# ✅ sites_metadata table (no harm)
# ❌ Back to UTC-based billing (TOU still wrong)
```

### Option 2: Full Rollback (Database + Code)

```bash
# Rollback migrations
cd /opt/solarhub/app/solar-hub/system_b
alembic downgrade 0004  # Removes 0007 and 0006

# Revert code
git checkout <previous-commit-hash>

# Restart services
sudo systemctl restart solarhub-system-a
sudo systemctl restart solarhub-system-b

# This removes everything:
# ❌ telemetry_hourly_local deleted
# ❌ sites_metadata deleted
# ❌ Auto-sync disabled
# ❌ Back to UTC-based system
```

**Note:** Only use Option 2 if there are critical database issues. Code rollback (Option 1) is usually sufficient.

---

## 📊 Success Criteria

After testing, verify all criteria are met:

- [ ] System A restarted successfully
- [ ] System B restarted successfully
- [ ] Auto-sync working (new sites appear in sites_metadata)
- [ ] API returns data from telemetry_hourly_local
- [ ] Billing calculations use local time boundaries
- [ ] Graphs display with correct local time
- [ ] No errors in System A logs
- [ ] No errors in System B logs
- [ ] Timezone conversion working (+5:00 offset verified)
- [ ] Daily totals match manual calculations

If all checks pass: **✅ Deployment successful!**

---

## 📝 Post-Deployment Monitoring

After successful deployment, monitor for 24-48 hours:

### Metrics to Watch

1. **API Response Times**
   ```bash
   # Check if queries are fast
   tail -f /var/log/solarhub/system_b.log | grep "duration"
   ```
   Expected: < 200ms for typical queries

2. **Continuous Aggregate Refresh**
   ```sql
   -- Check refresh job is running
   SELECT
       last_run_status,
       last_successful_finish,
       total_runs,
       total_successes,
       total_failures
   FROM timescaledb_information.job_stats
   WHERE job_id = (
       SELECT job_id FROM timescaledb_information.jobs
       WHERE proc_name = 'policy_refresh_continuous_aggregate'
       AND hypertable_name = 'telemetry_hourly_local'
   );
   ```
   Expected: last_run_status = 'Success', total_failures = 0

3. **Auto-Sync Activity**
   ```bash
   # Watch for sync messages
   tail -f /var/log/solarhub/system_a.log | grep "Synced site timezone"
   ```
   Expected: Message appears whenever new site is created

4. **Error Rate**
   ```bash
   # Check for errors
   tail -1000 /var/log/solarhub/system_a.log | grep -i error | wc -l
   tail -1000 /var/log/solarhub/system_b.log | grep -i error | wc -l
   ```
   Expected: 0 errors related to timezone or telemetry queries

---

## 🎯 Next Steps After Successful Deployment

Once everything is working:

1. **Monitor for 1 week** - Watch for any edge cases or issues
2. **Validate billing accuracy** - Compare with previous billing periods
3. **Collect user feedback** - Verify dashboard displays correctly
4. **Plan Phase 2** - When storage >50 GB, implement daily/monthly aggregates
   - See `docs/RETENTION_STRATEGY.md`

---

## 📚 Related Documentation

- **TIMEZONE_MIGRATION_COMPLETED.md** - What was implemented
- **TIMEZONE_MIGRATION_QUICK_REFERENCE.md** - Quick commands
- **RETENTION_STRATEGY.md** - Long-term planning
- **TIMEZONE_MIGRATION_SETUP.md** - Initial setup guide

---

**Last Updated:** 2026-02-03
**Status:** Ready for deployment testing
