# Solar Hub — Database Architecture & Design

## 1. Overview

Solar Hub uses a **two-database architecture** to separate concerns between business/management data and high-frequency telemetry ingestion.

| System | Database | Purpose |
|--------|----------|---------|
| **System A** | PostgreSQL 15+ | Business logic, user management, organizations, sites, devices, alerts, billing, reports |
| **System B** | TimescaleDB 2.x (PostgreSQL extension) | Real-time telemetry ingestion, time-series storage, continuous aggregation, device communication |

**Why two databases?**

- **Write pattern divergence** — System A handles low-volume transactional writes (users, config changes). System B handles high-volume append-only telemetry (thousands of metrics/second).
- **Query pattern divergence** — System A needs complex joins across business entities. System B needs time-range scans and rollup aggregations.
- **Scaling independence** — Telemetry storage grows linearly with device count and can be scaled horizontally via TimescaleDB multi-node, without affecting business database performance.
- **Retention isolation** — System B applies aggressive retention/compression policies (raw data kept 90 days). System A keeps business records permanently.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         SOLAR HUB ARCHITECTURE                          │
├─────────────────────────────┬────────────────────────────────────────────┤
│                             │                                            │
│   SYSTEM A (PostgreSQL)     │        SYSTEM B (TimescaleDB)              │
│   Business & Management     │        Telemetry & Communication           │
│                             │                                            │
│   ┌─────────┐ ┌──────────┐ │  ┌──────────────┐  ┌──────────────────┐   │
│   │  Users  │ │   Orgs   │ │  │device_registry│  │  telemetry_raw   │   │
│   └────┬────┘ └────┬─────┘ │  └──────┬───────┘  │   (hypertable)   │   │
│        │           │        │         │          └────────┬─────────┘   │
│   ┌────▼────┐ ┌────▼─────┐ │  ┌──────▼───────┐          │             │
│   │Members  │ │  Sites   │ │  │device_events  │   ┌──────▼───────┐     │
│   └─────────┘ └────┬─────┘ │  │ (hypertable)  │   │ Continuous   │     │
│               ┌────▼─────┐ │  └──────────────┘   │ Aggregates   │     │
│               │ Devices  │ │  ┌──────────────┐   │ 5m / 1h / 1d │     │
│               └────┬─────┘ │  │device_commands│   └──────────────┘     │
│        ┌───────────┼───┐   │  └──────────────┘                         │
│   ┌────▼──┐  ┌─────▼┐ │   │                                            │
│   │Alerts │  │Telem.│ │   │                                            │
│   │Rules  │  │Summ. │ │   │                                            │
│   └───────┘  └──────┘ │   │                                            │
│   ┌────────┐ ┌────────▼┐  │                                            │
│   │Billing │ │Reports  │  │                                            │
│   └────────┘ └─────────┘  │                                            │
│                             │                                            │
├─────────────────────────────┼────────────────────────────────────────────┤
│                             │                                            │
│              ┌──────────────┴──────────────┐                            │
│              │     Redis (Bridge Layer)     │                            │
│              │  • Pub/Sub: live snapshots   │                            │
│              │  • Cache: device status      │                            │
│              │  • Link: serial_number key   │                            │
│              └─────────────────────────────┘                            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Entity Relationship Diagram — System A

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     SYSTEM A — ENTITY RELATIONSHIPS                      │
└──────────────────────────────────────────────────────────────────────────┘

                            ┌─────────────┐
                            │    users     │
                            │─────────────│
                            │ id (PK)     │
                            │ email (UQ)  │
                            │ role        │
                            │ status      │
                            └──────┬──────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
          ┌─────────────┐  ┌────────────┐  ┌──────────────┐
          │organizations│  │organization│  │   reports     │
          │ (owner)     │  │  _members  │  │─────────────│
          │─────────────│  │────────────│  │ created_by   │──┐
          │ id (PK)     │  │ id (PK)    │  │ org_id (FK)  │  │
          │ owner_id(FK)│  │ org_id(FK) │  │ schedule_id  │  │
          │ slug (UQ)   │  │ user_id(FK)│  └──────────────┘  │
          │ site_count  │  │ role       │                     │
          └──────┬──────┘  │ status     │  ┌──────────────┐  │
                 │         └────────────┘  │report_schedules│ │
                 │                         │──────────────│  │
                 ▼                         │ org_id (FK)  │──┘
          ┌─────────────┐                  │ created_by   │
          │   sites     │                  └──────────────┘
          │─────────────│
          │ id (PK)     │                  ┌──────────────┐
          │ org_id (FK) │                  │report_templates│
          │ site_type   │                  │──────────────│
          │ device_ids[]│                  │ org_id (FK)  │
          │ address{}   │                  │ created_by   │
          │ config{}    │                  └──────────────┘
          └──────┬──────┘
                 │
                 ▼
          ┌─────────────────┐
          │    devices       │
          │─────────────────│
          │ id (PK)         │
          │ site_id (FK)    │
          │ org_id (FK)     │◄── denormalized
          │ serial_number(UQ)│◄── cross-system link
          │ device_type     │
          │ status          │
          └──────┬──────────┘
                 │
      ┌──────────┼──────────────────────┐
      │          │                      │
      ▼          ▼                      ▼
