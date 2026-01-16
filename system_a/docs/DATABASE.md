# Solar Hub - Database Schema Documentation

## Overview

System A uses **PostgreSQL 14+** with the `asyncpg` driver for async operations. The schema follows Domain-Driven Design principles with proper normalization and indexing strategies.

## Entity Relationship Diagram (ERD)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SOLAR HUB - SYSTEM A                                │
│                            Entity Relationship Diagram                           │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐          ┌───────────────────────┐          ┌─────────────────┐
│      USERS       │          │    ORGANIZATIONS      │          │  ALERT_RULES    │
├──────────────────┤          ├───────────────────────┤          ├─────────────────┤
│ PK id            │◄─────────┤ FK owner_id           │          │ PK id           │
│    email (U)     │          │ PK id                 │◄─────────┤ FK org_id       │
│    phone         │          │    name               │          │ FK site_id (N)  │
│    password_hash │          │    slug (U)           │          │    name         │
│    first_name    │          │    description        │          │    description  │
│    last_name     │          │    logo_url           │          │    condition    │
│    role          │          │    website            │          │    severity     │
│    is_active     │          │    status             │          │    channels[]   │
│    is_verified   │          │    settings           │          │    is_active    │
│    preferences   │          │    created_at         │          │    cooldown_min │
│    created_at    │          │    updated_at         │          │    auto_resolve │
│    updated_at    │          │    version            │          │    created_at   │
│    version       │          └───────────────────────┘          │    updated_at   │
└──────────────────┘                      │                      └─────────────────┘
         │                                │                               │
         │                                │                               │
         │      ┌─────────────────────────┴──────────────────────────┐    │
         │      │                                                    │    │
         │      ▼                                                    ▼    │
         │  ┌───────────────────────┐                     ┌──────────────────┐
         │  │ ORGANIZATION_MEMBERS  │                     │      SITES       │
         │  ├───────────────────────┤                     ├──────────────────┤
         │  │ PK id                 │                     │ PK id            │
         └──┤ FK organization_id    │                     │ FK org_id        │◄──────┐
            │ FK user_id            │                     │    name          │       │
            │    role               │                     │    description   │       │
            │ FK invited_by         │                     │    status        │       │
            │    invitation_token   │                     │    address       │       │
            │    invitation_expires │                     │    latitude      │       │
            │    invitation_accepted│                     │    longitude     │       │
            │    joined_at          │                     │    timezone      │       │
            │    created_at         │                     │    configuration │       │
            │    updated_at         │                     │    created_at    │       │
            │    version            │                     │    updated_at    │       │
            └───────────────────────┘                     │    version       │       │
                                                          └──────────────────┘       │
                                                                    │                │
                                      ┌─────────────────────────────┤                │
                                      │                             │                │
                                      ▼                             ▼                │
                              ┌──────────────────┐          ┌──────────────────┐     │
                              │     DEVICES      │          │     ALERTS       │     │
                              ├──────────────────┤          ├──────────────────┤     │
                              │ PK id            │          │ PK id            │     │
                              │ FK site_id       │◄─────────┤ FK rule_id       │     │
                              │ FK org_id        │          │ FK org_id        │─────┘
                              │    name          │          │ FK site_id       │
                              │    description   │          │ FK device_id (N) │
                              │    device_type   │          │    severity      │
                              │    manufacturer  │          │    status        │
                              │    model         │          │    title         │
                              │    serial_number │          │    message       │
                              │    firmware_ver  │          │    metric_name   │
                              │    protocol      │          │    metric_value  │
                              │    conn_config   │          │    threshold     │
                              │    status        │          │    triggered_at  │
                              │    last_seen_at  │          │ FK ack_by        │
                              │    last_error    │          │    ack_at        │
                              │    metadata      │          │ FK resolved_by   │
                              │    created_at    │          │    resolved_at   │
                              │    updated_at    │          │    notif_sent[]  │
                              │    version       │          │    escalated     │
                              └──────────────────┘          │    escalated_at  │
                                                            │    created_at    │
                                                            │    updated_at    │
                                                            │    version       │
                                                            └──────────────────┘

Legend:
  PK = Primary Key
  FK = Foreign Key
  U  = Unique Constraint
  N  = Nullable
  [] = Array type
