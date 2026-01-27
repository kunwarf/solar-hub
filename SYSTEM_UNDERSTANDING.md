# Solar Hub - System Understanding Document

**Purpose:** Reference document for AI sessions modifying this codebase.
**Last Updated:** 2026-01-27
**Source of Truth:** This document summarizes the codebase as-built and the requirements in `SYSTEM_REQUIREMENTS.md`.

---

## 1. High-Level System Purpose

Solar Hub is a **subscription-based solar monitoring and remote device management platform**. It ingests real-time telemetry from solar inverters, batteries, and energy meters via ESP32 dataloggers, and presents it through a web dashboard. The platform also provides energy billing simulation, AI-based optimization, load shedding tracking, and command execution.

The system is designed for the **Pakistan market** first (slab-based DISCO tariffs, load shedding, JazzCash/EasyPaisa payments, PKR currency) but architected to scale globally.

---

## 2. Business Goals and Constraints

### Goals
- Enable residential and commercial users to monitor solar systems in near-real-time.
- Simulate electricity bills against Pakistan DISCO tariff structures (LESCO, MEPCO, K-Electric, etc.) and calculate savings.
- Provide AI-powered battery charge/discharge optimization to maximize self-consumption and minimize grid dependence.
- Monetize via a tiered subscription model starting at Rs. 200/month per inverter+battery.
- Scale from millions of single-inverter residential users to multi-site corporate deployments (Phase-3).

### Constraints
- **Two-backend architecture is mandatory** (System A + System B), with clear separation of concerns.
- Devices are always clients; the server never initiates connections to devices (NAT/CGNAT compatibility).
- Must work on low-bandwidth connections (2G/3G) common in rural Pakistan.
- PWA with offline-first capability required at MVP.
- Pakistan-specific: NEPRA net metering rules, slab-based billing, Urdu language support (Phase-2).

---

## 3. Target Users and Use Cases

### User Types (Configuration Level)
| Type | Description |
|------|-------------|
| **Basic User** | One inverter, auto-provisioned hierarchy, simplified UI |
| **Advanced User** | Multiple systems/devices, full hierarchy editing |

### User Roles (Access Level)
| Role | Scope |
|------|-------|
| **Owner** | Full control including billing and ownership transfer |
| **Admin** | Device/user/settings management, no billing |
| **Viewer** | Read-only dashboard and report access |
| **Installer** | Time-limited commissioning access, auto-expires |

### Key Use Cases
1. Homeowner monitors daily solar generation and battery state-of-charge.
2. Homeowner views estimated electricity bill and savings vs. grid-only.
3. System detects load shedding, tracks outage duration, reports battery backup utilization.
4. Installer commissions a new device via QR code or serial number entry.
5. AI recommends optimal battery charge/discharge schedule based on weather, tariff, and consumption patterns.
6. Corporate admin (Phase-3) views aggregated performance across multiple sites.

---

## 4. Core Components and Their Responsibilities

### 4.1 Directory Structure

```
solar-hub/
├── system_a/            # Platform & Monitoring Backend (FastAPI, port 8000)
├── system_b/            # Communication & Telemetry Backend (FastAPI, port 8001)
├── frontend/            # React SPA (Vite, port 8080 dev / 5173)
├── adapters/            # Device protocol adapters (Modbus, MQTT, BLE)
├── esp32_datalogger/    # MicroPython firmware for ESP32 dataloggers
├── register_maps/       # JSON register definitions per inverter/battery brand
├── deployment/          # Docker/systemd production configs
├── scripts/             # Utility and seed scripts
└── docs/                # Architecture and design documents
```

### 4.2 System A - Platform & Monitoring Backend

**Tech:** Python 3, FastAPI, SQLAlchemy (async), PostgreSQL 16, Alembic migrations, Redis.

