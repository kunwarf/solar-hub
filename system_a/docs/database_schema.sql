-- ============================================================================
-- Solar Hub - System A Database Schema
-- Platform & Monitoring Backend
-- PostgreSQL 14+ with asyncpg driver
-- ============================================================================

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

-- User roles for system-wide permissions
CREATE TYPE user_role AS ENUM (
    'super_admin',  -- Full system access
    'owner',        -- Organization owner
    'admin',        -- Organization admin
    'manager',      -- Site manager
    'viewer',       -- Read-only access
    'installer'     -- Device installation access
);

-- Organization member roles
CREATE TYPE org_member_role AS ENUM (
    'owner',
    'admin',
    'manager',
    'viewer',
    'installer'
);

-- Site operational status
CREATE TYPE site_status AS ENUM (
    'active',           -- Normal operation
    'inactive',         -- Temporarily disabled
    'maintenance',      -- Under maintenance
    'decommissioned'    -- Permanently offline
);

-- Device types supported by the platform
CREATE TYPE device_type AS ENUM (
    'inverter',         -- Solar inverter
    'meter',            -- Energy meter
    'battery',          -- Battery storage
    'weather_station',  -- Weather monitoring
    'sensor',           -- Generic sensor
    'gateway'           -- Communication gateway
);

-- Device connection status
CREATE TYPE device_status AS ENUM (
    'online',       -- Connected and reporting
    'offline',      -- Not responding
    'error',        -- Error state
    'maintenance',  -- Under maintenance
    'unknown'       -- Status not determined
);

-- Communication protocols
CREATE TYPE protocol_type AS ENUM (
    'modbus_tcp',   -- Modbus over TCP/IP
    'modbus_rtu',   -- Modbus RTU (serial)
    'mqtt',         -- MQTT protocol
    'http',         -- HTTP/REST API
    'custom'        -- Custom protocol
);

-- Alert severity levels
CREATE TYPE alert_severity AS ENUM (
    'info',         -- Informational
    'warning',      -- Warning - attention needed
    'critical'      -- Critical - immediate action required
);

-- Alert status lifecycle
CREATE TYPE alert_status AS ENUM (
    'active',       -- Alert is active
    'acknowledged', -- User acknowledged
    'resolved',     -- Issue resolved
    'expired'       -- Auto-expired
);


-- ============================================================================
-- USERS TABLE
-- ============================================================================

CREATE TABLE users (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Authentication
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,

    -- Profile
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,

    -- Role & Status
    role user_role NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,

    -- Verification & Reset tokens
    verification_token VARCHAR(255),
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMPTZ,

    -- Activity tracking
    last_login_at TIMESTAMPTZ,

    -- User preferences (JSON)
    -- Structure: {
    --   "language": "en",
    --   "timezone": "Asia/Karachi",
    --   "currency": "PKR",
    --   "notifications": {
    --     "email": true,
    --     "sms": false,
    --     "push": true
    --   },
    --   "dashboard": {
    --     "default_view": "overview",
    --     "refresh_interval": 30
    --   }
    -- }
    preferences JSONB,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT chk_users_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Indexes
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_phone ON users (phone) WHERE phone IS NOT NULL;
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_active ON users (is_active) WHERE is_active = TRUE;

COMMENT ON TABLE users IS 'User accounts for the Solar Hub platform';
COMMENT ON COLUMN users.preferences IS 'User preferences stored as JSON (language, timezone, notifications)';


-- ============================================================================
-- ORGANIZATIONS TABLE
-- ============================================================================

CREATE TABLE organizations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic info
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,

    -- Ownership
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Branding
    logo_url VARCHAR(500),
    website VARCHAR(255),

    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'active',

    -- Organization settings (JSON)
    -- Structure: {
    --   "billing": {
    --     "default_currency": "PKR",
    --     "default_tariff": "commercial"
    --   },
    --   "notifications": {
    --     "admin_emails": ["admin@example.com"],
    --     "alert_escalation": true
    --   },
    --   "features": {
    --     "ai_enabled": true,
    --     "billing_simulation": true
    --   }
    -- }
    settings JSONB,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT uq_organizations_slug UNIQUE (slug),
    CONSTRAINT chk_organizations_slug CHECK (slug ~* '^[a-z0-9-]+$')
);

-- Indexes
CREATE INDEX idx_organizations_slug ON organizations (slug);
CREATE INDEX idx_organizations_owner ON organizations (owner_id);
CREATE INDEX idx_organizations_status ON organizations (status);

COMMENT ON TABLE organizations IS 'Organizations/companies using the platform';
COMMENT ON COLUMN organizations.slug IS 'URL-friendly unique identifier';


-- ============================================================================
-- ORGANIZATION MEMBERS TABLE (Junction table)
-- ============================================================================

CREATE TABLE organization_members (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Role within organization
    role org_member_role NOT NULL DEFAULT 'viewer',

    -- Invitation tracking
    invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
    invitation_token VARCHAR(255),
    invitation_expires TIMESTAMPTZ,
    invitation_accepted BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at TIMESTAMPTZ,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT uq_org_member UNIQUE (organization_id, user_id)
);

-- Indexes
CREATE INDEX idx_org_members_org ON organization_members (organization_id);
CREATE INDEX idx_org_members_user ON organization_members (user_id);
CREATE INDEX idx_org_members_role ON organization_members (role);
CREATE INDEX idx_org_members_pending ON organization_members (invitation_accepted)
    WHERE invitation_accepted = FALSE;

COMMENT ON TABLE organization_members IS 'Many-to-many relationship between users and organizations';


-- ============================================================================
-- SITES TABLE
-- ============================================================================

