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
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  telemetry_raw   │    │  device_events   │    │ device_commands  │
│   (Hypertable)   │    │   (Hypertable)   │    │     (Table)      │
│ 1-hour chunks    │    │  1-day chunks    │    │                  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         │
         │ Continuous Aggregates
         ▼
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ┌────────────┐    ┌────────────┐    ┌────────────┐            │
│   │telemetry   │    │telemetry   │    │telemetry   │            │
│   │  _5min     │───▶│  _hourly   │───▶│  _daily    │            │
│   │ (7 days)   │    │ (90 days)  │    │ (5 years)  │            │
│   └────────────┘    └────────────┘    └────────────┘            │
│                                                                  │
│   Real-time         Daily charts      Monthly/Yearly             │
│   dashboard                           reports                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Tables Summary

| Table | Type | Description | Retention |
|-------|------|-------------|-----------|
| `device_registry` | Regular | Device connection & auth info | Permanent |
| `telemetry_raw` | Hypertable | Raw telemetry readings | 90 days |
| `device_events` | Hypertable | Device events & errors | 1 year |
| `device_commands` | Regular | Command queue for devices | Permanent |
| `metric_definitions` | Regular | Standard metric definitions | Permanent |
| `ingestion_batches` | Regular | Ingestion tracking | Permanent |
| `telemetry_5min` | Continuous Aggregate | 5-minute aggregates | 7 days |
| `telemetry_hourly` | Continuous Aggregate | Hourly aggregates | 90 days |
| `telemetry_daily` | Continuous Aggregate | Daily aggregates | 5 years |

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

## Continuous Aggregates

TimescaleDB automatically maintains these pre-computed aggregations:

### telemetry_5min
**Use case:** Real-time dashboards, live charts

| Metric | Description |
|--------|-------------|
| `avg_value` | Average of values in 5-min bucket |
| `min_value` | Minimum value |
| `max_value` | Maximum value |
| `last_value` | Last recorded value |
| `sample_count` | Number of readings |
| `good_count` | Readings with 'good' quality |

**Refresh:** Every 5 minutes

### telemetry_hourly
**Use case:** Daily charts, intraday analysis

Additional metrics:
| Metric | Description |
|--------|-------------|
| `first_value` | First value in bucket |
| `delta_value` | last_value - first_value (for cumulative metrics) |

**Refresh:** Every hour

### telemetry_daily
**Use case:** Monthly/yearly reports, long-term trends

**Refresh:** Once per day

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

Automatic data lifecycle management:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA RETENTION TIMELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  telemetry_5min    ├────────┤                   (7 days)        │
│                                                                  │
│  telemetry_raw     ├──────────────────────────┤ (90 days)       │
│  telemetry_hourly  ├──────────────────────────┤ (90 days)       │
│                                                                  │
│  device_events     ├────────────────────────────────────┤       │
│                                                     (1 year)     │
│                                                                  │
│  telemetry_daily   ├────────────────────────────────────────────┤
│                                                        (5 years) │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

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

### Real-time Dashboard (Last 5 minutes)
```sql
SELECT device_id, metric_name, metric_value, time
FROM telemetry_raw
WHERE site_id = :site_id
  AND time > NOW() - INTERVAL '5 minutes'
ORDER BY time DESC;
```

### Daily Power Chart (24 hours)
```sql
SELECT bucket, device_id, avg_value
FROM telemetry_hourly
WHERE site_id = :site_id
  AND metric_name = 'power_ac'
  AND bucket > NOW() - INTERVAL '24 hours'
ORDER BY bucket;
```

### Monthly Energy Summary
```sql
SELECT
    date_trunc('day', bucket) AS day,
    SUM(delta_value) AS energy_kwh
FROM telemetry_daily
WHERE site_id = :site_id
  AND metric_name = 'energy_total'
  AND bucket > NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1;
```

### Current Power by Site
```sql
SELECT * FROM v_site_current_power
WHERE site_id = :site_id;
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