```

## Tables Summary

| Table | Description | Row Estimate |
|-------|-------------|--------------|
| `users` | User accounts | 1K-10K |
| `organizations` | Companies/organizations | 100-1K |
| `organization_members` | User-Organization mapping | 1K-50K |
| `sites` | Solar installation sites | 100-10K |
| `devices` | Physical devices | 1K-100K |
| `alert_rules` | Alert definitions | 1K-10K |
| `alerts` | Alert instances | 10K-1M |
| `tariff_plans` | DISCO tariff rates | 100-500 |
| `billing_simulations` | Simulated electricity bills | 10K-1M |
| `reports` | Generated reports | 10K-1M |
| `report_schedules` | Scheduled report configurations | 1K-10K |
| `report_templates` | Custom report templates | 100-1K |
| `telemetry_hourly_summary` | Hourly aggregated telemetry | 100K-10M |
| `telemetry_daily_summary` | Daily aggregated telemetry | 10K-1M |
| `telemetry_monthly_summary` | Monthly aggregated telemetry | 1K-100K |
| `device_telemetry_snapshot` | Latest device readings | 1K-100K |

## Enum Types

### user_role
| Value | Description |
|-------|-------------|
| `super_admin` | Full system access |
| `owner` | Organization owner |
| `admin` | Organization administrator |
| `manager` | Site manager |
| `viewer` | Read-only access |
| `installer` | Device installation access |

### org_member_role
| Value | Description |
|-------|-------------|
| `owner` | Organization owner |
| `admin` | Full org admin access |
| `manager` | Site management |
| `viewer` | Read-only |
| `installer` | Device setup only |

### site_status
| Value | Description |
|-------|-------------|
| `active` | Normal operation |
| `inactive` | Temporarily disabled |
| `maintenance` | Under maintenance |
| `decommissioned` | Permanently offline |

### device_type
| Value | Description |
|-------|-------------|
| `inverter` | Solar inverter |
| `meter` | Energy meter |
| `battery` | Battery storage |
| `weather_station` | Weather monitoring |
| `sensor` | Generic sensor |
| `gateway` | Communication gateway |

### device_status
| Value | Description |
|-------|-------------|
| `online` | Connected and reporting |
| `offline` | Not responding |
| `error` | Error state |
| `maintenance` | Under maintenance |
| `unknown` | Status undetermined |

### protocol_type
| Value | Description |
|-------|-------------|
| `modbus_tcp` | Modbus over TCP/IP |
| `modbus_rtu` | Modbus RTU (serial) |
| `mqtt` | MQTT protocol |
| `http` | HTTP/REST API |
| `custom` | Custom protocol |

### alert_severity
| Value | Description |
|-------|-------------|
| `info` | Informational |
| `warning` | Needs attention |
| `critical` | Immediate action required |

### alert_status
| Value | Description |
|-------|-------------|
| `active` | Alert is active |
| `acknowledged` | User acknowledged |
| `resolved` | Issue resolved |
| `expired` | Auto-expired |

### report_type
| Value | Description |
|-------|-------------|
| `performance_summary` | Overall site performance |
| `energy_generation` | Energy generation details |
| `billing_summary` | Billing and cost analysis |
| `device_status` | Device health report |
| `alert_summary` | Alert history and trends |
| `maintenance` | Maintenance recommendations |
| `environmental_impact` | CO2 savings, trees equivalent |
| `comparison` | Multi-site comparison |
| `financial` | ROI and financial analysis |
| `executive_summary` | High-level executive report |
| `technical_detailed` | Detailed technical data |
| `regulatory_compliance` | NEPRA compliance report |
| `custom` | Custom user-defined report |

### report_format
| Value | Description |
|-------|-------------|
| `pdf` | PDF document |
| `excel` | Excel spreadsheet |
| `csv` | CSV data export |
| `html` | HTML report |
| `json` | JSON data export |

### report_frequency
| Value | Description |
|-------|-------------|
| `once` | One-time report |
| `daily` | Daily scheduled |
| `weekly` | Weekly scheduled |
| `monthly` | Monthly scheduled |
| `quarterly` | Quarterly scheduled |
| `yearly` | Yearly scheduled |

### report_status
| Value | Description |
|-------|-------------|
| `pending` | Queued for generation |
| `generating` | Currently generating |
| `completed` | Successfully completed |
| `failed` | Generation failed |
| `delivered` | Delivered to recipients |
| `expired` | Expired (auto-cleanup) |

### delivery_method
| Value | Description |
|-------|-------------|
| `download` | Available for download |
| `email` | Email delivery |
| `webhook` | POST to webhook URL |
| `storage` | Save to cloud storage |

## JSON Schemas

### users.preferences
```json
{
  "language": "en",
  "timezone": "Asia/Karachi",
  "currency": "PKR",
  "notifications": {
    "email": true,
    "sms": false,
    "push": true
  },
  "dashboard": {
    "default_view": "overview",
    "refresh_interval": 30
  }
}
```

### sites.configuration
```json
{
  "system_capacity_kw": 100.0,
  "panel_count": 200,
  "panel_wattage": 500,
  "inverter_capacity_kw": 100.0,
  "battery_capacity_kwh": 50.0,
  "grid_connected": true,
  "net_metering_enabled": true,
  "disco_provider": "lesco",
  "tariff_category": "commercial_b2",
  "installation_date": "2024-01-15",
  "warranty_expiry": "2034-01-15"
}
```

### sites.address
```json
{
  "street": "123 Main St",
  "city": "Lahore",
  "state": "Punjab",
  "postal_code": "54000",
  "country": "Pakistan"
}
```

### devices.connection_config (Modbus TCP)
```json
{
  "host": "192.168.1.100",
  "port": 502,
  "slave_id": 1,
  "timeout_seconds": 5
}
```

### devices.connection_config (MQTT)
```json
{
  "broker": "mqtt.example.com",
  "port": 1883,
  "topic_prefix": "solar/site1/inv1",
  "client_id": "device-123",
  "username": "device",
  "use_tls": false
}
```

### alert_rules.condition
```json
{
  "metric": "power_output",
  "operator": "lt",
  "threshold": 10.0,
  "duration_seconds": 300,
  "device_type": "inverter"
}
```

### tariff_plans.rates
```json
{
  "energy_charge_per_kwh": "25.00",
  "slabs": [
    {"min_units": 0, "max_units": 100, "rate_per_kwh": "7.74", "fixed_charges": "0"},
    {"min_units": 101, "max_units": 200, "rate_per_kwh": "10.06", "fixed_charges": "0"},
    {"min_units": 201, "max_units": 300, "rate_per_kwh": "12.15", "fixed_charges": "0"},
    {"min_units": 301, "max_units": 700, "rate_per_kwh": "19.21", "fixed_charges": "0"},
    {"min_units": 701, "max_units": null, "rate_per_kwh": "25.72", "fixed_charges": "0"}
  ],
  "peak_rate_per_kwh": "30.00",
  "off_peak_rate_per_kwh": "18.00",
  "fixed_charges_per_month": "150.00",
  "meter_rent": "25.00",
  "fuel_price_adjustment": "3.50",
  "quarterly_tariff_adjustment": "1.20",
  "electricity_duty_percent": "1.5",
  "gst_percent": "17",
  "tv_fee": "35",
  "export_rate_per_kwh": "19.32",
  "demand_charge_per_kw": "400.00"
}
```

### billing_simulations.bill_breakdown
```json
{
  "energy_charges": "5000.00",
  "slab_breakdown": [
    {"slab": "0-100", "units": 100, "rate": "7.74", "amount": "774.00"},
    {"slab": "101-200", "units": 100, "rate": "10.06", "amount": "1006.00"},
    {"slab": "201-300", "units": 100, "rate": "12.15", "amount": "1215.00"}
  ],
  "fixed_charges": "150.00",
  "meter_rent": "25.00",
  "fuel_price_adjustment": "350.00",
  "quarterly_tariff_adjustment": "120.00",
  "electricity_duty": "75.00",
  "gst": "850.00",
  "tv_fee": "35.00",
  "export_credit": "500.00",
  "demand_charges": "0.00",
  "subtotal": "5500.00",
  "total_taxes": "960.00",
  "total_bill": "6460.00"
}
```

### billing_simulations.savings_breakdown
```json
{
  "bill_without_solar": "10000.00",
  "bill_with_solar": "6460.00",
  "total_savings": "3540.00",
  "savings_percent": "35.4",
  "export_income": "500.00",
  "co2_avoided_kg": "250.00",
  "trees_equivalent": "12.5"
}
```

### reports.parameters
```json
{
  "site_ids": ["uuid1", "uuid2"],
  "device_ids": ["uuid3"],
  "date_range": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "comparison_start_date": "2025-01-01",
    "comparison_end_date": "2025-01-31"
  },
  "include_sections": ["summary", "charts", "data_tables", "recommendations"],
  "grouping": "daily",
  "comparison_mode": "year_over_year",
  "custom_filters": {
    "min_power_kw": 10,
    "device_types": ["inverter"]
  }
}
```

### report_schedules.delivery_config
```json
{
  "methods": ["email", "storage"],
  "recipients": [
    {
      "email": "admin@company.com",
      "name": "Admin User",
      "type": "to"
    },
    {
      "email": "manager@company.com",
      "name": "Manager",
      "type": "cc"
    }
  ],
  "email_subject": "Monthly Performance Report - {{site_name}}",
  "email_body": "Please find attached the performance report for {{period}}.",
  "webhook_url": "https://api.example.com/reports",
  "webhook_headers": {
    "Authorization": "Bearer token123"
  },
  "storage_path": "/reports/monthly/{{year}}/{{month}}/",
  "storage_provider": "s3"
}
```

### report_templates.branding
```json
{
  "logo_url": "https://cdn.example.com/logo.png",
  "primary_color": "#1a73e8",
  "secondary_color": "#34a853",
  "font_family": "Roboto",
  "header_text": "Solar Performance Report",
  "footer_text": "Generated by Solar Hub - Confidential",
  "show_page_numbers": true,
  "include_cover_page": true,
  "cover_page_image": "https://cdn.example.com/cover.jpg"
}
```

### report_templates.sections
```json
[
  {
    "id": "executive_summary",
    "title": "Executive Summary",
    "type": "text_summary",
    "order": 1,
    "enabled": true,
    "config": {
      "max_bullets": 5
    }
  },
  {
    "id": "energy_chart",
    "title": "Energy Generation",
    "type": "chart",
    "order": 2,
    "enabled": true,
    "config": {
      "chart_type": "line",
      "show_comparison": true
    }
  },
  {
    "id": "device_table",
    "title": "Device Performance",
    "type": "data_table",
    "order": 3,
    "enabled": true,
    "config": {
      "columns": ["device_name", "energy_kwh", "uptime_percent"],
      "sort_by": "energy_kwh",
      "sort_order": "desc"
    }
  },
  {
    "id": "financial_summary",
    "title": "Financial Impact",
    "type": "kpi_cards",
    "order": 4,
    "enabled": true,
    "config": {
      "metrics": ["savings_pkr", "roi_percent", "payback_years"]
    }
  }
]
```

## Billing & Tariff Tables

The billing tables enable utility billing simulation, a key differentiator for the Solar Hub platform. They store Pakistan DISCO tariff structures and calculate simulated bills based on site energy consumption.

### tariff_plans
Stores electricity tariff plans for all Pakistan DISCOs with slab-based, flat-rate, and time-of-use (TOU) pricing structures.

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `disco_provider` | VARCHAR | DISCO code (lesco, fesco, etc.) |
| `category` | VARCHAR | Tariff category (residential, commercial, industrial) |
| `effective_from` | DATE | Start date of tariff validity |
| `effective_to` | DATE | End date (NULL = currently active) |
| `rates` | JSONB | Complete rate structure (slabs, TOU, surcharges) |
| `supports_net_metering` | BOOLEAN | Whether net metering is supported |
| `supports_tou` | BOOLEAN | Whether TOU pricing is available |

### billing_simulations
Stores simulated electricity bills for sites based on energy consumption and tariff plans.

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `site_id` | UUID | Reference to site |
| `tariff_plan_id` | UUID | Reference to tariff plan used |
| `period_start` | DATE | Billing period start |
| `period_end` | DATE | Billing period end |
| `energy_consumed_kwh` | NUMERIC | Total energy consumed |
| `energy_exported_kwh` | NUMERIC | Energy exported to grid (net metering) |
| `bill_breakdown` | JSONB | Detailed bill calculation |
| `savings_breakdown` | JSONB | Savings analysis with/without solar |
| `estimated_bill_pkr` | NUMERIC | Total estimated bill in PKR |
| `estimated_savings_pkr` | NUMERIC | Total savings in PKR |
| `is_actual` | BOOLEAN | TRUE if based on actual readings |

### Tariff Categories

| Category | Description |
|----------|-------------|
| `residential_protected` | Low-income residential (subsidized) |
| `residential_unprotected` | Standard residential |
| `commercial_a1` | Small commercial (<5kW) |
| `commercial_a2` | Medium commercial (5-500kW) |
| `commercial_a3` | Large commercial (>500kW) |
| `industrial_b1` | Small industrial (<25kW) |
| `industrial_b2` | Medium industrial (25-500kW) |
| `industrial_b3` | Large industrial (500-5000kW) |
| `industrial_b4` | Peak/off-peak industrial |
| `agricultural_tube_well` | Agricultural (tube wells) |
| `tou_industrial` | Time-of-use industrial |
| `tou_commercial` | Time-of-use commercial |

### Billing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    BILLING SIMULATION FLOW                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────┐      ┌──────────────────┐      ┌────────────────┐
│  Site Config    │      │   Tariff Plan    │      │ Energy Data    │
│  - DISCO        │      │   - Rates        │      │ - Consumed     │
│  - Category     │─────►│   - Slabs        │◄─────│ - Generated    │
│  - Net Metering │      │   - Surcharges   │      │ - Exported     │
└─────────────────┘      └────────┬─────────┘      └────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │    Billing Calculator       │
                    │    - Apply slab rates       │
                    │    - Calculate surcharges   │
                    │    - Apply taxes            │
                    │    - Calculate export credit│
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │   billing_simulations       │
                    │   - bill_breakdown          │
                    │   - savings_breakdown       │
                    │   - estimated_bill_pkr      │
                    │   - estimated_savings_pkr   │
                    └─────────────────────────────┘
```

