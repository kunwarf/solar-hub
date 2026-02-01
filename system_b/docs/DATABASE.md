# Solar Hub - System B TimescaleDB Schema Documentation

## Overview

System B uses **TimescaleDB 2.x** (PostgreSQL extension) for high-performance time-series data storage. The schema is optimized for:

- High-frequency telemetry ingestion (thousands of metrics per second)
- Efficient time-range queries for dashboards
- Automatic data aggregation via continuous aggregates
- Automatic data lifecycle management (retention, compression)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM B - TIMESCALEDB                                 │
│                      Communication & Telemetry Backend                           │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │         DEVICE SOURCES           │
                    │  (Modbus, MQTT, HTTP, Custom)    │
                    └──────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │      device_registry             │
                    │   (Device auth & connection)     │
                    └──────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │     Telemetry Parser             │
                    │  (JSON → Normalized Metrics)     │
                    └──────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       │                       ▼
┌──────────────────┐                │            ┌──────────────────┐
│  telemetry_raw   │                │            │device_telemetry  │
│  (Hypertable)    │                │            │  (Audit Trail)   │
│ Normalized       │                │            │   JSON Storage   │
│ Metrics Storage  │                │            │   (7 days)       │
└──────────────────┘                │            └──────────────────┘
         │                          │
         │ Continuous               ▼
         │ Aggregates    ┌──────────────────┐
         │               │  device_events   │
         │               │  (Hypertable)    │
         │               └──────────────────┘
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     CONTINUOUS AGGREGATES                             │
│                                                                       │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│   │telemetry   │─▶│telemetry   │─▶│telemetry   │─▶│telemetry   │    │
│   │  _hourly   │  │  _daily    │  │  _monthly  │  │  _yearly   │    │
│   │ (1 year)   │  │ (3 years)  │  │ (5 years)  │  │ (forever)  │    │
│   └────────────┘  └────────────┘  └────────────┘  └────────────┘    │
│                                                                       │
│  Intraday         Daily/Weekly     Monthly         Long-term          │
│  charts           charts            reports         trends            │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

## Tables Summary

| Table | Type | Description | Retention |
|-------|------|-------------|-----------|
| `device_registry` | Regular | Device connection & auth info | Permanent |
| `telemetry_raw` | Hypertable | Normalized telemetry metrics | 90 days (compressed after 7) |
| `device_telemetry` | Hypertable | Full JSON audit trail | 7 days |
| `device_events` | Hypertable | Device events & errors | 1 year |
| `device_commands` | Regular | Command queue for devices | Permanent |
| `metric_definitions` | Regular | Standard metric definitions | Permanent |
| `ingestion_batches` | Regular | Ingestion tracking | Permanent |
| `telemetry_hourly` | Continuous Aggregate | Hourly aggregates | 1 year |
| `telemetry_daily` | Continuous Aggregate | Daily aggregates | 3 years |
| `telemetry_monthly` | Continuous Aggregate | Monthly aggregates | 5 years |
| `telemetry_yearly` | Continuous Aggregate | Yearly aggregates | Forever |

## Hypertables

### telemetry_raw

The main time-series table storing all raw device readings.

**Chunk Interval:** 1 hour (optimized for recent queries)

**Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `time` | TIMESTAMPTZ | Timestamp of reading (partition key) |
| `device_id` | UUID | Device identifier |
| `site_id` | UUID | Site identifier |
| `metric_name` | VARCHAR(100) | Standardized metric name |
| `metric_value` | DOUBLE PRECISION | Numeric value |
| `metric_value_str` | VARCHAR(255) | String value (for status, codes) |
| `quality` | ENUM | Data quality indicator |
| `unit` | VARCHAR(20) | Unit of measurement |
| `tags` | JSONB | Flexible tags (e.g., mppt_id, phase) |
| `raw_value` | BYTEA | Original bytes from device |

**Compression:** Enabled after 7 days
- Segment by: `device_id, metric_name`
- Order by: `time DESC`

### device_events

Captures significant device events for monitoring.

**Chunk Interval:** 1 day

**Event Types:**
| Type | Description |
|------|-------------|
| `status_change` | Device status changed |
| `error` | Error occurred |
| `warning` | Warning condition |
| `connection` | Connection/disconnection |
| `command` | Command sent/completed |

### device_telemetry

Optional audit trail storing full JSON telemetry for debugging and compliance.