┌───────────┐ ┌───────────────┐  ┌────────────────────┐
│alert_rules│ │  alerts       │  │device_telemetry    │
│───────────│ │───────────────│  │  _snapshot          │
│ org_id(FK)│ │ rule_id (FK)  │  │────────────────────│
│ site_id   │ │ org_id (FK)   │  │ device_id (PK, FK) │
│ condition│ │ site_id (FK)  │  │ site_id (FK)       │
│ severity  │ │ device_id(FK) │  │ current_power_kw   │
└───────────┘ │ severity      │  │ raw_data{}         │
              │ status        │  └────────────────────┘
              └───────────────┘

┌──────────────────────────────────────────────────────────────┐
│                   TELEMETRY SUMMARIES                        │
│                                                              │
│  ┌────────────────────┐  ┌─────────────────────┐            │
│  │telemetry_hourly    │  │telemetry_daily      │            │
│  │  _summary          │  │  _summary           │            │
│  │────────────────────│  │─────────────────────│            │
│  │ site_id (FK)       │  │ site_id (FK)        │            │
│  │ device_id (FK)     │  │ device_id (FK)      │            │
│  │ timestamp_hour     │  │ summary_date        │            │
│  │ UQ(site,dev,hour)  │  │ UQ(site,dev,date)   │            │
│  └────────────────────┘  └─────────────────────┘            │
│                                                              │
│  ┌────────────────────┐                                      │
│  │telemetry_monthly   │                                      │
│  │  _summary          │                                      │
│  │────────────────────│                                      │
│  │ site_id (FK)       │                                      │
│  │ device_id (FK)     │                                      │
│  │ year, month        │                                      │
│  │ UQ(site,dev,y,m)   │                                      │
│  └────────────────────┘                                      │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    BILLING & TARIFFS                          │
│                                                              │
│  ┌─────────────────┐      ┌──────────────────────┐          │
│  │ tariff_plans     │      │ billing_simulations  │          │
│  │─────────────────│      │──────────────────────│          │
│  │ id (PK)         │◄─────│ tariff_plan_id (FK)  │          │
│  │ disco_provider  │      │ site_id (FK)         │──► sites │
│  │ category        │      │ bill_breakdown{}     │          │
│  │ rates{}         │      │ savings_breakdown{}  │          │
│  └─────────────────┘      └──────────────────────┘          │
│                                                              │
│  ┌──────────────────────┐                                    │
│  │protocol_definitions  │                                    │
│  │──────────────────────│                                    │
│  │ id (PK)              │                                    │
│  │ protocol_id (UQ)     │                                    │
│  │ device_type          │                                    │
│  │ protocol_type        │                                    │
│  │ adapter_class        │                                    │
│  └──────────────────────┘                                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Entity Relationship Diagram — System B

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     SYSTEM B — ENTITY RELATIONSHIPS                      │
└──────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │         DEVICE SOURCES            │
                    │  (Modbus, MQTT, HTTP, Custom)     │
                    └──────────────┬───────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────┐
                    │       device_registry             │
                    │──────────────────────────────────│
                    │ device_id (PK, UUID)              │
                    │ serial_number (UQ)       ◄── cross-system link
                    │ status: orphan | claimed          │
                    │ connection_status                 │
                    │ auth_token_hash                   │
                    └──────────────┬───────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
            ▼                      ▼                      ▼
 ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
 │  telemetry_raw   │   │  device_events   │   │ device_commands  │
 │  (Hypertable)    │   │  (Hypertable)    │   │  (Regular)       │
 │──────────────────│   │──────────────────│   │──────────────────│
 │ PK: time,        │   │ PK: time,        │   │ id (PK)          │
 │   device_id,     │   │   device_id,     │   │ device_id        │
 │   metric_name    │   │   event_type     │   │ command_type     │
 │ Chunk: 1 hour    │   │ Chunk: 1 day     │   │ status           │
 │ Retention: 90d   │   │ Retention: 1yr   │   │ priority         │
 │ Compress: 7d     │   │ Compress: 30d    │   └──────────────────┘
 └────────┬─────────┘   └──────────────────┘
          │
          │ Continuous Aggregates (auto-refreshed)
          │
          ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                                                              │
 │   ┌────────────┐    ┌────────────┐    ┌────────────┐        │
 │   │telemetry   │    │telemetry   │    │telemetry   │        │
 │   │  _5min     │───▶│  _hourly   │───▶│  _daily    │        │
 │   │ (7 days)   │    │ (90 days)  │    │ (5 years)  │        │
 │   └────────────┘    └────────────┘    └────────────┘        │
 │                                                              │
 │   Real-time          Daily charts     Monthly/Yearly         │
 │   dashboard                           reports                │
 │                                                              │
 │   ┌────────────────┐  (from device_events)                   │
 │   │event_counts    │                                         │
 │   │  _hourly       │  Event monitoring                       │
 │   └────────────────┘                                         │
 └──────────────────────────────────────────────────────────────┘

 ┌──────────────────┐   ┌──────────────────┐
 │metric_definitions│   │ingestion_batches │
 │──────────────────│   │──────────────────│
 │ metric_name (PK) │   │ id (PK)          │
 │ display_name     │   │ source_type      │
 │ unit             │   │ record_count     │
 │ device_types[]   │   │ status           │
 │ min/max_value    │   └──────────────────┘
 │ aggregation_method│
 └──────────────────┘

 ┌──────────────────────────────────┐
 │        VIEWS & FUNCTIONS         │
 │──────────────────────────────────│
 │ v_site_current_power (view)      │
 │ v_site_energy_today  (view)      │
 │ get_latest_metric()              │
 │ get_metrics_interpolated()       │
 │ calculate_energy_produced()      │
 │ get_site_status_summary()        │
 └──────────────────────────────────┘
