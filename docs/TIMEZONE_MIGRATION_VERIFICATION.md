# Timezone Migration - Verification & Testing Guide

**Date:** 2026-02-03
**Purpose:** Verify timezone-aware system is working correctly and rebuild billing data

---

## 📋 Quick Verification Checklist

Run these checks on the production server to verify everything is working:

### 1. Database Verification

```bash
cd /opt/solarhub/app/solar-hub
psql -U solarhub_telemetry -d solar_hub_telemetry -f scratchpad/verify_timezone_migration.sql
```

**Expected results:**
- ✅ sites_metadata table exists with 1+ sites
- ✅ telemetry_hourly_local aggregate exists
- ✅ Recent data shows timezone: Asia/Karachi
- ✅ TOU classification uses local hours (18-21 = peak)
- ✅ Continuous aggregate refresh job is running

### 2. System B API Verification

Check System B logs for table selection:

```bash
# If using systemd
sudo journalctl -u solarhub-system-b -n 100 | grep "Auto-selected"

# Or check recent logs
tail -100 /var/log/solarhub/system_b.log | grep "Auto-selected"
```

**Expected output:**
```
✓ Auto-selected telemetry_raw with 5 minutes bucket for range ... (< 7 days)
✓ Auto-selected telemetry_hourly_local with 1 hour bucket for range ... (> 7 days)
```

### 3. Dashboard Verification

1. **Open dashboard** in browser
2. **Check energy charts:**
   - Today: Should use telemetry_raw
   - Last week: Should use telemetry_raw
   - Last month: Should use telemetry_hourly_local ✅

3. **Check billing widget:**
   - Running total should reflect TOU rates
   - Peak hours: 6 PM - 10 PM **local time** (not UTC)

### 4. Billing Calculation Verification

Test TOU classification manually:

```bash
psql -U solarhub_telemetry -d solar_hub_telemetry << 'EOF'
-- Check billing for Feb 2, 2026
SELECT
    bucket AT TIME ZONE 'Asia/Karachi' as local_hour,
    EXTRACT(HOUR FROM (bucket AT TIME ZONE 'Asia/Karachi')) as hour_of_day,
    CASE
        WHEN EXTRACT(HOUR FROM (bucket AT TIME ZONE 'Asia/Karachi')) BETWEEN 18 AND 21
        THEN 'peak'
        ELSE 'off-peak'
    END as tou_period,
    ROUND(total_energy::numeric, 2) as load_kwh
FROM telemetry_hourly_local
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643'
  AND bucket::date = '2026-02-02'
  AND metric_name LIKE '%load_energy%'
ORDER BY bucket;
EOF
```

**Expected:**
- Hours 18-21 (local time) = "peak"
- All other hours = "off-peak"
- Peak energy is charged at higher rate

---

## 🔧 Rebuilding Billing Data

Old billing data was calculated using UTC time boundaries, which caused incorrect TOU classification. You need to rebuild it with timezone-aware calculations.

### Why Rebuild?

**Before (incorrect):**
```
Hour 13:00 UTC → Classified as off-peak
Actually 18:00 PKT → Should be PEAK!
```

**After rebuild (correct):**
```
Hour 13:00 UTC → Converted to 18:00 PKT → Classified as PEAK ✅
```

### Rebuild Options

#### Option 1: Rebuild Specific Month

```bash
cd /opt/solarhub/app/solar-hub/system_a
source /opt/solarhub/venv/bin/activate

# Dry run first (see what would happen)
python scripts/rebuild_billing_data.py \
  --site-id 271edc3f-f8e8-4aac-acae-78ffd8bf4643 \
  --year 2026 \
  --month 1 \
  --dry-run

# Actually rebuild January 2026
python scripts/rebuild_billing_data.py \
  --site-id 271edc3f-f8e8-4aac-acae-78ffd8bf4643 \
  --year 2026 \
  --month 1
```

#### Option 2: Rebuild Date Range

```bash
# Rebuild all billing from Dec 2025 to Feb 2026
python scripts/rebuild_billing_data.py \
  --site-id 271edc3f-f8e8-4aac-acae-78ffd8bf4643 \
  --start-date 2025-12-01 \
  --end-date 2026-02-28
```

#### Option 3: Rebuild ALL Billing Data

```bash
# Rebuild everything for this site
python scripts/rebuild_billing_data.py \
  --site-id 271edc3f-f8e8-4aac-acae-78ffd8bf4643 \
  --all
```

### What the Rebuild Script Does

