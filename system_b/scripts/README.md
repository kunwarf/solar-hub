# System B Scripts

Utility scripts for System B (Device Server & TimescaleDB).

## migrate_device_telemetry_ids.py

**⚠️ Run this FIRST before backfill_telemetry.py**

Updates historical `device_telemetry` records to use the data logger's stable device_id instead of transient inverter device_ids.

### Why This Is Needed

When inverters reconnect, they get new device_ids each time. Historical telemetry was written with these transient device_ids, which don't exist in `device_registry` (and thus have no `site_id`). The backfill script needs a valid `site_id` to work.

This script migrates all historical records to use the **data logger's device_id**, which is stable and has a `site_id` in the registry.

### Usage

```bash
# Dry run to preview changes
python3 migrate_device_telemetry_ids.py \
  --db-host 127.0.0.1 \
  --db-port 5432 \
  --db-name solar_hub_telemetry \
  --db-user solarhub_telemetry \
  --db-password 'your_password' \
  --dry-run

# Apply migration
python3 migrate_device_telemetry_ids.py \
  --db-host 127.0.0.1 \
  --db-port 5432 \
  --db-name solar_hub_telemetry \
  --db-user solarhub_telemetry \
  --db-password 'your_password'
```

### What It Does

1. Finds the data logger device_id from `device_registry` (serial: SH01IN9A423V4CU0)
2. Analyzes current `device_telemetry` records by device_id
3. Updates all records to use the data logger's device_id
4. Verifies the migration

After this, all telemetry records will have the same device_id that has a `site_id` in the registry.

## backfill_telemetry.py

**⚠️ Run migrate_device_telemetry_ids.py FIRST**

Backfills historical telemetry data from `device_telemetry` (JSON) into `telemetry_raw` (normalized metrics).

### When to Use

Use this script when:
- Historical telemetry exists in `device_telemetry` but not in `telemetry_raw`
- After deploying the parser for the first time
- After fixing parser bugs to reprocess old data

### Requirements

```bash
pip install asyncpg
```

### Usage

**Test with small batch:**
```bash
python3 backfill_telemetry.py --limit 100 --dry-run
python3 backfill_telemetry.py --limit 100
```

**Process all records:**
```bash
python3 backfill_telemetry.py --batch-size 1000
```

**Custom database connection:**
```bash
python3 backfill_telemetry.py \
  --db-host localhost \
  --db-port 5432 \
  --db-name solarhub_db \
  --db-user solarhub \
  --db-password your_password \
  --batch-size 1000
```

### Options

- `--limit N` - Process only N records (for testing)
- `--batch-size N` - Process N records per batch (default: 1000)
- `--dry-run` - Show what would be done without writing to database
- `--db-host` - Database host (default: localhost)
- `--db-port` - Database port (default: 5432)
- `--db-name` - Database name (default: solarhub_db)
- `--db-user` - Database user (default: solarhub)
- `--db-password` - Database password (default: solarhub_dev_2024)

### What It Does

1. Reads telemetry from `device_telemetry` table
2. Parses each JSON record using DeyeHybridParser (~50 metrics per record)
3. Writes normalized metrics to `telemetry_raw`
4. Processes in batches to avoid memory issues
5. Refreshes continuous aggregates when complete

### Performance

- **Batch size**: Default 1000 records/batch. Increase to 5000 for faster processing.
- **Duration**: ~30 seconds per 1000 records
- **Example**: 32,810 records = ~10-15 minutes total

### Running in Background

Use `nohup` or `screen` to prevent disconnection:

```bash
nohup python3 backfill_telemetry.py --batch-size 1000 > backfill.log 2>&1 &
tail -f backfill.log
```

### Troubleshooting

**"No site_id for device X, skipping"**
- Device exists in device_telemetry but not in device_registry
- This is normal for orphaned devices, they will be skipped

**"Error parsing record"**
- JSON structure doesn't match DeyeHybridParser expectations
- Check that JSON has sections: power, battery, energy_today, temperatures, grid, status, raw

**Continuous aggregate refresh fails**
- Manually refresh with:
  ```sql
  CALL refresh_continuous_aggregate('telemetry_hourly', NULL, NULL);
  CALL refresh_continuous_aggregate('telemetry_daily', NULL, NULL);
  CALL refresh_continuous_aggregate('telemetry_monthly', NULL, NULL);
  CALL refresh_continuous_aggregate('telemetry_yearly', NULL, NULL);
  ```
