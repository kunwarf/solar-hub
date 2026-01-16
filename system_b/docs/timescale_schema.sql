-- ============================================================================
-- Solar Hub - System B TimescaleDB Schema
-- Communication & Telemetry Backend
-- TimescaleDB 2.x on PostgreSQL 14+
-- ============================================================================

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_stat_statements for query analysis (optional)
-- CREATE EXTENSION IF NOT EXISTS pg_stat_statements;


-- ============================================================================
-- ENUM TYPES
-- ============================================================================

-- Device types (mirrors System A)
CREATE TYPE device_type AS ENUM (
    'inverter',
    'meter',
    'battery',
    'weather_station',
    'sensor',
    'gateway'
);

-- Telemetry data quality indicators
CREATE TYPE data_quality AS ENUM (
    'good',           -- Normal reading
    'interpolated',   -- Interpolated from nearby values
    'estimated',      -- Estimated value
    'suspect',        -- Suspicious reading (out of range)
    'missing',        -- Gap marker
    'invalid'         -- Invalid/corrupt data
);

-- Device connection status
CREATE TYPE connection_status AS ENUM (
    'connected',
    'disconnected',
    'connecting',
    'error',
    'timeout'
);

-- Command execution status
CREATE TYPE command_status AS ENUM (
    'pending',
    'sent',
    'acknowledged',
    'completed',
    'failed',
    'timeout',
    'cancelled'
);


-- ============================================================================
-- DEVICE REGISTRY TABLE
-- Lightweight device info for System B (main registry in System A)
-- ============================================================================

CREATE TABLE device_registry (
    -- Primary key
    device_id UUID PRIMARY KEY,

    -- References (from System A)
    site_id UUID NOT NULL,
    organization_id UUID NOT NULL,

    -- Device info
    device_type device_type NOT NULL,
    serial_number VARCHAR(100) NOT NULL UNIQUE,

    -- Authentication
    auth_token_hash VARCHAR(255),
    token_expires_at TIMESTAMPTZ,

    -- Connection state
    connection_status connection_status NOT NULL DEFAULT 'disconnected',
    last_connected_at TIMESTAMPTZ,
    last_disconnected_at TIMESTAMPTZ,
    reconnect_count INTEGER DEFAULT 0,

    -- Protocol configuration (cached from System A)
    protocol VARCHAR(50),
    connection_config JSONB,

    -- Polling configuration
    polling_interval_seconds INTEGER DEFAULT 60,
    last_polled_at TIMESTAMPTZ,
    next_poll_at TIMESTAMPTZ,

    -- Metadata
    metadata JSONB,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ  -- Last sync with System A
);

-- Indexes
CREATE INDEX idx_device_registry_site ON device_registry (site_id);
CREATE INDEX idx_device_registry_org ON device_registry (organization_id);
CREATE INDEX idx_device_registry_status ON device_registry (connection_status);
CREATE INDEX idx_device_registry_next_poll ON device_registry (next_poll_at)
    WHERE connection_status = 'connected';

COMMENT ON TABLE device_registry IS 'Lightweight device registry for telemetry collection (main registry in System A)';


-- ============================================================================
-- RAW TELEMETRY HYPERTABLE
-- Main time-series table for all device readings
-- ============================================================================

CREATE TABLE telemetry_raw (
    -- Time column (required for hypertable)
    time TIMESTAMPTZ NOT NULL,

    -- Device identification
    device_id UUID NOT NULL,
    site_id UUID NOT NULL,

    -- Metric identification
    metric_name VARCHAR(100) NOT NULL,
    metric_value DOUBLE PRECISION,

    -- For string/enum values (status, states)
    metric_value_str VARCHAR(255),

    -- Data quality indicator
    quality data_quality NOT NULL DEFAULT 'good',

    -- Unit of measurement
    unit VARCHAR(20),

    -- Source information
    source VARCHAR(50),  -- 'device', 'calculated', 'manual'

    -- Additional context
    tags JSONB,  -- Flexible tags for filtering

    -- Raw protocol data (for debugging)
    raw_value BYTEA,  -- Original bytes from device

    -- Ingestion tracking
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed BOOLEAN NOT NULL DEFAULT FALSE
);

