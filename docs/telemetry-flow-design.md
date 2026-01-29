# Telemetry Flow Architecture Design

## Overview

This document describes the data flow architecture for Solar Hub, covering how telemetry data flows from ESP32 devices through System B and System A to the frontend dashboard.

## Key Design Decisions

1. **Serial Number as Universal Identifier**: All systems use device serial number as the primary identifier
2. **Shared Redis Cache**: System B writes, System A reads - eliminates HTTP overhead
3. **Widget-Based APIs**: Each dashboard widget has its own endpoint with appropriate caching
4. **Pull Model**: Frontend polls System A, System A reads from Redis (no push from System B to System A)

---

## Architecture Diagram

```
                              ┌──────────────────────┐
                              │       REDIS          │
                              │   (Shared Cache)     │
                              │                      │
                              │  device:{serial}:    │
                              │    telemetry         │
                              │    status            │
                              │    last_seen         │
                              └──────────┬───────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │ WRITE                    │                    READ  │
              ▼                          │                          ▼
┌─────────────────────┐                  │              ┌─────────────────────┐
│      System B       │                  │              │      System A       │
│   (Telemetry)       │                  │              │    (Platform)       │
│                     │                  │              │                     │
│  - Receive ESP32    │                  │              │  - User Auth        │
│  - Process data     │                  │              │  - Dashboard APIs   │
│  - Write to Redis   │                  │              │  - Read from Redis  │
│  - Store TimescaleDB│                  │              │  - Fallback to B    │
└─────────────────────┘                  │              └─────────────────────┘
          ▲                              │                          │
          │                              │                          │
    ┌─────┴─────┐                        │                    ┌─────▼─────┐
    │   ESP32   │                        │                    │  Frontend │
    │  Device   │                        │                    │           │
    └───────────┘                        │                    └───────────┘
```

---

## Serial Number Format

**Format:** `MMHH-TTNN-NNNN-NNCC` (16 characters, dashes optional)

- **MM** (chars 0-1): Manufacturer code - "SH" (SolarHub)
- **HH** (chars 2-3): Hardware revision - "01", "02", etc.
- **TT** (chars 4-5): Device type code
  - "IN" = Inverter
  - "BT" = Battery
  - "MT" = Meter
  - "GW" = Gateway
  - "SR" = Sensor
  - "WS" = Weather Station
  - "XX" = Other
- **NNNNNNNN** (chars 6-13): Random alphanumeric string (8 chars)
- **CC** (chars 14-15): Check digits (modified Luhn algorithm)

**Example:** `SH01IN2406130092`

---

## Redis Key Structure

### Written by System B (Read by System A)

```
# Real-time telemetry snapshot
device:{serial}:telemetry     → JSON blob (TTL: 120s)

# Device online/offline status
device:{serial}:status        → "online" | "offline" (TTL: 120s)

# Last seen timestamp
device:{serial}:last_seen     → Unix timestamp (TTL: 120s)
```

### Written by System A (Dashboard Cache)

```
# Cached aggregates for performance
device:{serial}:stats:today   → Energy stats JSON (TTL: 60s)
device:{serial}:chart:day     → Chart data JSON (TTL: 5min)
device:{serial}:chart:week    → Chart data JSON (TTL: 15min)
device:{serial}:chart:month   → Chart data JSON (TTL: 1hr)
```

---