**Architecture:** Domain-Driven Design with clear layers:
- `app/api/v1/` - REST endpoints (auth, users, organizations, sites, devices, dashboards, dashboard_widgets, billing, alerts, protocol_definitions, discovery)
- `app/api/schemas/` - Pydantic request/response schemas
- `app/application/services/` - Business logic (auth, registration, billing, telemetry, protocol_definition)
- `app/application/interfaces/` - Abstract repositories, services, unit of work
- `app/domain/entities/` - Domain models (user, organization, site, device, billing, alert, report, telemetry)
- `app/domain/events/` - Domain events (user_events, device_events, and others)
- `app/domain/exceptions/` - Domain-specific exception types
- `app/infrastructure/database/models/` - SQLAlchemy ORM models (user, organization, site, device, alert, billing, telemetry, report, protocol_definition)
- `app/infrastructure/database/repositories/` - Concrete repository implementations
- `app/infrastructure/cache/` - Redis cache integration (redis_cache, site_cache, telemetry_cache)
- `app/infrastructure/websocket/` - WebSocket support for real-time updates

**Responsibilities:**
- User authentication (JWT) and authorization
- Organization and site CRUD
- Device claiming and management (links to System B devices)
- Dashboard widget APIs (power-flow, stats, energy-chart, battery, alerts, environmental, billing)
- Billing simulation against DISCO tariff plans
- Alert rule management and alert instances
- Protocol definition management
- Telemetry aggregation summaries (hourly, daily, monthly)
- Reads real-time telemetry from **shared Redis** (written by System B)
- Background task processing via **Celery 5.3** (with Flower monitoring)
- WebSocket connections for real-time frontend updates

### 4.3 System B - Communication & Telemetry Backend

**Tech:** Python 3, FastAPI, TimescaleDB (PostgreSQL + extension), Redis Streams, asyncio TCP server.

**Architecture:**
- `app/api/v1/` - REST endpoints (devices, telemetry, commands, events)
- `app/application/services/` - Business logic (telemetry, device, command, event, auth, serial_number services)
- `app/domain/entities/` - Domain models (device, telemetry, command, event)
- `app/infrastructure/database/` - TimescaleDB connection, telemetry/event/command/device_registry repositories
- `app/infrastructure/messaging/` - Redis Streams for pub/sub (redis_streams, stream_services)
- `app/infrastructure/protocols/` - Protocol handlers
- `device_server/main.py` - Standalone TCP server module on port 8502 accepting ESP32 connections
- `workers/` - Background worker processes

**Responsibilities:**
- Device self-registration (ESP32 connects, sends serial/type/firmware)
- Telemetry ingestion and storage in TimescaleDB hypertables
- Real-time telemetry write to shared Redis (`device:{serial}:telemetry`, TTL 120s)
- Device command queue (pending -> sent -> acknowledged -> completed/failed/timeout)
- Device event logging (status changes, errors, connections)
- Continuous aggregates: 5-min, hourly, daily rollups
- Enforces polling frequency per subscription tier

### 4.4 Frontend

**Tech:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Recharts, Framer Motion, Axios.

**Key Pages:**
- `Auth.tsx` - Login/registration
- `Index.tsx` - Main dashboard
- `Devices.tsx`, `DeviceManagement.tsx`, `DeviceSettings.tsx` - Device CRUD
- `ClaimDevice.tsx`, `Commissioning.tsx`, `Install.tsx` - Device onboarding
- `Billing.tsx`, `BillingSettings.tsx`, `TariffSettings.tsx` - Billing simulation
- `Savings.tsx` - Savings tracking
- `Outages.tsx` - Load shedding tracking
- `AlertCenter.tsx`, `Notifications.tsx` - Alerts
- `SmartScheduler.tsx` - Battery charge/discharge scheduling
- `Telemetry.tsx` - Raw telemetry view
- `UserManagement.tsx` - User/role management
- `Settings.tsx`, `Profile.tsx` - User settings

**Dashboard Widgets (in `components/dashboard/`):**
- `EnergyFlowDiagram.tsx` - Animated power flow (solar -> battery -> load -> grid)
- `StatCard.tsx` - KPI cards
- `EnergyChart.tsx` - Generation/consumption charts
- `DeviceOverview.tsx`, `HierarchicalDeviceOverview.tsx` - Device status
- `BillingSummary.tsx` - Bill estimates
- `LoadSheddingTracker.tsx` - Outage monitoring
- `WeatherWidget.tsx` - Weather integration
- `AIInsightsWidget.tsx` - AI recommendations
- `EnvironmentalImpactWidget.tsx` - CO2 savings
- `GoalTrackingWidget.tsx` - User goals
- `VisualSystemDiagram.tsx` - System visualization
- `QuickActions.tsx` - One-click common actions
- `WidgetPicker.tsx`, `DraggableWidget.tsx`, `DashboardEditControls.tsx` - Layout customization