```

---

## 4. Cross-System Relationships

System A and System B are separate databases with no direct foreign keys. They are linked through two mechanisms:

### 4.1 Serial Number (Primary Link)

The `serial_number` field is the canonical cross-system identifier:

```
System A                          System B
┌─────────────────┐              ┌──────────────────┐
│ devices          │              │ device_registry   │
│                  │              │                   │
│ serial_number ◄──┼──── same ───┼──► serial_number  │
│ (UQ, indexed)    │   value     │ (UQ, indexed)     │
│                  │              │                   │
│ id: UUID-A       │              │ device_id: UUID-B │
│ site_id          │              │ site_id           │
│ organization_id  │              │ organization_id   │
└─────────────────┘              └──────────────────┘
```

- Each system generates its own UUID for the device.
- `serial_number` is unique in both systems and serves as the join key during sync operations.
- When a device is "claimed" in System B (`status: orphan → claimed`), it is matched to a System A device record by serial number.

### 4.2 Redis (Bridge Layer)

Redis acts as the real-time bridge between the two systems:

| Redis Key Pattern | Direction | Purpose |
|-------------------|-----------|---------|
| `device:{serial_number}:status` | B → A | Live connection status |
| `device:{serial_number}:snapshot` | B → A | Latest telemetry snapshot (JSON) |
| `device:{serial_number}:metrics` | B → A | Current metric values |
| `site:{site_id}:power` | B → A | Aggregated site power |
| Channel: `telemetry.{serial_number}` | B → A | Pub/Sub live updates |
| Channel: `commands.{serial_number}` | A → B | Device command dispatch |

### 4.3 Sync Table Mapping

Aggregated data flows from System B to System A on a schedule:

| System B Source | System A Destination | Frequency |
|-----------------|---------------------|-----------|
| `telemetry_5min` (continuous agg) | `device_telemetry_snapshot` | Real-time via Redis |
| `telemetry_hourly` (continuous agg) | `telemetry_hourly_summary` | Every hour |
| `telemetry_daily` (continuous agg) | `telemetry_daily_summary` | End of day |
| Monthly rollup query | `telemetry_monthly_summary` | 1st of month |

---

## 5. Design Decisions

### 5.1 Denormalized `organization_id` on Devices

The `devices` table stores `organization_id` directly, even though it can be derived via `devices → sites → organizations`.

**Rationale:**
- Eliminates a JOIN for authorization queries (`SELECT ... FROM devices WHERE organization_id = :org_id`)
- Alert creation needs `org_id` without loading the full site
- Multi-tenant query filtering is a hot path — every API request filters by org
- Trade-off: Requires keeping `devices.organization_id` in sync when a site is transferred between organizations (rare operation)

### 5.2 Bidirectional `device_ids` on Sites

The `sites` table has a `device_ids: ARRAY(UUID)` column, while `devices` has `site_id: FK → sites`.

**Rationale:**
- `devices.site_id` is the authoritative foreign key (enforced by DB)
- `sites.device_ids[]` is a denormalized cache for fast site-level device listing without a reverse query
- Used by the frontend to quickly render device counts and lists on site cards
- Trade-off: Must be updated on device add/remove (handled by domain methods `site.add_device()` / `site.remove_device()`)

### 5.3 Hypertable Chunking Strategy

| Hypertable | Chunk Interval | Rationale |
|------------|---------------|-----------|
| `telemetry_raw` | 1 hour | Queries typically access "last few hours"; small chunks enable fast pruning and compression of older data |
| `device_events` | 1 day | Lower volume than telemetry; queries span days/weeks for incident analysis |

### 5.4 Continuous Aggregates

Four continuous aggregates avoid expensive real-time rollups:

| Aggregate | Source | Bucket | Refresh | Retention | Use Case |
|-----------|--------|--------|---------|-----------|----------|
| `telemetry_5min` | `telemetry_raw` | 5 minutes | Every 5 min | 7 days | Live dashboard, real-time charts |
| `telemetry_hourly` | `telemetry_raw` | 1 hour | Every hour | 90 days | Intraday analysis, daily charts |
| `telemetry_daily` | `telemetry_raw` | 1 day | Once/day | 5 years | Monthly/yearly reports, trends |
| `event_counts_hourly` | `device_events` | 1 hour | Every hour | — | Event monitoring, alert frequency |

The three telemetry aggregates each compute: `avg_value`, `min_value`, `max_value`, `first_value`, `last_value`, `delta_value`, `sample_count`, `good_count`.

The `event_counts_hourly` aggregate computes: `event_count`, `unacknowledged_count` grouped by `site_id`, `event_type`, `severity`.

The `delta_value` (last − first) is critical for cumulative metrics like `energy_total` where the raw values are monotonically increasing counters.

### 5.5 Retention & Compression Policies

```
Time ──────────────────────────────────────────────────►