## Telemetry Tables

The telemetry tables store aggregated data summaries for dashboard queries and historical analysis. Raw telemetry is stored in System B (TimescaleDB).

### telemetry_hourly_summary
Hourly aggregated data for each site/device. Used for:
- Intraday performance charts
- Real-time dashboard updates
- Short-term trend analysis

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `site_id` | UUID | Reference to site |
| `device_id` | UUID | Device reference (NULL = site-level) |
| `timestamp_hour` | TIMESTAMPTZ | Start of the hour |
| `energy_generated_kwh` | FLOAT | Energy generated in hour |
| `peak_power_kw` | FLOAT | Peak power during hour |
| `performance_ratio` | FLOAT | Performance ratio (0-1) |
| `sample_count` | INT | Number of readings aggregated |

### telemetry_daily_summary
Daily aggregated data for historical analysis and reporting. Used for:
- Daily performance reports
- Month-over-month comparison
- Billing calculations

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `summary_date` | DATE | Date of summary |
| `net_energy_kwh` | FLOAT | Generated - Consumed |
| `sunshine_hours` | FLOAT | Hours with significant generation |
| `co2_avoided_kg` | FLOAT | Environmental impact |
| `estimated_savings_pkr` | FLOAT | Financial savings in PKR |
| `data_completeness_percent` | FLOAT | Data quality metric |

