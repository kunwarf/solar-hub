# Home Assistant Integration — Design Document

**Project:** Solar Hub
**Feature:** Home Assistant MQTT Integration
**Date:** 2026-04-08
**Version:** 1.0
**Status:** Approved for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Option Analysis](#3-option-analysis)
4. [Architecture Design](#4-architecture-design)
5. [Topic Structure](#5-topic-structure)
6. [Database Schema](#6-database-schema)
7. [API Design](#7-api-design)
8. [Component Design](#8-component-design)
9. [Infrastructure Changes](#9-infrastructure-changes)
10. [Security Model](#10-security-model)
11. [Backward Compatibility](#11-backward-compatibility)
12. [Resource Impact](#12-resource-impact)
13. [Subscription & Monetisation](#13-subscription--monetisation)
14. [Implementation Phases](#14-implementation-phases)
15. [Testing Strategy](#15-testing-strategy)
16. [Risks & Mitigations](#16-risks--mitigations)

---

## 1. Executive Summary

Expose Solar Hub device telemetry to Home Assistant via a dedicated MQTT broker.
Each user who opts in receives a unique MQTT username and password. They connect
their Home Assistant instance to the Solar Hub HA broker, and all enrolled devices
appear automatically as HA entities via MQTT Discovery — no manual YAML required.

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transport | MQTT (not REST) | Push-based, real-time, HA natively supports |
| Broker | Dedicated `solarhub_ha_mqtt` instance | Isolates HA clients from internal device bus |
| HA Setup | MQTT Discovery | Zero-config on HA side |
| Auth | Per-user credentials (generated) | Fine-grained access control |
| Opt-in | User-controlled feature | No impact on existing users |

---

## 2. Background & Motivation

The system already runs an Eclipse Mosquitto broker (`solarhub_mqtt`, port 1883)
for internal device-to-System-B communication. The existing broker must not be
exposed to Home Assistant clients because:

- Internal topics (`solar-hub/{device_id}/telemetry`) carry all device data
  without per-user scoping — any HA client could subscribe to all devices.
- The internal broker's `allow_anonymous true` setting is a development shortcut
  that cannot remain in production.
- Mixing internal device traffic with external HA subscriptions creates a shared
  bottleneck and complicates ACL reasoning.

A second, dedicated Mosquitto instance for HA integration solves all three issues.

---

## 3. Option Analysis

### Option A: REST API with API Key

- User creates a personal API key in Solar Hub.
- Home Assistant polls `GET /api/v1/integrations/ha/telemetry?api_key=...`.
- Polling interval ≥ 30 s to avoid overloading System A.

**Rejected because:**
- Polling adds HTTP load to System A proportional to user count.
- Latency: 30 s poll interval vs. sub-second MQTT push.
- HA REST integration requires manual YAML configuration per sensor.

### Option B: MQTT on Existing Internal Broker

- System B publishes HA topics to `solarhub_mqtt`.
- User connects HA to the existing broker on port 1883.

**Rejected because:**
- Exposes internal device topics to HA clients without per-user topic scoping.
- Cross-user data leakage risk if ACLs are misconfigured.
- Any HA client misbehaviour could affect internal device communication.

### Option C: Dedicated HA MQTT Broker ✅ (Selected)

- New `solarhub_ha_mqtt` Mosquitto container (port 1884 external / 1884 internal).
- Per-user credentials managed via Mosquitto Dynamic Security Plugin.
- ACL: each user can only read `solarhub/ha/{their_username}/#`.
- System B's `HATelemetryPublisher` connects with a privileged internal account.
- HA MQTT Discovery publishes entity config automatically.

---

## 4. Architecture Design

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  EXISTING PIPELINE (unchanged)                                       │
│                                                                      │
│  ESP32 ──TCP 8502──► System B ──► TimescaleDB                       │
│                         │                                            │
│                         └──► Redis  device:{serial}:telemetry       │
│                                  └──► System A ──► Frontend         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  NEW HA INTEGRATION FLOW                                             │
│                                                                      │
│  System A                                                            │
│  MqttIntegrationService                                              │
│     │  manage user credentials + enrolled devices                   │
│     │  call Mosquitto Dynamic Security API (via MQTT)               │
│     ▼                                                                │
│  solarhub_ha_mqtt (port 1884)                                        │
│     ▲                                                                │
│  System B                                                            │
│  HATelemetryPublisher (background task, every 30 s)                 │
│     │  reads Redis: device:{serial}:telemetry                       │
│     │  reads enrolled devices from System A API                     │
│     │  publishes state + availability + HA Discovery payloads       │
│     ▼                                                                │
│  solarhub_ha_mqtt (port 1884)                                        │
│     ▼                                                                │
│  Home Assistant (external)                                           │
│     subscribes with user's credentials                               │
│     receives MQTT Discovery → entities auto-created                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Ownership

| Component | Owned By | Responsibility |
|-----------|----------|----------------|
| `mqtt_integrations` table | System A | User credentials, settings |
| `mqtt_integration_devices` table | System A | Device enrolment |
| `MqttIntegrationService` | System A | Credential lifecycle, Mosquitto user management |
| `/api/v1/integrations/mqtt` | System A | REST API for frontend |
| `HATelemetryPublisher` | System B | Read Redis → publish to HA broker |
| `solarhub_ha_mqtt` | Infrastructure | Broker, per-user ACL |
| `MQTTIntegrationCard` | Frontend | UI for setup + device enrolment |

---

## 5. Topic Structure

### State Topics (published by System B every 30 s)

```
solarhub/ha/{ha_username}/{device_serial}/state
solarhub/ha/{ha_username}/{device_serial}/availability
```

**State payload (JSON):**
```json
{
  "pv_power_w": 4200,
  "battery_power_w": -800,
  "battery_soc_pct": 78,
  "grid_power_w": 0,
  "load_power_w": 3400,
  "battery_voltage_v": 52.4,
  "battery_current_a": -15.3,
  "grid_voltage_v": 220.5,
  "grid_frequency_hz": 50.0,
  "inverter_temp_c": 42.1,
  "pv_energy_today_kwh": 18.2,
  "grid_import_today_kwh": 0.3,
  "grid_export_today_kwh": 5.1,
  "timestamp": "2026-04-08T10:30:00Z"
}
```

**Availability payload:** `"online"` or `"offline"`

### HA MQTT Discovery Topics (published once per device on enrolment)

```
homeassistant/sensor/{ha_username}_{device_serial}_{metric}/config
```

**Discovery payload example (PV Power):**
```json
{
  "name": "PV Power",
  "unique_id": "solarhub_{device_serial}_pv_power_w",
  "state_topic": "solarhub/ha/{ha_username}/{device_serial}/state",
  "value_template": "{{ value_json.pv_power_w | float(0) | round(1) }}",
  "unit_of_measurement": "W",
  "device_class": "power",
  "state_class": "measurement",
  "availability_topic": "solarhub/ha/{ha_username}/{device_serial}/availability",
  "payload_available": "online",
  "payload_not_available": "offline",
  "device": {
    "identifiers": ["solarhub_{device_serial}"],
    "name": "{device_name}",
    "manufacturer": "{manufacturer}",
    "model": "{model}"
  }
}
```

### Metrics Published via Discovery

| Metric | HA device_class | unit | state_class |
|--------|----------------|------|-------------|
| `pv_power_w` | power | W | measurement |
| `battery_power_w` | power | W | measurement |
| `grid_power_w` | power | W | measurement |
| `load_power_w` | power | W | measurement |
| `battery_soc_pct` | battery | % | measurement |
| `battery_voltage_v` | voltage | V | measurement |
| `battery_current_a` | current | A | measurement |
| `grid_voltage_v` | voltage | V | measurement |
| `grid_frequency_hz` | frequency | Hz | measurement |
| `inverter_temp_c` | temperature | °C | measurement |
| `pv_energy_today_kwh` | energy | kWh | total_increasing |
| `grid_import_today_kwh` | energy | kWh | total_increasing |
| `grid_export_today_kwh` | energy | kWh | total_increasing |

---

## 6. Database Schema

### New Migration: `20260408_0001_add_mqtt_integrations.py`

```sql
-- One MQTT integration per user
CREATE TABLE mqtt_integrations (
    id          UUID PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ha_username VARCHAR(64) UNIQUE NOT NULL,   -- system-generated, e.g. "sh_abc123"
    password_hash VARCHAR(255) NOT NULL,        -- bcrypt hash
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    publish_interval_seconds INTEGER NOT NULL DEFAULT 30,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    version     INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX uq_mqtt_integrations_user_id ON mqtt_integrations(user_id);
CREATE INDEX ix_mqtt_integrations_ha_username   ON mqtt_integrations(ha_username);

-- Devices enrolled for HA publishing
CREATE TABLE mqtt_integration_devices (
    id             UUID PRIMARY KEY,
    integration_id UUID NOT NULL REFERENCES mqtt_integrations(id) ON DELETE CASCADE,
    device_id      UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (integration_id, device_id)
);

CREATE INDEX ix_mqtt_integration_devices_integration_id
    ON mqtt_integration_devices(integration_id);
```

---

## 7. API Design

All endpoints require user authentication via the existing `get_current_active_user` dependency.

### `POST /api/v1/integrations/mqtt`

Create integration for the authenticated user. Generates `ha_username` and password.
Creates Mosquitto user + ACL. Returns the plaintext password **once** (not stored).

**Response:**
```json
{
  "id": "uuid",
  "ha_username": "sh_abc123",
  "password": "plaintext-shown-once",
  "broker_host": "mqtt.solarhub.io",
  "broker_port": 1884,
  "enabled": true,
  "created_at": "2026-04-08T10:00:00Z"
}
```

### `GET /api/v1/integrations/mqtt`

Returns the user's integration (without password).

### `DELETE /api/v1/integrations/mqtt`

Deletes integration, removes Mosquitto user, unenrols all devices.

### `POST /api/v1/integrations/mqtt/rotate-password`

Generates new password, updates hash + Mosquitto. Returns new plaintext password once.

### `GET /api/v1/integrations/mqtt/devices`

Returns list of devices with `enrolled: bool` for each.

### `PUT /api/v1/integrations/mqtt/devices/{device_id}`

Enrol or unenrol a device. Body: `{"enrolled": true}`.

Validation: device must belong to the authenticated user's site.

---

## 8. Component Design

### 8.1 System A — `MqttIntegrationService`

```python
class MqttIntegrationService:
    def __init__(self, uow: UnitOfWork, mosquitto_client: MosquittoAdminClient): ...

    async def create_integration(self, user_id: UUID) -> MqttIntegrationResult:
        """Generate credentials, create Mosquitto user + ACL, persist to DB."""

    async def rotate_password(self, integration_id: UUID) -> str:
        """Generate new password, update hash and Mosquitto. Return plaintext."""

    async def delete_integration(self, integration_id: UUID) -> None:
        """Remove Mosquitto user, delete DB record (cascade removes devices)."""

    async def add_device(self, integration_id: UUID, device_id: UUID) -> None:
        """Validate device belongs to user, create mqtt_integration_devices row."""

    async def remove_device(self, integration_id: UUID, device_id: UUID) -> None:

    async def get_integration(self, user_id: UUID) -> Optional[MqttIntegration]:

    async def get_enrolled_devices(self, integration_id: UUID) -> List[UUID]:
```

### 8.2 System A — `MosquittoAdminClient`

Manages Mosquitto Dynamic Security Plugin users via the `$CONTROL/dynamic-security/v1`
MQTT topic using a privileged internal publisher connection.

```python
class MosquittoAdminClient:
    async def create_user(self, username: str, password: str) -> None:
        """Create Mosquitto user with ACL: read-only on solarhub/ha/{username}/#"""

    async def delete_user(self, username: str) -> None:

    async def update_password(self, username: str, new_password: str) -> None:
```

### 8.3 System B — `HATelemetryPublisher`

Background task started in `main.py` lifespan. Connects to `solarhub_ha_mqtt`
with a privileged internal account. LWT configured to flip all availability topics
to `"offline"` on unexpected disconnect.

```python
class HATelemetryPublisher:
    async def start(self) -> None:
        """Connect to HA broker, publish Discovery for all enrolled devices."""

    async def stop(self) -> None:

    async def _publish_loop(self) -> None:
        """Every publish_interval_seconds: fetch enrollments, read Redis, publish."""

    async def _publish_device_state(
        self, ha_username: str, device_serial: str, telemetry: dict
    ) -> None:

    async def _publish_ha_discovery(
        self, ha_username: str, device_serial: str, device_info: dict
    ) -> None:
        """Publish one discovery config payload per metric. Retained=True."""

    def _build_state_payload(self, telemetry: dict) -> dict:
        """Extract HA-relevant fields from Redis telemetry blob."""
```

**Enrolled device cache:** The publisher fetches enrolled devices from System A's
internal API (`GET /api/v1/integrations/mqtt/enrolled-devices`) on startup and
refreshes every 5 minutes. A direct DB query is not appropriate (System B must not
read System A's PostgreSQL directly).

### 8.4 Frontend — `MQTTIntegrationCard`

Location: `frontend/src/components/settings/MQTTIntegrationCard.tsx`

UI Sections:
- **Status**: enabled/disabled toggle
- **Broker details**: host, port (copyable)
- **Credentials**: username (copyable), password (hidden by default, show once
  after creation, "Regenerate" button with confirmation dialog)
- **Enrolled devices**: checklist of user's devices with toggle per device
- **Setup guide**: collapsible "How to connect Home Assistant" with step-by-step
  instructions referencing the exact broker host/port/credentials

---

## 9. Infrastructure Changes

### docker-compose.yml additions

```yaml
solarhub_ha_mqtt:
  image: eclipse-mosquitto:2
  container_name: solarhub_ha_mqtt
  ports:
    - "1884:1884"      # MQTT external access for Home Assistant
    - "9002:9002"      # WebSocket (optional)
  volumes:
    - mosquitto_ha_data:/mosquitto/data
    - mosquitto_ha_log:/mosquitto/log
    - ./mosquitto_ha.conf:/mosquitto/config/mosquitto.conf:ro
    - ./mosquitto_ha_dynsec.json:/mosquitto/config/dynamic-security.json
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "mosquitto_sub", "-t", "$$SYS/#", "-C", "1", "-i", "healthcheck", "-W", "3"]
    interval: 10s
    timeout: 5s
    retries: 3
```

### `mosquitto_ha.conf`

```
listener 1884
protocol mqtt

listener 9002
protocol websockets

allow_anonymous false
plugin /usr/lib/mosquitto_dynamic_security.so
plugin_opt_config_file /mosquitto/config/dynamic-security.json

persistence true
persistence_location /mosquitto/data/

log_dest file /mosquitto/log/mosquitto.log
log_dest stdout
log_type error
log_type warning
log_type notice
log_type information
```

### New Environment Variables

```bash
# System A
HA_MQTT_BROKER_HOST=solarhub_ha_mqtt
HA_MQTT_BROKER_PORT=1884
HA_MQTT_ADMIN_USERNAME=solarhub_admin
HA_MQTT_ADMIN_PASSWORD=<strong-random>

# System B
HA_MQTT_ENABLED=true
HA_MQTT_BROKER_HOST=solarhub_ha_mqtt
HA_MQTT_BROKER_PORT=1884
HA_MQTT_PUBLISHER_USERNAME=solarhub_publisher
HA_MQTT_PUBLISHER_PASSWORD=<strong-random>
HA_MQTT_PUBLISH_INTERVAL=30

# Public-facing (shown to users in UI)
HA_MQTT_PUBLIC_HOST=mqtt.solarhub.io
HA_MQTT_PUBLIC_PORT=1884
```

---

## 10. Security Model

### ACL Design

| Account | Can Publish | Can Subscribe |
|---------|------------|---------------|
| `solarhub_publisher` (System B) | `solarhub/ha/#`, `homeassistant/#` | Nothing |
| `solarhub_admin` (System A) | `$CONTROL/dynamic-security/v1` | `$CONTROL/dynamic-security/v1/response` |
| `sh_{user}` (HA user) | Nothing | `solarhub/ha/{sh_user}/#` (read-only) |

### Credential Security

- Passwords are generated as 32-character random strings (URL-safe base64).
- Only the bcrypt hash is stored in PostgreSQL.
- Plaintext is returned **only** at creation or rotation — never stored, never
  retrievable after the initial response.
- Frontend shows the password once with a "Copy" button and a warning:
  "Save this password — it cannot be shown again."

### Transport

- In development: MQTT plain on port 1884 (acceptable behind VPN/local network).
- In production: TLS recommended (`listener 8883`, cert mounted as volume).
  This is a Phase 2 enhancement.

---

## 11. Backward Compatibility

This feature introduces **no breaking changes**:

- The existing `solarhub_mqtt` broker and all its configuration are untouched.
- No existing Redis keys, API endpoints, or DB tables are modified.
- No existing System B device polling, TCP server, or telemetry pipeline is changed.
- No existing System A domain entities or services are modified.
- The feature is entirely opt-in — no existing user is affected until they
  explicitly call `POST /api/v1/integrations/mqtt`.

---

## 12. Resource Impact

| Resource | Additional Load | Notes |
|----------|----------------|-------|
| Mosquitto (HA broker) | 1 connection per HA user, ~1 msg/30s per enrolled device | Negligible; Mosquitto handles 10k+ connections |
| System B | 1 Redis GET per enrolled device per 30s | Redis GET latency ~0.1 ms; 100 devices = 0.01s/cycle |
| System A | New table lookups on integration create/rotate | O(1) per user action, infrequent |
| PostgreSQL (System A) | 2 new small tables | Static user data, minimal growth |
| Network (external) | ~2–5 KB per device per 30s | 10 devices = ~100 KB/min per user |
| CPU | Near zero | Async publish, no computation |

---

## 13. Subscription & Monetisation

The integration is an optional add-on. Access is controlled by a feature flag
`ha_integration_enabled` on the user's subscription record (no new table needed;
use existing `preferences` JSONB on `organizations` or add a column in a future
subscription migration).

**Recommended models:**

| Model | Notes |
|-------|-------|
| Free: 1 device | Encourages trial, limits broker load |
| Paid add-on: Rs. 150/month | All devices, shorter publish interval (10s) |
| Included in Professional tier | Upsell differentiator |

Implementation: `MqttIntegrationService.create_integration()` checks the user's
subscription flag before creating. Returns a 402 if not entitled.

---

## 14. Implementation Phases

### Phase 1 — Infrastructure (0.5 day)
- [ ] Add `solarhub_ha_mqtt` service to `docker-compose.yml`
- [ ] Create `mosquitto_ha.conf`
- [ ] Initialise Dynamic Security Plugin with admin + publisher accounts
- [ ] Update `.env.example` with new variables

### Phase 2 — System A: Integration Management (2 days)
- [ ] DB migration `20260408_0001_add_mqtt_integrations.py`
- [ ] Domain entities: `MqttIntegration`, `MqttIntegrationDevice`
- [ ] Repository interface methods in `repositories.py`
- [ ] SQLAlchemy ORM models
- [ ] SQLAlchemy repository implementations
- [ ] UoW: add `mqtt_integrations` and `mqtt_integration_devices` properties
- [ ] `MosquittoAdminClient` (infrastructure, injectable)
- [ ] `MqttIntegrationService`
- [ ] API router `/api/v1/integrations/mqtt` with all endpoints
- [ ] Register router in `system_a/app/api/v1/__init__.py`
- [ ] Add config fields to `system_a/app/config.py`

### Phase 3 — System B: HA Publisher (1.5 days)
- [ ] `HATelemetryPublisher` service
- [ ] HA Discovery payload builder (one payload per metric per device)
- [ ] Internal endpoint in System A: `GET /api/v1/integrations/mqtt/enrolled-devices`
  (used by System B publisher to know what to publish, protected by internal API key)
- [ ] Wire `HATelemetryPublisher` into `system_b/app/main.py` lifespan
- [ ] Add config fields to `system_b/app/config.py`

### Phase 4 — Frontend (1 day)
- [ ] `MQTTIntegrationCard.tsx` component
- [ ] Add "Integrations" tab to `Settings.tsx`
- [ ] New service methods in `settings.service.ts` (or new `integrations.service.ts`)
- [ ] API endpoint definitions in `frontend/src/api/config.ts`

### Phase 5 — Tests (1 day)
- See Section 15.

---

## 15. Testing Strategy

### Unit Tests — System A

**File:** `system_a/tests/unit/services/test_mqtt_integration_service.py`

```python
"""
Unit tests for MqttIntegrationService.
All external dependencies (UoW, MosquittoAdminClient) are mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from system_a.app.application.services.mqtt_integration_service import MqttIntegrationService
from system_a.app.domain.entities.mqtt_integration import MqttIntegration


class TestCreateIntegration:
    async def test_create_generates_unique_ha_username(self, service, mock_uow):
        """ha_username must be unique and follow the 'sh_' prefix convention."""
        result = await service.create_integration(user_id=uuid4())
        assert result.ha_username.startswith("sh_")
        assert len(result.ha_username) > 4

    async def test_create_returns_plaintext_password_once(self, service, mock_uow):
        """Plaintext password returned in result; only hash persisted."""
        result = await service.create_integration(user_id=uuid4())
        assert result.plaintext_password is not None
        assert len(result.plaintext_password) >= 32

    async def test_create_stores_bcrypt_hash_not_plaintext(self, service, mock_uow):
        """The entity saved to the repository must store a hash, not the raw password."""
        result = await service.create_integration(user_id=uuid4())
        saved: MqttIntegration = mock_uow.mqtt_integrations.add.call_args[0][0]
        assert saved.password_hash != result.plaintext_password
        assert saved.password_hash.startswith("$2b$")

    async def test_create_calls_mosquitto_to_provision_user(self, service, mock_mosquitto):
        """Mosquitto user must be provisioned before DB commit."""
        await service.create_integration(user_id=uuid4())
        mock_mosquitto.create_user.assert_awaited_once()

    async def test_create_fails_if_integration_already_exists(self, service, mock_uow):
        """A user can only have one MQTT integration."""
        mock_uow.mqtt_integrations.get_by_user_id.return_value = MagicMock()
        with pytest.raises(Exception, match="already exists"):
            await service.create_integration(user_id=uuid4())

    async def test_create_rolls_back_if_mosquitto_fails(self, service, mock_mosquitto, mock_uow):
        """If Mosquitto provisioning fails, the DB record must not be committed."""
        mock_mosquitto.create_user.side_effect = Exception("broker unavailable")
        with pytest.raises(Exception):
            await service.create_integration(user_id=uuid4())
        mock_uow.commit.assert_not_awaited()


class TestRotatePassword:
    async def test_rotate_returns_new_plaintext(self, service, mock_uow, existing_integration):
        result = await service.rotate_password(existing_integration.id)
        assert result.plaintext_password is not None

    async def test_rotate_updates_hash_in_db(self, service, mock_uow, existing_integration):
        old_hash = existing_integration.password_hash
        await service.rotate_password(existing_integration.id)
        updated: MqttIntegration = mock_uow.mqtt_integrations.update.call_args[0][0]
        assert updated.password_hash != old_hash

    async def test_rotate_calls_mosquitto_update(self, service, mock_mosquitto, existing_integration):
        await service.rotate_password(existing_integration.id)
        mock_mosquitto.update_password.assert_awaited_once_with(
            existing_integration.ha_username, pytest.approx(any)
        )


class TestDeleteIntegration:
    async def test_delete_removes_mosquitto_user(self, service, mock_mosquitto, existing_integration):
        await service.delete_integration(existing_integration.id)
        mock_mosquitto.delete_user.assert_awaited_once_with(existing_integration.ha_username)

    async def test_delete_removes_db_record(self, service, mock_uow, existing_integration):
        await service.delete_integration(existing_integration.id)
        mock_uow.mqtt_integrations.delete.assert_awaited_once_with(existing_integration.id)


class TestAddDevice:
    async def test_add_device_validates_ownership(self, service, mock_uow, existing_integration):
        """Device must belong to the same user's organisation."""
        mock_uow.devices.get_by_id.return_value = None
        with pytest.raises(Exception, match="not found"):
            await service.add_device(existing_integration.id, device_id=uuid4())

    async def test_add_device_prevents_duplicate_enrolment(
        self, service, mock_uow, existing_integration
    ):
        mock_uow.mqtt_integration_devices.exists.return_value = True
        with pytest.raises(Exception, match="already enrolled"):
            await service.add_device(existing_integration.id, device_id=uuid4())

    async def test_add_device_persists_record(self, service, mock_uow, existing_integration, mock_device):
        await service.add_device(existing_integration.id, device_id=mock_device.id)
        mock_uow.mqtt_integration_devices.add.assert_awaited_once()
```

### Unit Tests — System B

**File:** `system_b/tests/unit/test_ha_telemetry_publisher.py`

```python
"""
Unit tests for HATelemetryPublisher.
MQTT client and Redis reads are mocked.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from system_b.device_server.services.ha_telemetry_publisher import HATelemetryPublisher


SAMPLE_TELEMETRY = {
    "serial_number": "SH01IN2406130001",
    "timestamp": "2026-04-08T10:00:00Z",
    "power": {
        "pv_total_w": 4200,
        "grid_w": 0,
        "load_w": 3400,
        "battery_w": -800,
    },
    "battery": {"soc_pct": 78, "voltage_v": 52.4, "current_a": -15.3},
    "grid": {"voltage_v": 220.5, "frequency_hz": 50.0},
}


class TestBuildStatePayload:
    def test_extracts_pv_power(self, publisher):
        payload = publisher._build_state_payload(SAMPLE_TELEMETRY)
        assert payload["pv_power_w"] == 4200

    def test_extracts_battery_soc(self, publisher):
        payload = publisher._build_state_payload(SAMPLE_TELEMETRY)
        assert payload["battery_soc_pct"] == 78

    def test_missing_fields_default_to_none(self, publisher):
        payload = publisher._build_state_payload({})
        assert payload.get("pv_power_w") is None

    def test_payload_contains_timestamp(self, publisher):
        payload = publisher._build_state_payload(SAMPLE_TELEMETRY)
        assert "timestamp" in payload


class TestPublishDeviceState:
    async def test_publishes_to_correct_topic(self, publisher, mock_mqtt_client):
        await publisher._publish_device_state(
            ha_username="sh_testuser",
            device_serial="SH01IN2406130001",
            telemetry=SAMPLE_TELEMETRY,
        )
        topic = mock_mqtt_client.publish.call_args[0][0]
        assert topic == "solarhub/ha/sh_testuser/SH01IN2406130001/state"

    async def test_publishes_valid_json(self, publisher, mock_mqtt_client):
        await publisher._publish_device_state(
            ha_username="sh_testuser",
            device_serial="SH01IN2406130001",
            telemetry=SAMPLE_TELEMETRY,
        )
        payload_str = mock_mqtt_client.publish.call_args[0][1]
        payload = json.loads(payload_str)
        assert isinstance(payload, dict)

    async def test_publishes_online_availability(self, publisher, mock_mqtt_client):
        await publisher._publish_device_state(
            ha_username="sh_testuser",
            device_serial="SH01IN2406130001",
            telemetry=SAMPLE_TELEMETRY,
        )
        calls = [c[0][0] for c in mock_mqtt_client.publish.call_args_list]
        assert any("availability" in t for t in calls)
        avail_call = next(c for c in mock_mqtt_client.publish.call_args_list
                          if "availability" in c[0][0])
        assert avail_call[0][1] == "online"

    async def test_stale_telemetry_publishes_offline(self, publisher, mock_mqtt_client):
        """If last_seen is older than 120s, publish availability=offline."""
        import time
        stale = {**SAMPLE_TELEMETRY, "last_seen": time.time() - 200}
        await publisher._publish_device_state(
            ha_username="sh_testuser",
            device_serial="SH01IN2406130001",
            telemetry=stale,
        )
        avail_call = next(c for c in mock_mqtt_client.publish.call_args_list
                          if "availability" in c[0][0])
        assert avail_call[0][1] == "offline"


class TestHADiscovery:
    async def test_publishes_retained_discovery_for_each_metric(
        self, publisher, mock_mqtt_client
    ):
        await publisher._publish_ha_discovery(
            ha_username="sh_testuser",
            device_serial="SH01IN2406130001",
            device_info={"name": "Test Inverter", "manufacturer": "Senergy", "model": "SEN-5K"},
        )
        retained_topics = [
            c[0][0]
            for c in mock_mqtt_client.publish.call_args_list
            if c[1].get("retain") is True
        ]
        assert any("pv_power_w" in t for t in retained_topics)
        assert any("battery_soc_pct" in t for t in retained_topics)
        assert any("grid_power_w" in t for t in retained_topics)

    async def test_discovery_payload_contains_required_ha_fields(
        self, publisher, mock_mqtt_client
    ):
        await publisher._publish_ha_discovery(
            ha_username="sh_testuser",
            device_serial="SH01IN2406130001",
            device_info={"name": "Test Inverter", "manufacturer": "Senergy", "model": "SEN-5K"},
        )
        pv_call = next(
            c for c in mock_mqtt_client.publish.call_args_list
            if "pv_power_w" in c[0][0]
        )
        config = json.loads(pv_call[0][1])
        assert "state_topic" in config
        assert "value_template" in config
        assert "unique_id" in config
        assert "device" in config
        assert "unit_of_measurement" in config


class TestPublishLoop:
    async def test_skips_device_with_no_redis_data(
        self, publisher, mock_redis, mock_enrolled_devices
    ):
        mock_redis.get.return_value = None
        await publisher._publish_loop()
        # Should not raise, should publish offline for the device
        avail_calls = [
            c for c in mock_redis.get.call_args_list
        ]
        assert len(avail_calls) == len(mock_enrolled_devices)

    async def test_loop_does_not_raise_on_single_device_failure(
        self, publisher, mock_mqtt_client
    ):
        """A publish failure for one device must not abort the entire loop."""
        mock_mqtt_client.publish.side_effect = [Exception("broker error"), None, None]
        # Should complete without raising
        await publisher._publish_loop()
```

### Integration Tests

**File:** `system_a/tests/integration/test_mqtt_integration_api.py`

Tests the full API endpoint behaviour with a real (in-memory) DB and a mock
`MosquittoAdminClient`. Covers: create, get, rotate, delete, add device,
remove device, and auth-required checks.

---

## 16. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| HA user subscribes to wrong user's topics | High | Per-user ACL: read-only on own prefix only |
| Plaintext password leak via browser storage | Medium | Show once; never store in frontend state after navigation |
| Mosquitto Dynamic Security API message loss | Low | Retry with exponential backoff; log failure |
| Publisher disconnect causes all entities to show unavailable | Low | LWT on publisher connection sets availability=offline correctly |
| Redis TTL expires between publish cycles | Low | Publisher checks `last_seen` timestamp; marks offline if stale |
| User adds a device that later goes orphan | Low | Availability topic handles; device is marked offline not errored |
| Port 1884 exposed without TLS in production | Medium | Phase 2: add TLS cert; document in deployment guide |
| System A and Mosquitto state diverge (e.g. Mosquitto restart wipes dynsec) | Medium | On startup, System A reconciles: re-provisions any integration users missing from Mosquitto |

---

## Appendix A: Home Assistant Setup Instructions (for UI help section)

1. In HA, go to **Settings → Devices & Services → Add Integration → MQTT**.
2. Enter the broker details:
   - **Host:** `mqtt.solarhub.io` (or your server IP)
   - **Port:** `1884`
   - **Username:** _(copy from Solar Hub Settings → Integrations)_
   - **Password:** _(copy from Solar Hub Settings → Integrations)_
3. Click **Submit**.
4. Solar Hub devices will appear automatically within 60 seconds under
   **Settings → Devices & Services → MQTT → Devices**.

No YAML configuration is required.

---

*Document version 1.0 — approved 2026-04-08*
