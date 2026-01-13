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
- GIN indexes on JSONB columns for JSON queries

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