**Chunk Interval:** 1 day
**Retention:** 7 days

**Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `time` | TIMESTAMPTZ | Timestamp of reading |
| `device_id` | UUID | Device identifier |
| `serial_number` | TEXT | Device serial number |
| `protocol_id` | TEXT | Protocol used (modbus, mqtt, etc) |
| `device_type` | TEXT | Device type (deye_hybrid, etc) |
| `data` | JSONB | Full JSON telemetry payload |
| `poll_duration_ms` | FLOAT | Time taken to poll device |

**Use case:** Short-term audit trail, debugging, raw data recovery

## Dual Write Architecture

The telemetry ingestion system uses a **dual write** strategy to optimize both real-time performance and long-term analytics:

### Write Path
```
Device JSON → Telemetry Parser → ┬→ telemetry_raw (normalized metrics)
                                  └→ device_telemetry (full JSON, optional)
                                  └→ Redis (real-time pub/sub)
```

### Telemetry Parser

Converts device-specific JSON into normalized metrics:

**Example - Deye Hybrid Inverter:**
```json
{
  "power": {"pv_total_w": 2500.0, "load_w": 1800.0},
  "battery": {"soc_pct": 75.0},
  "energy_today": {"pv_kwh": 15.5}
}
```

↓ Parsed into normalized metrics ↓

| time | device_id | metric_name | metric_value | unit | source |
|------|-----------|-------------|--------------|------|--------|
| 2024-01-15 12:30 | uuid-123 | pv_total_w | 2500.0 | W | power |
| 2024-01-15 12:30 | uuid-123 | load_w | 1800.0 | W | power |
| 2024-01-15 12:30 | uuid-123 | battery_soc_pct | 75.0 | % | battery |
| 2024-01-15 12:30 | uuid-123 | pv_energy_today_kwh | 15.5 | kWh | energy |

**Benefits:**
- **telemetry_raw**: Optimized for TimescaleDB aggregations and time-series queries
- **device_telemetry**: Preserves original data for debugging (7-day retention)
- **Redis**: Real-time dashboard updates without database queries

### Supported Parsers

| Device Type | Parser | Metrics Extracted |
|-------------|--------|-------------------|
| `deye_hybrid` | DeyeHybridParser | ~50 metrics (power, battery, energy, grid, temp) |

*More parsers can be added by extending the TelemetryParser base class*

## Continuous Aggregates

TimescaleDB automatically maintains these pre-computed aggregations in a hierarchical structure. The repository automatically selects the best table based on query time range.

### Auto-Selection Logic

| Time Range | Table Used | Bucket Interval | Query Optimization |
|------------|------------|-----------------|-------------------|
| Last 24 hours | `telemetry_raw` | 5 minutes - 1 hour | Highest resolution |
| Last 90 days | `telemetry_raw` | 1 hour | Recent detailed data |
| Last 1 year | `telemetry_hourly` | 1 hour - 1 day | Intraday analysis |
| Last 3 years | `telemetry_daily` | 1 day | Daily trends |
| Last 5 years | `telemetry_monthly` | 1 month | Monthly summaries |
| 5+ years | `telemetry_yearly` | 1 year | Long-term trends |

### telemetry_hourly
**Use case:** Intraday analysis, daily/weekly charts
**Retention:** 1 year
**Refresh Policy:** Every hour

Aggregated metrics:
| Metric | Description |
|--------|-------------|
| `avg_value` | Average of values in 1-hour bucket |
| `min_value` | Minimum value |
| `max_value` | Maximum value |
| `stddev_value` | Standard deviation |
| `sample_count` | Number of raw readings |
| `good_samples` | Readings with 'good' quality |
| `total_energy` | Sum of energy metrics (kWh) |

### telemetry_daily
**Use case:** Daily/weekly/monthly reports
**Retention:** 3 years
**Refresh Policy:** Daily at 1 AM

Aggregated from hourly:
| Metric | Description |
|--------|-------------|
| `avg_value` | Average of hourly averages |
| `min_value` | Minimum from hourly minimums |
| `max_value` | Maximum from hourly maximums |
| `daily_energy` | Sum of hourly energy totals |
| `total_samples` | Sum of hourly sample counts |
| `good_samples` | Sum of hourly good samples |
| `availability_pct` | (good_samples / total_samples) × 100 |

