# Home Assistant Energy Spike — Investigation & Cleanup Runbook

**Incident:** ~20,377 kWh spike in HA's "Solar" energy sensor at ~07:00 Asia/Karachi on 2026-08-18, making the Aug-18 Energy dashboard unusable.

**Class of bug:** A single publish cycle landed a lifetime-total counter value on a `total_increasing` sensor. HA counted the full jump as one hour of production.

**Status of the fix:** Code changes in this PR (`spike_guard.py` + `redis_cache.py` clamp + `publisher.py` interval fix) prevent recurrence. This runbook covers the one-time cleanup of the historical bad data.

---

## Part 1 — Identify the affected device

Run on the production System-B/A DB:

```sql
SELECT
    i.ha_username,
    d.serial_number,
    d.device_type,
    d.manufacturer,
    d.model,
    d.name
FROM mqtt_integrations       i
JOIN mqtt_integration_devices ind ON ind.integration_id = i.id
JOIN devices                  d   ON d.id = ind.device_id
WHERE i.enabled
  AND ind.enabled;
```

Note the `serial_number` values — you'll need them for Parts 2 and 3.

---

## Part 2 — Clean the anomalous rows in our TimescaleDB

Two tables can hold the spike: `telemetry_raw` (normalized metrics) and
`device_telemetry` (raw JSON, 7-day retention). We treat any daily energy
counter over 500 kWh as garbage — that ceiling matches the runtime guard we
just added, so anything above it was already rejected going forward.

### 2a. Dry run — count what would be deleted

```sql
-- Anomalous normalized metrics
SELECT
    date_trunc('hour', time) AS hour,
    device_id,
    metric_name,
    count(*)                  AS rows,
    min(metric_value)         AS min_val,
    max(metric_value)         AS max_val
FROM telemetry_raw
WHERE metric_name LIKE '%_today_kwh'
  AND metric_value > 500
  AND time >= '2026-08-01'
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 2, 3;

-- Anomalous JSON audit rows (any daily _kwh field > 500)
SELECT
    date_trunc('hour', time) AS hour,
    serial_number,
    count(*)                 AS rows
FROM device_telemetry
WHERE time >= '2026-08-01'
  AND (
        (data->>'today_pv_kwh')::float                    > 500
     OR (data->>'today_load_kwh')::float                  > 500
     OR (data->>'today_import_kwh')::float                > 500
     OR (data->>'today_export_kwh')::float                > 500
     OR (data->>'pv_energy_today_kwh')::float             > 500
     OR (data->>'load_energy_today_kwh')::float           > 500
     OR (data->>'grid_import_energy_today_kwh')::float    > 500
     OR (data->>'grid_export_energy_today_kwh')::float    > 500
     OR (data->>'battery_charge_energy_today_kwh')::float > 500
     OR (data->>'battery_discharge_energy_today_kwh')::float > 500
     OR (data->>'battery_daily_charge_energy')::float     > 500
     OR (data->>'battery_daily_discharge_energy')::float  > 500
  )
GROUP BY 1, 2
ORDER BY 1 DESC;
```

### 2b. Apply — delete the anomalous rows

Wrap in a transaction so you can `ROLLBACK` if the counts look wrong:

```sql
BEGIN;

DELETE FROM telemetry_raw
WHERE metric_name LIKE '%_today_kwh'
  AND metric_value > 500
  AND time >= '2026-08-01';

DELETE FROM device_telemetry
WHERE time >= '2026-08-01'
  AND (
        (data->>'today_pv_kwh')::float                    > 500
     OR (data->>'today_load_kwh')::float                  > 500
     OR (data->>'today_import_kwh')::float                > 500
     OR (data->>'today_export_kwh')::float                > 500
     OR (data->>'pv_energy_today_kwh')::float             > 500
     OR (data->>'load_energy_today_kwh')::float           > 500
     OR (data->>'grid_import_energy_today_kwh')::float    > 500
     OR (data->>'grid_export_energy_today_kwh')::float    > 500
     OR (data->>'battery_charge_energy_today_kwh')::float > 500
     OR (data->>'battery_discharge_energy_today_kwh')::float > 500
     OR (data->>'battery_daily_charge_energy')::float     > 500
     OR (data->>'battery_daily_discharge_energy')::float  > 500
  );

-- Verify counts sanity
SELECT 'telemetry_raw'  AS tbl, count(*) FROM telemetry_raw
  WHERE metric_name LIKE '%_today_kwh' AND metric_value > 500 AND time >= '2026-08-01'
UNION ALL
SELECT 'device_telemetry', count(*) FROM device_telemetry
  WHERE time >= '2026-08-01'
    AND (data->>'today_pv_kwh')::float > 500;

-- COMMIT;   -- Only run once counts show 0
-- ROLLBACK; -- If anything looks wrong
```