CREATE TABLE sites (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Basic info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status site_status NOT NULL DEFAULT 'active',

    -- Location - Address (JSON)
    -- Structure: {
    --   "street": "123 Main St",
    --   "city": "Lahore",
    --   "state": "Punjab",
    --   "postal_code": "54000",
    --   "country": "Pakistan"
    -- }
    address JSONB,

    -- Geographic coordinates
    latitude NUMERIC(10, 8),   -- -90 to 90
    longitude NUMERIC(11, 8),  -- -180 to 180

    -- Timezone (IANA format)
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Karachi',

    -- Site configuration (JSON)
    -- Structure: {
    --   "system_capacity_kw": 100.0,
    --   "panel_count": 200,
    --   "panel_wattage": 500,
    --   "inverter_capacity_kw": 100.0,
    --   "battery_capacity_kwh": 50.0,
    --   "grid_connected": true,
    --   "net_metering_enabled": true,
    --   "disco_provider": "lesco",
    --   "tariff_category": "commercial_b2",
    --   "installation_date": "2024-01-15",
    --   "warranty_expiry": "2034-01-15"
    -- }
    configuration JSONB,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

-- Indexes
CREATE INDEX idx_sites_org ON sites (organization_id);
CREATE INDEX idx_sites_status ON sites (status);
CREATE INDEX idx_sites_location ON sites (latitude, longitude);
CREATE INDEX idx_sites_timezone ON sites (timezone);

-- GIN index for JSON queries on configuration
CREATE INDEX idx_sites_config ON sites USING GIN (configuration);

COMMENT ON TABLE sites IS 'Solar installation sites';
COMMENT ON COLUMN sites.configuration IS 'Site configuration including capacity, panels, inverters, and DISCO info';
COMMENT ON COLUMN sites.address IS 'Physical address stored as JSON';


-- ============================================================================
-- DEVICES TABLE
-- ============================================================================

CREATE TABLE devices (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Basic info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    device_type device_type NOT NULL,

    -- Hardware info
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    serial_number VARCHAR(100) NOT NULL,
    firmware_version VARCHAR(50),

    -- Communication
    protocol protocol_type,

    -- Connection configuration (JSON)
    -- Structure varies by protocol:
    -- Modbus TCP: {
    --   "host": "192.168.1.100",
    --   "port": 502,
    --   "slave_id": 1,
    --   "timeout_seconds": 5
    -- }
    -- MQTT: {
    --   "broker": "mqtt.example.com",
    --   "port": 1883,
    --   "topic_prefix": "solar/site1/inv1",
    --   "client_id": "device-123"
    -- }
    connection_config JSONB,

    -- Status
    status device_status NOT NULL DEFAULT 'unknown',
    last_seen_at TIMESTAMPTZ,
    last_error TEXT,

    -- Additional metadata (JSON)
    -- Structure: {
    --   "rated_power_kw": 50.0,
    --   "mppt_count": 2,
    --   "phases": 3,
    --   "commissioning_date": "2024-01-15"
    -- }
    metadata JSONB,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT uq_devices_serial UNIQUE (serial_number)
);

-- Indexes
CREATE INDEX idx_devices_site ON devices (site_id);
CREATE INDEX idx_devices_org ON devices (organization_id);
CREATE INDEX idx_devices_type ON devices (device_type);
CREATE INDEX idx_devices_status ON devices (status);
CREATE INDEX idx_devices_serial ON devices (serial_number);
CREATE INDEX idx_devices_last_seen ON devices (last_seen_at DESC);

-- Partial index for online devices
CREATE INDEX idx_devices_online ON devices (site_id, last_seen_at)
    WHERE status = 'online';

COMMENT ON TABLE devices IS 'Physical devices (inverters, meters, batteries, etc.)';
COMMENT ON COLUMN devices.connection_config IS 'Protocol-specific connection parameters';


-- ============================================================================
-- ALERT RULES TABLE
-- ============================================================================

CREATE TABLE alert_rules (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE CASCADE,  -- NULL = all sites

    -- Basic info
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Alert condition (JSON)
    -- Structure: {
    --   "metric": "power_output",
    --   "operator": "lt",  -- gt, lt, eq, gte, lte, neq
    --   "threshold": 10.0,
    --   "duration_seconds": 300,
    --   "device_type": "inverter"  -- optional filter
    -- }
    condition JSONB NOT NULL,

    -- Severity
    severity alert_severity NOT NULL DEFAULT 'warning',

    -- Notification channels (array)
    -- Values: email, sms, push, webhook, in_app
    notification_channels VARCHAR(50)[] NOT NULL DEFAULT ARRAY['in_app'],

    -- Behavior settings
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    cooldown_minutes INTEGER NOT NULL DEFAULT 15,
    auto_resolve BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_trigger BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_resolve BOOLEAN NOT NULL DEFAULT TRUE,
    escalation_minutes INTEGER,  -- NULL = no escalation

    -- Tracking
    last_triggered_at TIMESTAMPTZ,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT chk_cooldown CHECK (cooldown_minutes >= 1 AND cooldown_minutes <= 1440),
    CONSTRAINT chk_escalation CHECK (escalation_minutes IS NULL OR (escalation_minutes >= 1 AND escalation_minutes <= 1440))
);

-- Indexes
CREATE INDEX idx_alert_rules_org ON alert_rules (organization_id);
CREATE INDEX idx_alert_rules_site ON alert_rules (site_id);
CREATE INDEX idx_alert_rules_active ON alert_rules (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_alert_rules_severity ON alert_rules (severity);

-- GIN index for condition JSON queries
CREATE INDEX idx_alert_rules_condition ON alert_rules USING GIN (condition);

COMMENT ON TABLE alert_rules IS 'Rules that define when alerts should be triggered';
COMMENT ON COLUMN alert_rules.condition IS 'JSON condition defining metric, operator, threshold, and duration';
COMMENT ON COLUMN alert_rules.site_id IS 'NULL means rule applies to all sites in the organization';


-- ============================================================================
-- ALERTS TABLE
-- ============================================================================

CREATE TABLE alerts (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    rule_id UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE SET NULL,

    -- Alert info
    severity alert_severity NOT NULL DEFAULT 'warning',
    status alert_status NOT NULL DEFAULT 'active',
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,

    -- Metric data at trigger time
    metric_name VARCHAR(100),
    metric_value DOUBLE PRECISION,
    threshold_value DOUBLE PRECISION,

    -- Lifecycle timestamps
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Notification tracking (array of "channel:timestamp" strings)
    notifications_sent VARCHAR(255)[] NOT NULL DEFAULT ARRAY[]::VARCHAR[],

    -- Escalation
    escalated BOOLEAN NOT NULL DEFAULT FALSE,
    escalated_at TIMESTAMPTZ,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

-- Indexes
CREATE INDEX idx_alerts_rule ON alerts (rule_id);
CREATE INDEX idx_alerts_org ON alerts (organization_id);
CREATE INDEX idx_alerts_site ON alerts (site_id);
CREATE INDEX idx_alerts_device ON alerts (device_id);
CREATE INDEX idx_alerts_status ON alerts (status);
CREATE INDEX idx_alerts_severity ON alerts (severity);
CREATE INDEX idx_alerts_triggered ON alerts (triggered_at DESC);

-- Composite indexes for common queries
CREATE INDEX idx_alerts_status_severity ON alerts (status, severity);
CREATE INDEX idx_alerts_org_active ON alerts (organization_id, status)
    WHERE status IN ('active', 'acknowledged');

-- Partial index for unescalated active alerts (for escalation worker)
CREATE INDEX idx_alerts_needs_escalation ON alerts (triggered_at)
    WHERE status = 'active' AND escalated = FALSE;

COMMENT ON TABLE alerts IS 'Individual alert instances triggered by rules';
COMMENT ON COLUMN alerts.notifications_sent IS 'Array tracking sent notifications (channel:timestamp format)';


-- ============================================================================
-- TARIFF PLANS TABLE
-- ============================================================================

CREATE TABLE tariff_plans (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- DISCO (Distribution Company) and category
    disco_provider VARCHAR(50) NOT NULL,  -- lesco, fesco, iesco, etc.
    category VARCHAR(100) NOT NULL,       -- residential_protected, commercial_a1, etc.
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Validity period
    effective_from DATE NOT NULL,
    effective_to DATE,  -- NULL = currently active

    -- Rates structure (JSON)
    -- Structure: {
    --   "energy_charge_per_kwh": "25.00",
    --   "slabs": [
    --     {"min_units": 0, "max_units": 100, "rate_per_kwh": "7.74", "fixed_charges": "0"},
    --     {"min_units": 101, "max_units": 200, "rate_per_kwh": "10.06", "fixed_charges": "0"},
    --     {"min_units": 201, "max_units": 300, "rate_per_kwh": "12.15", "fixed_charges": "0"},
    --     {"min_units": 301, "max_units": 700, "rate_per_kwh": "19.21", "fixed_charges": "0"},
    --     {"min_units": 701, "max_units": null, "rate_per_kwh": "25.72", "fixed_charges": "0"}
    --   ],
    --   "peak_rate_per_kwh": "30.00",
    --   "off_peak_rate_per_kwh": "18.00",
    --   "fixed_charges_per_month": "150.00",
    --   "meter_rent": "25.00",
    --   "fuel_price_adjustment": "3.50",
    --   "quarterly_tariff_adjustment": "1.20",
    --   "electricity_duty_percent": "1.5",
    --   "gst_percent": "17",
    --   "tv_fee": "35",
    --   "export_rate_per_kwh": "19.32",
    --   "demand_charge_per_kw": "400.00"
    -- }
    rates JSONB NOT NULL,

    -- Features
    supports_net_metering BOOLEAN NOT NULL DEFAULT TRUE,
    supports_tou BOOLEAN NOT NULL DEFAULT FALSE,

    -- Metadata
    source_url VARCHAR(500),  -- URL to official NEPRA tariff document
    notes TEXT,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

-- Indexes
CREATE INDEX idx_tariff_plans_disco ON tariff_plans (disco_provider);
CREATE INDEX idx_tariff_plans_category ON tariff_plans (category);
CREATE INDEX idx_tariff_plans_effective_from ON tariff_plans (effective_from);
CREATE INDEX idx_tariff_disco_category ON tariff_plans (disco_provider, category);
CREATE INDEX idx_tariff_active ON tariff_plans (disco_provider, category, effective_from, effective_to);

-- GIN index for rates JSON queries
CREATE INDEX idx_tariff_plans_rates ON tariff_plans USING GIN (rates);

COMMENT ON TABLE tariff_plans IS 'Electricity tariff plans for Pakistan DISCOs (LESCO, FESCO, etc.)';
COMMENT ON COLUMN tariff_plans.disco_provider IS 'Pakistan DISCO: lesco, fesco, iesco, gepco, mepco, pesco, hesco, sepco, qesco, tesco, kelectric';
COMMENT ON COLUMN tariff_plans.category IS 'Tariff category: residential_protected, residential_unprotected, commercial_a1-a3, industrial_b1-b4, agricultural, etc.';
COMMENT ON COLUMN tariff_plans.rates IS 'JSON structure containing slab rates, TOU rates, fixed charges, and additional surcharges';


-- ============================================================================
-- BILLING SIMULATIONS TABLE
-- ============================================================================

CREATE TABLE billing_simulations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    tariff_plan_id UUID REFERENCES tariff_plans(id) ON DELETE SET NULL,

    -- Billing period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Energy consumption data
    energy_consumed_kwh NUMERIC(12, 3) NOT NULL DEFAULT 0,
    energy_generated_kwh NUMERIC(12, 3) NOT NULL DEFAULT 0,
    energy_exported_kwh NUMERIC(12, 3) NOT NULL DEFAULT 0,
    energy_imported_kwh NUMERIC(12, 3) NOT NULL DEFAULT 0,

    -- Peak demand (for industrial tariffs)
    peak_demand_kw NUMERIC(10, 2),

    -- Bill breakdown (JSON)
    -- Structure: {
    --   "energy_charges": "5000.00",
    --   "slab_breakdown": [
    --     {"slab": "0-100", "units": 100, "rate": "7.74", "amount": "774.00"},
    --     {"slab": "101-200", "units": 100, "rate": "10.06", "amount": "1006.00"},
    --     ...
    --   ],
    --   "fixed_charges": "150.00",
    --   "meter_rent": "25.00",
    --   "fuel_price_adjustment": "350.00",
    --   "quarterly_tariff_adjustment": "120.00",
    --   "electricity_duty": "75.00",
    --   "gst": "850.00",
    --   "tv_fee": "35.00",
    --   "export_credit": "500.00",
    --   "demand_charges": "0.00",
    --   "subtotal": "5500.00",
    --   "total_taxes": "960.00",
    --   "total_bill": "6460.00"
    -- }
    bill_breakdown JSONB NOT NULL DEFAULT '{}',

    -- Savings analysis (JSON)
    -- Structure: {
    --   "bill_without_solar": "10000.00",
    --   "bill_with_solar": "6460.00",
    --   "total_savings": "3540.00",
    --   "savings_percent": "35.4",
    --   "export_income": "500.00",
    --   "co2_avoided_kg": "250.00",
    --   "trees_equivalent": "12.5"
    -- }
    savings_breakdown JSONB NOT NULL DEFAULT '{}',

    -- Totals (convenience fields for querying)
    estimated_bill_pkr NUMERIC(12, 2) NOT NULL DEFAULT 0,
    estimated_savings_pkr NUMERIC(12, 2) NOT NULL DEFAULT 0,

    -- Status
    is_actual BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE if based on actual meter readings
    notes TEXT,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT chk_billing_period CHECK (period_end >= period_start),
    CONSTRAINT chk_billing_energy CHECK (
        energy_consumed_kwh >= 0 AND
        energy_generated_kwh >= 0 AND
        energy_exported_kwh >= 0 AND
        energy_imported_kwh >= 0
    )
);

-- Indexes
CREATE INDEX idx_billing_sim_site ON billing_simulations (site_id);
CREATE INDEX idx_billing_sim_tariff ON billing_simulations (tariff_plan_id);
CREATE INDEX idx_billing_sim_period_start ON billing_simulations (period_start);
CREATE INDEX idx_billing_sim_period_end ON billing_simulations (period_end);
CREATE INDEX idx_billing_site_period ON billing_simulations (site_id, period_start, period_end);
CREATE INDEX idx_billing_period ON billing_simulations (period_start, period_end);

-- GIN indexes for JSON queries
CREATE INDEX idx_billing_sim_breakdown ON billing_simulations USING GIN (bill_breakdown);
CREATE INDEX idx_billing_sim_savings ON billing_simulations USING GIN (savings_breakdown);

COMMENT ON TABLE billing_simulations IS 'Simulated electricity bills based on consumption and tariff plans';
COMMENT ON COLUMN billing_simulations.tariff_plan_id IS 'Reference to tariff plan used; NULL if custom calculation';
COMMENT ON COLUMN billing_simulations.bill_breakdown IS 'Detailed bill breakdown including slab charges, taxes, and adjustments';
COMMENT ON COLUMN billing_simulations.savings_breakdown IS 'Savings analysis comparing bill with/without solar generation';
COMMENT ON COLUMN billing_simulations.is_actual IS 'TRUE if based on actual meter readings, FALSE if simulated/estimated';


-- Triggers for billing tables
CREATE TRIGGER trg_tariff_plans_updated_at
    BEFORE UPDATE ON tariff_plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_tariff_plans_version
    BEFORE UPDATE ON tariff_plans
    FOR EACH ROW EXECUTE FUNCTION increment_version();

CREATE TRIGGER trg_billing_simulations_updated_at
    BEFORE UPDATE ON billing_simulations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_billing_simulations_version
    BEFORE UPDATE ON billing_simulations
    FOR EACH ROW EXECUTE FUNCTION increment_version();


-- ============================================================================
-- REPORT SCHEDULES TABLE
-- ============================================================================

CREATE TABLE report_schedules (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ownership
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Schedule definition
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Report template
    report_type VARCHAR(50) NOT NULL,  -- performance_summary, energy_generation, billing_summary, etc.
    parameters JSONB NOT NULL DEFAULT '{}',
    format VARCHAR(20) NOT NULL DEFAULT 'pdf',  -- pdf, excel, csv, html

    -- Scheduling
    frequency VARCHAR(20) NOT NULL DEFAULT 'monthly',  -- once, daily, weekly, monthly, quarterly, yearly

    -- Time settings
    run_time TIME NOT NULL DEFAULT '06:00:00',
    day_of_week INTEGER,  -- 0=Monday, 6=Sunday (for weekly)
    day_of_month INTEGER,  -- 1-28 (for monthly)

    -- Timezone
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Karachi',

    -- Active period
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    start_date DATE,
    end_date DATE,

    -- Delivery configuration (JSON)
    -- Structure: {
    --   "method": "email",
    --   "recipients": [{"email": "user@example.com", "name": "User Name"}],
    --   "webhook_url": null,
    --   "email_subject_template": "Monthly Performance Report - {month}"
    -- }
    delivery_config JSONB NOT NULL DEFAULT '{}',

    -- Tracking
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    last_report_id UUID,

    -- Statistics
    total_runs INTEGER NOT NULL DEFAULT 0,
    successful_runs INTEGER NOT NULL DEFAULT 0,
    failed_runs INTEGER NOT NULL DEFAULT 0,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT chk_schedule_day_of_week CHECK (day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)),
    CONSTRAINT chk_schedule_day_of_month CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 28))
);