### telemetry_monthly_summary
Monthly aggregated data for long-term analysis and billing. Used for:
- Monthly reports and invoices
- Year-over-year comparison
- Capacity planning

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `year` | INT | Year (2020-2100) |
| `month` | INT | Month (1-12) |
| `expected_generation_kwh` | FLOAT | Expected based on capacity |
| `generation_variance_percent` | FLOAT | Actual vs expected variance |
| `trees_equivalent` | FLOAT | CO2 offset visualization |

### device_telemetry_snapshot
Latest readings per device for real-time dashboard display. Updated on each reading.

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `device_id` | UUID | Primary key (one per device) |
| `timestamp` | TIMESTAMPTZ | Time of reading |
| `current_power_kw` | FLOAT | Current power output |
| `battery_soc_percent` | FLOAT | Battery state of charge |
| `operating_state` | VARCHAR | Device operating state |
| `raw_data` | JSONB | Raw device data for debugging |

### Telemetry Aggregation Hierarchy

```
Raw Telemetry (System B - TimescaleDB)
        │
        ▼ (every 5-15 min)
┌─────────────────────────────────┐
│  device_telemetry_snapshot      │ ◄── Real-time dashboard
│  (one per device, latest only)  │
└─────────────────────────────────┘
        │
        ▼ (hourly worker)
┌─────────────────────────────────┐
│  telemetry_hourly_summary       │ ◄── Intraday charts
│  (per site/device per hour)     │
└─────────────────────────────────┘
        │
        ▼ (end of day)
┌─────────────────────────────────┐
│  telemetry_daily_summary        │ ◄── Daily reports
│  (per site/device per day)      │
└─────────────────────────────────┘
        │
        ▼ (end of month)
┌─────────────────────────────────┐
│  telemetry_monthly_summary      │ ◄── Monthly reports, billing
│  (per site/device per month)    │
└─────────────────────────────────┘
```

