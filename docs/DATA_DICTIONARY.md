# Solar Hub — Data Dictionary

Complete column-level reference for every table, column, constraint, enum, and index across System A (PostgreSQL) and System B (TimescaleDB).

---

## Table of Contents

1. [System A Tables](#1-system-a-tables)
2. [System B Tables](#2-system-b-tables)
3. [Enum Reference](#3-enum-reference)
4. [Domain Value Objects](#4-domain-value-objects)
5. [Index Reference](#5-index-reference)

---

## 1. System A Tables

System A uses PostgreSQL 15+ with SQLAlchemy ORM. All tables inherit from `BaseModel` (UUID PK + `created_at` + `updated_at` + `version`) unless noted otherwise.

### 1.1 `users`

User accounts and authentication.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `email` | `VARCHAR(254)` | NO | — | UNIQUE, indexed |
| `password_hash` | `VARCHAR(255)` | NO | — | — |
| `first_name` | `VARCHAR(100)` | NO | — | — |
| `last_name` | `VARCHAR(100)` | NO | — | — |
| `phone` | `VARCHAR(20)` | YES | `NULL` | indexed |
| `status` | `ENUM(user_status)` | NO | `'pending'` | indexed |
| `role` | `ENUM(user_role)` | NO | `'viewer'` | indexed |
| `email_verified_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `last_login_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `failed_login_attempts` | `INTEGER` | NO | `0` | — |
| `locked_until` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `preferences` | `JSONB` | NO | `{}` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `owned_organizations` → `organizations` (1:N via `owner_id`)
- `memberships` → `organization_members` (1:N via `user_id`)
- `reports` → `reports` (1:N via `created_by`)
- `report_schedules` → `report_schedules` (1:N via `created_by`)
- `report_templates` → `report_templates` (1:N via `created_by`)

**`preferences` JSONB schema:**
```json
{
  "language": "en",
  "timezone": "Asia/Karachi",
  "date_format": "DD/MM/YYYY",
  "time_format": "HH:mm",
  "currency": "PKR",
  "notifications_enabled": true,
  "email_notifications": true,
  "sms_notifications": false,
  "dashboard_refresh_interval": 30
}
```

---

### 1.2 `organizations`

Company or organizational unit.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `name` | `VARCHAR(200)` | NO | — | — |
| `slug` | `VARCHAR(100)` | NO | — | UNIQUE, indexed |
| `description` | `TEXT` | YES | `NULL` | — |
| `owner_id` | `UUID` | NO | — | FK → `users.id`, indexed |
| `status` | `ENUM(organization_status)` | NO | `'active'` | indexed |
| `settings` | `JSONB` | NO | `{}` | — |
| `site_count` | `INTEGER` | NO | `0` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `owner` → `users` (N:1 via `owner_id`)
- `members` → `organization_members` (1:N, cascade delete, eager load)
- `sites` → `sites` (1:N via `org_id`)
- `reports` → `reports` (1:N)
- `report_schedules` → `report_schedules` (1:N)
- `report_templates` → `report_templates` (1:N)

**`settings` JSONB schema:**
```json
{
  "default_timezone": "Asia/Karachi",
  "default_currency": "PKR",
  "default_language": "en",
  "billing_email": "billing@example.com",
  "support_email": "support@example.com",
  "max_sites": 100,
  "max_users": 50,
  "max_devices_per_site": 100,
  "alert_notifications_enabled": true,
  "daily_report_enabled": false,
  "weekly_report_enabled": false
}
```

---

### 1.3 `organization_members`

Many-to-many association between users and organizations.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `organization_id` | `UUID` | NO | — | FK → `organizations.id` CASCADE, indexed |
| `user_id` | `UUID` | NO | — | FK → `users.id` CASCADE, indexed |
| `role` | `ENUM(user_role)` | NO | — | — |
| `status` | `ENUM(membership_status)` | NO | `'pending'` | — |
| `invited_by` | `UUID` | YES | `NULL` | — |
| `invited_at` | `TIMESTAMPTZ` | NO | — | — |
| `accepted_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `organization` → `organizations` (N:1)
- `user` → `users` (N:1)

---

### 1.4 `sites`

Solar installation locations.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `organization_id` | `UUID` | NO | — | FK → `organizations.id` CASCADE, indexed |
| `name` | `VARCHAR(200)` | NO | — | — |
| `timezone` | `VARCHAR(50)` | NO | `'Asia/Karachi'` | — |
| `site_type` | `ENUM(site_type)` | NO | `'residential'` | indexed |
| `status` | `ENUM(site_status)` | NO | `'pending_setup'` | indexed |
| `address` | `JSONB` | NO | — | — |
| `configuration` | `JSONB` | YES | `NULL` | — |
| `device_ids` | `ARRAY(UUID)` | NO | `[]` | — |
| `notes` | `TEXT` | YES | `NULL` | — |
| `contact_name` | `VARCHAR(200)` | YES | `NULL` | — |
| `contact_phone` | `VARCHAR(20)` | YES | `NULL` | — |
| `contact_email` | `VARCHAR(254)` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `organization` → `organizations` (N:1)
- `devices` → `devices` (1:N via `site_id`)
- `billing_simulations` → `billing_simulations` (1:N)

**`address` JSONB schema:**
```json
{
  "street_address": "123 Main St",
  "city": "Lahore",
  "province": "Punjab",
  "country": "Pakistan",
  "postal_code": "54000",
  "district": "Gulberg",
  "area": "Block H",
  "geo_location": {
    "latitude": 31.5204,
    "longitude": 74.3587
  }
}
```

**`configuration` JSONB schema:**
```json
{
  "system_capacity_kw": 10.0,
  "panel_count": 24,
  "panel_wattage": 415,
  "panel_manufacturer": "Longi",
  "panel_model": "LR5-54HPH-415M",
  "inverter_capacity_kw": 10.0,
  "inverter_count": 1,
  "inverter_manufacturer": "Solis",
  "inverter_model": "S6-GR1P10K",
  "battery_capacity_kwh": null,
  "battery_count": 0,
  "battery_manufacturer": null,
  "battery_model": null,
  "grid_connection_type": "on_grid",
  "net_metering_enabled": true,
  "net_metering_capacity_kw": 10.0,
  "sanctioned_load_kw": 5.0,
  "disco_provider": "LESCO",
  "tariff_category": "residential_unprotected",
  "consumer_reference": "01-234-5678901-0",
  "installation_date": "2025-06-15",
  "warranty_expiry": "2035-06-15",
  "installer_company": "SolarCo",
  "tilt_angle": 25.0,
  "azimuth_angle": 180.0,
  "mounting_type": "rooftop"
}
```

---

### 1.5 `devices`

Physical equipment installed at sites (inverters, meters, batteries, etc.).

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `site_id` | `UUID` | NO | — | FK → `sites.id` CASCADE, indexed |
| `organization_id` | `UUID` | NO | — | FK → `organizations.id` CASCADE, indexed |
| `device_type` | `ENUM(device_type)` | NO | — | indexed |
| `name` | `VARCHAR(200)` | NO | — | — |
| `manufacturer` | `VARCHAR(100)` | NO | — | — |
| `model` | `VARCHAR(100)` | NO | — | — |
| `serial_number` | `VARCHAR(100)` | NO | — | UNIQUE, indexed |
| `firmware_version` | `VARCHAR(50)` | YES | `NULL` | — |
| `status` | `ENUM(device_status)` | NO | `'pending'` | indexed |
| `connection_config` | `JSONB` | YES | `NULL` | — |
| `last_seen_at` | `TIMESTAMPTZ` | YES | `NULL` | indexed |
| `last_error_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `last_error_message` | `TEXT` | YES | `NULL` | — |
| `latest_metrics` | `JSONB` | YES | `NULL` | — |
| `metadata` | `JSONB` | NO | `{}` | — |
| `tags` | `ARRAY(VARCHAR)` | NO | `[]` | — |
| `total_messages_received` | `INTEGER` | NO | `0` | — |
| `total_errors` | `INTEGER` | NO | `0` | — |
| `uptime_percentage` | `FLOAT` | NO | `0.0` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `site` → `sites` (N:1)

**`connection_config` JSONB schema:**
```json
{
  "protocol": "modbus_tcp",
  "host": "192.168.1.100",
  "port": 502,
  "slave_id": 1,
  "topic_prefix": null,
  "endpoint": null,
  "username": null,
  "password": null,
  "ssl_enabled": false,
  "polling_interval_seconds": 30,
  "timeout_seconds": 10,
  "retry_attempts": 3,
  "custom_config": null
}
```

**`latest_metrics` JSONB schema:**
```json
{
  "power_output_w": 5200.0,
  "energy_today_kwh": 18.7,
  "energy_total_kwh": 12450.3,
  "voltage_v": 240.5,
  "current_a": 21.6,
  "frequency_hz": 50.01,
  "temperature_c": 42.3,
  "battery_soc_percent": null,
  "battery_power_w": null,
  "grid_power_w": -3200.0,
  "load_power_w": 2000.0,
  "efficiency_percent": 97.2,
  "error_codes": [],
  "recorded_at": "2026-01-28T10:30:00Z"
}
```

---

### 1.6 `alert_rules`

Configurable alert triggers.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `organization_id` | `UUID` | NO | — | FK → `organizations.id` CASCADE, indexed |
| `site_id` | `UUID` | YES | `NULL` | FK → `sites.id` CASCADE, indexed |
| `name` | `VARCHAR(255)` | NO | — | — |
| `description` | `TEXT` | YES | `NULL` | — |
| `condition` | `JSONB` | NO | — | — |
| `severity` | `ENUM(alert_severity)` | NO | `'warning'` | — |
| `notification_channels` | `ARRAY(VARCHAR(50))` | NO | `[]` | — |
| `is_active` | `BOOLEAN` | NO | `true` | — |
| `cooldown_minutes` | `INTEGER` | NO | `15` | — |
| `auto_resolve` | `BOOLEAN` | NO | `true` | — |
| `notify_on_trigger` | `BOOLEAN` | NO | `true` | — |
| `notify_on_resolve` | `BOOLEAN` | NO | `true` | — |
| `escalation_minutes` | `INTEGER` | YES | `NULL` | — |
| `last_triggered_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `alerts` → `alerts` (1:N, cascade delete)

**`condition` JSONB schema:**
```json
{
  "metric": "temperature_internal",
  "operator": "gt",
  "threshold": 85.0,
  "duration_seconds": 300,
  "device_type": "inverter"
}
```

Operator values: `gt`, `lt`, `eq`, `gte`, `lte`, `neq`

---

### 1.7 `alerts`

Active and historical alert instances.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `rule_id` | `UUID` | NO | — | FK → `alert_rules.id` CASCADE, indexed |
| `organization_id` | `UUID` | NO | — | FK → `organizations.id` CASCADE, indexed |
| `site_id` | `UUID` | NO | — | FK → `sites.id` CASCADE, indexed |
| `device_id` | `UUID` | YES | `NULL` | FK → `devices.id` SET NULL, indexed |
| `severity` | `ENUM(alert_severity)` | NO | `'warning'` | — |
| `status` | `ENUM(alert_status)` | NO | `'active'` | indexed |
| `title` | `VARCHAR(255)` | NO | — | — |
| `message` | `TEXT` | NO | — | — |
| `metric_name` | `VARCHAR(100)` | YES | `NULL` | — |
| `metric_value` | `FLOAT` | YES | `NULL` | — |
| `threshold_value` | `FLOAT` | YES | `NULL` | — |
| `triggered_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `acknowledged_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `acknowledged_by` | `UUID` | YES | `NULL` | FK → `users.id` SET NULL |
| `resolved_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `resolved_by` | `UUID` | YES | `NULL` | FK → `users.id` SET NULL |
| `notifications_sent` | `ARRAY(VARCHAR(255))` | NO | `[]` | — |
| `escalated` | `BOOLEAN` | NO | `false` | — |
| `escalated_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `rule` → `alert_rules` (N:1)

---

### 1.8 `telemetry_hourly_summary`

Hourly aggregated telemetry data synced from System B.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `site_id` | `UUID` | NO | — | FK → `sites.id` CASCADE, indexed |
| `device_id` | `UUID` | YES | `NULL` | FK → `devices.id` CASCADE, indexed |
| `timestamp_hour` | `TIMESTAMPTZ` | NO | — | indexed |
| `energy_generated_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_consumed_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_exported_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_imported_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_stored_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_discharged_kwh` | `FLOAT` | NO | `0.0` | — |
| `peak_power_kw` | `FLOAT` | NO | `0.0` | — |
| `average_power_kw` | `FLOAT` | NO | `0.0` | — |
| `min_power_kw` | `FLOAT` | NO | `0.0` | — |
| `peak_power_time` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `avg_irradiance_w_m2` | `FLOAT` | YES | `NULL` | — |
| `avg_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `max_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `min_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `avg_battery_soc_percent` | `FLOAT` | YES | `NULL` | — |
| `min_battery_soc_percent` | `FLOAT` | YES | `NULL` | — |
| `max_battery_soc_percent` | `FLOAT` | YES | `NULL` | — |
| `avg_grid_voltage_v` | `FLOAT` | YES | `NULL` | — |
| `avg_grid_frequency_hz` | `FLOAT` | YES | `NULL` | — |
| `avg_power_factor` | `FLOAT` | YES | `NULL` | — |
| `sample_count` | `INTEGER` | NO | `0` | — |
| `data_quality_percent` | `FLOAT` | NO | `100.0` | — |
| `performance_ratio` | `FLOAT` | YES | `NULL` | — |
| `capacity_factor` | `FLOAT` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Unique Constraint:** `uq_hourly_site_device_time` (`site_id`, `device_id`, `timestamp_hour`)

Note: `device_id = NULL` indicates a site-level aggregate (all devices combined).

---

### 1.9 `telemetry_daily_summary`

Daily aggregated telemetry data.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `site_id` | `UUID` | NO | — | FK → `sites.id` CASCADE, indexed |
| `device_id` | `UUID` | YES | `NULL` | FK → `devices.id` CASCADE, indexed |
| `summary_date` | `DATE` | NO | — | indexed |
| `energy_generated_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_consumed_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_exported_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_imported_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_stored_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_discharged_kwh` | `FLOAT` | NO | `0.0` | — |
| `net_energy_kwh` | `FLOAT` | NO | `0.0` | — |
| `peak_power_kw` | `FLOAT` | NO | `0.0` | — |
| `average_power_kw` | `FLOAT` | NO | `0.0` | — |
| `peak_power_time` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `sunshine_hours` | `FLOAT` | NO | `0.0` | — |
| `production_hours` | `FLOAT` | NO | `0.0` | — |
| `grid_outage_minutes` | `INTEGER` | NO | `0` | — |
| `avg_irradiance_w_m2` | `FLOAT` | YES | `NULL` | — |
| `total_irradiation_kwh_m2` | `FLOAT` | YES | `NULL` | — |
| `avg_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `max_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `min_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `avg_humidity_percent` | `FLOAT` | YES | `NULL` | — |
| `battery_cycles` | `FLOAT` | NO | `0.0` | — |
| `avg_battery_soc_percent` | `FLOAT` | YES | `NULL` | — |
| `avg_grid_voltage_v` | `FLOAT` | YES | `NULL` | — |
| `avg_power_factor` | `FLOAT` | YES | `NULL` | — |
| `performance_ratio` | `FLOAT` | YES | `NULL` | — |
| `capacity_factor` | `FLOAT` | YES | `NULL` | — |
| `specific_yield_kwh_kwp` | `FLOAT` | YES | `NULL` | — |
| `co2_avoided_kg` | `FLOAT` | NO | `0.0` | — |
| `estimated_revenue_pkr` | `FLOAT` | NO | `0.0` | — |
| `estimated_savings_pkr` | `FLOAT` | NO | `0.0` | — |
| `hours_with_data` | `INTEGER` | NO | `0` | — |
| `data_completeness_percent` | `FLOAT` | NO | `100.0` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |

**Unique Constraint:** `uq_daily_site_device_date` (`site_id`, `device_id`, `summary_date`)

---

### 1.10 `telemetry_monthly_summary`

Monthly aggregated telemetry data.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `site_id` | `UUID` | NO | — | FK → `sites.id` CASCADE, indexed |
| `device_id` | `UUID` | YES | `NULL` | FK → `devices.id` CASCADE, indexed |
| `year` | `INTEGER` | NO | — | — |
| `month` | `INTEGER` | NO | — | — |
| `energy_generated_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_consumed_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_exported_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_imported_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_stored_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_discharged_kwh` | `FLOAT` | NO | `0.0` | — |
| `net_energy_kwh` | `FLOAT` | NO | `0.0` | — |
| `peak_power_kw` | `FLOAT` | NO | `0.0` | — |
| `average_daily_generation_kwh` | `FLOAT` | NO | `0.0` | — |
| `peak_power_date` | `DATE` | YES | `NULL` | — |
| `total_sunshine_hours` | `FLOAT` | NO | `0.0` | — |
| `total_production_hours` | `FLOAT` | NO | `0.0` | — |
| `total_grid_outage_minutes` | `INTEGER` | NO | `0` | — |
| `avg_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `total_irradiation_kwh_m2` | `FLOAT` | YES | `NULL` | — |
| `performance_ratio` | `FLOAT` | YES | `NULL` | — |
| `capacity_factor` | `FLOAT` | YES | `NULL` | — |
| `specific_yield_kwh_kwp` | `FLOAT` | YES | `NULL` | — |
| `expected_generation_kwh` | `FLOAT` | YES | `NULL` | — |
| `generation_variance_percent` | `FLOAT` | YES | `NULL` | — |
| `co2_avoided_kg` | `FLOAT` | NO | `0.0` | — |
| `trees_equivalent` | `FLOAT` | NO | `0.0` | — |
| `estimated_revenue_pkr` | `FLOAT` | NO | `0.0` | — |
| `estimated_savings_pkr` | `FLOAT` | NO | `0.0` | — |
| `days_with_data` | `INTEGER` | NO | `0` | — |
| `data_completeness_percent` | `FLOAT` | NO | `100.0` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |

**Unique Constraint:** `uq_monthly_site_device_period` (`site_id`, `device_id`, `year`, `month`)

---

### 1.11 `device_telemetry_snapshot`

Latest telemetry reading per device (one row per device, upserted).

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `device_id` | `UUID` | NO | — | PK, FK → `devices.id` CASCADE |
| `site_id` | `UUID` | NO | — | FK → `sites.id` CASCADE, indexed |
| `timestamp` | `TIMESTAMPTZ` | NO | — | indexed |
| `current_power_kw` | `FLOAT` | NO | `0.0` | — |
| `power_limit_kw` | `FLOAT` | YES | `NULL` | — |
| `energy_today_kwh` | `FLOAT` | NO | `0.0` | — |
| `energy_lifetime_kwh` | `FLOAT` | NO | `0.0` | — |
| `dc_voltage_v` | `FLOAT` | YES | `NULL` | — |
| `dc_current_a` | `FLOAT` | YES | `NULL` | — |
| `dc_power_kw` | `FLOAT` | YES | `NULL` | — |
| `ac_voltage_v` | `FLOAT` | YES | `NULL` | — |
| `ac_current_a` | `FLOAT` | YES | `NULL` | — |
| `ac_frequency_hz` | `FLOAT` | YES | `NULL` | — |
| `power_factor` | `FLOAT` | YES | `NULL` | — |
| `voltage_l1_v` | `FLOAT` | YES | `NULL` | — |
| `voltage_l2_v` | `FLOAT` | YES | `NULL` | — |
| `voltage_l3_v` | `FLOAT` | YES | `NULL` | — |
| `current_l1_a` | `FLOAT` | YES | `NULL` | — |
| `current_l2_a` | `FLOAT` | YES | `NULL` | — |
| `current_l3_a` | `FLOAT` | YES | `NULL` | — |
| `internal_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `ambient_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `battery_soc_percent` | `FLOAT` | YES | `NULL` | — |
| `battery_voltage_v` | `FLOAT` | YES | `NULL` | — |
| `battery_current_a` | `FLOAT` | YES | `NULL` | — |
| `battery_power_kw` | `FLOAT` | YES | `NULL` | — |
| `battery_temperature_c` | `FLOAT` | YES | `NULL` | — |
| `charging_state` | `VARCHAR(50)` | YES | `NULL` | — |
| `grid_import_power_kw` | `FLOAT` | YES | `NULL` | — |
| `grid_export_power_kw` | `FLOAT` | YES | `NULL` | — |
| `irradiance_w_m2` | `FLOAT` | YES | `NULL` | — |
| `wind_speed_m_s` | `FLOAT` | YES | `NULL` | — |
| `humidity_percent` | `FLOAT` | YES | `NULL` | — |
| `operating_state` | `VARCHAR(100)` | YES | `NULL` | — |
| `error_code` | `VARCHAR(50)` | YES | `NULL` | — |
| `warning_code` | `VARCHAR(50)` | YES | `NULL` | — |
| `raw_data` | `JSONB` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |

Note: Does not use the `BaseModel` UUID mixin — `device_id` is both PK and FK.

---

### 1.12 `tariff_plans`

Electricity tariff rate structures by DISCO provider.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `disco_provider` | `VARCHAR(50)` | NO | — | indexed |
| `category` | `VARCHAR(100)` | NO | — | indexed |
| `name` | `VARCHAR(255)` | NO | — | — |
| `description` | `TEXT` | YES | `NULL` | — |
| `effective_from` | `DATE` | NO | — | indexed |
| `effective_to` | `DATE` | YES | `NULL` | — |
| `rates` | `JSONB` | NO | — | — |
| `supports_net_metering` | `BOOLEAN` | NO | `true` | — |
| `supports_tou` | `BOOLEAN` | NO | `false` | — |
| `source_url` | `VARCHAR(500)` | YES | `NULL` | — |
| `notes` | `TEXT` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `billing_simulations` → `billing_simulations` (1:N via `tariff_plan_id`)

**`rates` JSONB schema:**
```json
{
  "energy_charge_per_kwh": "25.00",
  "slabs": [
    {"min_units": 0, "max_units": 100, "rate_per_kwh": "7.74", "fixed_charges": "0"},
    {"min_units": 101, "max_units": 200, "rate_per_kwh": "11.50", "fixed_charges": "0"},
    {"min_units": 201, "max_units": 300, "rate_per_kwh": "16.00", "fixed_charges": "0"},
    {"min_units": 301, "max_units": 700, "rate_per_kwh": "24.00", "fixed_charges": "0"},
    {"min_units": 701, "max_units": null, "rate_per_kwh": "32.00", "fixed_charges": "0"}
  ],
  "peak_rate_per_kwh": null,
  "off_peak_rate_per_kwh": null,
  "fixed_charges_per_month": "150.00",
  "meter_rent": "25.00",
  "fuel_price_adjustment": "3.23",
  "quarterly_tariff_adjustment": "1.15",
  "electricity_duty_percent": "1.5",
  "gst_percent": "17.0",
  "tv_fee": "35.00",
  "export_rate_per_kwh": "19.32",
  "demand_charge_per_kw": null
}
```

---

### 1.13 `billing_simulations`

Electricity bill calculations per site and billing period.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `site_id` | `UUID` | NO | — | FK → `sites.id` CASCADE, indexed |
| `tariff_plan_id` | `UUID` | YES | `NULL` | FK → `tariff_plans.id` SET NULL, indexed |
| `period_start` | `DATE` | NO | — | — |
| `period_end` | `DATE` | NO | — | — |
| `energy_consumed_kwh` | `NUMERIC(12,3)` | NO | `0` | — |
| `energy_generated_kwh` | `NUMERIC(12,3)` | NO | `0` | — |
| `energy_exported_kwh` | `NUMERIC(12,3)` | NO | `0` | — |
| `energy_imported_kwh` | `NUMERIC(12,3)` | NO | `0` | — |
| `peak_demand_kw` | `NUMERIC(10,2)` | YES | `NULL` | — |
| `bill_breakdown` | `JSONB` | NO | — | — |
| `savings_breakdown` | `JSONB` | NO | — | — |
| `estimated_bill_pkr` | `NUMERIC(12,2)` | NO | `0` | — |
| `estimated_savings_pkr` | `NUMERIC(12,2)` | NO | `0` | — |
| `is_actual` | `BOOLEAN` | NO | `false` | — |
| `notes` | `TEXT` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `site` → `sites` (N:1)
- `tariff_plan` → `tariff_plans` (N:1, SET NULL on delete)

**`bill_breakdown` JSONB schema:**
```json
{
  "energy_charges": "4500.00",
  "slab_breakdown": [
    {"slab": "0-100", "units": 100, "rate": "7.74", "amount": "774.00"},
    {"slab": "101-200", "units": 100, "rate": "11.50", "amount": "1150.00"},
    {"slab": "201-300", "units": 50, "rate": "16.00", "amount": "800.00"}
  ],
  "fixed_charges": "150.00",
  "meter_rent": "25.00",
  "fuel_price_adjustment": "807.50",
  "quarterly_tariff_adjustment": "287.50",
  "electricity_duty": "101.40",
  "gst": "1148.60",
  "tv_fee": "35.00",
  "export_credit": "-1932.00",
  "demand_charges": "0.00",
  "subtotal": "5770.00",
  "total_taxes": "1285.00",
  "total_bill": "5123.00"
}
```

**`savings_breakdown` JSONB schema:**
```json
{
  "bill_without_solar": "12500.00",
  "bill_with_solar": "5123.00",
  "total_savings": "7377.00",
  "savings_percent": "59.0",
  "export_income": "1932.00",
  "co2_avoided_kg": "175.5",
  "trees_equivalent": "8.0"
}
```

---

### 1.14 `reports`

Generated report records.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `organization_id` | `UUID` | NO | — | FK → `organizations.id` CASCADE, indexed |
| `created_by` | `UUID` | YES | `NULL` | FK → `users.id` SET NULL, indexed |
| `report_type` | `VARCHAR(50)` | NO | — | indexed |
| `name` | `VARCHAR(255)` | NO | — | — |
| `description` | `TEXT` | YES | `NULL` | — |
| `parameters` | `JSONB` | NO | — | — |
| `format` | `VARCHAR(20)` | NO | `'pdf'` | — |
| `status` | `VARCHAR(20)` | NO | `'pending'` | indexed |
| `requested_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `started_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `completed_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `file_path` | `VARCHAR(500)` | YES | `NULL` | — |
| `file_size_bytes` | `INTEGER` | YES | `NULL` | — |
| `page_count` | `INTEGER` | YES | `NULL` | — |
| `error_message` | `TEXT` | YES | `NULL` | — |
| `retry_count` | `INTEGER` | NO | `0` | — |
| `max_retries` | `INTEGER` | NO | `3` | — |
| `delivery_config` | `JSONB` | YES | `NULL` | — |
| `delivered_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `expires_at` | `TIMESTAMPTZ` | YES | `NULL` | indexed |
| `schedule_id` | `UUID` | YES | `NULL` | FK → `report_schedules.id` SET NULL, indexed |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `organization` → `organizations` (N:1)
- `creator` → `users` (N:1)
- `schedule` → `report_schedules` (N:1)

**`parameters` JSONB schema:**
```json
{
  "site_ids": ["uuid-1", "uuid-2"],
  "device_ids": [],
  "date_range": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-31"
  },
  "group_by": "daily",
  "compare_previous_period": true,
  "include_charts": true,
  "include_raw_data": false,
  "include_recommendations": true,
  "alert_severities": [],
  "device_types": [],
  "custom_fields": {}
}
```

**`delivery_config` JSONB schema:**
```json
{
  "method": "email",
  "recipients": [
    {"email": "admin@example.com", "name": "Admin", "include_summary": true}
  ],
  "webhook_url": null,
  "storage_path": null,
  "email_subject_template": "Solar Report: {report_name} - {date}",
  "include_inline_preview": false
}
```

---

### 1.15 `report_schedules`

Recurring report generation schedules.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `organization_id` | `UUID` | NO | — | FK → `organizations.id` CASCADE, indexed |
| `created_by` | `UUID` | YES | `NULL` | FK → `users.id` SET NULL |
| `name` | `VARCHAR(255)` | NO | — | — |
| `description` | `TEXT` | YES | `NULL` | — |
| `report_type` | `VARCHAR(50)` | NO | — | indexed |
| `parameters` | `JSONB` | NO | `{}` | — |
| `format` | `VARCHAR(20)` | NO | `'pdf'` | — |
| `frequency` | `VARCHAR(20)` | NO | `'monthly'` | — |
| `run_time` | `TIME` | NO | `06:00:00` | — |
| `day_of_week` | `INTEGER` | YES | `NULL` | 0=Monday |
| `day_of_month` | `INTEGER` | YES | `NULL` | 1–28 |
| `timezone` | `VARCHAR(50)` | NO | `'Asia/Karachi'` | — |
| `is_active` | `BOOLEAN` | NO | `true` | indexed |
| `start_date` | `DATE` | YES | `NULL` | — |
| `end_date` | `DATE` | YES | `NULL` | — |
| `delivery_config` | `JSONB` | NO | `{}` | — |
| `last_run_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `next_run_at` | `TIMESTAMPTZ` | YES | `NULL` | indexed |
| `last_report_id` | `UUID` | YES | `NULL` | — |
| `total_runs` | `INTEGER` | NO | `0` | — |
| `successful_runs` | `INTEGER` | NO | `0` | — |
| `failed_runs` | `INTEGER` | NO | `0` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `organization` → `organizations` (N:1)
- `creator` → `users` (N:1)
- `reports` → `reports` (1:N via `schedule_id`)

---

### 1.16 `report_templates`

Reusable report layouts with branding.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `organization_id` | `UUID` | NO | — | FK → `organizations.id` CASCADE, indexed |
| `created_by` | `UUID` | YES | `NULL` | FK → `users.id` SET NULL |
| `name` | `VARCHAR(255)` | NO | — | — |
| `description` | `TEXT` | YES | `NULL` | — |
| `report_type` | `VARCHAR(50)` | NO | — | indexed |
| `branding` | `JSONB` | NO | — | — |
| `sections` | `JSONB` | NO | — | — |
| `default_parameters` | `JSONB` | NO | `{}` | — |
| `is_active` | `BOOLEAN` | NO | `true` | — |
| `is_default` | `BOOLEAN` | NO | `false` | — |
| `usage_count` | `INTEGER` | NO | `0` | — |
| `last_used_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**Relationships:**
- `organization` → `organizations` (N:1)
- `creator` → `users` (N:1)

**`branding` JSONB schema:**
```json
{
  "logo_url": "https://example.com/logo.png",
  "header_text": "Monthly Solar Performance Report",
  "footer_text": "Generated by Solar Hub",
  "color_scheme": {
    "primary": "#1a73e8",
    "secondary": "#34a853"
  }
}
```

**`sections` JSONB schema:**
```json
[
  {
    "type": "energy_summary",
    "title": "Energy Overview",
    "enabled": true
  },
  {
    "type": "power_chart",
    "title": "Power Generation",
    "enabled": true,
    "metric": "power_ac"
  },
  {
    "type": "data_table",
    "title": "Daily Breakdown",
    "enabled": true,
    "columns": ["date", "generated", "consumed", "exported"]
  }
]
```

---

### 1.17 `protocol_definitions`

Maps device types and communication protocols to adapter implementations.

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `protocol_id` | `VARCHAR(100)` | NO | — | UNIQUE, indexed |
| `name` | `VARCHAR(200)` | NO | — | — |
| `description` | `TEXT` | YES | `NULL` | — |
| `device_type` | `ENUM(device_type)` | NO | — | indexed |
| `protocol_type` | `ENUM(protocol_type)` | NO | — | indexed |
| `priority` | `INTEGER` | NO | `100` | indexed |
| `manufacturer` | `VARCHAR(100)` | YES | `NULL` | — |
| `model_pattern` | `VARCHAR(200)` | YES | `NULL` | — |
| `adapter_class` | `VARCHAR(200)` | NO | — | — |
| `register_map_file` | `VARCHAR(200)` | YES | `NULL` | — |
| `identification_config` | `JSONB` | YES | `NULL` | — |
| `serial_number_config` | `JSONB` | YES | `NULL` | — |
| `polling_config` | `JSONB` | YES | `NULL` | — |
| `modbus_config` | `JSONB` | YES | `NULL` | — |
| `command_config` | `JSONB` | YES | `NULL` | — |
| `default_connection_config` | `JSONB` | YES | `NULL` | — |
| `is_active` | `BOOLEAN` | NO | `true` | indexed |
| `is_system` | `BOOLEAN` | NO | `false` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` on update | — |
| `version` | `INTEGER` | NO | `1` | — |

**`identification_config` JSONB schema:**
```json
{
  "register": 30000,
  "size": 16,
  "expected_values": ["SUN2000"],
  "command": null,
  "expected_response": null,
  "timeout": 5
}
```

**`serial_number_config` JSONB schema:**
```json
{
  "register": 30015,
  "size": 10,
  "encoding": "utf-8",
  "command": null,
  "parse_regex": null
}
```

**`polling_config` JSONB schema:**
```json
{
  "default_interval": 10,
  "timeout": 5,
  "max_consecutive_failures": 5
}
```

**`modbus_config` JSONB schema:**
```json
{
  "unit_id": 1,
  "timeout": 5,
  "retries": 3
}
```

**`command_config` JSONB schema:**
```json
{
  "line_ending": "\r\n",
  "response_timeout": 5,
  "command_delay": 0.1
}
```

---

## 2. System B Tables

System B uses TimescaleDB 2.x (PostgreSQL extension) for time-series data.

### 2.1 `device_registry`

Device connection, authentication, and polling state.

**Type:** Regular table (not a hypertable)
**Retention:** Permanent

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `device_id` | `UUID` | NO | — | PK |
| `site_id` | `UUID` | YES | `NULL` | — |
| `organization_id` | `UUID` | YES | `NULL` | — |
| `device_type` | `VARCHAR(50)` | NO | — | — |
| `serial_number` | `VARCHAR(100)` | NO | — | UNIQUE |
| `manufacturer` | `VARCHAR(100)` | YES | `NULL` | — |
| `model` | `VARCHAR(100)` | YES | `NULL` | — |
| `firmware_version` | `VARCHAR(50)` | YES | `NULL` | — |
| `status` | `ENUM(device_status)` | NO | `'orphan'` | indexed |
| `owner_id` | `UUID` | YES | `NULL` | — |
| `capabilities` | `JSONB` | YES | `NULL` | — |
| `auth_token_hash` | `VARCHAR(255)` | YES | `NULL` | — |
| `token_expires_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `connection_status` | `VARCHAR(20)` | NO | `'disconnected'` | indexed |
| `last_connected_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `last_disconnected_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `reconnect_count` | `INTEGER` | NO | `0` | — |
| `protocol` | `VARCHAR(50)` | YES | `NULL` | — |
| `connection_config` | `JSONB` | YES | `NULL` | — |
| `polling_interval_seconds` | `INTEGER` | NO | `60` | — |
| `last_polled_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `next_poll_at` | `TIMESTAMPTZ` | YES | `NULL` | indexed |
| `last_telemetry_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `metadata` | `JSONB` | YES | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `synced_at` | `TIMESTAMPTZ` | YES | `NULL` | — |

Device status values: `orphan` (self-registered, unclaimed), `claimed` (linked to System A user).

Connection status values: `connected`, `disconnected`, `connecting`, `error`, `timeout`.

---

### 2.2 `telemetry_raw`

Raw telemetry readings from all devices.

**Type:** TimescaleDB Hypertable
**Chunk interval:** 1 hour
**Retention:** 90 days
**Compression:** After 7 days (segment by `device_id`, `metric_name`; order by `time DESC`)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `time` | `TIMESTAMPTZ` | NO | — | PK (composite), partition key |
| `device_id` | `UUID` | NO | — | PK (composite) |
| `metric_name` | `VARCHAR(100)` | NO | — | PK (composite) |
| `site_id` | `UUID` | NO | — | indexed |
| `metric_value` | `DOUBLE PRECISION` | YES | `NULL` | — |
| `metric_value_str` | `VARCHAR(255)` | YES | `NULL` | — |
| `quality` | `VARCHAR(20)` | NO | `'good'` | — |
| `unit` | `VARCHAR(20)` | YES | `NULL` | — |
| `source` | `VARCHAR(50)` | YES | `NULL` | — |
| `tags` | `JSONB` | YES | `NULL` | — |
| `raw_value` | `BYTEA` | YES | `NULL` | — |
| `received_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `processed` | `BOOLEAN` | NO | `false` | — |

**Composite Primary Key:** (`time`, `device_id`, `metric_name`)

Quality values: `good`, `interpolated`, `estimated`, `suspect`, `missing`, `invalid`.

Source values: `device`, `calculated`, `manual`.

**`tags` JSONB examples:**
```json
{"mppt_id": 1, "string_id": "A"}
{"phase": "L1"}
{"aggregation": "site_total"}
```

---

### 2.3 `device_events`

Device lifecycle and error events.

**Type:** TimescaleDB Hypertable
**Chunk interval:** 1 day
**Retention:** 1 year
**Compression:** After 30 days

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `time` | `TIMESTAMPTZ` | NO | — | PK (composite), partition key |
| `device_id` | `UUID` | NO | — | PK (composite) |
| `event_type` | `VARCHAR(50)` | NO | — | PK (composite) |
| `site_id` | `UUID` | NO | — | indexed |
| `event_code` | `VARCHAR(50)` | YES | `NULL` | — |
| `severity` | `VARCHAR(20)` | NO | `'info'` | — |
| `message` | `TEXT` | YES | `NULL` | — |
| `details` | `JSONB` | YES | `NULL` | — |
| `acknowledged` | `BOOLEAN` | NO | `false` | — |
| `acknowledged_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `acknowledged_by` | `UUID` | YES | `NULL` | — |

**Composite Primary Key:** (`time`, `device_id`, `event_type`)

Event type values: `status_change`, `error`, `warning`, `connection`, `command`, `firmware`, `configuration`, `alarm`, `fault`.

Severity values: `info`, `warning`, `error`, `critical`.

---

### 2.4 `device_commands`

Command queue for remote device control.

**Type:** Regular table
**Retention:** Permanent

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | — | PK |
| `device_id` | `UUID` | NO | — | indexed |
| `site_id` | `UUID` | NO | — | — |
| `command_type` | `VARCHAR(100)` | NO | — | — |
| `command_params` | `JSONB` | YES | `NULL` | — |
| `status` | `VARCHAR(20)` | NO | `'pending'` | indexed |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `scheduled_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `sent_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `acknowledged_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `completed_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `expires_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `result` | `JSONB` | YES | `NULL` | — |
| `error_message` | `TEXT` | YES | `NULL` | — |
| `retry_count` | `INTEGER` | NO | `0` | — |
| `max_retries` | `INTEGER` | NO | `3` | — |
| `created_by` | `UUID` | YES | `NULL` | — |
| `priority` | `INTEGER` | NO | `5` | 1=highest, 10=lowest |

Command type values: `set_power_limit`, `restart`, `update_firmware`, `set_time`, `clear_errors`, `enable_export`, `disable_export`, `set_battery_mode`, `set_charge_limit`, `set_discharge_limit`, `read_registers`, `write_registers`, `custom`.

Status flow: `pending` → `sent` → `acknowledged` → `completed` | `failed` | `timeout` | `cancelled`.

---

### 2.5 `metric_definitions`

Standard metric catalog defining valid metric names, units, and validation ranges.

**Type:** Regular table
**Retention:** Permanent

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `metric_name` | `VARCHAR(100)` | NO | — | PK |
| `display_name` | `VARCHAR(255)` | NO | — | — |
| `description` | `TEXT` | YES | `NULL` | — |
| `unit` | `VARCHAR(20)` | NO | — | — |
| `data_type` | `VARCHAR(20)` | NO | — | — |
| `device_types` | `ARRAY(VARCHAR(50))` | NO | — | — |
| `min_value` | `DOUBLE PRECISION` | YES | `NULL` | — |
| `max_value` | `DOUBLE PRECISION` | YES | `NULL` | — |
| `aggregation_method` | `VARCHAR(20)` | NO | `'avg'` | — |
| `is_cumulative` | `BOOLEAN` | NO | `false` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |

Data type values: `float`, `integer`, `string`, `boolean`.

Aggregation method values: `avg`, `sum`, `min`, `max`, `last`.

**Standard metrics (50+):**

| Metric Name | Display Name | Unit | Device Types | Cumulative |
|-------------|-------------|------|-------------|-----------|
| `power_ac` | AC Power | kW | inverter | No |
| `power_dc` | DC Power | kW | inverter | No |
| `power_active` | Active Power | kW | meter | No |
| `power_reactive` | Reactive Power | kVAR | meter | No |
| `power_apparent` | Apparent Power | kVA | meter | No |
| `voltage_dc` | DC Voltage | V | inverter | No |
| `voltage_ac` | AC Voltage | V | inverter | No |
| `voltage_l1` | L1 Voltage | V | inverter, meter | No |
| `voltage_l2` | L2 Voltage | V | inverter, meter | No |
| `voltage_l3` | L3 Voltage | V | inverter, meter | No |
| `current_dc` | DC Current | A | inverter | No |
| `current_ac` | AC Current | A | inverter | No |
| `current_l1` | L1 Current | A | inverter, meter | No |
| `current_l2` | L2 Current | A | inverter, meter | No |
| `current_l3` | L3 Current | A | inverter, meter | No |
| `energy_total` | Lifetime Energy | kWh | inverter, meter | Yes |
| `energy_today` | Today's Energy | kWh | inverter | No |
| `energy_import` | Energy Import | kWh | meter | Yes |
| `energy_export` | Energy Export | kWh | meter | Yes |
| `frequency` | Grid Frequency | Hz | inverter, meter | No |
| `power_factor` | Power Factor | — | inverter, meter | No |
| `temperature_internal` | Internal Temp | °C | inverter | No |
| `temperature_ambient` | Ambient Temp | °C | weather_station | No |
| `temperature_module` | Module Temp | °C | weather_station | No |
| `temperature_battery` | Battery Temp | °C | battery | No |
| `battery_soc` | State of Charge | % | battery | No |
| `battery_soh` | State of Health | % | battery | No |
| `battery_voltage` | Battery Voltage | V | battery | No |
| `battery_current` | Battery Current | A | battery | No |
| `battery_power` | Battery Power | kW | battery | No |
| `battery_cycles` | Cycle Count | — | battery | Yes |
| `irradiance` | GHI | W/m² | weather_station | No |
| `irradiance_poa` | POA Irradiance | W/m² | weather_station | No |
| `wind_speed` | Wind Speed | m/s | weather_station | No |
| `wind_direction` | Wind Direction | ° | weather_station | No |
| `humidity` | Humidity | % | weather_station | No |
| `pressure` | Pressure | hPa | weather_station | No |
| `rainfall` | Rainfall | mm | weather_station | No |
| `mppt_voltage` | MPPT Voltage | V | inverter | No |
| `mppt_current` | MPPT Current | A | inverter | No |
| `mppt_power` | MPPT Power | kW | inverter | No |
| `status` | Status | — | inverter, battery | No |
| `error_code` | Error Code | — | inverter, battery | No |
| `warning_code` | Warning Code | — | inverter | No |

---

### 2.6 `ingestion_batches`

Tracks telemetry batch processing for monitoring and debugging.

**Type:** Regular table
**Retention:** Permanent

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | — | PK |
| `source_type` | `VARCHAR(50)` | NO | — | — |
| `source_identifier` | `VARCHAR(255)` | YES | `NULL` | — |
| `device_count` | `INTEGER` | NO | `0` | — |
| `record_count` | `INTEGER` | NO | `0` | — |
| `started_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `completed_at` | `TIMESTAMPTZ` | YES | `NULL` | — |
| `status` | `VARCHAR(20)` | NO | `'processing'` | indexed |
| `records_inserted` | `INTEGER` | NO | `0` | — |
| `records_failed` | `INTEGER` | NO | `0` | — |
| `errors` | `JSONB` | YES | `NULL` | — |
| `processing_time_ms` | `INTEGER` | YES | `NULL` | — |

Source type values: `mqtt`, `http`, `modbus`, `file`.

Status values: `processing`, `completed`, `failed`.

---

### 2.7 Continuous Aggregates

TimescaleDB continuous aggregates are materialized views automatically refreshed by background workers.

#### `telemetry_5min`

**Source:** `telemetry_raw`
**Bucket:** 5 minutes
**Refresh:** Every 5 minutes
**Retention:** 7 days
**Use case:** Real-time dashboard, live charts

| Column | Type | Description |
|--------|------|-------------|
| `bucket` | `TIMESTAMPTZ` | 5-minute time bucket |
| `device_id` | `UUID` | Device identifier |
| `site_id` | `UUID` | Site identifier |
| `metric_name` | `VARCHAR(100)` | Metric name |
| `avg_value` | `DOUBLE PRECISION` | Average value in bucket |
| `min_value` | `DOUBLE PRECISION` | Minimum value |
| `max_value` | `DOUBLE PRECISION` | Maximum value |
| `last_value` | `DOUBLE PRECISION` | Last recorded value (TimescaleDB `last()`) |
| `first_value` | `DOUBLE PRECISION` | First recorded value |
| `delta_value` | `DOUBLE PRECISION` | `last_value - first_value` (for cumulative metrics) |
| `sample_count` | `BIGINT` | Number of readings |
| `good_count` | `BIGINT` | Readings with `quality = 'good'` |

#### `telemetry_hourly`

**Source:** `telemetry_raw`
**Bucket:** 1 hour
**Refresh:** Every hour
**Retention:** 90 days
**Use case:** Daily charts, intraday analysis

Same columns as `telemetry_5min` with hourly time buckets.

#### `telemetry_daily`

**Source:** `telemetry_raw`
**Bucket:** 1 day
**Refresh:** Once per day
**Retention:** 5 years
**Use case:** Monthly/yearly reports, long-term trends

Same columns as `telemetry_5min` with daily time buckets.

#### `event_counts_hourly`

**Source:** `device_events`
**Bucket:** 1 hour
**Refresh:** Every hour
**Use case:** Event monitoring dashboards, alert frequency analysis

| Column | Type | Description |
|--------|------|-------------|
| `bucket` | `TIMESTAMPTZ` | 1-hour time bucket |
| `site_id` | `UUID` | Site identifier |
| `event_type` | `VARCHAR(50)` | Event type |
| `severity` | `VARCHAR(20)` | Event severity |
| `event_count` | `BIGINT` | Total events in bucket |
| `unacknowledged_count` | `BIGINT` | Unacknowledged events in bucket |

---

### 2.8 Views

#### `v_site_current_power`

Returns current total power output across all devices at a site.

```sql
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
```

#### `v_site_energy_today`

Returns total energy produced today across all inverters at a site.

```sql
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
```

---

### 2.9 Helper Functions

#### `get_latest_metric(device_id UUID, metric_name VARCHAR)`

Returns the most recent value for a specific metric on a device.

#### `get_metrics_interpolated(device_id UUID, metric_name VARCHAR, start TIMESTAMPTZ, end TIMESTAMPTZ, interval VARCHAR)`

Returns metric values with linear interpolation for missing data points. Used for gap filling in historical charts.

#### `calculate_energy_produced(device_id UUID, start TIMESTAMPTZ, end TIMESTAMPTZ)`

Calculates total energy produced in a time range. Handles counter resets (when cumulative `energy_total` resets to zero after firmware update or device restart).

#### `get_site_status_summary(site_id UUID)`

Returns the current status of all devices at a site. Used by the site overview dashboard.

---

## 3. Enum Reference

### 3.1 System A Enums (PostgreSQL)

#### `user_role`

| Value | Description |
|-------|-------------|
| `super_admin` | Platform-wide admin |
| `owner` | Organization owner |
| `admin` | Organization admin |
| `manager` | Site/device manager |
| `viewer` | Read-only access |
| `installer` | Installation technician |

#### `user_status`

| Value | Description |
|-------|-------------|
| `pending` | Awaiting email verification |
| `active` | Verified and active |
| `suspended` | Temporarily disabled |
| `deactivated` | Permanently disabled |

#### `organization_status`

| Value | Description |
|-------|-------------|
| `active` | Operational |
| `suspended` | Temporarily disabled |
| `deactivated` | Permanently disabled |

#### `membership_status`

| Value | Description |
|-------|-------------|
| `pending` | Invitation sent, not accepted |
| `active` | Active member |
| `removed` | Removed from organization |

#### `site_status`

| Value | Description |
|-------|-------------|
| `pending_setup` | Initial state, awaiting configuration |
| `commissioning` | Being installed and tested |
| `active` | Operational |
| `maintenance` | Under maintenance |
| `offline` | Not producing/communicating |
| `decommissioned` | Permanently retired |

Valid transitions: `pending_setup` → `commissioning` | `decommissioned`; `commissioning` → `active` | `pending_setup`; `active` → `maintenance` | `offline` | `decommissioned`; `maintenance` → `active` | `offline`; `offline` → `active` | `maintenance` | `decommissioned`.

#### `site_type`

| Value | Description |
|-------|-------------|
| `residential` | Home installation |
| `commercial` | Commercial building |
| `industrial` | Factory/warehouse |
| `utility` | Utility-scale solar farm |
| `agricultural` | Farm/agricultural use |

#### `device_type`

| Value | Description |
|-------|-------------|
| `inverter` | Solar inverter |
| `meter` | Energy meter (grid/load) |
| `battery` | Battery storage system |
| `weather_station` | Weather monitoring station |
| `sensor` | Generic sensor |
| `controller` | Control system |
| `gateway` | Communication gateway |
| `other` | Uncategorized device |

#### `device_status`

| Value | Description |
|-------|-------------|
| `pending` | Registered, not yet communicating |
| `online` | Connected and reporting |
| `offline` | Not communicating (> 300 seconds) |
| `error` | Reporting errors |
| `maintenance` | Under maintenance |
| `decommissioned` | Permanently retired |

#### `protocol_type`

| Value | Description |
|-------|-------------|
| `modbus_tcp` | Modbus over TCP/IP |
| `modbus_rtu` | Modbus over serial (RS-485) |
| `mqtt` | MQTT pub/sub |
| `http` | HTTP REST API |
| `https` | HTTPS REST API |
| `custom` | Custom protocol |

#### `alert_severity`

| Value | Description |
|-------|-------------|
| `info` | Informational |
| `warning` | Warning, attention needed |
| `critical` | Critical, immediate action required |

#### `alert_status`

| Value | Description |
|-------|-------------|
| `active` | Currently active |
| `acknowledged` | Seen by user |
| `resolved` | Issue resolved |
| `expired` | Auto-expired |

### 3.2 System B Enums / Constants

#### `device_status` (System B)

| Value | Description |
|-------|-------------|
| `orphan` | Self-registered, not yet claimed by a user |
| `claimed` | Linked to a System A device record |

#### Data Quality

| Value | Description |
|-------|-------------|
| `good` | Normal, validated reading |
| `interpolated` | Calculated via interpolation |
| `estimated` | Manual/estimated value |
| `suspect` | Out of expected range |
| `missing` | Gap marker |
| `invalid` | Corrupt or malformed data |

#### Connection Status

| Value | Description |
|-------|-------------|
| `connected` | Device is connected |
| `disconnected` | Device is disconnected |
| `connecting` | Connection in progress |
| `error` | Connection error |
| `timeout` | Connection timed out |

#### Event Types

| Value | Description |
|-------|-------------|
| `status_change` | Device operating status changed |
| `error` | Error condition detected |
| `warning` | Warning condition detected |
| `connection` | Connection/disconnection event |
| `command` | Command sent or completed |
| `firmware` | Firmware update event |
| `configuration` | Configuration change |
| `alarm` | Alarm triggered |
| `fault` | Fault condition |

#### Event Severity

| Value | Description |
|-------|-------------|
| `info` | Informational |
| `warning` | Warning |
| `error` | Error |
| `critical` | Critical/urgent |

#### Command Types

| Value | Description | Example Params |
|-------|-------------|---------------|
| `set_power_limit` | Limit power output | `{"limit_kw": 50.0}` |
| `restart` | Restart device | `{}` |
| `update_firmware` | Update firmware | `{"version": "1.2.3", "url": "..."}` |
| `set_time` | Sync device clock | `{"timestamp": "2026-01-28T10:00:00Z"}` |
| `clear_errors` | Clear error codes | `{}` |
| `enable_export` | Enable grid export | `{"enabled": true}` |
| `disable_export` | Disable grid export | `{"enabled": false}` |
| `set_battery_mode` | Set battery operation mode | `{"mode": "self_consumption"}` |
| `set_charge_limit` | Set charge limit | `{"limit_percent": 90}` |
| `set_discharge_limit` | Set discharge limit | `{"limit_percent": 10}` |
| `read_registers` | Read Modbus registers | `{"start": 30000, "count": 10}` |
| `write_registers` | Write Modbus registers | `{"register": 40000, "value": 100}` |
| `custom` | Custom command | `{"raw": "..."}` |

---

## 4. Domain Value Objects

Value objects are immutable types used in domain entities. They validate input and provide formatting.

### 4.1 Email

**File:** `system_a/app/domain/value_objects/email.py`

| Field | Type | Constraints |
|-------|------|-------------|
| `value` | `str` | Required, RFC 5322 format, max 254 chars, normalized to lowercase |

**Validation:** Regex pattern matching RFC 5322. Rejects empty strings, invalid formats.

**Properties:** `domain` (part after @), `local_part` (part before @).

---

### 4.2 PhoneNumber

**File:** `system_a/app/domain/value_objects/phone.py`

| Field | Type | Constraints |
|-------|------|-------------|
| `number` | `str` | Required, valid format |
| `country_code` | `str` | Default `"+92"` (Pakistan) |

**Phone Types:** `MOBILE`, `LANDLINE`, `UNKNOWN`

**Validation:** Pakistani mobile format `03XX-XXXXXXX` or international format. Strips spaces, dashes, parentheses during normalization.

**Properties:** `normalized` (international format e.g., `+923001234567`), `phone_type`, `display_format`.

---

### 4.3 Address

**File:** `system_a/app/domain/value_objects/address.py`

| Field | Type | Constraints |
|-------|------|-------------|
| `street_address` | `str` | Required |
| `city` | `str` | Required |
| `province` | `str` | Required |
| `country` | `str` | Default `"Pakistan"` |
| `postal_code` | `str` | Optional |
| `district` | `str` | Optional |
| `area` | `str` | Optional |
| `geo_location` | `GeoLocation` | Optional |

**GeoLocation** (nested):

| Field | Type | Constraints |
|-------|------|-------------|
| `latitude` | `float` | -90 to 90 |
| `longitude` | `float` | -180 to 180 |

**Validation:** Pakistani provinces: Punjab, Sindh, Khyber Pakhtunkhwa, Balochistan, Islamabad Capital Territory, Gilgit-Baltistan, Azad Jammu and Kashmir.

**Methods:** `distance_to(other)` — Haversine formula for distance between geo locations.

---

### 4.4 Money

**File:** `system_a/app/domain/value_objects/money.py`

| Field | Type | Constraints |
|-------|------|-------------|
| `amount` | `Decimal` | Precise financial arithmetic |
| `currency` | `Currency` | Default `PKR` |

**Currencies:** `PKR` (2 decimal places), `USD` (2), `EUR` (2).

**Arithmetic:** Supports `+`, `-`, `*`, `/` with currency validation (cannot mix currencies).

**Formatting:** `PKR` → `"Rs. 1,234.56"`, `USD` → `"$1,234.56"`, `EUR` → `"€1,234.56"`.

**Factories:** `Money.pkr(amount)`, `Money.zero(currency)`.

---

### 4.5 Energy & Power

**File:** `system_a/app/domain/value_objects/energy.py`

#### EnergyReading

| Field | Type | Constraints |
|-------|------|-------------|
| `value` | `Decimal` | Energy amount |
| `unit` | `EnergyUnit` | Default `KWH` |

**Units:** `WH`, `KWH`, `MWH`.

**Conversions:** `to_kwh()`, `to_wh()`, `to_mwh()`.

**Formatting:** `"1,234.567 kWh"`.

#### PowerReading

| Field | Type | Constraints |
|-------|------|-------------|
| `value` | `Decimal` | Power amount |
| `unit` | `PowerUnit` | Default `KW` |

**Units:** `W`, `KW`, `MW`.

**Conversions:** `to_kw()`, `to_w()`, `to_mw()`.

**Method:** `energy_over_hours(hours)` → `EnergyReading`.

#### SolarIrradiance

| Field | Type | Constraints |
|-------|------|-------------|
| `value` | `Decimal` | W/m², non-negative |

**Properties:** `is_peak_sun` (≥ 1000 W/m²), `condition` (`Sunny` / `Partly Cloudy` / `Cloudy` / `Low Light`).

---

### 4.6 TimeRange & DateRange

**File:** `system_a/app/domain/value_objects/time_range.py`

#### TimeRange

| Field | Type | Constraints |
|-------|------|-------------|
| `start` | `datetime` | Timezone-aware (UTC default) |
| `end` | `datetime` | Must be ≥ `start` |

**Granularities:** `MINUTE`, `FIVE_MINUTES`, `FIFTEEN_MINUTES`, `HOURLY`, `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY`.

**Methods:** `contains(timestamp)`, `overlaps(other)`, `intersection(other)`, `union(other)`, `split_by_granularity(granularity)`, `extend(before, after)`.

**Factories:** `TimeRange.last_hours(n)`, `TimeRange.last_days(n)`, `TimeRange.today()`, `TimeRange.this_month()`.

#### DateRange

| Field | Type | Constraints |
|-------|------|-------------|
| `start_date` | `date` | Must be ≤ `end_date` |
| `end_date` | `date` | — |

**Methods:** `contains(d)`, `overlaps(other)`, `iterate_days()`, `to_time_range(tz)`.

**Factories:** `DateRange.last_days(n)`, `DateRange.this_month()`, `DateRange.for_month(year, month)`.

---

## 5. Index Reference

### 5.1 System A Indexes

#### User Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `ix_users_email` | `email` | Login, uniqueness check |
| `ix_users_phone` | `phone` | Phone lookup |
| `ix_users_status` | `status` | Filter active/pending users |
| `ix_users_role` | `role` | Role-based queries |

#### Organization Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `ix_organizations_slug` | `slug` | URL-based lookup |
| `ix_organizations_status` | `status` | Filter active orgs |
| `ix_organizations_owner_id` | `owner_id` | Owner's organizations |

#### Membership Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `ix_organization_members_organization_id` | `organization_id` | List org members |
| `ix_organization_members_user_id` | `user_id` | User's memberships |

#### Site Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `ix_sites_organization_id` | `organization_id` | Org's sites |
| `ix_sites_status` | `status` | Filter by status |
| `ix_sites_site_type` | `site_type` | Filter by type |

#### Device Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `ix_devices_site_id` | `site_id` | Site's devices |
| `ix_devices_organization_id` | `organization_id` | Org-wide device list |
| `ix_devices_serial_number` | `serial_number` | Cross-system lookup (UNIQUE) |
| `ix_devices_device_type` | `device_type` | Filter by device type |
| `ix_devices_status` | `status` | Filter by status |
| `idx_devices_last_seen_at` | `last_seen_at` | Stale device detection |

#### Alert Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `ix_alert_rules_organization_id` | `organization_id` | Org's alert rules |
| `ix_alert_rules_site_id` | `site_id` | Site-specific rules |
| `ix_alerts_rule_id` | `rule_id` | Alerts for a rule |
| `ix_alerts_organization_id` | `organization_id` | Org's alerts |
| `ix_alerts_site_id` | `site_id` | Site's alerts |
| `ix_alerts_device_id` | `device_id` | Device's alerts |
| `ix_alerts_status` | `status` | Active/resolved filter |
| `idx_alerts_triggered` | `triggered_at` | Chronological listing |
| `idx_alerts_status_severity` | `status`, `severity` | Dashboard: active alerts by severity |

#### Telemetry Summary Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `idx_hourly_site_time` | `site_id`, `timestamp_hour` | Site hourly data |
| `idx_hourly_device_time` | `device_id`, `timestamp_hour` | Device hourly data |
| `idx_daily_site_date` | `site_id`, `summary_date` | Site daily data |
| `idx_daily_device_date` | `device_id`, `summary_date` | Device daily data |
| `idx_monthly_site_period` | `site_id`, `year`, `month` | Site monthly data |
| `idx_monthly_device_period` | `device_id`, `year`, `month` | Device monthly data |
| `idx_snapshot_site` | `site_id` | Site's device snapshots |
| `idx_snapshot_timestamp` | `timestamp` | Latest snapshot lookup |

#### Billing Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `idx_tariff_disco_category` | `disco_provider`, `category` | DISCO tariff lookup |
| `idx_tariff_active` | `disco_provider`, `category`, `effective_from`, `effective_to` | Active tariff lookup |
| `idx_billing_site_period` | `site_id`, `period_start`, `period_end` | Site billing history |
| `idx_billing_period` | `period_start`, `period_end` | Period-based queries |

#### Report Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `idx_reports_org_type` | `organization_id`, `report_type` | Org's reports by type |
| `idx_reports_status_requested` | `status`, `requested_at` | Processing queue |
| `idx_reports_org_status` | `organization_id`, `status` | Org reports by status |
| `idx_schedules_org_active` | `organization_id`, `is_active` | Org's active schedules |
| `idx_schedules_next_run` | `is_active`, `next_run_at` | Scheduler: next due |
| `idx_templates_org_type` | `organization_id`, `report_type` | Org templates by type |
| `idx_templates_org_default` | `organization_id`, `is_default` | Default template lookup |

#### Protocol Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `ix_protocol_definitions_protocol_id` | `protocol_id` | Protocol lookup (UNIQUE) |
| `idx_protocol_definitions_device_protocol` | `device_type`, `protocol_type` | Adapter resolution |
| `idx_protocol_definitions_priority` | `priority` | Priority ordering |
| `idx_protocol_definitions_is_active` | `is_active` | Active protocols |

### 5.2 System B Indexes

#### Device Registry Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `idx_device_registry_status` | `connection_status` | Connected device listing |
| `idx_device_registry_next_poll` | `next_poll_at` | Polling scheduler |
| `idx_device_registry_device_status` | `status` | Orphan vs claimed |

#### Telemetry Raw Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `idx_telemetry_raw_device_time` | `device_id`, `time` | Per-device time queries |
| `idx_telemetry_raw_site_time` | `site_id`, `time` | Per-site time queries |
| `idx_telemetry_raw_metric` | `metric_name`, `time` | Metric-specific queries |
| `idx_telemetry_raw_device_metric` | `device_id`, `metric_name`, `time` | Specific metric per device |

#### Device Events Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `idx_device_events_device` | `device_id`, `time` | Device event history |
| `idx_device_events_site` | `site_id`, `time` | Site event history |
| `idx_device_events_type` | `event_type`, `time` | Events by type |

#### Device Commands Queries

| Index | Columns | Use Case |
|-------|---------|----------|
| `idx_device_commands_pending` | `device_id`, `priority`, `created_at` | Pending command queue |

#### Ingestion Monitoring

| Index | Columns | Use Case |
|-------|---------|----------|
| `idx_ingestion_batches_status` | `status`, `started_at` | Active/failed batch monitoring |

### 5.3 Unique Constraints Summary

| Table | Constraint Name | Columns |
|-------|----------------|---------|
| `users` | `uq_users_email` | `email` |
| `organizations` | `uq_organizations_slug` | `slug` |
| `devices` | `uq_devices_serial_number` | `serial_number` |
| `protocol_definitions` | `uq_protocol_definitions_protocol_id` | `protocol_id` |
| `device_registry` | (unnamed) | `serial_number` |
| `telemetry_hourly_summary` | `uq_hourly_site_device_time` | `site_id`, `device_id`, `timestamp_hour` |
| `telemetry_daily_summary` | `uq_daily_site_device_date` | `site_id`, `device_id`, `summary_date` |
| `telemetry_monthly_summary` | `uq_monthly_site_device_period` | `site_id`, `device_id`, `year`, `month` |

### 5.4 Foreign Key Cascade Summary

| Source Table | Column | Target | On Delete |
|-------------|--------|--------|-----------|
| `organizations` | `owner_id` | `users.id` | (no cascade) |
| `organization_members` | `organization_id` | `organizations.id` | CASCADE |
| `organization_members` | `user_id` | `users.id` | CASCADE |
| `sites` | `organization_id` | `organizations.id` | CASCADE |
| `devices` | `site_id` | `sites.id` | CASCADE |
| `devices` | `organization_id` | `organizations.id` | CASCADE |
| `alert_rules` | `organization_id` | `organizations.id` | CASCADE |
| `alert_rules` | `site_id` | `sites.id` | CASCADE |
| `alerts` | `rule_id` | `alert_rules.id` | CASCADE |
| `alerts` | `organization_id` | `organizations.id` | CASCADE |
| `alerts` | `site_id` | `sites.id` | CASCADE |
| `alerts` | `device_id` | `devices.id` | SET NULL |
| `alerts` | `acknowledged_by` | `users.id` | SET NULL |
| `alerts` | `resolved_by` | `users.id` | SET NULL |
| `telemetry_hourly_summary` | `site_id` | `sites.id` | CASCADE |
| `telemetry_hourly_summary` | `device_id` | `devices.id` | CASCADE |
| `telemetry_daily_summary` | `site_id` | `sites.id` | CASCADE |
| `telemetry_daily_summary` | `device_id` | `devices.id` | CASCADE |
| `telemetry_monthly_summary` | `site_id` | `sites.id` | CASCADE |
| `telemetry_monthly_summary` | `device_id` | `devices.id` | CASCADE |
| `device_telemetry_snapshot` | `device_id` | `devices.id` | CASCADE |
| `device_telemetry_snapshot` | `site_id` | `sites.id` | CASCADE |
| `billing_simulations` | `site_id` | `sites.id` | CASCADE |
| `billing_simulations` | `tariff_plan_id` | `tariff_plans.id` | SET NULL |
| `reports` | `organization_id` | `organizations.id` | CASCADE |
| `reports` | `created_by` | `users.id` | SET NULL |
| `reports` | `schedule_id` | `report_schedules.id` | SET NULL |
| `report_schedules` | `organization_id` | `organizations.id` | CASCADE |
| `report_schedules` | `created_by` | `users.id` | SET NULL |
| `report_templates` | `organization_id` | `organizations.id` | CASCADE |
| `report_templates` | `created_by` | `users.id` | SET NULL |