### 2c. Refresh continuous aggregates for the affected window

Continuous aggregates cache their inputs — you have to refresh the window
you changed. Use the same start/end for every aggregate view.

```sql
CALL refresh_continuous_aggregate('telemetry_hourly',  '2026-08-18', '2026-08-19');
CALL refresh_continuous_aggregate('telemetry_daily',   '2026-08-18', '2026-08-19');
CALL refresh_continuous_aggregate('telemetry_monthly', '2026-08-01', '2026-09-01');
CALL refresh_continuous_aggregate('telemetry_yearly',  '2026-01-01', '2027-01-01');
```

Also refresh the timezone-aware aggregate if it exists (added Feb 2026):

```sql
CALL refresh_continuous_aggregate('telemetry_hourly_local', '2026-08-18', '2026-08-19');
```

---

## Part 3 — Clean the spike from Home Assistant's statistics DB

HA's Energy dashboard is driven by two recorder tables: `statistics` (long-term
hourly rollups) and `statistics_short_term` (5-minute rows kept for ~10 days).
The `sum` column in each row is where the spike lives. Deleting the affected
rows makes HA re-compute the sum from history on next Statistics run —
which is exactly what we want because the underlying state history is either
correct or already gone.

Connection settings for HA's recorder DB depend on your HA install:

- **Default (SQLite):** file at `/config/home-assistant_v2.db`. Use the
  `sqlite3` CLI or the "SQLite Web" add-on.
- **MariaDB / PostgreSQL recorder:** use the DB CLI directly.

### 3a. Find the affected `statistic_id`s

Home Assistant names our sensors like
`sensor.<device_name>_solar_energy_today`
(the discovery `name` field is `"{device_name} Solar Energy Today"`). To be
safe, search by `unit_of_measurement`:

```sql
SELECT id, statistic_id, unit_of_measurement, source
FROM statistics_meta
WHERE unit_of_measurement = 'kWh'
  AND statistic_id LIKE 'sensor.%';
```

Note the `id` (`metadata_id`) of every sensor you want to clean. If the
"Solar" chip in the Energy dashboard maps to a specific sensor
(you can see it via **Settings → Dashboards → Energy → Solar Panels →
`sensor: ...`**), you only need that one.

### 3b. Dry run — see the spiked rows

```sql
-- Long-term hourly stats (this is what the Energy dashboard reads)
SELECT
    metadata_id,
    to_char(to_timestamp(start_ts) AT TIME ZONE 'Asia/Karachi', 'YYYY-MM-DD HH24:MI') AS local_start,
    sum,
    state,
    "max" AS max_val
FROM statistics
WHERE metadata_id IN ( /* paste the ids from 3a */ )
  AND start_ts >= extract(epoch FROM TIMESTAMP '2026-08-18 00:00:00 Asia/Karachi')
  AND start_ts <  extract(epoch FROM TIMESTAMP '2026-08-19 00:00:00 Asia/Karachi')
ORDER BY metadata_id, start_ts;

-- Short-term (5-min) stats
SELECT
    metadata_id,
    to_char(to_timestamp(start_ts) AT TIME ZONE 'Asia/Karachi', 'YYYY-MM-DD HH24:MI') AS local_start,
    sum,
    state
FROM statistics_short_term
WHERE metadata_id IN ( /* same ids */ )
  AND start_ts >= extract(epoch FROM TIMESTAMP '2026-08-18 00:00:00 Asia/Karachi')
  AND start_ts <  extract(epoch FROM TIMESTAMP '2026-08-19 00:00:00 Asia/Karachi')
ORDER BY metadata_id, start_ts;
```

You will see one or more rows where `sum` or `state` jumps by ~20 000. Note
the exact `start_ts` window.

### 3c. Delete the spiked rows