### telemetry_monthly
**Use case:** Monthly/quarterly/yearly reports
**Retention:** 5 years
**Refresh Policy:** Daily

Aggregated from daily:
| Metric | Description |
|--------|-------------|
| `avg_value` | Average of daily averages |
| `min_value` | Minimum from daily minimums |
| `max_value` | Maximum from daily maximums |
| `monthly_energy` | Sum of daily energy totals |
| `availability_pct` | Monthly availability percentage |
| `days_with_data` | Count of days with telemetry |

### telemetry_yearly
**Use case:** Multi-year trends, lifetime statistics
**Retention:** Forever
**Refresh Policy:** Weekly

Aggregated from monthly:
| Metric | Description |
|--------|-------------|
| `avg_value` | Average of monthly averages |
| `min_value` | Minimum from monthly minimums |
| `max_value` | Maximum from monthly maximums |
| `yearly_energy` | Sum of monthly energy totals |
| `availability_pct` | Yearly availability percentage |
| `months_with_data` | Count of months with telemetry |

## Standard Metrics

The `metric_definitions` table defines 50+ standard metrics:

### Inverter Metrics
| Metric Name | Unit | Description |
|-------------|------|-------------|
| `power_ac` | kW | AC power output |
| `power_dc` | kW | DC power input |
| `voltage_dc` | V | DC input voltage |
| `voltage_ac` | V | AC output voltage |
| `voltage_l1/l2/l3` | V | Phase voltages |
| `current_dc` | A | DC input current |
| `current_ac` | A | AC output current |
| `current_l1/l2/l3` | A | Phase currents |
| `energy_total` | kWh | Lifetime energy (cumulative) |
| `energy_today` | kWh | Today's energy |
| `frequency` | Hz | Grid frequency |
| `power_factor` | - | Power factor (-1 to 1) |
| `temperature_internal` | °C | Internal temperature |
| `mppt_voltage` | V | MPPT tracker voltage |
| `mppt_current` | A | MPPT tracker current |
| `status` | - | Operating status (string) |
| `error_code` | - | Error code if any |

### Battery Metrics
| Metric Name | Unit | Description |
|-------------|------|-------------|
| `battery_soc` | % | State of charge |
| `battery_soh` | % | State of health |
| `battery_voltage` | V | Battery voltage |
| `battery_current` | A | Current (+charging, -discharging) |
| `battery_power` | kW | Power (+charging, -discharging) |
| `battery_cycles` | - | Cycle count (cumulative) |
| `temperature_battery` | °C | Battery temperature |

### Meter Metrics
| Metric Name | Unit | Description |
|-------------|------|-------------|
| `power_active` | kW | Active power |
| `power_reactive` | kVAR | Reactive power |
| `power_apparent` | kVA | Apparent power |
| `energy_import` | kWh | Energy imported (cumulative) |
| `energy_export` | kWh | Energy exported (cumulative) |

### Weather Station Metrics
| Metric Name | Unit | Description |
|-------------|------|-------------|
| `irradiance` | W/m² | Global horizontal irradiance |
| `irradiance_poa` | W/m² | Plane of array irradiance |
| `temperature_ambient` | °C | Ambient temperature |
| `temperature_module` | °C | Module temperature |
| `wind_speed` | m/s | Wind speed |
| `wind_direction` | ° | Wind direction |
| `humidity` | % | Relative humidity |
| `pressure` | hPa | Atmospheric pressure |
| `rainfall` | mm | Rainfall amount |

## Data Quality Indicators

| Quality | Description | Use Case |
|---------|-------------|----------|
| `good` | Normal reading | Standard data |
| `interpolated` | Interpolated value | Gap filling |
| `estimated` | Estimated value | Manual entry |
| `suspect` | Out of range | Needs review |
| `missing` | Gap marker | Data gaps |
| `invalid` | Corrupt data | Excluded from aggregates |

## Retention Policies

Automatic data lifecycle management with hierarchical aggregation for 5-year retention:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      DATA RETENTION TIMELINE                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  device_telemetry  ├──┤                             (7 days, audit)      │
│                                                                           │
│  telemetry_raw     ├──────────────────────────┤    (90 days, compressed) │
│                                                                           │
│  telemetry_hourly  ├─────────────────────────────────────┤  (1 year)     │
│                                                                           │
│  telemetry_daily   ├────────────────────────────────────────────────────┤
│                                                                (3 years)  │
│                                                                           │
│  telemetry_monthly ├───────────────────────────────────────────────────────┤
│                                                                  (5 years) │
│                                                                           │
│  telemetry_yearly  ├──────────────────────────────────────────────────────▶
│                                                             (forever)     │
│                                                                           │
│  device_events     ├────────────────────────────────┤         (1 year)   │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Storage Efficiency

