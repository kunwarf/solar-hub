# Solar Hub: Frontend-Backend Integration - Implementation Plan

> **Created:** 2026-01-28
> **Status:** Phase 1 - Ready for Implementation
> **Purpose:** This document captures the full analysis and implementation plan for hooking all frontend screens/widgets with the backend. It persists across sessions.

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Gap Analysis](#2-gap-analysis)
3. [Phase Overview](#3-phase-overview)
4. [Phase 1: Telemetry Aggregation Foundation (Detailed)](#4-phase-1-detailed)
5. [Phase 2-6 Summary](#5-phases-2-6-summary)
6. [Architecture Reference](#6-architecture-reference)
7. [Key File Paths](#7-key-file-paths)

---

## 1. Current State Analysis

### Frontend Data Coverage

| Category | Real API | Mock/Hardcoded | Coverage |
|----------|----------|----------------|----------|
| Frontend Pages (21 total) | 8 (~38%) | 13 (~62%) | Low |
| Dashboard Widgets (20 total) | 2 (10%) | 18 (90%) | Very Low |
| Hooks (15 total) | 9 (60%) | 6 (40%) | Medium |
| API Services (8 total) | 8 (100%) | 0 (0%) | Full |
| Backend Endpoints (System A) | ~90% implemented | ~10% partial/TODO | High |
| Backend Endpoints (System B) | ~95% implemented | ~5% TODO | High |

### Pages Using Mock Data

| Page | Mock Data Areas | Priority |
|------|----------------|----------|
| **Index (Dashboard)** | 18/20 widgets use hardcoded data | Critical |
| **Billing** | Static PKR slab data, no real consumption | High |
| **BillingSettings** | Default config, no persistence | High |
| **TariffSettings** | Static Pakistan tariff files | High |
| **Outages** | Entire page is mock load-shedding data | Medium |
| **Savings** | Mock savings calculations | Medium |
| **SmartScheduler** | Mock scheduling logic | Low (Phase 2) |
| **DeviceManagement** | Partial mock device settings | Medium |
| **DeviceSettings** | Mock configuration data | Medium |
| **Settings** | Local storage only | Low |
| **Notifications** | Mock notification data | Medium |
| **Commissioning** | Mock commissioning flow | Low |
| **Profile** | Partial - real user data, mock preferences | Low |

### Dashboard Widgets Using Mock Data (18/20)

| Widget | Required Backend Support |
|--------|------------------------|
| **StatCards** | Telemetry summaries + billing calc |
| **EnergyFlowDiagram** | Real-time telemetry (Redis) |
| **SystemDiagram** | Real-time telemetry (Redis) |
| **EnergyChart** | TimescaleDB aggregates |
| **WeatherWidget** | External weather API |
| **QuickActions** | Device command API |
| **GoalTracking** | Goal config + telemetry summaries |
| **EnvironmentalImpact** | Telemetry summaries + factors |
| **LoadSheddingSchedule** | External API or manual config |
| **BillingSummary** | Billing engine + telemetry summaries |
| **AlertsSummary** | Alert query API (exists) |
| **AIInsights** | ML pipeline or rule engine |
| **ComparisonChart** | TimescaleDB aggregates |
| **SystemStatus** | Device status from Redis |
| **BatteryDetail** | Telemetry summaries + device metadata |
| **GridStatus** | Real-time telemetry (Redis) |
| **SelfConsumption** | Telemetry summaries |
| **PeakDemand** | Telemetry aggregates |

### Widgets Already Using Real Data (2/20)

- **HierarchicalDeviceOverview** - polls `/api/v1/dashboard/device-status` at 5s intervals
- **PowerFlow** (partial) - via TelemetryContext polling `/api/v1/dashboard/power-flow`

---

## 2. Gap Analysis

### The Core Problem

System A's telemetry summary tables exist (schema + models + repository) but are **EMPTY**:
- `telemetry_hourly_summary` - created in migration 002, has SQLAlchemy model, has repository queries - **NO DATA**
- `telemetry_daily_summary` - same - **NO DATA**
- `telemetry_monthly_summary` - same - **NO DATA**

**Root Cause:** No mechanism exists to populate these tables from System B's TimescaleDB continuous aggregates.

### System B Has the Data

System B's TimescaleDB already has:
- `telemetry_raw` hypertable (7-day retention, compressed after 2 days)
- `telemetry_5min` continuous aggregate (30-day retention)
- `telemetry_hourly` continuous aggregate (365-day retention)
- `telemetry_daily` continuous aggregate (forever retention)

System B already exposes these via API:
- `GET /api/v1/telemetry/aggregate/{device_id}/{metric_name}` - time-bucketed aggregates
- `GET /api/v1/telemetry/site/{site_id}` - site-wide telemetry
- `GET /api/v1/telemetry/power-chart/{site_id}` - power chart data
- `GET /api/v1/telemetry/latest/{device_id}` - latest readings

### Dashboard Widget API TODOs

In `system_a/app/api/v1/dashboard_widgets.py`:
- **Line 533:** `peak_power_kw=0` - TODO: Get from historical data
- **Line 546:** `energy_month_kwh=0` - TODO: Get from historical data
- **Line 815:** `# TODO: Get historical data from TimescaleDB`
- **Line 881:** `# TODO: Get actual tariff rates from site configuration`
- **Line 894:** `estimated_savings_month=0` - TODO: Get from historical data

### SystemBClient Missing Methods

`system_a/app/infrastructure/external/system_b_client.py` only has:
- `get_device_by_serial()` - device lookup
- `claim_device()` - device claiming
- `release_device()` - device release
- `get_orphan_devices()` - list orphans

**Missing:** All telemetry query methods.

### No Scheduler Infrastructure

- Celery is installed (`celery>=5.3.0` in requirements.txt) but NOT wired
- No APScheduler
- Only `FastAPI.BackgroundTasks` used minimally in `discovery.py`

---

## 3. Phase Overview

```
Phase 1 (Foundation)     -> StatCards, EnergyChart, Environmental work with real data
Phase 2 (Real-Time)      -> Power flow, battery, grid, system status widgets work
Phase 3 (Billing)        -> Billing summary, tariff, savings pages work
Phase 4 (Analytics)      -> Goals, comparisons, AI insights, peak demand work
Phase 5 (Integrations)   -> Weather, load-shedding work
Phase 6 (Polish)         -> Notifications, preferences, settings work
```

Each phase is independently deployable and adds visible value. Phase 1 is the critical foundation.

---

## 4. Phase 1: Telemetry Aggregation Foundation (Detailed)

### Step 1: Add Telemetry Query Methods to SystemBClient

**File:** `system_a/app/infrastructure/external/system_b_client.py`

Add methods to call System B's existing API endpoints:
- `get_device_aggregates(device_id, metric_name, start_time, end_time, bucket_interval)` → `GET /api/v1/telemetry/aggregate/{device_id}/{metric_name}`
- `get_site_telemetry(site_id, start_time, end_time, metric_names, bucket_interval)` → `GET /api/v1/telemetry/site/{site_id}`
- `get_site_power_chart(site_id, start_time, end_time, bucket_interval)` → `GET /api/v1/telemetry/power-chart/{site_id}`
- `get_device_latest(device_id)` → `GET /api/v1/telemetry/latest/{device_id}`

Follow the existing httpx async pattern already in the client.

### Step 2: Create TelemetrySyncService

**New file:** `system_a/app/application/services/telemetry_sync_service.py`

Application service that:
1. Queries System B for aggregated telemetry data via SystemBClient
2. Transforms data into System A's summary format
3. Upserts into System A's summary tables

Methods:
- `sync_hourly_for_site(site_id, hour_start, hour_end)` — Pull hourly aggregates from System B, insert/update `telemetry_hourly_summary`
- `sync_daily_for_site(site_id, target_date)` — Aggregate hourly rows into `telemetry_daily_summary`
- `sync_monthly_for_site(site_id, year, month)` — Aggregate daily rows into `telemetry_monthly_summary`
- `sync_all_sites()` — Iterate all active sites and sync each
- `backfill(site_id, start_date, end_date)` — Backfill historical data

Key design:
- Uses UPSERT (INSERT ON CONFLICT UPDATE) for idempotency
- Creates both device-level AND site-level (device_id=NULL) summary rows
- Site-level rows = SUM/AVG across all devices at that site
- Calculates derived fields: co2_avoided_kg, estimated_savings_pkr, performance_ratio

### Step 3: Add Upsert Methods to Telemetry Repository

**File:** `system_a/app/infrastructure/database/repositories/telemetry_repository.py`

Add:
- `upsert_hourly_summary(summary_data)` — INSERT ON CONFLICT (site_id, device_id, timestamp_hour) DO UPDATE
- `upsert_daily_summary(summary_data)` — INSERT ON CONFLICT (site_id, device_id, summary_date) DO UPDATE
- `upsert_monthly_summary(summary_data)` — INSERT ON CONFLICT (site_id, device_id, year, month) DO UPDATE
- `aggregate_hourly_to_daily(site_id, target_date)` — SQL aggregation from hourly → daily
- `aggregate_daily_to_monthly(site_id, year, month)` — SQL aggregation from daily → monthly

### Step 4: Set Up APScheduler

**New file:** `system_a/app/infrastructure/scheduler/telemetry_scheduler.py`

Jobs:
- **Hourly** (at :05 past): Sync previous hour's data for all active sites
- **Daily** (00:15 UTC): Aggregate yesterday's hourly data into daily for all sites
- **Monthly** (1st of month, 00:30 UTC): Aggregate previous month's daily into monthly

**New file:** `system_a/app/infrastructure/scheduler/__init__.py`

Integration with FastAPI lifecycle (startup/shutdown events).

**Modify:** `system_a/app/main.py` — Register scheduler in lifespan
**Modify:** `system_a/requirements.txt` — Add `apscheduler>=3.10.0`

### Step 5: Enhance Dashboard Widget APIs

**File:** `system_a/app/api/v1/dashboard_widgets.py`

Fix TODOs:

**`GET /dashboard/stats`:**
- `peak_power_kw` from today's hourly summaries (MAX of hourly peaks)
- `energy_month_kwh` from monthly summary table

**`GET /dashboard/energy-chart`:**
- `period=day`: Query hourly summaries → 24 data points
- `period=week`: Query daily summaries → 7 data points
- `period=month`: Query daily summaries → 30 data points

**`GET /dashboard/billing`:**
- `estimated_savings_month` from monthly summary or SUM of daily summaries

**`GET /dashboard/environmental`:**
- Cumulative energy from monthly summaries (not just today's real-time)

**`GET /dashboard/all`:**
- Include all enhanced data above

### Step 6: Wire Up Dependencies

**File:** `system_a/app/api/dependencies.py`

Add: `get_telemetry_sync_service()` dependency provider

### Step 7: Update Frontend useEnergyData Hook

**File:** `frontend/src/hooks/useEnergyData.tsx`

Replace mock data with:
- `dashboardService.getStats()` for energy statistics
- `dashboardService.getEnergyChart(period)` for chart data
- React Query for caching/polling
- Same interface shape so consuming components don't change

### Step 8: Create Device Simulator

**New file:** `scripts/device_simulator.py`

A standalone Python script that:
- Simulates ESP32 device telemetry
- Sends data to System B's ingest endpoint (`POST /api/v1/telemetry/ingest`)
- Configurable: device count, serial numbers, update interval, data patterns (sunny day, cloudy, night)
- Generates realistic solar inverter data (PV power follows bell curve, battery charges/discharges, grid import/export)
- Runs continuously for local testing

### Step 9: Create Test Suite for Phase 1

**New files:**
- `system_a/tests/unit/test_telemetry_sync_service.py` — Unit tests for sync logic
- `system_a/tests/unit/test_telemetry_repository_upsert.py` — Unit tests for upsert methods
- `system_a/tests/integration/test_scheduler.py` — Integration test for scheduler startup
- `system_a/tests/integration/test_dashboard_widgets_enhanced.py` — Integration tests for enhanced widget APIs
- `frontend/src/hooks/__tests__/useEnergyData.test.tsx` — Frontend hook tests

### Step 10: Local Environment Setup

**New file:** `scripts/local_setup.sh` (or `local_setup.ps1` for Windows)

Script that:
1. Creates/checks PostgreSQL database for System A
2. Creates/checks TimescaleDB database for System B
3. Starts Redis
4. Runs Alembic migrations for both systems
5. Seeds demo data (device registration, user, site)
6. Starts device simulator in background
7. Starts System B
8. Starts System A
9. Starts Frontend dev server

### Files to Create (Phase 1)

| # | File | Purpose |
|---|------|---------|
| 1 | `system_a/app/application/services/telemetry_sync_service.py` | Sync service |
| 2 | `system_a/app/infrastructure/scheduler/__init__.py` | Scheduler package |
| 3 | `system_a/app/infrastructure/scheduler/telemetry_scheduler.py` | APScheduler jobs |
| 4 | `scripts/device_simulator.py` | Device telemetry simulator |
| 5 | `scripts/local_setup.ps1` | Windows local environment setup |
| 6 | `system_a/tests/unit/test_telemetry_sync_service.py` | Sync service unit tests |
| 7 | `system_a/tests/unit/test_telemetry_repository_upsert.py` | Repository upsert tests |
| 8 | `system_a/tests/integration/test_dashboard_widgets_enhanced.py` | Widget API integration tests |

### Files to Modify (Phase 1)

| # | File | Changes |
|---|------|---------|
| 1 | `system_a/app/infrastructure/external/system_b_client.py` | Add telemetry query methods |
| 2 | `system_a/app/infrastructure/database/repositories/telemetry_repository.py` | Add upsert + aggregation methods |
| 3 | `system_a/app/api/v1/dashboard_widgets.py` | Enhance stats, chart, billing, environmental |
| 4 | `system_a/app/api/dependencies.py` | Add sync service dependency |
| 5 | `system_a/app/main.py` | Register scheduler lifecycle |
| 6 | `system_a/requirements.txt` | Add apscheduler |
| 7 | `frontend/src/hooks/useEnergyData.tsx` | Replace mock with API calls |

---

## 5. Phases 2-6 Summary

### Phase 2: Real-Time Dashboard Widgets
- Create `/dashboard/grid-status` and `/dashboard/system-status` APIs
- Connect EnergyFlowDiagram, SystemDiagram, GridStatus, SystemStatus, BatteryDetail widgets
- Implement device command forwarding (QuickActions widget)

### Phase 3: Billing & Tariff Integration
- Create `GET/PUT /billing/tariff-config` for persisting tariff settings
- Create BillingCalculationService using real consumption from summaries
- Connect BillingSummary, BillingSettings, TariffSettings, SelfConsumption widgets

### Phase 4: Analytics & Insights
- Create `energy_goals` table + GoalTrackingService + CRUD endpoints
- Create EnvironmentalCalculator using real PV production data
- Create `/telemetry/comparison` for period-over-period data
- Create rule-based AI Insights engine
- Connect GoalTracking, EnvironmentalImpact, ComparisonChart, PeakDemand, AIInsights widgets

### Phase 5: External Integrations
- Create WeatherService + external API integration (OpenWeatherMap)
- Create LoadSheddingService + `load_shedding_schedules` table
- Connect WeatherWidget, LoadSheddingSchedule widget, Outages page

### Phase 6: Notifications & Preferences
- Create `notifications` table + NotificationService
- Create `user_preferences` table + UserPreferencesService
- Connect Notifications page, Settings page, Profile page

---

## 6. Architecture Reference

### Two-System Architecture
```
ESP32 Devices → System B (TimescaleDB, port 8001) → Redis Cache → System A (PostgreSQL, port 8000) → Frontend (port 5173)
```

### Data Flow for Telemetry
```
1. ESP32 sends data to System B via Modbus TCP
2. System B stores in telemetry_raw hypertable
3. System B writes to Redis: device:{serial}:telemetry (TTL 120s)
4. TimescaleDB auto-refreshes continuous aggregates (5min, hourly, daily)
5. System A scheduler pulls aggregates from System B API → populates summary tables
6. Frontend polls System A dashboard APIs → gets real data
```

### Key Design Decisions
- Serial number is the universal cross-system identifier
- Redis bridge: System B writes, System A reads (~1ms latency)
- Widget-based APIs: each widget has its own endpoint
- Pull model: Frontend polls System A (no push/WebSocket for now)
- DDD architecture in System A: domain purity, UnitOfWork transactions
- Repositories use flush() never commit() — UoW manages transactions

### System A DDD Layers
```
API Layer (FastAPI routers) → Application Layer (services) → Domain Layer (entities)
                                                               ↕
Infrastructure Layer (repositories, cache, external clients, scheduler)
```

---

## 7. Key File Paths

### System A - Backend
```
system_a/
├── app/
│   ├── api/
│   │   ├── dependencies.py                    # FastAPI DI container
│   │   ├── v1/
│   │   │   ├── dashboard_widgets.py           # Widget APIs (main target)
│   │   │   ├── dashboards.py                  # Dashboard overview APIs
│   │   │   ├── billing.py                     # Billing APIs
│   │   │   └── ...
│   ├── application/
│   │   ├── services/
│   │   │   ├── telemetry_service.py           # Existing telemetry service
│   │   │   ├── telemetry_sync_service.py      # NEW: Sync service
│   │   │   └── ...
│   │   └── interfaces/
│   │       ├── repositories.py                # Repository interfaces
│   │       └── unit_of_work.py                # UoW interface
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── models/
│   │   │   │   ├── telemetry_model.py         # Summary table models
│   │   │   │   └── ...
│   │   │   ├── repositories/
│   │   │   │   ├── telemetry_repository.py    # Summary queries (modify)
│   │   │   │   └── ...
│   │   │   └── unit_of_work.py                # UoW implementation
│   │   ├── cache/
│   │   │   ├── telemetry_cache.py             # Redis cache reader
│   │   │   └── site_cache.py                  # Site info cache
│   │   ├── external/
│   │   │   └── system_b_client.py             # System B HTTP client (modify)
│   │   └── scheduler/                          # NEW: Scheduler package
│   │       ├── __init__.py
│   │       └── telemetry_scheduler.py
│   ├── domain/entities/
│   │   ├── base.py                            # AggregateRoot, Entity, ValueObject
│   │   ├── user.py, device.py, site.py        # Domain entities
│   │   └── ...
│   └── main.py                                # FastAPI app (modify)
├── alembic/versions/                          # Migrations (no new ones needed)
├── requirements.txt                           # Dependencies (add apscheduler)
└── tests/                                     # Test files (new tests)
```

### System B - Telemetry
```
system_b/
├── app/api/v1/
│   ├── telemetry.py                           # Telemetry ingest + query APIs
│   ├── devices.py                             # Device registration/claiming
│   ├── commands.py                            # Device commands
│   └── events.py                              # Device events
├── app/infrastructure/database/
│   ├── models/telemetry_model.py              # TimescaleDB models
│   └── timescale_connection.py                # DB connection
└── alembic/versions/
    ├── 20260115_0001_initial_timescale_schema.py  # Hypertables
    └── 20260115_0002_add_continuous_aggregates.py  # Continuous aggregates
```

### Frontend
```
frontend/src/
├── api/
│   ├── config.ts                              # API endpoints (70+)
│   ├── client.ts                              # Axios client with auth
│   └── services/
│       ├── dashboard.service.ts               # Dashboard API calls
│       └── ...
├── hooks/
│   ├── useEnergyData.tsx                      # KEY: Replace mock data (modify)
│   ├── use-billing-config.tsx                 # Mock billing config
│   └── ...
├── contexts/
│   ├── TelemetryContext.tsx                    # Real-time polling (working)
│   ├── TariffContext.tsx                       # Static tariff data
│   ├── DashboardLayoutContext.tsx              # Widget layout (13 widgets)
│   └── UserRoleContext.tsx                     # User roles
├── components/dashboard/                      # 20 widget components
└── pages/                                     # 21 pages
```

### Telemetry Data Structure (Redis)
```json
{
  "serial_number": "SH01IN2406130092",
  "timestamp": "2026-01-24T12:48:07Z",
  "power": {
    "pv_total_w": 5234,
    "pv1_w": 2617,
    "pv2_w": 2617,
    "grid_w": 9,
    "load_w": 1135,
    "battery_w": 1168
  },
  "battery": {
    "soc_pct": 98,
    "voltage_v": 53.17,
    "current_a": 21.98,
    "charging": true
  },
  "energy_today": {
    "pv_kwh": 57.4,
    "load_kwh": 20.4,
    "grid_import_kwh": 3.2,
    "grid_export_kwh": 24.2,
    "battery_charge_kwh": 15.8,
    "battery_discharge_kwh": 2.4
  },
  "temperatures": {
    "inverter_c": 45.0,
    "battery_c": 22.2,
    "ambient_c": 28.0
  },
  "grid": {
    "voltage_v": 220.8,
    "frequency_hz": 50.0
  },
  "status": {
    "working_mode": 2,
    "working_mode_name": "battery_priority",
    "grid_connected": true,
    "faults": [],
    "warnings": []
  }
}
```

### Summary Table Schemas (System A)

**telemetry_hourly_summary:** site_id, device_id (nullable), timestamp_hour, energy_generated/consumed/exported/imported/stored/discharged_kwh, peak/average/min_power_kw, environmental, battery SOC, grid metrics, sample_count, data_quality_percent

**telemetry_daily_summary:** site_id, device_id (nullable), summary_date, all energy metrics + net_energy_kwh, sunshine_hours, production_hours, grid_outage_minutes, co2_avoided_kg, estimated_revenue/savings_pkr, hours_with_data

**telemetry_monthly_summary:** site_id, device_id (nullable), year, month, all energy metrics, average_daily_generation_kwh, total_sunshine_hours, expected_generation_kwh, generation_variance_percent, trees_equivalent, days_with_data

---

*This document should be read by Claude at the start of each session to restore context.*