-- Convert to hypertable with 1-hour chunks
-- Chunk size optimized for typical query patterns (last 24-48 hours)
SELECT create_hypertable(
    'telemetry_raw',
    'time',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Primary indexes for hypertable
CREATE INDEX idx_telemetry_raw_device_time ON telemetry_raw (device_id, time DESC);
CREATE INDEX idx_telemetry_raw_site_time ON telemetry_raw (site_id, time DESC);
CREATE INDEX idx_telemetry_raw_metric ON telemetry_raw (metric_name, time DESC);
CREATE INDEX idx_telemetry_raw_device_metric ON telemetry_raw (device_id, metric_name, time DESC);

-- Index for unprocessed records (aggregation worker)
CREATE INDEX idx_telemetry_raw_unprocessed ON telemetry_raw (time)
    WHERE processed = FALSE;

-- GIN index for tag queries
CREATE INDEX idx_telemetry_raw_tags ON telemetry_raw USING GIN (tags);

COMMENT ON TABLE telemetry_raw IS 'Raw time-series telemetry data from all devices';
COMMENT ON COLUMN telemetry_raw.metric_name IS 'Standardized metric name (e.g., power_output, voltage_dc, temperature)';
COMMENT ON COLUMN telemetry_raw.tags IS 'Flexible key-value tags for filtering (e.g., mppt_id, phase)';


-- ============================================================================
-- STANDARD METRIC NAMES
-- Reference table for standardized metric naming
-- ============================================================================

CREATE TABLE metric_definitions (
    metric_name VARCHAR(100) PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    unit VARCHAR(20) NOT NULL,
    data_type VARCHAR(20) NOT NULL,  -- 'float', 'integer', 'string', 'boolean'
    device_types device_type[] NOT NULL,  -- Applicable device types
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    aggregation_method VARCHAR(20) DEFAULT 'avg',  -- 'avg', 'sum', 'min', 'max', 'last'
    is_cumulative BOOLEAN DEFAULT FALSE,  -- True for counters like energy_total
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert standard metrics
INSERT INTO metric_definitions (metric_name, display_name, description, unit, data_type, device_types, min_value, max_value, aggregation_method, is_cumulative) VALUES
-- Power metrics
('power_ac', 'AC Power', 'AC power output', 'kW', 'float', ARRAY['inverter']::device_type[], 0, 1000, 'avg', FALSE),
('power_dc', 'DC Power', 'DC power input', 'kW', 'float', ARRAY['inverter']::device_type[], 0, 1000, 'avg', FALSE),
('power_active', 'Active Power', 'Active power', 'kW', 'float', ARRAY['inverter', 'meter']::device_type[], -1000, 1000, 'avg', FALSE),
('power_reactive', 'Reactive Power', 'Reactive power', 'kVAR', 'float', ARRAY['inverter', 'meter']::device_type[], -1000, 1000, 'avg', FALSE),
('power_apparent', 'Apparent Power', 'Apparent power', 'kVA', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 1000, 'avg', FALSE),

-- Voltage metrics
('voltage_dc', 'DC Voltage', 'DC input voltage', 'V', 'float', ARRAY['inverter']::device_type[], 0, 1500, 'avg', FALSE),
('voltage_ac', 'AC Voltage', 'AC output voltage', 'V', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 500, 'avg', FALSE),
('voltage_l1', 'Voltage L1', 'Phase L1 voltage', 'V', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 500, 'avg', FALSE),
('voltage_l2', 'Voltage L2', 'Phase L2 voltage', 'V', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 500, 'avg', FALSE),
('voltage_l3', 'Voltage L3', 'Phase L3 voltage', 'V', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 500, 'avg', FALSE),
('voltage_ln', 'Voltage L-N', 'Line to neutral voltage', 'V', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 300, 'avg', FALSE),
('voltage_ll', 'Voltage L-L', 'Line to line voltage', 'V', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 500, 'avg', FALSE),

-- Current metrics
('current_dc', 'DC Current', 'DC input current', 'A', 'float', ARRAY['inverter']::device_type[], 0, 100, 'avg', FALSE),
('current_ac', 'AC Current', 'AC output current', 'A', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 1000, 'avg', FALSE),
('current_l1', 'Current L1', 'Phase L1 current', 'A', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 1000, 'avg', FALSE),
('current_l2', 'Current L2', 'Phase L2 current', 'A', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 1000, 'avg', FALSE),
('current_l3', 'Current L3', 'Phase L3 current', 'A', 'float', ARRAY['inverter', 'meter']::device_type[], 0, 1000, 'avg', FALSE),

-- Energy metrics (cumulative counters)
('energy_total', 'Total Energy', 'Lifetime energy produced', 'kWh', 'float', ARRAY['inverter', 'meter']::device_type[], 0, NULL, 'last', TRUE),
('energy_today', 'Today Energy', 'Energy produced today', 'kWh', 'float', ARRAY['inverter']::device_type[], 0, NULL, 'last', FALSE),
('energy_import', 'Energy Import', 'Energy imported from grid', 'kWh', 'float', ARRAY['meter']::device_type[], 0, NULL, 'last', TRUE),
('energy_export', 'Energy Export', 'Energy exported to grid', 'kWh', 'float', ARRAY['meter']::device_type[], 0, NULL, 'last', TRUE),

-- Frequency
('frequency', 'Grid Frequency', 'AC frequency', 'Hz', 'float', ARRAY['inverter', 'meter']::device_type[], 45, 65, 'avg', FALSE),

-- Power factor
('power_factor', 'Power Factor', 'Power factor', '', 'float', ARRAY['inverter', 'meter']::device_type[], -1, 1, 'avg', FALSE),

-- Temperature metrics
('temperature_internal', 'Internal Temp', 'Internal device temperature', '°C', 'float', ARRAY['inverter', 'battery']::device_type[], -40, 100, 'avg', FALSE),
('temperature_ambient', 'Ambient Temp', 'Ambient temperature', '°C', 'float', ARRAY['inverter', 'weather_station']::device_type[], -40, 60, 'avg', FALSE),
('temperature_module', 'Module Temp', 'PV module temperature', '°C', 'float', ARRAY['sensor']::device_type[], -40, 100, 'avg', FALSE),
('temperature_battery', 'Battery Temp', 'Battery temperature', '°C', 'float', ARRAY['battery']::device_type[], -20, 60, 'avg', FALSE),

-- Battery metrics
('battery_soc', 'Battery SOC', 'State of charge', '%', 'float', ARRAY['battery']::device_type[], 0, 100, 'avg', FALSE),
('battery_soh', 'Battery SOH', 'State of health', '%', 'float', ARRAY['battery']::device_type[], 0, 100, 'last', FALSE),
('battery_voltage', 'Battery Voltage', 'Battery voltage', 'V', 'float', ARRAY['battery']::device_type[], 0, 1000, 'avg', FALSE),
('battery_current', 'Battery Current', 'Battery current', 'A', 'float', ARRAY['battery']::device_type[], -500, 500, 'avg', FALSE),
('battery_power', 'Battery Power', 'Battery power (+ charging, - discharging)', 'kW', 'float', ARRAY['battery']::device_type[], -500, 500, 'avg', FALSE),
('battery_cycles', 'Battery Cycles', 'Charge/discharge cycle count', '', 'integer', ARRAY['battery']::device_type[], 0, NULL, 'last', TRUE),

-- Weather station metrics
('irradiance', 'Solar Irradiance', 'Global horizontal irradiance', 'W/m²', 'float', ARRAY['weather_station', 'sensor']::device_type[], 0, 1500, 'avg', FALSE),
('irradiance_poa', 'POA Irradiance', 'Plane of array irradiance', 'W/m²', 'float', ARRAY['sensor']::device_type[], 0, 1500, 'avg', FALSE),
('wind_speed', 'Wind Speed', 'Wind speed', 'm/s', 'float', ARRAY['weather_station']::device_type[], 0, 100, 'avg', FALSE),
('wind_direction', 'Wind Direction', 'Wind direction', '°', 'float', ARRAY['weather_station']::device_type[], 0, 360, 'avg', FALSE),
('humidity', 'Humidity', 'Relative humidity', '%', 'float', ARRAY['weather_station']::device_type[], 0, 100, 'avg', FALSE),
('pressure', 'Pressure', 'Atmospheric pressure', 'hPa', 'float', ARRAY['weather_station']::device_type[], 800, 1200, 'avg', FALSE),
('rainfall', 'Rainfall', 'Rainfall amount', 'mm', 'float', ARRAY['weather_station']::device_type[], 0, NULL, 'sum', FALSE),

-- Status metrics (string values)
('status', 'Device Status', 'Operating status', '', 'string', ARRAY['inverter', 'battery', 'meter']::device_type[], NULL, NULL, 'last', FALSE),
('error_code', 'Error Code', 'Error code if any', '', 'string', ARRAY['inverter', 'battery']::device_type[], NULL, NULL, 'last', FALSE),
('warning_code', 'Warning Code', 'Warning code if any', '', 'string', ARRAY['inverter', 'battery']::device_type[], NULL, NULL, 'last', FALSE),

-- MPPT specific (use tags for mppt_id)
('mppt_voltage', 'MPPT Voltage', 'MPPT tracker voltage', 'V', 'float', ARRAY['inverter']::device_type[], 0, 1500, 'avg', FALSE),
('mppt_current', 'MPPT Current', 'MPPT tracker current', 'A', 'float', ARRAY['inverter']::device_type[], 0, 50, 'avg', FALSE),
('mppt_power', 'MPPT Power', 'MPPT tracker power', 'kW', 'float', ARRAY['inverter']::device_type[], 0, 100, 'avg', FALSE);

COMMENT ON TABLE metric_definitions IS 'Standard metric definitions for consistent data collection and display';


-- ============================================================================
-- CONTINUOUS AGGREGATES
-- Pre-computed aggregations for efficient dashboard queries
-- ============================================================================

-- 5-minute aggregates (for real-time dashboards)
CREATE MATERIALIZED VIEW telemetry_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    device_id,
    site_id,
    metric_name,
    AVG(metric_value) AS avg_value,
    MIN(metric_value) AS min_value,
    MAX(metric_value) AS max_value,
    LAST(metric_value, time) AS last_value,
    COUNT(*) AS sample_count,
    COUNT(*) FILTER (WHERE quality = 'good') AS good_count
FROM telemetry_raw
WHERE metric_value IS NOT NULL
GROUP BY bucket, device_id, site_id, metric_name
WITH NO DATA;

-- Refresh policy: refresh every 5 minutes, keep data up to 2 hours old fresh
SELECT add_continuous_aggregate_policy('telemetry_5min',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

COMMENT ON MATERIALIZED VIEW telemetry_5min IS '5-minute aggregates for real-time dashboard queries';


-- Hourly aggregates (for daily charts)
CREATE MATERIALIZED VIEW telemetry_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    site_id,
    metric_name,
    AVG(metric_value) AS avg_value,
    MIN(metric_value) AS min_value,
    MAX(metric_value) AS max_value,
    FIRST(metric_value, time) AS first_value,
    LAST(metric_value, time) AS last_value,
    COUNT(*) AS sample_count,
    COUNT(*) FILTER (WHERE quality = 'good') AS good_count,
    -- For cumulative metrics, calculate delta
    LAST(metric_value, time) - FIRST(metric_value, time) AS delta_value
FROM telemetry_raw
WHERE metric_value IS NOT NULL
GROUP BY bucket, device_id, site_id, metric_name
WITH NO DATA;

-- Refresh policy: refresh every hour, keep data up to 1 day old fresh
SELECT add_continuous_aggregate_policy('telemetry_hourly',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

COMMENT ON MATERIALIZED VIEW telemetry_hourly IS 'Hourly aggregates for daily chart queries';


-- Daily aggregates (for monthly/yearly charts)
CREATE MATERIALIZED VIEW telemetry_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    device_id,
    site_id,
    metric_name,
    AVG(metric_value) AS avg_value,
    MIN(metric_value) AS min_value,
    MAX(metric_value) AS max_value,
    FIRST(metric_value, time) AS first_value,
    LAST(metric_value, time) AS last_value,
    COUNT(*) AS sample_count,
    COUNT(*) FILTER (WHERE quality = 'good') AS good_count,
    LAST(metric_value, time) - FIRST(metric_value, time) AS delta_value
FROM telemetry_raw
WHERE metric_value IS NOT NULL
GROUP BY bucket, device_id, site_id, metric_name
WITH NO DATA;

-- Refresh policy: refresh daily
SELECT add_continuous_aggregate_policy('telemetry_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

COMMENT ON MATERIALIZED VIEW telemetry_daily IS 'Daily aggregates for monthly/yearly chart queries';


-- ============================================================================
-- DEVICE EVENTS TABLE
-- Captures significant device events (status changes, errors, etc.)
-- ============================================================================

CREATE TABLE device_events (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL,
    site_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- 'status_change', 'error', 'warning', 'connection', 'command'
    event_code VARCHAR(50),
    severity VARCHAR(20) NOT NULL DEFAULT 'info',  -- 'info', 'warning', 'error', 'critical'
    message TEXT,
    details JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID
);

-- Convert to hypertable
SELECT create_hypertable('device_events', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- Indexes
CREATE INDEX idx_device_events_device ON device_events (device_id, time DESC);
CREATE INDEX idx_device_events_site ON device_events (site_id, time DESC);
CREATE INDEX idx_device_events_type ON device_events (event_type, time DESC);
CREATE INDEX idx_device_events_unack ON device_events (time DESC) WHERE acknowledged = FALSE;

COMMENT ON TABLE device_events IS 'Significant device events for monitoring and alerting';


-- ============================================================================
-- DEVICE COMMANDS TABLE
-- Commands sent to devices for remote control
-- ============================================================================

CREATE TABLE device_commands (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Target device
    device_id UUID NOT NULL,
    site_id UUID NOT NULL,

    -- Command details
    command_type VARCHAR(100) NOT NULL,  -- 'set_power_limit', 'restart', 'update_firmware', etc.
    command_params JSONB,

    -- Status tracking
    status command_status NOT NULL DEFAULT 'pending',

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scheduled_at TIMESTAMPTZ,  -- For scheduled commands
    sent_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,  -- Command expires if not executed

    -- Result
    result JSONB,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Audit
    created_by UUID,  -- User who created the command
    priority INTEGER DEFAULT 5  -- 1=highest, 10=lowest
);

-- Indexes
CREATE INDEX idx_device_commands_device ON device_commands (device_id);
CREATE INDEX idx_device_commands_status ON device_commands (status);
CREATE INDEX idx_device_commands_pending ON device_commands (device_id, priority, created_at)
    WHERE status = 'pending';

COMMENT ON TABLE device_commands IS 'Commands queue for remote device control';


-- ============================================================================
-- INGESTION BATCHES TABLE
-- Tracks telemetry ingestion batches for debugging and monitoring
-- ============================================================================

CREATE TABLE ingestion_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source
    source_type VARCHAR(50) NOT NULL,  -- 'mqtt', 'http', 'modbus', 'file'
    source_identifier VARCHAR(255),

    -- Batch info
    device_count INTEGER NOT NULL DEFAULT 0,
    record_count INTEGER NOT NULL DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'processing',  -- 'processing', 'completed', 'failed', 'partial'
    records_inserted INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,

    -- Errors
    errors JSONB,

    -- Performance
    processing_time_ms INTEGER
);

-- Index for monitoring
CREATE INDEX idx_ingestion_batches_status ON ingestion_batches (status, started_at DESC);

COMMENT ON TABLE ingestion_batches IS 'Tracks telemetry ingestion batches for monitoring';


-- ============================================================================
-- DATA RETENTION POLICIES
-- Automatic data cleanup based on age
-- ============================================================================

-- Raw data: Keep for 90 days
SELECT add_retention_policy('telemetry_raw', INTERVAL '90 days', if_not_exists => TRUE);

-- Device events: Keep for 1 year
SELECT add_retention_policy('device_events', INTERVAL '365 days', if_not_exists => TRUE);

-- 5-minute aggregates: Keep for 7 days
SELECT add_retention_policy('telemetry_5min', INTERVAL '7 days', if_not_exists => TRUE);

-- Hourly aggregates: Keep for 90 days
SELECT add_retention_policy('telemetry_hourly', INTERVAL '90 days', if_not_exists => TRUE);

-- Daily aggregates: Keep for 5 years
SELECT add_retention_policy('telemetry_daily', INTERVAL '1825 days', if_not_exists => TRUE);


-- ============================================================================
-- COMPRESSION POLICIES
-- Compress old data to save storage
-- ============================================================================

-- Enable compression on raw telemetry (after 7 days)
ALTER TABLE telemetry_raw SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, metric_name',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('telemetry_raw', INTERVAL '7 days', if_not_exists => TRUE);

-- Enable compression on device events (after 30 days)
ALTER TABLE device_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, event_type',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('device_events', INTERVAL '30 days', if_not_exists => TRUE);


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function: Get latest value for a metric
CREATE OR REPLACE FUNCTION get_latest_metric(
    p_device_id UUID,
    p_metric_name VARCHAR(100)
)
RETURNS TABLE (
    time TIMESTAMPTZ,
    value DOUBLE PRECISION,
    quality data_quality
) AS $$
BEGIN
    RETURN QUERY
    SELECT t.time, t.metric_value, t.quality
    FROM telemetry_raw t
    WHERE t.device_id = p_device_id
      AND t.metric_name = p_metric_name
    ORDER BY t.time DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;


-- Function: Get metrics for a time range with interpolation for missing points
CREATE OR REPLACE FUNCTION get_metrics_interpolated(
    p_device_id UUID,
    p_metric_name VARCHAR(100),
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ,
    p_interval INTERVAL DEFAULT '5 minutes'
)
RETURNS TABLE (
    bucket TIMESTAMPTZ,
    value DOUBLE PRECISION,
    is_interpolated BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH time_series AS (
        SELECT generate_series(
            time_bucket(p_interval, p_start_time),
            time_bucket(p_interval, p_end_time),
            p_interval
        ) AS bucket
    ),
    actual_data AS (
        SELECT
            time_bucket(p_interval, t.time) AS bucket,
            AVG(t.metric_value) AS value
        FROM telemetry_raw t
        WHERE t.device_id = p_device_id
          AND t.metric_name = p_metric_name
          AND t.time >= p_start_time
          AND t.time <= p_end_time
        GROUP BY 1
    )
    SELECT
        ts.bucket,
        COALESCE(
            ad.value,
            -- Linear interpolation for missing values
            (
                SELECT AVG(ad2.value)
                FROM actual_data ad2
                WHERE ad2.bucket BETWEEN ts.bucket - p_interval AND ts.bucket + p_interval
            )
        ) AS value,
        ad.value IS NULL AS is_interpolated
    FROM time_series ts
    LEFT JOIN actual_data ad ON ad.bucket = ts.bucket
    ORDER BY ts.bucket;
END;
$$ LANGUAGE plpgsql;


-- Function: Calculate energy produced in a time range
CREATE OR REPLACE FUNCTION calculate_energy_produced(
    p_device_id UUID,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
)
RETURNS DOUBLE PRECISION AS $$
DECLARE
    v_start_energy DOUBLE PRECISION;
    v_end_energy DOUBLE PRECISION;
BEGIN
    -- Get energy_total at start
    SELECT metric_value INTO v_start_energy
    FROM telemetry_raw
    WHERE device_id = p_device_id
      AND metric_name = 'energy_total'
      AND time <= p_start_time
    ORDER BY time DESC
    LIMIT 1;

    -- Get energy_total at end
    SELECT metric_value INTO v_end_energy
    FROM telemetry_raw
    WHERE device_id = p_device_id
      AND metric_name = 'energy_total'
      AND time <= p_end_time
    ORDER BY time DESC
    LIMIT 1;

    -- Return difference (handle counter resets)
    IF v_end_energy >= v_start_energy THEN
        RETURN v_end_energy - v_start_energy;
    ELSE
        -- Counter reset detected, return end value (approximate)
        RETURN v_end_energy;
    END IF;
END;
$$ LANGUAGE plpgsql;


-- Function: Get device status summary
CREATE OR REPLACE FUNCTION get_site_status_summary(p_site_id UUID)
RETURNS TABLE (
    device_id UUID,
    device_type device_type,
    connection_status connection_status,
    last_reading TIMESTAMPTZ,
    current_power DOUBLE PRECISION,
    energy_today DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dr.device_id,
        dr.device_type,
        dr.connection_status,
        (SELECT MAX(t.time) FROM telemetry_raw t WHERE t.device_id = dr.device_id) AS last_reading,
        (SELECT t.metric_value FROM telemetry_raw t
         WHERE t.device_id = dr.device_id AND t.metric_name = 'power_ac'
         ORDER BY t.time DESC LIMIT 1) AS current_power,
        (SELECT t.metric_value FROM telemetry_raw t
         WHERE t.device_id = dr.device_id AND t.metric_name = 'energy_today'
         ORDER BY t.time DESC LIMIT 1) AS energy_today
    FROM device_registry dr
    WHERE dr.site_id = p_site_id;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View: Current power by site (for dashboard)
CREATE VIEW v_site_current_power AS
SELECT
    dr.site_id,
    SUM(CASE WHEN t.metric_name = 'power_ac' THEN t.metric_value ELSE 0 END) AS total_power_kw,
    COUNT(DISTINCT dr.device_id) FILTER (WHERE dr.connection_status = 'connected') AS devices_online,
    MAX(t.time) AS last_update
FROM device_registry dr
LEFT JOIN LATERAL (
    SELECT metric_name, metric_value, time
    FROM telemetry_raw
    WHERE device_id = dr.device_id
      AND time > NOW() - INTERVAL '5 minutes'
    ORDER BY time DESC
    LIMIT 10
) t ON TRUE
WHERE dr.device_type = 'inverter'
GROUP BY dr.site_id;

COMMENT ON VIEW v_site_current_power IS 'Current power production by site for real-time dashboard';


-- View: Energy production today by site
CREATE VIEW v_site_energy_today AS
SELECT
    dr.site_id,
    SUM(t.metric_value) AS total_energy_today_kwh,
    COUNT(DISTINCT dr.device_id) AS device_count
FROM device_registry dr
JOIN LATERAL (
    SELECT metric_value
    FROM telemetry_raw
    WHERE device_id = dr.device_id
      AND metric_name = 'energy_today'
    ORDER BY time DESC
    LIMIT 1
) t ON TRUE
WHERE dr.device_type = 'inverter'
GROUP BY dr.site_id;

COMMENT ON VIEW v_site_energy_today IS 'Total energy produced today by site';


-- ============================================================================
-- INDEXES FOR COMMON QUERY PATTERNS
-- ============================================================================

-- For "current power" dashboard queries
CREATE INDEX idx_telemetry_raw_recent ON telemetry_raw (device_id, metric_name, time DESC)
    WHERE time > NOW() - INTERVAL '1 hour';

-- For energy calculation queries
CREATE INDEX idx_telemetry_raw_energy ON telemetry_raw (device_id, time DESC)
    WHERE metric_name = 'energy_total';


-- ============================================================================
-- SAMPLE DATA (Development Only)
-- ============================================================================

/*
-- Sample device registration
INSERT INTO device_registry (device_id, site_id, organization_id, device_type, serial_number, protocol)
VALUES (
    'f0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44',
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33',
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
    'inverter',
    'INV-2024-001',
    'modbus_tcp'
);

-- Sample telemetry data
INSERT INTO telemetry_raw (time, device_id, site_id, metric_name, metric_value, unit, quality)
SELECT
    generate_series(
        NOW() - INTERVAL '1 hour',
        NOW(),
        INTERVAL '1 minute'
    ) AS time,
    'f0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44'::UUID,
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33'::UUID,
    'power_ac',
    (random() * 50)::DOUBLE PRECISION,  -- Random power between 0-50 kW
    'kW',
    'good';
*/


-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