The safest cleanup for HA is to **delete every row in the affected day** for
that metadata_id. HA's recorder will not re-generate the deleted history
(it doesn't back-fill), so the dashboard simply shows zero for that hour
instead of the spike. Since Aug 18 is already lost data-wise, this is the
right trade-off.

```sql
BEGIN;

DELETE FROM statistics_short_term
WHERE metadata_id IN ( /* ids */ )
  AND start_ts >= extract(epoch FROM TIMESTAMP '2026-08-18 00:00:00 Asia/Karachi')
  AND start_ts <  extract(epoch FROM TIMESTAMP '2026-08-19 00:00:00 Asia/Karachi');

DELETE FROM statistics
WHERE metadata_id IN ( /* ids */ )
  AND start_ts >= extract(epoch FROM TIMESTAMP '2026-08-18 00:00:00 Asia/Karachi')
  AND start_ts <  extract(epoch FROM TIMESTAMP '2026-08-19 00:00:00 Asia/Karachi');

-- COMMIT;   -- when you're satisfied
-- ROLLBACK; -- otherwise
```

### 3d. Adjust cumulative sum (alternative to delete)

If you'd rather keep the row but zero out the bad hour, HA exposes an
**Adjust sum** action instead of running SQL:

1. In HA, open **Developer Tools → Statistics**.
2. Search for the sensor (`sensor.<...>_solar_energy_today`).
3. If HA flagged the spike itself, click **Fix issue → Adjust sum**.
4. Enter a negative offset equal to the spike (e.g. `-20 372`) — HA subtracts
   this from every subsequent hourly row so the running total stays sane.

For MQTT sensors HA does not always auto-detect the spike, in which case the
SQL delete (3c) is faster and cleaner.

### 3e. Restart HA (optional but recommended)

After DB surgery, restart HA so the recorder re-reads its state cache:

```
Settings → System → Restart → Restart Home Assistant
```

Reload the Energy dashboard — the Aug-18 bar for Solar should now show
either zero or the real ~88 kWh depending on how you edited.

---

## Part 3.5 — Flush poisoned "0.00 kWh" cache values

If your lifetime `*_total_kwh` sensors have been displaying `0.00 kWh` in
HA, the InverterEnergyCalculator / BatteryEnergyCalculator wrote fake
zeros into Redis (the pre-fix `_get_totals` cached
`totals.get(key, 0.0)` for one hour whenever the DB integration query
returned no matching rows).  After deploying the code fix you also need
to purge those Redis keys so real values start flowing on the next
publish cycle instead of waiting for the 1 h TTL to expire.

```bash
# Wipe both inverter and battery lifetime-total caches for every device.
# Uses SCAN so it's safe against big keyspaces.
redis-cli --scan --pattern 'ha:inv:*:total_*_kwh' | xargs -r redis-cli DEL
redis-cli --scan --pattern 'ha:batt:*:total_*_kwh' | xargs -r redis-cli DEL
```

If lifetime sensors keep showing `Unknown` after this + a `solarhub-telemetry`
restart, tail the log — the calculator now logs the reason (no rows /
wrong `device_type` / raw fields missing) so you can fix the underlying
data path:

```bash
sudo journalctl -u solarhub-telemetry -f | grep -E 'inv_energy_calc|energy_calc'
```

---

## Part 4 — Make HA adopt the new discovery config

Our publisher republishes MQTT discovery on every process restart with the
correct `state_class: total` for all `_total_kwh` sensors. To force HA to
re-adopt those attributes on your existing sensors (without creating new
entities):

1. Restart `solarhub-telemetry.service` (the System-B publisher).
   ```bash
   sudo systemctl restart solarhub-telemetry
   ```
2. Wait ~2 minutes for one publish cycle to complete.
3. In HA, go to **Settings → Devices & Services → MQTT** and open one of
   your solar entities. Under **Attributes** the `state_class` should now
   read `total` for lifetime sensors and `total_increasing` only for the
   daily `_today_kwh` sensors.

Since we kept the same `unique_id`, no new sensors are created — history is
preserved and the fixed `state_class` takes effect from the next reading
forward.

---

## Part 5 — Verify

Wait one full day, then re-check the Energy dashboard on 2026-08-19. You
should see:

- **Solar total** for the day matching real generation (tens of kWh, not thousands).
- **Electricity chart** with only hour-sized bars, no ~20 000 kWh spike.
- Server logs from `solarhub-telemetry` should contain no lines matching
  `[spike_guard] Rejected` unless the underlying device is misbehaving —
  in which case investigate the device / register map, not HA.