**API Services (in `api/services/`):**
- `auth.service.ts`, `users.service.ts`, `organizations.service.ts`
- `sites.service.ts`, `devices.service.ts`, `dashboard.service.ts`
- `billing.service.ts`, `alerts.service.ts`

**React Context Providers (in `contexts/`):**
- `UserRoleContext.tsx` - Current user role and permissions
- `TelemetryContext.tsx` - Real-time telemetry data provider
- `TariffContext.tsx` - Active tariff configuration
- `DashboardLayoutContext.tsx` - Widget layout state

**Custom Hooks (in `hooks/`, 15 total):**
- `use-auth.tsx` - Authentication state and actions
- `useDevices.ts`, `useSites.ts`, `useOrganizations.ts` - Data fetching
- `use-websocket.tsx` - WebSocket connection management for live updates
- `useAlerts.ts` - Alert management
- `use-toast.ts` - Toast notifications
- And 8 others for various UI/data concerns

### 4.5 Adapters

Protocol-specific device communication modules:
- `base.py` - Abstract base adapter
- `senergy.py` - Senergy inverters (Modbus TCP)
- `powdrive.py` - Powdrive inverters (Modbus TCP)
- `iammeter.py` - IAMmeter energy meters
- `battery_jkbms_tcpip.py`, `battery_jkbms_ble.py` - JK BMS batteries
- `battery_pytes.py` - Pytes batteries
- `battery_failover.py` - Battery failover logic
- `mqtt_adapter.py` - Generic MQTT devices
- `command_queue.py` - Device command queue management

### 4.6 Register Maps

JSON files defining Modbus register addresses per device brand:
- `senergy_registers.json`, `powdrive_registers.json`, `pytes_registers.json`, `iammeter_registers.json`
- `mqtt_generic_fields.json`
- Each register maps a `standard_id` to device-specific address, type, scale, and unit
- Standard field names documented in `STANDARD_FIELD_NAMES.md` and `STANDARD_REGISTER_IDS.md`

### 4.7 ESP32 Datalogger

MicroPython firmware for ESP32 devices that act as field dataloggers:
- `main.py`, `boot.py` - Entry points
- `wifi_manager.py` - WiFi connection management
- `modbus_bridge.py`, `modbus_rtu.py` - Modbus RTU communication with inverters
- `web_server.py` - Local configuration web interface
- `config.py`, `config.json` - Device configuration

---

## 5. Data Flow

### 5.1 Telemetry Ingestion (Device -> Dashboard)

```
ESP32 Datalogger                System B                    Redis               System A              Frontend
     |                            |                           |                    |                     |
     |--TCP connect (8502)------->|                           |                    |                     |
     |--REGISTER {serial,type}--->|                           |                    |                     |
     |<--ACK {device_id,interval}-|                           |                    |                     |
     |                            |                           |                    |                     |
     |--Modbus polling----------->|                           |                    |                     |
     |<--Telemetry data-----------|                           |                    |                     |
     |                            |--WRITE device:{serial}:-->|                    |                     |
     |                            |   telemetry (TTL 120s)    |                    |                     |
     |                            |--INSERT telemetry_raw---->|                    |                     |
     |                            |   (TimescaleDB)           |                    |                     |
     |                            |                           |<--READ telemetry---|                     |
     |                            |                           |                    |--JSON response----->|
     |                            |                           |                    |                     |
```

### 5.2 Device Registration & User Claim

1. ESP32 powers on, connects to System B TCP server (port 8502), sends `REGISTER` message with serial number.
2. System B creates device record with status `orphan`, owner_id=NULL.
3. User registers via frontend -> `POST /api/v1/auth/register` to System A with optional `device_serial`.
4. System A validates serial with System B -> `GET /devices/serial/{serial}`.
5. If device exists and is orphan: System A creates user, creates default site "My Home", claims device via `PUT /devices/{id}/claim`.
6. Device status changes from `orphan` to `claimed`.

### 5.3 Dashboard Widget Data

Each dashboard widget has its own API endpoint with independent cache TTL and refresh rate:
- Power Flow: 5s cache, 5s refresh (reads Redis `device:{serial}:telemetry`)
- Statistics Cards: 30s cache, 30s refresh
- Energy Chart: 5min cache, manual refresh
- Battery Status: 10s cache, 10s refresh
- All endpoints accept `site_id` and optional `device_serial` query parameters