## Telemetry Data Structure

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
    "frequency_hz": 50.0,
    "l1_voltage_v": 220.8,
    "l2_voltage_v": 220.4,
    "l3_voltage_v": 222.0
  },
  "status": {
    "working_mode": 2,
    "working_mode_name": "battery_priority",
    "grid_status": 5,
    "grid_connected": true,
    "faults": [],
    "warnings": []
  }
}
```

---

## Dashboard API Endpoints

### Widget-Based Design

Each widget has its own endpoint for:
- Independent loading (one failure doesn't break others)
- Different cache TTLs per widget
- Different refresh rates

| Widget | Endpoint | Cache TTL | Refresh Rate |
|--------|----------|-----------|--------------|
| **Power Flow (Real-time)** | `GET /api/v1/dashboard/power-flow` | 5s | 5s |
| **Statistics Cards** | `GET /api/v1/dashboard/stats` | 30s | 30s |
| **Energy Chart** | `GET /api/v1/dashboard/energy-chart` | 5min | Manual |
| **Battery Status** | `GET /api/v1/dashboard/battery` | 10s | 10s |
| **Device Status** | `GET /api/v1/dashboard/device-status` | 30s | 30s |
| **Alerts** | `GET /api/v1/dashboard/alerts` | 60s | 60s |
| **Environmental Impact** | `GET /api/v1/dashboard/environmental` | 1hr | Manual |
| **Billing Summary** | `GET /api/v1/dashboard/billing` | 1hr | Manual |

### Query Parameters

All endpoints accept:
- `site_id` (UUID) - Site to get data for
- `device_serial` (string) - Specific device (optional, defaults to all site devices)

---

## Data Flow Sequences

### 1. Device Registration Flow

```
1. User fills registration form (email, password, device_serial)
2. Frontend → POST /api/v1/auth/register → System A
3. System A → GET /api/v1/devices/validate/{serial} → System B
4. System B checks if device exists and returns device info
5. System A creates user, site, and links device
6. System A returns success with user + device info
```

### 2. Telemetry Ingestion Flow (System B)

```
1. ESP32 connects to System B via Modbus TCP
2. System B identifies device by protocol probing
3. System B polls device for telemetry data
4. System B processes and validates data
5. System B writes to Redis: device:{serial}:telemetry
6. System B writes to TimescaleDB for historical storage
```

### 3. Dashboard Data Flow

```
1. Frontend requests dashboard widget data
2. System A receives request, extracts user's device serials
3. System A reads from Redis: device:{serial}:telemetry
4. If cache miss → System A calls System B API (fallback)
5. System A formats response for widget
6. Frontend renders widget with data
```

---

## Implementation Phases

### Phase 1: System B Redis Write
- Add Redis write after telemetry processing
- Use serial number as key
- Set appropriate TTL (120s)

### Phase 2: System A Redis Read
- Add Redis client to read telemetry
- Implement fallback to System B API
- Cache responses appropriately

### Phase 3: System A Widget APIs
- Create new widget-based endpoints
- Each endpoint reads from Redis
- Independent caching per widget

### Phase 4: Frontend Updates
- Update API calls to new widget endpoints
- Implement per-widget polling
- Handle loading/error states per widget

### Phase 5: Cleanup
- Remove old snapshot push endpoint
- Remove System B → System A HTTP calls
- Update documentation

---

## Why Redis?

| Use Case | Purpose |
|----------|---------|
| **Telemetry Cache** | System B writes, System A reads (~1ms latency) |
| **Session/Token Store** | JWT blacklist, refresh tokens |
| **Rate Limiting** | Track API request counts per user |
| **Dashboard Cache** | Cache expensive aggregation queries |
| **Real-time Updates** | Pub/Sub for future WebSocket support |

---

## Configuration

### Redis Settings (Shared)

```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=<optional>
```

### Cache TTLs

```python
TELEMETRY_TTL = 120      # 2 minutes
STATUS_TTL = 120         # 2 minutes
STATS_CACHE_TTL = 60     # 1 minute
CHART_DAY_TTL = 300      # 5 minutes
CHART_WEEK_TTL = 900     # 15 minutes
CHART_MONTH_TTL = 3600   # 1 hour
```

---

## Error Handling

### Redis Unavailable
- System A falls back to direct System B API call
- Log warning for monitoring
- Continue serving requests (degraded performance)

### Device Not Found
- Return 404 with helpful message including serial number
- Suggest user to register/claim the device

### Stale Data
- Check `last_seen` timestamp
- If > 5 minutes old, mark device as "offline"
- Still return last known data with staleness indicator

---

## Future Enhancements

1. **WebSocket Support**: Real-time push updates to frontend
2. **Redis Cluster**: For high availability
3. **Data Compression**: Compress telemetry JSON in Redis
4. **Alerting Pipeline**: Redis Pub/Sub for real-time alerts

---

*Document Version: 1.0*
*Last Updated: 2026-01-24*