## Report Tables

The report tables enable automated report generation and scheduling, allowing users to create custom reports with organization branding and schedule automated delivery via email or webhook.

### reports
Stores individual report instances (both on-demand and scheduled).

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `organization_id` | UUID | Reference to organization |
| `created_by` | UUID | User who requested the report |
| `report_type` | VARCHAR(50) | Type of report (performance_summary, billing_summary, etc.) |
| `name` | VARCHAR(255) | User-friendly report name |
| `parameters` | JSONB | Report generation parameters |
| `format` | VARCHAR(20) | Output format (pdf, excel, csv, html, json) |
| `status` | VARCHAR(20) | Generation status (pending, generating, completed, failed) |
| `file_path` | VARCHAR(500) | Path to generated report file |
| `file_size_bytes` | INTEGER | Size of generated file |
| `schedule_id` | UUID | Reference to schedule (NULL = on-demand) |
| `expires_at` | TIMESTAMPTZ | When report file should be deleted |

### report_schedules
Defines scheduled report configurations for automated generation.

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `organization_id` | UUID | Reference to organization |
| `created_by` | UUID | User who created the schedule |
| `name` | VARCHAR(255) | Schedule name |
| `report_type` | VARCHAR(50) | Type of report to generate |
| `parameters` | JSONB | Default report parameters |
| `format` | VARCHAR(20) | Output format |
| `frequency` | VARCHAR(20) | Generation frequency (daily, weekly, monthly, etc.) |
| `run_time` | TIME | Time of day to run |
| `day_of_week` | INTEGER | Day for weekly reports (0=Monday) |
| `day_of_month` | INTEGER | Day for monthly reports (1-28) |
| `timezone` | VARCHAR(50) | Timezone for scheduling |
| `delivery_config` | JSONB | Email/webhook delivery configuration |
| `is_active` | BOOLEAN | Whether schedule is active |
| `next_run_at` | TIMESTAMPTZ | Next scheduled execution time |
| `total_runs` | INTEGER | Total number of executions |
| `successful_runs` | INTEGER | Successful executions |
| `failed_runs` | INTEGER | Failed executions |