telemetry_raw:
  │◄─ uncompressed ─►│◄─── compressed (10-20x) ──►│ dropped
  0                  7 days                       90 days

device_events:
  │◄── uncompressed ──►│◄─── compressed (5-10x) ──────────►│ dropped
  0                   30 days                              1 year

telemetry_5min:      │◄───►│ dropped
                     0    7 days

telemetry_hourly:    │◄──────────────────────────►│ dropped
                     0                           90 days

telemetry_daily:     │◄──────────────────────────────────────────────►│ dropped
                     0                                              5 years
```

**Compression settings for `telemetry_raw`:**
- Segment by: `device_id`, `metric_name` (queries filter by device)
- Order by: `time DESC` (most queries access recent data first)
- Expected compression ratio: 10-20x

### 5.6 Separate Device Registries

System B maintains its own `device_registry` rather than querying System A's `devices` table.

**Rationale:**
- System B must function independently (network partition tolerance)
- Device auth tokens and connection state are System B concerns
- Polling schedules and protocol configs are real-time operational data
- The `orphan → claimed` lifecycle is System B specific (devices self-register before being claimed by a user in System A)

---

## 6. Naming Conventions

### 6.1 Constraint Naming (SQLAlchemy MetaData Convention)

Both systems use the same convention defined in `connection.py`:

```python
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