### 5.4 Redis Key Structure

```
device:{serial}:telemetry     -> JSON blob (TTL: 120s)     [Written by System B]
device:{serial}:status        -> "online"|"offline" (TTL: 120s) [Written by System B]
device:{serial}:last_seen     -> Unix timestamp (TTL: 120s) [Written by System B]
device:{serial}:stats:today   -> Energy stats JSON (TTL: 60s) [Written by System A]
device:{serial}:chart:day     -> Chart data JSON (TTL: 5min)  [Written by System A]
device:{serial}:chart:week    -> Chart data JSON (TTL: 15min) [Written by System A]
device:{serial}:chart:month   -> Chart data JSON (TTL: 1hr)   [Written by System A]
```

---

## 6. Key Dependencies

### Infrastructure
| Component | Technology | Port | Purpose |
|-----------|-----------|------|---------|
| System A DB | PostgreSQL 16 | 5432 | Users, orgs, sites, devices, alerts, billing, reports |
| System B DB | TimescaleDB (PG16) | 5433 | Raw telemetry hypertables, continuous aggregates |
| Cache/Pub-Sub | Redis 7 | 6379 | Shared telemetry cache, sessions, rate limiting |
| MQTT Broker | Eclipse Mosquitto 2 | 1883/9001 | MQTT device communication |

### System A Python Dependencies (Key)
- **FastAPI** + **uvicorn** - ASGI web framework
- **SQLAlchemy 2.0** (async) + **asyncpg** - PostgreSQL ORM
- **Alembic** - Database migrations (8 migration files)
- **Pydantic 2.5** - Data validation and serialization
- **Redis 5.0** (aioredis) - Async Redis client
- **Celery 5.3** + **Flower** - Background task processing and monitoring
- **passlib** + **bcrypt** - Password hashing
- **python-jose** / **PyJWT** - JWT token management
- **aiosmtplib** - Async email sending

### System B Python Dependencies (Key)
- **FastAPI** + **uvicorn** - ASGI web framework
- **SQLAlchemy 2.0** + **asyncpg** - TimescaleDB access
- **Redis 5.0** (Streams) - Async messaging/pub-sub
- **pymodbus 3.6** - Modbus TCP/RTU protocol implementation
- **paho-mqtt** / **asyncio-mqtt 0.16** - MQTT client
- **numpy**, **pandas** - Telemetry data processing
- **httpx**, **aiohttp** - Async HTTP clients (inter-service calls)

### Frontend Dependencies (Key)
- **React 18** + **TypeScript** - UI framework
- **Vite** - Build tool
- **Tailwind CSS** + **shadcn/ui** - Styling and component library (Radix UI primitives)
- **TanStack Query** - Server state management and caching
- **Recharts** - Charting library
- **Framer Motion** - Animations (power flow diagram)
- **Axios** - HTTP client
- **vite-plugin-pwa** - PWA/service worker support

### External APIs (Future/Planned)
- Weather API (for generation forecasting)
- JazzCash / EasyPaisa payment APIs
- SMS gateway (for notifications)

---

## 7. Non-Goals (What This System Should NOT Do)

Per `SYSTEM_REQUIREMENTS.md` Section 27 and architectural constraints:

1. **No hardware manufacturing workflows** - The platform manages devices post-manufacture only.
2. **No physical inventory management** - Out of scope entirely.
3. **No external invoicing** - Platform billing is subscription-based; it does not generate utility invoices.
4. **No grid operator integrations** - The platform does not communicate with utility companies or grid operators.
5. **No energy trading** - Battery optimization maximizes self-reliance, not energy trading (Phase-3 placeholder only).
6. **No inbound device connections** - Devices always initiate connections; the server never connects to devices.
7. **No direct device-to-frontend communication** - All telemetry flows through System B -> Redis -> System A -> Frontend.
8. **No mock data fallbacks** - Recent commit (`1079def`) removed all mock data fallbacks from frontend services. The system must operate with real backend data.

---

## 8. Known Risks and Fragile Areas

### 8.1 Redis as Single Point of Coupling
- System A reads real-time telemetry exclusively from Redis (written by System B). If Redis is unavailable, System A falls back to direct HTTP calls to System B, but this fallback path is secondary and less tested.
- All keys have 120s TTL. If System B stops writing, stale data silently expires and dashboards show "offline" after 5 minutes.