### report_templates
Stores custom report templates with branding and section configuration.

Key fields:
| Field | Type | Description |
|-------|------|-------------|
| `organization_id` | UUID | Reference to organization |
| `created_by` | UUID | User who created the template |
| `name` | VARCHAR(255) | Template name |
| `report_type` | VARCHAR(50) | Type of report this template applies to |
| `branding` | JSONB | Logo, colors, fonts configuration |
| `sections` | JSONB | Array of section definitions |
| `default_parameters` | JSONB | Default parameters for reports using this template |
| `is_active` | BOOLEAN | Whether template is available |
| `is_default` | BOOLEAN | Whether this is the default template for its type |
| `usage_count` | INTEGER | Number of reports generated with this template |

### Report Types

| Type | Description | Typical Use |
|------|-------------|-------------|
| `performance_summary` | Overall site performance metrics | Monthly executive reports |
| `energy_generation` | Detailed energy generation data | Technical analysis |
| `billing_summary` | Billing and cost analysis | Finance team |
| `device_status` | Device health and status report | O&M team |
| `alert_summary` | Alert history and trends | Operations monitoring |
| `environmental_impact` | CO2 savings, environmental metrics | ESG reporting |
| `comparison` | Multi-site performance comparison | Portfolio management |
| `financial` | ROI, payback analysis | Investment tracking |
| `regulatory_compliance` | NEPRA compliance report | Regulatory requirements |

### Report Generation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    REPORT GENERATION FLOW                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────┐      ┌──────────────────┐      ┌────────────────┐
│  User Request   │      │  Schedule Trigger │      │  Template      │
│  (On-Demand)    │      │  (Automated)      │      │  Configuration │
└────────┬────────┘      └────────┬─────────┘      └───────┬────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │     reports (pending)        │
                    │     - report_type            │
                    │     - parameters             │
                    │     - format                 │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │    Report Generator Worker   │
                    │    - Fetch data              │
                    │    - Apply template          │
                    │    - Generate output         │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │   reports (completed)        │
                    │   - file_path               │
                    │   - file_size_bytes         │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │   Delivery Service           │
                    │   - Email attachment         │
                    │   - Webhook POST             │
                    │   - Cloud storage upload     │
                    └─────────────────────────────┘