-- Indexes
CREATE INDEX idx_schedules_org ON report_schedules (organization_id);
CREATE INDEX idx_schedules_type ON report_schedules (report_type);
CREATE INDEX idx_schedules_active ON report_schedules (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_schedules_next_run ON report_schedules (next_run_at) WHERE is_active = TRUE;
CREATE INDEX idx_schedules_org_active ON report_schedules (organization_id, is_active);

COMMENT ON TABLE report_schedules IS 'Scheduled automatic report generation';
COMMENT ON COLUMN report_schedules.frequency IS 'Report generation frequency: once, daily, weekly, monthly, quarterly, yearly';
COMMENT ON COLUMN report_schedules.delivery_config IS 'How and where to deliver the generated report';


-- ============================================================================
-- REPORTS TABLE
-- ============================================================================

CREATE TABLE reports (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ownership
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Report definition
    report_type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Parameters (JSON)
    -- Structure: {
    --   "site_ids": ["uuid1", "uuid2"],
    --   "device_ids": [],
    --   "date_range": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
    --   "group_by": "day",
    --   "include_charts": true,
    --   "include_raw_data": false,
    --   "include_recommendations": true
    -- }
    parameters JSONB NOT NULL DEFAULT '{}',

    -- Output format
    format VARCHAR(20) NOT NULL DEFAULT 'pdf',

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, generating, completed, failed, cancelled

    -- Generation tracking
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Result
    file_path VARCHAR(500),
    file_size_bytes INTEGER,
    page_count INTEGER,

    -- Error handling
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,

    -- Delivery configuration (JSON)
    delivery_config JSONB NOT NULL DEFAULT '{}',
    delivered_at TIMESTAMPTZ,

    -- Expiration
    expires_at TIMESTAMPTZ,

    -- Schedule reference
    schedule_id UUID REFERENCES report_schedules(id) ON DELETE SET NULL,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT chk_report_retry CHECK (retry_count >= 0 AND retry_count <= max_retries)
);

-- Indexes
CREATE INDEX idx_reports_org ON reports (organization_id);
CREATE INDEX idx_reports_creator ON reports (created_by);
CREATE INDEX idx_reports_type ON reports (report_type);
CREATE INDEX idx_reports_status ON reports (status);
CREATE INDEX idx_reports_schedule ON reports (schedule_id);
CREATE INDEX idx_reports_expires ON reports (expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_reports_org_type ON reports (organization_id, report_type);
CREATE INDEX idx_reports_status_requested ON reports (status, requested_at);
CREATE INDEX idx_reports_org_status ON reports (organization_id, status);

-- Partial index for pending reports (for worker queue)
CREATE INDEX idx_reports_pending ON reports (requested_at)
    WHERE status = 'pending';

COMMENT ON TABLE reports IS 'Generated report instances with status and file location';
COMMENT ON COLUMN reports.status IS 'Report status: pending, generating, completed, failed, cancelled';
COMMENT ON COLUMN reports.parameters IS 'Report parameters including scope, date range, and options';


-- ============================================================================
-- REPORT TEMPLATES TABLE
-- ============================================================================

CREATE TABLE report_templates (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ownership
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Template info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    report_type VARCHAR(50) NOT NULL,

    -- Branding (JSON)
    -- Structure: {
    --   "logo_url": "https://...",
    --   "header_text": "Company Name",
    --   "footer_text": "Confidential",
    --   "color_scheme": {"primary": "#1a73e8", "secondary": "#34a853", "accent": "#ea4335"}
    -- }
    branding JSONB NOT NULL DEFAULT '{}',

    -- Content sections (JSON array)
    -- Structure: [
    --   {"type": "summary", "title": "Executive Summary", "enabled": true},
    --   {"type": "chart", "chart_type": "line", "metric": "energy_generated", "enabled": true},
    --   {"type": "table", "columns": ["date", "energy", "savings"], "enabled": true},
    --   {"type": "text", "content": "Custom disclaimer text", "enabled": true}
    -- ]
    sections JSONB NOT NULL DEFAULT '[]',

    -- Default parameters
    default_parameters JSONB NOT NULL DEFAULT '{}',

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,

    -- Usage tracking
    usage_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

-- Indexes
CREATE INDEX idx_templates_org ON report_templates (organization_id);
CREATE INDEX idx_templates_type ON report_templates (report_type);
CREATE INDEX idx_templates_org_type ON report_templates (organization_id, report_type);
CREATE INDEX idx_templates_org_default ON report_templates (organization_id, is_default);

COMMENT ON TABLE report_templates IS 'Custom report templates with organization branding';
COMMENT ON COLUMN report_templates.branding IS 'Organization branding (logo, colors, header/footer text)';
COMMENT ON COLUMN report_templates.sections IS 'Report sections to include (charts, tables, summaries)';


-- Triggers for report tables
CREATE TRIGGER trg_report_schedules_updated_at
    BEFORE UPDATE ON report_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_report_schedules_version
    BEFORE UPDATE ON report_schedules
    FOR EACH ROW EXECUTE FUNCTION increment_version();

CREATE TRIGGER trg_reports_updated_at
    BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_reports_version
    BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION increment_version();

CREATE TRIGGER trg_report_templates_updated_at
    BEFORE UPDATE ON report_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_report_templates_version
    BEFORE UPDATE ON report_templates
    FOR EACH ROW EXECUTE FUNCTION increment_version();


-- ============================================================================
-- TELEMETRY HOURLY SUMMARY TABLE
-- ============================================================================

CREATE TABLE telemetry_hourly_summary (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,  -- NULL = site-level aggregation

    -- Time bucket (start of hour)
    timestamp_hour TIMESTAMPTZ NOT NULL,

    -- Energy metrics (kWh)
    energy_generated_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_consumed_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_exported_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_imported_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_stored_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_discharged_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Power metrics (kW)
    peak_power_kw DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    peak_power_time TIMESTAMPTZ,
    average_power_kw DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    min_power_kw DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Environmental
    avg_irradiance_w_m2 DOUBLE PRECISION,
    avg_temperature_c DOUBLE PRECISION,
    max_temperature_c DOUBLE PRECISION,
    min_temperature_c DOUBLE PRECISION,

    -- Battery
    avg_battery_soc_percent DOUBLE PRECISION,
    min_battery_soc_percent DOUBLE PRECISION,
    max_battery_soc_percent DOUBLE PRECISION,

    -- Grid
    avg_grid_voltage_v DOUBLE PRECISION,
    avg_grid_frequency_hz DOUBLE PRECISION,
    avg_power_factor DOUBLE PRECISION,

    -- Data quality
    sample_count INTEGER NOT NULL DEFAULT 0,
    data_quality_percent DOUBLE PRECISION NOT NULL DEFAULT 100.0,

    -- Calculated performance metrics
    performance_ratio DOUBLE PRECISION,
    capacity_factor DOUBLE PRECISION,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT uq_hourly_site_device_time UNIQUE (site_id, device_id, timestamp_hour),
    CONSTRAINT chk_hourly_data_quality CHECK (data_quality_percent >= 0.0 AND data_quality_percent <= 100.0)
);

-- Indexes
CREATE INDEX idx_hourly_site ON telemetry_hourly_summary (site_id);
CREATE INDEX idx_hourly_device ON telemetry_hourly_summary (device_id);
CREATE INDEX idx_hourly_timestamp ON telemetry_hourly_summary (timestamp_hour);
CREATE INDEX idx_hourly_site_time ON telemetry_hourly_summary (site_id, timestamp_hour);
CREATE INDEX idx_hourly_device_time ON telemetry_hourly_summary (device_id, timestamp_hour);

COMMENT ON TABLE telemetry_hourly_summary IS 'Hourly aggregated telemetry data for dashboard queries';
COMMENT ON COLUMN telemetry_hourly_summary.device_id IS 'NULL means site-level aggregation (all devices combined)';
COMMENT ON COLUMN telemetry_hourly_summary.timestamp_hour IS 'Start of the hour for this summary';


-- ============================================================================
-- TELEMETRY DAILY SUMMARY TABLE
-- ============================================================================

CREATE TABLE telemetry_daily_summary (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,  -- NULL = site-level aggregation

    -- Date
    summary_date DATE NOT NULL,

    -- Energy metrics (kWh)
    energy_generated_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_consumed_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_exported_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_imported_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_stored_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_discharged_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    net_energy_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,  -- generated - consumed

    -- Power metrics (kW)
    peak_power_kw DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    peak_power_time TIMESTAMPTZ,
    average_power_kw DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Time-based metrics
    sunshine_hours DOUBLE PRECISION NOT NULL DEFAULT 0.0,  -- Hours with significant generation
    production_hours DOUBLE PRECISION NOT NULL DEFAULT 0.0,  -- Hours with any generation
    grid_outage_minutes INTEGER NOT NULL DEFAULT 0,

    -- Environmental
    avg_irradiance_w_m2 DOUBLE PRECISION,
    total_irradiation_kwh_m2 DOUBLE PRECISION,  -- Daily solar irradiation
    avg_temperature_c DOUBLE PRECISION,
    max_temperature_c DOUBLE PRECISION,
    min_temperature_c DOUBLE PRECISION,
    avg_humidity_percent DOUBLE PRECISION,

    -- Battery
    battery_cycles DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_battery_soc_percent DOUBLE PRECISION,

    -- Grid
    avg_grid_voltage_v DOUBLE PRECISION,
    avg_power_factor DOUBLE PRECISION,

    -- Performance
    performance_ratio DOUBLE PRECISION,
    capacity_factor DOUBLE PRECISION,
    specific_yield_kwh_kwp DOUBLE PRECISION,  -- kWh per kWp installed

    -- Environmental impact
    co2_avoided_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Financial (PKR)
    estimated_revenue_pkr DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    estimated_savings_pkr DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Data quality
    hours_with_data INTEGER NOT NULL DEFAULT 0,
    data_completeness_percent DOUBLE PRECISION NOT NULL DEFAULT 100.0,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT uq_daily_site_device_date UNIQUE (site_id, device_id, summary_date),
    CONSTRAINT chk_daily_data_completeness CHECK (data_completeness_percent >= 0.0 AND data_completeness_percent <= 100.0),
    CONSTRAINT chk_daily_hours_with_data CHECK (hours_with_data >= 0 AND hours_with_data <= 24)
);

-- Indexes
CREATE INDEX idx_daily_site ON telemetry_daily_summary (site_id);
CREATE INDEX idx_daily_device ON telemetry_daily_summary (device_id);
CREATE INDEX idx_daily_date ON telemetry_daily_summary (summary_date);
CREATE INDEX idx_daily_site_date ON telemetry_daily_summary (site_id, summary_date);
CREATE INDEX idx_daily_device_date ON telemetry_daily_summary (device_id, summary_date);

COMMENT ON TABLE telemetry_daily_summary IS 'Daily aggregated telemetry data for historical analysis and reporting';
COMMENT ON COLUMN telemetry_daily_summary.net_energy_kwh IS 'Net energy = generated - consumed (positive = net producer)';
COMMENT ON COLUMN telemetry_daily_summary.specific_yield_kwh_kwp IS 'Energy yield per kWp of installed capacity';


-- ============================================================================
-- TELEMETRY MONTHLY SUMMARY TABLE
-- ============================================================================

CREATE TABLE telemetry_monthly_summary (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,  -- NULL = site-level aggregation

    -- Month identifier
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,

    -- Energy metrics (kWh)
    energy_generated_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_consumed_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_exported_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_imported_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_stored_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_discharged_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    net_energy_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Power metrics
    peak_power_kw DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    peak_power_date DATE,
    average_daily_generation_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Time metrics
    total_sunshine_hours DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_production_hours DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_grid_outage_minutes INTEGER NOT NULL DEFAULT 0,

    -- Environmental
    avg_temperature_c DOUBLE PRECISION,
    total_irradiation_kwh_m2 DOUBLE PRECISION,

    -- Performance
    performance_ratio DOUBLE PRECISION,
    capacity_factor DOUBLE PRECISION,
    specific_yield_kwh_kwp DOUBLE PRECISION,

    -- Expected vs actual
    expected_generation_kwh DOUBLE PRECISION,
    generation_variance_percent DOUBLE PRECISION,  -- (actual - expected) / expected * 100

    -- Environmental impact
    co2_avoided_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    trees_equivalent DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Financial (PKR)
    estimated_revenue_pkr DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    estimated_savings_pkr DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Data quality
    days_with_data INTEGER NOT NULL DEFAULT 0,
    data_completeness_percent DOUBLE PRECISION NOT NULL DEFAULT 100.0,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT uq_monthly_site_device_period UNIQUE (site_id, device_id, year, month),
    CONSTRAINT chk_monthly_month CHECK (month >= 1 AND month <= 12),
    CONSTRAINT chk_monthly_year CHECK (year >= 2020 AND year <= 2100),
    CONSTRAINT chk_monthly_data_completeness CHECK (data_completeness_percent >= 0.0 AND data_completeness_percent <= 100.0)
);

-- Indexes
CREATE INDEX idx_monthly_site ON telemetry_monthly_summary (site_id);
CREATE INDEX idx_monthly_device ON telemetry_monthly_summary (device_id);
CREATE INDEX idx_monthly_period ON telemetry_monthly_summary (year, month);
CREATE INDEX idx_monthly_site_period ON telemetry_monthly_summary (site_id, year, month);
CREATE INDEX idx_monthly_device_period ON telemetry_monthly_summary (device_id, year, month);

COMMENT ON TABLE telemetry_monthly_summary IS 'Monthly aggregated telemetry data for long-term analysis and billing';
COMMENT ON COLUMN telemetry_monthly_summary.generation_variance_percent IS 'Percentage variance from expected: (actual - expected) / expected * 100';
COMMENT ON COLUMN telemetry_monthly_summary.trees_equivalent IS 'Equivalent number of trees for CO2 offset visualization';


-- ============================================================================
-- DEVICE TELEMETRY SNAPSHOT TABLE (Latest readings)
-- ============================================================================

CREATE TABLE device_telemetry_snapshot (
    -- Device ID is primary key (one snapshot per device)
    device_id UUID PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,

    -- Site reference
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,

    -- Timestamp of reading
    timestamp TIMESTAMPTZ NOT NULL,

    -- Power readings
    current_power_kw DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    power_limit_kw DOUBLE PRECISION,

    -- Energy totals
    energy_today_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_lifetime_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- DC side (for inverters)
    dc_voltage_v DOUBLE PRECISION,
    dc_current_a DOUBLE PRECISION,
    dc_power_kw DOUBLE PRECISION,

    -- AC side
    ac_voltage_v DOUBLE PRECISION,
    ac_current_a DOUBLE PRECISION,
    ac_frequency_hz DOUBLE PRECISION,
    power_factor DOUBLE PRECISION,

    -- 3-phase measurements
    voltage_l1_v DOUBLE PRECISION,
    voltage_l2_v DOUBLE PRECISION,
    voltage_l3_v DOUBLE PRECISION,
    current_l1_a DOUBLE PRECISION,
    current_l2_a DOUBLE PRECISION,
    current_l3_a DOUBLE PRECISION,

    -- Temperature
    internal_temperature_c DOUBLE PRECISION,
    ambient_temperature_c DOUBLE PRECISION,

    -- Battery specific
    battery_soc_percent DOUBLE PRECISION,
    battery_voltage_v DOUBLE PRECISION,
    battery_current_a DOUBLE PRECISION,
    battery_power_kw DOUBLE PRECISION,
    battery_temperature_c DOUBLE PRECISION,
    charging_state VARCHAR(50),  -- charging, discharging, idle

    -- Grid/Meter specific
    grid_import_power_kw DOUBLE PRECISION,
    grid_export_power_kw DOUBLE PRECISION,

    -- Weather station specific
    irradiance_w_m2 DOUBLE PRECISION,
    wind_speed_m_s DOUBLE PRECISION,
    humidity_percent DOUBLE PRECISION,

    -- Status
    operating_state VARCHAR(100),
    error_code VARCHAR(50),
    warning_code VARCHAR(50),

    -- Raw data for debugging
    raw_data JSONB,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT chk_snapshot_battery_soc CHECK (battery_soc_percent IS NULL OR (battery_soc_percent >= 0.0 AND battery_soc_percent <= 100.0)),
    CONSTRAINT chk_snapshot_power_factor CHECK (power_factor IS NULL OR (power_factor >= -1.0 AND power_factor <= 1.0))
);

-- Indexes
CREATE INDEX idx_snapshot_site ON device_telemetry_snapshot (site_id);
CREATE INDEX idx_snapshot_timestamp ON device_telemetry_snapshot (timestamp);
CREATE INDEX idx_snapshot_site_timestamp ON device_telemetry_snapshot (site_id, timestamp);

COMMENT ON TABLE device_telemetry_snapshot IS 'Latest telemetry readings per device for real-time dashboard display';
COMMENT ON COLUMN device_telemetry_snapshot.device_id IS 'Primary key - one snapshot per device, updated on each reading';
COMMENT ON COLUMN device_telemetry_snapshot.raw_data IS 'Raw device data for debugging and protocol-specific fields';


-- ============================================================================
-- TRIGGERS FOR TELEMETRY TABLES
-- ============================================================================

-- updated_at triggers for tables that have it
CREATE TRIGGER trg_daily_summary_updated_at
    BEFORE UPDATE ON telemetry_daily_summary
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_monthly_summary_updated_at
    BEFORE UPDATE ON telemetry_monthly_summary
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_snapshot_updated_at
    BEFORE UPDATE ON device_telemetry_snapshot
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View: Active alerts summary by organization
CREATE VIEW v_active_alerts_summary AS
SELECT
    organization_id,
    COUNT(*) FILTER (WHERE status = 'active') AS active_count,
    COUNT(*) FILTER (WHERE status = 'acknowledged') AS acknowledged_count,
    COUNT(*) FILTER (WHERE severity = 'critical' AND status IN ('active', 'acknowledged')) AS critical_count,
    COUNT(*) FILTER (WHERE severity = 'warning' AND status IN ('active', 'acknowledged')) AS warning_count,
    COUNT(*) FILTER (WHERE severity = 'info' AND status IN ('active', 'acknowledged')) AS info_count
FROM alerts
WHERE status IN ('active', 'acknowledged')
GROUP BY organization_id;

COMMENT ON VIEW v_active_alerts_summary IS 'Summary of active alerts per organization';


-- View: Device status summary by site
CREATE VIEW v_device_status_summary AS
SELECT
    site_id,
    organization_id,
    COUNT(*) AS total_devices,
    COUNT(*) FILTER (WHERE status = 'online') AS online_count,
    COUNT(*) FILTER (WHERE status = 'offline') AS offline_count,
    COUNT(*) FILTER (WHERE status = 'error') AS error_count,
    COUNT(*) FILTER (WHERE status = 'maintenance') AS maintenance_count
FROM devices
GROUP BY site_id, organization_id;

COMMENT ON VIEW v_device_status_summary IS 'Device status counts per site';


-- View: Site capacity overview
CREATE VIEW v_site_capacity AS
SELECT
    s.id AS site_id,
    s.organization_id,
    s.name AS site_name,
    s.status,
    (s.configuration->>'system_capacity_kw')::NUMERIC AS system_capacity_kw,
    (s.configuration->>'panel_count')::INTEGER AS panel_count,
    (s.configuration->>'inverter_capacity_kw')::NUMERIC AS inverter_capacity_kw,
    (s.configuration->>'battery_capacity_kwh')::NUMERIC AS battery_capacity_kwh,
    s.configuration->>'disco_provider' AS disco_provider,
    COUNT(d.id) AS device_count
FROM sites s
LEFT JOIN devices d ON d.site_id = s.id
GROUP BY s.id;

COMMENT ON VIEW v_site_capacity IS 'Site configuration and capacity overview';


-- View: Latest telemetry snapshot summary by site
CREATE VIEW v_site_telemetry_live AS
SELECT
    s.id AS site_id,
    s.name AS site_name,
    s.organization_id,
    COALESCE(SUM(dts.current_power_kw), 0) AS total_current_power_kw,
    COALESCE(SUM(dts.energy_today_kwh), 0) AS total_energy_today_kwh,
    COUNT(dts.device_id) AS devices_reporting,
    MIN(dts.timestamp) AS oldest_reading,
    MAX(dts.timestamp) AS newest_reading
FROM sites s
LEFT JOIN device_telemetry_snapshot dts ON dts.site_id = s.id
GROUP BY s.id, s.name, s.organization_id;

COMMENT ON VIEW v_site_telemetry_live IS 'Real-time telemetry summary per site from latest device snapshots';


-- View: Daily energy summary by site (last 30 days)
CREATE VIEW v_site_daily_energy AS
SELECT
    site_id,
    summary_date,
    SUM(energy_generated_kwh) AS total_generated_kwh,
    SUM(energy_consumed_kwh) AS total_consumed_kwh,
    SUM(energy_exported_kwh) AS total_exported_kwh,
    SUM(energy_imported_kwh) AS total_imported_kwh,
    SUM(net_energy_kwh) AS total_net_energy_kwh,
    AVG(performance_ratio) AS avg_performance_ratio,
    SUM(co2_avoided_kg) AS total_co2_avoided_kg
FROM telemetry_daily_summary
WHERE device_id IS NULL  -- Site-level aggregation only
  AND summary_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY site_id, summary_date
ORDER BY site_id, summary_date DESC;

COMMENT ON VIEW v_site_daily_energy IS 'Daily energy totals per site for the last 30 days';


-- View: Monthly performance comparison
CREATE VIEW v_monthly_performance AS
SELECT
    tms.site_id,
    s.name AS site_name,
    tms.year,
    tms.month,
    tms.energy_generated_kwh,
    tms.expected_generation_kwh,
    tms.generation_variance_percent,
    tms.performance_ratio,
    tms.capacity_factor,
    tms.co2_avoided_kg,
    tms.estimated_savings_pkr,
    tms.data_completeness_percent
FROM telemetry_monthly_summary tms
JOIN sites s ON s.id = tms.site_id
WHERE tms.device_id IS NULL  -- Site-level only
ORDER BY tms.site_id, tms.year DESC, tms.month DESC;

COMMENT ON VIEW v_monthly_performance IS 'Monthly performance metrics and financial impact per site';


-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_organization_members_updated_at
    BEFORE UPDATE ON organization_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_sites_updated_at
    BEFORE UPDATE ON sites
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_alert_rules_updated_at
    BEFORE UPDATE ON alert_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_alerts_updated_at
    BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- Function: Increment version on update
CREATE OR REPLACE FUNCTION increment_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply version increment triggers
CREATE TRIGGER trg_users_version
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION increment_version();

CREATE TRIGGER trg_organizations_version
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION increment_version();

CREATE TRIGGER trg_sites_version
    BEFORE UPDATE ON sites
    FOR EACH ROW EXECUTE FUNCTION increment_version();

CREATE TRIGGER trg_devices_version
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION increment_version();

CREATE TRIGGER trg_alert_rules_version
    BEFORE UPDATE ON alert_rules
    FOR EACH ROW EXECUTE FUNCTION increment_version();

CREATE TRIGGER trg_alerts_version
    BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION increment_version();


-- ============================================================================
-- SAMPLE DATA (Development Only)
-- ============================================================================

-- Uncomment below to insert sample data for development/testing

/*
-- Sample super admin user (password: admin123)
INSERT INTO users (id, email, password_hash, first_name, last_name, role, is_active, is_verified)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'admin@solarhub.pk',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G1VOd5x/lkLnXu',  -- bcrypt hash
    'System',
    'Admin',
    'super_admin',
    TRUE,
    TRUE
);

-- Sample organization
INSERT INTO organizations (id, name, slug, owner_id, status)
VALUES (
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
    'Demo Solar Company',
    'demo-solar',
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'active'
);

-- Sample site
INSERT INTO sites (id, organization_id, name, status, timezone, configuration)
VALUES (
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33',
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
    'Lahore Office Rooftop',
    'active',
    'Asia/Karachi',
    '{
        "system_capacity_kw": 50.0,
        "panel_count": 100,
        "panel_wattage": 500,
        "inverter_capacity_kw": 50.0,
        "grid_connected": true,
        "net_metering_enabled": true,
        "disco_provider": "lesco",
        "tariff_category": "commercial_b2"
    }'::jsonb
);
*/


-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