### 8.2 Serial Number as Universal Identifier
- The serial number (`SH01IN2406130092` format) is the join key between System A, System B, Redis, and frontend. Any mismatch or format change breaks the entire chain.
- System A stores `device_serial` in `user_devices`, System B stores `serial_number` in `devices`. These must stay synchronized.

### 8.3 Dual-Database Synchronization
- Device ownership state (`orphan`/`claimed`, `owner_id`, `site_id`) must be consistent between System A's PostgreSQL and System B's TimescaleDB. The claim/release operations cross system boundaries via HTTP API calls, with no distributed transaction guarantee.

### 8.4 Register Map Maintenance
- Each supported inverter/battery brand requires a JSON register map. Adding a new brand requires a new register map file, potentially a new adapter in `adapters/`, and potentially new standard field mappings. The `standard_id` field in register maps must match `STANDARD_FIELD_NAMES.md` exactly.

### 8.5 Telemetry Aggregation Pipeline
- TimescaleDB continuous aggregates (5-min, hourly, daily) depend on correct time-zone handling. Pakistan uses `Asia/Karachi` (UTC+5, no DST), but this is hardcoded in some places and configurable in others.
- Aggregation data syncs from System B to System A summary tables (hourly/daily/monthly). This sync mechanism is a potential consistency risk.

### 8.6 ESP32 Firmware
- The ESP32 datalogger firmware is MicroPython-based. It connects to System B over raw TCP. Connection stability on poor networks (2G/3G) is critical and is a known challenge.
- Firmware updates require physical access or OTA capability (Phase-1 feature, not yet implemented).

### 8.7 Frontend State Management
- The frontend uses TanStack Query for server state and 4 React Context providers (UserRole, Telemetry, Tariff, DashboardLayout) plus 15 custom hooks. No centralized state store (no Redux). Widget-level independent fetching means many concurrent API calls on dashboard load.
- WebSocket support exists (`use-websocket.tsx`) but the polling-based approach is the primary data delivery mechanism.
- Recent removal of mock data fallbacks means the frontend may show errors/empty states if backend is unavailable during development.