```

## Indexes

### Primary Indexes
- All tables have UUID primary keys
- Unique constraints on `users.email`, `organizations.slug`, `devices.serial_number`

### Foreign Key Indexes
- `organization_members(organization_id, user_id)`
- `sites(organization_id)`
- `devices(site_id, organization_id)`
- `alert_rules(organization_id, site_id)`
- `alerts(rule_id, organization_id, site_id, device_id)`

### Query Optimization Indexes
- `users(email)` - Login lookups
- `devices(status)` - Filter by status
- `devices(last_seen_at)` - Offline detection
- `alerts(triggered_at)` - Time-based queries
- `alerts(status, severity)` - Dashboard summaries
- `tariff_plans(disco_provider, category)` - Active tariff lookups
- `billing_simulations(site_id, period_start, period_end)` - Billing history queries
- `reports(organization_id, report_type)` - Filter by org and type
- `reports(status, requested_at)` - Report queue processing
- `report_schedules(organization_id, is_active)` - Active schedules lookup
- `report_schedules(is_active, next_run_at)` - Schedule worker queries
- `report_templates(organization_id, report_type)` - Template lookup
- GIN indexes on JSONB columns for JSON queries

### Telemetry Indexes
- `telemetry_hourly_summary(site_id, timestamp_hour)` - Site hourly queries
- `telemetry_hourly_summary(device_id, timestamp_hour)` - Device hourly queries
- `telemetry_daily_summary(site_id, summary_date)` - Site daily queries
- `telemetry_monthly_summary(site_id, year, month)` - Site monthly queries
- `device_telemetry_snapshot(site_id, timestamp)` - Real-time site queries

### Unique Constraints (Telemetry)
- `(site_id, device_id, timestamp_hour)` - One hourly record per site/device/hour
- `(site_id, device_id, summary_date)` - One daily record per site/device/date
- `(site_id, device_id, year, month)` - One monthly record per site/device/period

### Partial Indexes
- `devices WHERE status = 'online'` - Online device queries
- `alerts WHERE status = 'active' AND escalated = FALSE` - Escalation worker

## Triggers

### Auto-update `updated_at`
All tables have triggers that automatically set `updated_at = NOW()` on UPDATE.

### Auto-increment `version`
All tables have triggers that automatically increment `version` on UPDATE for optimistic locking.

## Views

### v_active_alerts_summary
Summary of active alerts per organization with counts by status and severity.

### v_device_status_summary
Device status counts per site (online, offline, error, maintenance).

### v_site_capacity
Site configuration overview with device counts.

### v_site_telemetry_live
Real-time telemetry summary per site from latest device snapshots. Includes:
- Total current power (kW)
- Total energy today (kWh)
- Number of devices reporting
- Oldest/newest reading timestamps

### v_site_daily_energy
Daily energy totals per site for the last 30 days. Used for dashboard charts.

### v_monthly_performance
Monthly performance metrics and financial impact per site. Includes:
- Energy generated vs expected
- Generation variance percentage
- Performance ratio and capacity factor
- CO2 avoided and estimated savings

## Pakistan-Specific Configurations

### DISCO Providers
Supported electricity distribution companies:
- `lesco` - Lahore
- `fesco` - Faisalabad
- `iesco` - Islamabad
- `gepco` - Gujranwala
- `mepco` - Multan
- `pesco` - Peshawar
- `hesco` - Hyderabad
- `sepco` - Sukkur
- `qesco` - Quetta
- `tesco` - Tribal Areas
- `kelectric` - Karachi

### Default Settings
- Timezone: `Asia/Karachi`
- Currency: `PKR`
- Language: English/Urdu

## Migration Commands

```bash
# Generate new migration
cd system_a
alembic revision --autogenerate -m "Description"

# Apply all migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Show current version
alembic current

# Show history
alembic history
```

## Performance Considerations

1. **Connection Pooling**: Use `pool_size=5` and `max_overflow=10` for production
2. **Query Optimization**: Use indexes for frequently filtered columns
3. **JSON Queries**: Use GIN indexes for JSONB columns
4. **Pagination**: Always use `LIMIT/OFFSET` for list queries
5. **Archival**: Consider partitioning `alerts` table by `triggered_at` for large installations