1. **Finds billing periods** that need recalculation
2. **Deletes old billing records** (incorrect UTC-based calculations)
3. **Fetches fresh data from System B** (timezone-aware aggregate)
4. **Recalculates billing** using correct local time TOU classification
5. **Creates new billing records** with correct amounts

### Verify Rebuild Success

After rebuilding, compare old vs new billing:

```sql
-- Check billing for January 2026
SELECT
    period_start,
    period_end,
    peak_energy_kwh,
    off_peak_energy_kwh,
    total_cost,
    created_at
FROM billing_cycles
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643'
  AND period_start >= '2026-01-01'
ORDER BY period_start;
```

**What to look for:**
- New `created_at` timestamp (should be recent)
- Different peak/off-peak energy amounts
- Updated total cost

---

## 🧪 Testing Scenarios

### Test 1: Week Query (Should Use Raw Table)

```bash
curl http://localhost:8001/api/v1/telemetry/energy-chart/271edc3f-f8e8-4aac-acae-78ffd8bf4643?period=week
```

Check logs:
```
✓ Auto-selected telemetry_raw with 1 hour bucket
```

### Test 2: Month Query (Should Use Aggregate)

```bash
curl http://localhost:8001/api/v1/telemetry/energy-chart/271edc3f-f8e8-4aac-acae-78ffd8bf4643?period=month
```

Check logs:
```
✓ Auto-selected telemetry_hourly_local with 1 hour bucket
```

### Test 3: Billing Calculation

1. Open dashboard billing widget
2. Note current billing amount
3. Rebuild billing for current month
4. Refresh dashboard
5. Billing amount should update (likely higher due to correct peak classification)

### Test 4: Daily Boundaries

Query daily totals:

```sql
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

**Verify:** Daily totals align with midnight **local time**, not UTC.

---

## 📊 Expected Differences After Rebuild

### Old Billing (UTC-based, WRONG)
```
Peak hours: 18:00-22:00 UTC = 23:00-03:00 PKT (middle of night!)
Peak energy: 2.5 kWh (very low, most people sleep)
Off-peak energy: 45.0 kWh (includes actual 6 PM - 10 PM usage)
Total cost: PKR 4,200
```

### New Billing (Local time, CORRECT)
```
Peak hours: 18:00-22:00 PKT (6 PM - 10 PM local)
Peak energy: 18.5 kWh (correct - evening usage)
Off-peak energy: 29.0 kWh (correct)
Total cost: PKR 5,800 (higher, but accurate!)
```

**Why higher?** Because your actual peak usage (6-10 PM local) is now correctly classified as peak, not off-peak.

---

## 🔍 Troubleshooting

### Problem: Billing amounts haven't changed

**Check:**
1. Did you rebuild for the correct period?
2. Is System B returning timezone-aware data?
3. Are TOU rates configured correctly?

```sql
-- Check TOU configuration
SELECT * FROM tariff_plans
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643';
```

### Problem: Graphs show wrong daily boundaries

**Check:**
1. Is System B querying telemetry_hourly_local?
2. Check System B logs for "Auto-selected" messages
3. Verify aggregate has data:

```sql
SELECT COUNT(*) FROM telemetry_hourly_local
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643';
```

### Problem: System B still using telemetry_raw for month query

**Check:**
1. Did you restart System B after the latest code changes?
2. Check bucket_interval logic:

```bash
grep -n "Auto-selected" /opt/solarhub/logs/system_b.log
```

Should see "telemetry_hourly_local" for queries > 7 days.

---

## ✅ Final Checklist

Before considering migration complete:

- [ ] Verified sites_metadata table has all sites
- [ ] Verified telemetry_hourly_local has data
- [ ] Verified System B logs show correct table selection
- [ ] Tested week query (uses telemetry_raw)
- [ ] Tested month query (uses telemetry_hourly_local)
- [ ] Rebuilt billing data for affected periods
- [ ] Verified billing amounts reflect correct TOU classification
- [ ] Checked dashboard displays correct local time boundaries
- [ ] Monitored continuous aggregate refresh job
- [ ] No errors in System A or System B logs

---

## 📞 Support

If you encounter issues:

1. Check logs: `sudo journalctl -u solarhub-system-b -n 200`
2. Verify database: `psql -U solarhub_telemetry -d solar_hub_telemetry`
3. Review documentation:
   - TIMEZONE_MIGRATION_COMPLETED.md
   - TIMEZONE_MIGRATION_TESTING_PLAN.md
   - RETENTION_STRATEGY.md

**Last Updated:** 2026-02-03