The tiered retention strategy provides 97% storage reduction compared to keeping all raw data for 5 years:

| Strategy | 5-Year Storage | Notes |
|----------|----------------|-------|
| Raw data only | ~1.8 TB | Uncompressed, all samples |
| Raw + Compression | ~180 GB | 10x compression ratio |
| **Tiered aggregates** | **~50 GB** | 90 days raw + aggregates |

**Benefits:**
- Full-resolution data for recent queries (90 days)
- Hourly resolution for the last year
- Daily resolution for 3 years
- Monthly summaries for 5 years
- Yearly trends forever
- 97% less storage than keeping 5 years of raw data

## Compression

Compression significantly reduces storage for older data:

| Table | Compress After | Expected Ratio |
|-------|---------------|----------------|
| `telemetry_raw` | 7 days | 10-20x |
| `device_events` | 30 days | 5-10x |

**Compression Strategy:**
- Segment by: `device_id, metric_name` (queries are usually per-device)
- Order by: `time DESC` (most queries access recent data first)

## Query Patterns

### Auto-Selection Query (Recommended)

The repository automatically selects the optimal table based on time range:

```python
# Python using repository
from app.infrastructure.database.repositories.telemetry_repository import TelemetryRepository

# Automatically uses the best table
energy_data = await telemetry_repo.get_site_energy_chart(
    site_id=site_id,
    start_time=start,
    end_time=end,
    bucket_interval="auto"  # Automatically selects best bucket size
)
```

**What happens:**
- Last 24 hours → Uses `telemetry_raw` with 5-minute buckets
- Last 7 days → Uses `telemetry_raw` with 1-hour buckets
- Last 90 days → Uses `telemetry_raw` with 1-hour buckets
- Last 1 year → Uses `telemetry_hourly` with 1-day buckets
- Last 3 years → Uses `telemetry_daily` with 1-day buckets
- Last 5 years → Uses `telemetry_monthly` with 1-month buckets
- 5+ years → Uses `telemetry_yearly` with 1-year buckets

### Real-time Dashboard (Raw Data)
```sql
SELECT device_id, metric_name, metric_value, time
FROM telemetry_raw
WHERE site_id = :site_id
  AND time > NOW() - INTERVAL '5 minutes'
ORDER BY time DESC;
```

### Daily Power Chart (Hourly Aggregate)
```sql
SELECT bucket, device_id, avg_value
FROM telemetry_hourly
WHERE site_id = :site_id
  AND metric_name = 'pv_total_w'
  AND bucket > NOW() - INTERVAL '24 hours'
ORDER BY bucket;
```

### Monthly Energy Summary (Daily Aggregate)
```sql
SELECT
    time_bucket('1 day', bucket) AS day,
    SUM(daily_energy) AS energy_kwh
FROM telemetry_daily
WHERE site_id = :site_id
  AND metric_name LIKE '%energy%'
  AND bucket > NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1;
```

### Yearly Trend (Monthly Aggregate)
```sql
SELECT
    bucket AS month,
    avg_value,
    monthly_energy
FROM telemetry_monthly
WHERE site_id = :site_id
  AND metric_name = 'pv_total_w'
  AND bucket >= DATE_TRUNC('year', NOW()) - INTERVAL '5 years'
ORDER BY bucket;
```

## Tags Usage

The `tags` JSONB column allows flexible filtering:

```json
// MPPT-specific reading
{
  "mppt_id": 1,
  "string_id": "A"
}

// 3-phase measurement
{
  "phase": "L1"
}

// Multiple inverters aggregated
{
  "aggregation": "site_total"
}
```

**Query by tag:**
```sql
SELECT * FROM telemetry_raw
WHERE tags->>'mppt_id' = '1'
  AND metric_name = 'mppt_voltage';
```

## Device Commands

Remote control commands stored in `device_commands`:

