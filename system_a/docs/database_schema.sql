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