### 8.8 Database Migrations
- System A uses Alembic migrations. System B uses raw SQL (TimescaleDB hypertables and continuous aggregates don't map cleanly to ORM migrations). Schema changes to System B require manual SQL scripts.

---

## 9. Terminology and Definitions

| Term | Definition |
|------|------------|
| **System A** | Platform & Monitoring Backend. Handles users, auth, billing, dashboards. FastAPI on port 8000. |
| **System B** | Communication & Telemetry Backend. Handles device connections, telemetry ingestion, commands. FastAPI on port 8001, TCP device server on port 8502. |
| **Device Server** | TCP server within System B that accepts raw connections from ESP32 dataloggers. |
| **ESP32 Datalogger** | Physical ESP32 microcontroller running MicroPython. Connects to inverters via Modbus RTU/TCP, relays data to System B. |
| **Adapter** | Python module that knows how to communicate with a specific brand of inverter/battery (e.g., `senergy.py`, `powdrive.py`). |
| **Register Map** | JSON file defining Modbus register addresses, data types, scales, and standard field mappings for a specific device brand. |
| **Standard Field Name** | Normalized telemetry field name (e.g., `pv_power_w`, `batt_soc_pct`) used across all device types regardless of brand. |
| **Orphan Device** | A device registered in System B but not yet claimed by any user. |
| **Claimed Device** | A device linked to a user and site via the claim flow. |
| **Site** | A physical location (home/building) with one or more devices. Auto-created as "My Home" for new users. |
| **Organization** | A company or entity that owns one or more sites. Supports multi-tenant access with role-based membership. |
| **DISCO** | Distribution Company - Pakistan electricity utility (LESCO, K-Electric, MEPCO, etc.). |
| **Slab Billing** | Pakistan tiered electricity pricing where rate increases with consumption brackets. |
| **Net Metering** | NEPRA-regulated scheme where solar export to grid generates credits on electricity bill. |
| **Load Shedding** | Scheduled or unscheduled power outages, common in Pakistan. A key feature differentiator. |
| **Hypertable** | TimescaleDB table partitioned by time for efficient time-series queries. `telemetry_raw` uses 1-hour chunks. |
| **Continuous Aggregate** | TimescaleDB materialized view that automatically maintains pre-computed rollups (5-min, hourly, daily). |
| **Power Flow** | Animated dashboard widget showing real-time energy direction: solar -> battery -> load -> grid. |
| **Telemetry Snapshot** | Latest device reading cached in Redis with 120s TTL and stored in `device_telemetry_snapshot` table. |
| **Widget API** | Independent REST endpoint per dashboard widget, each with its own cache TTL and refresh rate. |

---

## 10. Assumptions Made

1. **Phase scope:** The system is currently implementing MVP features. Phase-1 features (subscription tiers, advanced reports, OTA updates) are designed in schema but not fully implemented in application logic.

2. **Single deployment target:** The system targets a single deployment (not multi-region). Docker Compose is used for development; production deployment uses systemd services (evidenced by `system_b/deployment/systemd/`).

3. **No mock data in production paths:** Per commit `1079def`, all mock data fallbacks have been removed. The frontend expects real backend responses.

4. **Organization model is implemented:** The System A database schema includes a full `organizations` and `organization_members` model with invitation flows, despite this being more of a Phase-3 feature. The code uses organizations as the top-level tenant boundary.

5. **Modbus TCP is the primary protocol:** While MQTT support exists via `mqtt_adapter.py`, the primary device communication path is Modbus TCP via the ESP32 TCP server connection. The adapters directory confirms support for Senergy, Powdrive, IAMmeter, JK BMS, and Pytes devices.

6. **Python 3.10+ required:** The codebase uses modern Python features (async/await, type hints, match statements presumed). MicroPython on ESP32 has its own constraints.

7. **Frontend assumes authenticated state:** Most pages require authentication. The auth flow is JWT-based with tokens stored client-side. The `Auth.tsx` page handles both login and registration.

8. **Redis DB separation:** System A uses Redis DB 0, System B uses Redis DB 1 (per docker-compose config), but they share the same Redis instance and use the same key namespace for telemetry data.

9. **No CI/CD pipeline visible:** No GitHub Actions, Jenkins, or other CI/CD configuration files were found in the repository. Testing and deployment appear to be manual.

10. **Database schemas are ahead of application code:** The database documentation describes tables for reports, report_schedules, report_templates, billing_simulations, and tariff_plans that may not be fully wired into application service layers yet.

---

## Appendix A: Port Map

| Service | Dev Port | Description |
|---------|----------|-------------|
| System A API | 8000 | Platform REST API |
| System B API | 8001 | Telemetry REST API |
| System B Device Server | 8502 | Raw TCP for ESP32 connections |
| Frontend (Vite) | 8080 | React development server |
| PostgreSQL (System A) | 5432 | Platform database |
| TimescaleDB (System B) | 5433 | Telemetry database |
| Redis | 6379 | Shared cache |
| MQTT (Mosquitto) | 1883 | Device MQTT broker |
| MQTT WebSocket | 9001 | MQTT over WebSocket |

## Appendix B: API Route Summary

### System A (`/api/v1/`)
| Module | Route Prefix | Key Operations |
|--------|-------------|----------------|
| Auth | `/auth` | Register, login, refresh token |
| Users | `/users` | CRUD, profile |
| Organizations | `/organizations` | CRUD, member management, invitations |
| Sites | `/sites` | CRUD, configuration |
| Devices | `/devices` | Claim, release, list, details |
| Dashboards | `/dashboard` | Power-flow, stats, energy-chart, battery, alerts, environmental, billing |
| Dashboard Widgets | `/dashboard/widgets` | Widget-specific endpoints |
| Billing | `/billing` | Tariff plans, simulations |
| Alerts | `/alerts` | Alert rules, alert instances |
| Protocol Definitions | `/protocol-definitions` | Register map management |
| Discovery | `/discovery` | Device discovery |

### System B (`/api/v1/`)
| Module | Route Prefix | Key Operations |
|--------|-------------|----------------|
| Devices | `/devices` | Register, serial lookup, claim/release, status |
| Telemetry | `/telemetry` | Ingestion, query by device/time-range |
| Commands | `/commands` | Queue, status, execution |
| Events | `/events` | Device event log |

---

*End of System Understanding Document*