| Command Type | Description | Parameters |
|--------------|-------------|------------|
| `set_power_limit` | Limit power output | `{"limit_kw": 50.0}` |
| `restart` | Restart device | `{}` |
| `update_firmware` | Update firmware | `{"version": "1.2.3", "url": "..."}` |
| `set_time` | Sync device time | `{"timestamp": "..."}` |
| `clear_errors` | Clear error codes | `{}` |
| `enable_export` | Enable grid export | `{"enabled": true}` |

**Command Status Flow:**
```
pending → sent → acknowledged → completed
                            └→ failed
                            └→ timeout
```

## Helper Functions

### get_latest_metric(device_id, metric_name)
Returns the most recent value for a metric.

### get_metrics_interpolated(device_id, metric_name, start, end, interval)
Returns values with linear interpolation for missing points.

### calculate_energy_produced(device_id, start, end)
Calculates energy produced in a time range (handles counter resets).

### get_site_status_summary(site_id)
Returns current status of all devices at a site.

## Performance Optimization

### Chunk Size
- **telemetry_raw:** 1 hour (optimized for "last few hours" queries)
- **device_events:** 1 day (lower volume, broader time range queries)

### Indexes
```sql
-- Primary access patterns
(device_id, time DESC)      -- Per-device queries
(site_id, time DESC)        -- Per-site queries
(metric_name, time DESC)    -- Metric-specific queries

-- Combination patterns
(device_id, metric_name, time DESC)  -- Specific metric per device

-- Partial indexes
WHERE time > NOW() - INTERVAL '1 hour'  -- Recent data queries
WHERE metric_name = 'energy_total'      -- Energy calculations
```

## Integration with System A

### Data Flow: System B → System A

1. **Real-time:** Device snapshots pushed via Redis Pub/Sub
2. **Hourly:** Aggregation worker syncs hourly summaries
3. **Daily:** Daily summary pushed at end of day
4. **Monthly:** Monthly summary generated on 1st of month

### Sync Tables
| System B | System A |
|----------|----------|
| `telemetry_5min` | `device_telemetry_snapshot` |
| `telemetry_hourly` | `telemetry_hourly_summary` |
| `telemetry_daily` | `telemetry_daily_summary` |
| Monthly aggregation | `telemetry_monthly_summary` |

## Storage Estimates

For a typical installation with 100 devices, 10 metrics each, 1-minute interval:

| Data | Records/Day | Size/Day | Size/Month |
|------|-------------|----------|------------|
| Raw (uncompressed) | 1.44M | ~200 MB | ~6 GB |
| Raw (compressed) | 1.44M | ~15 MB | ~450 MB |
| 5-min aggregates | 288K | ~40 MB | ~1.2 GB |
| Hourly aggregates | 24K | ~3 MB | ~90 MB |
| Daily aggregates | 1K | ~150 KB | ~4.5 MB |

**With retention policies:**
- 90-day raw + 5-year daily ≈ 50 GB per 100 devices

## Migration Commands

```bash
# Connect to TimescaleDB
psql -h localhost -p 5432 -U solarhub -d telemetry

# Check TimescaleDB version
SELECT timescaledb_version();

# View hypertable info
SELECT * FROM timescaledb_information.hypertables;

# View chunk info
SELECT * FROM timescaledb_information.chunks
WHERE hypertable_name = 'telemetry_raw';

# View continuous aggregate info
SELECT * FROM timescaledb_information.continuous_aggregates;

# View compression status
SELECT * FROM timescaledb_information.compression_settings;

# Manually compress chunks older than 7 days
SELECT compress_chunk(chunk)
FROM show_chunks('telemetry_raw', older_than => INTERVAL '7 days') AS chunk;

# View retention policies
SELECT * FROM timescaledb_information.jobs
WHERE proc_name = 'policy_retention';

# Manually run retention
CALL run_job(:job_id);
```

## Monitoring Queries

### Ingestion Rate
```sql
SELECT
    time_bucket('1 minute', time) AS minute,
    COUNT(*) AS records
FROM telemetry_raw
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY 1
ORDER BY 1 DESC;
```

### Chunk Statistics
```sql
SELECT
    chunk_name,
    range_start,
    range_end,
    is_compressed,
    pg_size_pretty(total_bytes) AS size
FROM timescaledb_information.chunks
WHERE hypertable_name = 'telemetry_raw'
ORDER BY range_start DESC
LIMIT 20;
```

### Data Quality Summary
```sql
SELECT
    quality,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) AS percentage
FROM telemetry_raw
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY quality;
```