| Type | Pattern | Example |
|------|---------|---------|
| Primary Key | `pk_{table}` | `pk_users` |
| Foreign Key | `fk_{table}_{column}_{referred_table}` | `fk_devices_site_id_sites` |
| Unique | `uq_{table}_{column}` | `uq_users_email` |
| Check | `ck_{table}_{name}` | `ck_devices_status` |
| Index | `ix_{column}` | `ix_users_email` |

### 6.2 Table Naming

- Auto-generated from ORM class names: `CamelCase` → `snake_case` + `s`
- Examples: `UserModel` → `users`, `AlertRuleModel` → `alert_rules`
- System B tables use descriptive names without the `s` suffix: `device_registry`, `telemetry_raw`

### 6.3 Enum Naming

PostgreSQL enums use lowercase string values matching the Python enum `.value`:

```python
class DeviceStatus(str, Enum):
    PENDING = "pending"
    ONLINE = "online"
    ...
```

Stored via `values_callable=lambda e: [x.value for x in e]` to persist lowercase strings rather than Python enum names.

### 6.4 Custom Index Naming

Beyond the convention, many indexes use explicit names for composite or special-purpose indexes:

```
idx_{table}_{columns}        — composite indexes
idx_{table}_{purpose}        — purpose-named indexes
```

Examples: `idx_hourly_site_time`, `idx_billing_site_period`, `idx_reports_status_requested`

---

## 7. Base Model Pattern

All System A ORM models inherit from a `BaseModel` that provides three mixins:

```python
class BaseModel(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """Standard base for all business entities."""
```

### UUIDMixin

```python
id: UUID  # Primary key, auto-generated via uuid4()
```

### TimestampMixin

```python
created_at: DateTime(timezone=True)  # Set on INSERT, never modified
updated_at: DateTime(timezone=True)  # Auto-updated on every UPDATE via onupdate=func.now()
```

### VersionMixin

```python
version: Integer  # Default 1, incremented for optimistic locking
```

**Optimistic locking pattern:** Domain entities call `increment_version()` before persistence. The repository layer includes `WHERE version = :expected_version` in UPDATE statements to detect concurrent modifications.

**Exceptions:**
- `DeviceTelemetrySnapshotModel` — Uses `device_id` as PK (one row per device, upserted). Has `created_at` / `updated_at` but no `version`.
- `TelemetryHourlySummaryModel` — Has UUID PK but only `created_at` (immutable after creation).
- System B models — Do not use the BaseModel; they define columns directly with appropriate defaults.

---

## 8. Migration History

System A uses Alembic for schema migrations. 8 migrations have been applied:

| # | Date | Revision | Description |
|---|------|----------|-------------|
| 001 | 2026-01-13 | `001` | **Initial schema** — `users`, `organizations`, `organization_members`, `sites`, `devices`, `alert_rules`, `alerts`. Created core enums: `user_role`, `device_type`, `device_status`, `protocol_type`, `alert_severity`, `alert_status`, `site_status`. |
| 002 | 2026-01-13 | `002` | **Telemetry tables** — `telemetry_hourly_summary`, `telemetry_daily_summary`, `telemetry_monthly_summary`, `device_telemetry_snapshot`. Added composite unique constraints and time-based indexes. |
| 003 | 2026-01-13 | `003` | **Billing tables** — `tariff_plans`, `billing_simulations`. Added JSONB columns for rate structures and bill breakdowns. |
| 004 | 2026-01-14 | `004` | **Report tables** — `reports`, `report_schedules`, `report_templates`. Added JSONB columns for parameters, branding, sections, delivery config. |
| 005 | 2026-01-15 | `005` | **Protocol definitions** — `protocol_definitions`. Maps device types and protocols to adapter implementations. |
| 006 | 2026-01-22 | `006` | **Device table updates** — Added `last_error_at`, `last_error_message`, `latest_metrics` (JSONB), `tags` (array), `total_messages_received`, `total_errors`, `uptime_percentage`. Made `manufacturer`/`model` NOT NULL. |
| 007 | 2026-01-24 | `007` | **User table refactor** — Added `status` enum (`user_status`), `email_verified_at`, `failed_login_attempts`, `locked_until`. Removed `is_active`, `is_verified`, `verification_token`, `reset_token`. Migrated existing data. |
| 008 | 2026-01-24 | `008` | **Org & site updates** — Added enums `organization_status`, `membership_status`, `site_type`. Added `site_count` to orgs. Added `site_type`, `device_ids[]`, `notes`, contact fields to sites. Refactored member invitation fields. |

System B does not use Alembic — schema is created programmatically via SQLAlchemy models and TimescaleDB API calls (`create_hypertable`, `add_retention_policy`, `add_compression_policy`, `CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)`).

---

## 9. Data Retention & Lifecycle

### 9.1 System A — Permanent Storage

All System A tables are retained permanently. No automatic retention policies.

| Data Type | Retention | Notes |
|-----------|-----------|-------|
| Users, Orgs, Sites, Devices | Permanent | Soft-delete via `status` enum (e.g., `DEACTIVATED`, `DECOMMISSIONED`) |
| Telemetry summaries (hourly/daily/monthly) | Permanent | Pre-aggregated from System B data |
| Device snapshots | Permanent | Upserted (1 row per device, always current) |
| Alerts | Permanent | Lifecycle: `ACTIVE → ACKNOWLEDGED → RESOLVED/EXPIRED` |
| Billing simulations | Permanent | Historical billing records |
| Reports | Permanent | Generated files may have `expires_at` for cleanup |
| Report schedules/templates | Permanent | `is_active` flag for soft-disable |

### 9.2 System B — Managed Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA RETENTION TIMELINE                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  telemetry_5min    ├────────┤                   (7 days)    │
│                                                             │
│  telemetry_raw     ├──────────────────────────┤ (90 days)   │
│  telemetry_hourly  ├──────────────────────────┤ (90 days)   │
│                                                             │
│  device_events     ├────────────────────────────────────┤   │
│                                                  (1 year)   │
│                                                             │
│  telemetry_daily   ├────────────────────────────────────────┤
│                                                    (5 years) │
│                                                             │
│  device_registry   │ permanent                              │
│  device_commands   │ permanent                              │
│  metric_definitions│ permanent                              │
│  ingestion_batches │ permanent                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 Storage Estimates (per 100 devices, 10 metrics, 1-min interval)

| Data | Records/Day | Size/Day | Size/Month |
|------|-------------|----------|------------|
| Raw (uncompressed) | 1.44M | ~200 MB | ~6 GB |
| Raw (compressed, after 7d) | 1.44M | ~15 MB | ~450 MB |
| 5-min aggregates | 288K | ~40 MB | ~1.2 GB |
| Hourly aggregates | 24K | ~3 MB | ~90 MB |
| Daily aggregates | 1K | ~150 KB | ~4.5 MB |

**With retention policies applied:** ~50 GB per 100 devices for 90-day raw + 5-year daily.
