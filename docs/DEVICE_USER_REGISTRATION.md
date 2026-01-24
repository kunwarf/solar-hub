# Device and User Registration Design

## Overview

This document describes the complete flow for device self-registration and user registration with device claiming in the Solar Hub system.

## Architecture

### System Components

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ESP Logger    │     │    System B     │     │    System A     │
│   (Device)      │────>│  Device Server  │<───>│   Backend API   │
│                 │     │   Port 8502     │     │   Port 8000     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        v
                                                ┌─────────────────┐
                                                │    Frontend     │
                                                │   Port 5173     │
                                                └─────────────────┘
```

### Data Model

#### Logger = Device (1:1 Relationship)
- Each ESP logger represents exactly ONE physical device
- The logger IS the device in our system
- Device types: `inverter`, `battery`, `meter`

#### Hierarchy
```
User
  └── Site (Home) [auto-created: "My Home" for new users]
       └── Device (ESP Logger + Physical Device as one entity)
```

---

## 1. Device Self-Registration (ESP → System B)

### 1.1 Registration Message Format

When ESP device powers on and connects to System B:

```json
{
  "action": "register",
  "payload": {
    "serial_number": "SH-2024-001",
    "device_type": "inverter",
    "firmware_version": "1.0.0",
    "manufacturer": "Solis",
    "protocol": "modbus_tcp",
    "capabilities": {
      "has_battery": false,
      "has_meter": true,
      "max_power_kw": 10
    }
  }
}
```

### 1.2 Registration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `serial_number` | string | Yes | Unique device serial (embedded in ESP) |
| `device_type` | enum | Yes | `inverter`, `battery`, `meter` |
| `firmware_version` | string | Yes | ESP firmware version |
| `manufacturer` | string | No | Device manufacturer (e.g., "Solis", "Growatt", "Huawei") |
| `protocol` | string | No | Communication protocol (e.g., "modbus_tcp", "modbus_rtu", "sunspec") |
| `capabilities` | object | No | Device capabilities metadata |

### 1.3 Registration Response

**Success:**
```json
{
  "status": "success",
  "device_id": "uuid-here",
  "message": "Device registered successfully",
  "polling_interval_ms": 5000
}
```

**Already Registered:**
```json
{
  "status": "success",
  "device_id": "existing-uuid",
  "message": "Device reconnected",
  "polling_interval_ms": 5000
}
```

### 1.4 Device States

| State | Description | Transitions |
|-------|-------------|-------------|
| `orphan` | Registered by ESP, no user attached | → `claimed` |
| `claimed` | Attached to a user and site | → `orphan` (if released) |
| `offline` | Device not communicating | (overlay state) |

### 1.5 Sequence Diagram

```
   ESP Logger                    System B                      Database
   (with serial)                 (Device Server)
        │                              │                           │
        │ 1. TCP Connect (port 8502)   │                           │
        │─────────────────────────────>│                           │
        │                              │                           │
        │ 2. REGISTER                  │                           │
        │   {                          │                           │
        │     serial: "SH-2024-001",   │                           │
        │     device_type: "inverter", │                           │
        │     firmware: "1.0.0",       │                           │
        │     manufacturer: "Solis",   │                           │
        │     protocol: "modbus_tcp"   │                           │
        │   }                          │                           │
        │─────────────────────────────>│                           │
        │                              │                           │
        │                              │ 3. Check if exists        │
        │                              │──────────────────────────>│
        │                              │                           │
        │                              │ 4. INSERT/UPDATE device   │
        │                              │    status='orphan'        │
        │                              │    owner_id=NULL          │
        │                              │──────────────────────────>│
        │                              │                           │
        │ 5. ACK {device_id, interval} │                           │
        │<─────────────────────────────│                           │
        │                              │                           │
        │ 6. START POLLING (Modbus)    │                           │
        │<────────────────────────────>│                           │
        │                              │                           │
        │ 7. Telemetry flows           │ 8. Store in TimescaleDB   │
        │<────────────────────────────>│──────────────────────────>│
```

---

## 2. User Registration with Device Claim

### 2.1 Registration Request

**Endpoint:** `POST /api/v1/auth/register`

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "Ahmed",
  "last_name": "Khan",
  "phone": "+92-300-1234567",
  "device_serial": "SH-2024-001"
}
```

### 2.2 Registration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `password` | string | Yes | Password (min 8 chars) |
| `first_name` | string | Yes | User's first name |
| `last_name` | string | Yes | User's last name |
| `phone` | string | No | Phone number |
| `device_serial` | string | No | Device serial to claim during registration |

### 2.3 Registration Flow

```
   Frontend                      System A                      System B
                                 (Backend API)                 (Device API)
        │                              │                           │
        │ 1. POST /auth/register       │                           │
        │   {email, password, name,    │                           │
        │    device_serial}            │                           │
        │─────────────────────────────>│                           │
        │                              │                           │
        │                              │ 2. Validate input         │
        │                              │    Check email unique     │
        │                              │                           │
        │                              │ 3. If device_serial:      │
        │                              │    GET /devices/serial/   │
        │                              │        {serial}           │
        │                              │──────────────────────────>│
        │                              │                           │
        │                              │ 4. Return device status   │
        │                              │<──────────────────────────│
        │                              │                           │
        │                              │ 5. Validate device:       │
        │                              │    - exists? ✓            │
        │                              │    - orphan? ✓            │
        │                              │                           │
        │                              │ 6. Create user            │
        │                              │                           │
        │                              │ 7. Create default site    │
        │                              │    "My Home"              │
        │                              │                           │
        │                              │ 8. Claim device           │
        │                              │    PUT /devices/{id}/claim│
        │                              │    {owner_id, site_id}    │
        │                              │──────────────────────────>│
        │                              │                           │
        │                              │ 9. Device claimed         │
        │                              │<──────────────────────────│
        │                              │                           │
        │ 10. Success Response         │                           │
        │    {user, site, device}      │                           │
        │<─────────────────────────────│                           │
```

### 2.4 Registration Response

**Success (with device):**
```json
{
  "success": true,
  "message": "Registration successful",
  "data": {
    "user": {
      "id": "user-uuid",
      "email": "user@example.com",
      "first_name": "Ahmed",
      "last_name": "Khan"
    },
    "site": {
      "id": "site-uuid",
      "name": "My Home",
      "is_default": true
    },
    "device": {
      "id": "device-uuid",
      "serial_number": "SH-2024-001",
      "device_type": "inverter",
      "manufacturer": "Solis",
      "status": "claimed"
    }
  }
}
```

**Success (without device):**
```json
{
  "success": true,
  "message": "Registration successful. You can add a device later.",
  "data": {
    "user": {
      "id": "user-uuid",
      "email": "user@example.com"
    },
    "site": null,
    "device": null
  }
}
```

### 2.5 Error Responses

| Error | Code | Message |
|-------|------|---------|
| Email exists | 400 | "An account with this email already exists" |
| Device not found | 404 | "Device not found. Please ensure your device is powered on and connected." |
| Device already claimed | 409 | "This device is already registered to another user" |
| Invalid serial format | 400 | "Invalid device serial number format" |

---

## 3. Device Claim API (Add Device Later)

### 3.1 Claim Request

**Endpoint:** `POST /api/v1/devices/claim`

```json
{
  "serial_number": "SH-2024-002",
  "site_id": "site-uuid",
  "display_name": "Rooftop Inverter"
}
```

### 3.2 Claim Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `serial_number` | string | Yes | Device serial to claim |
| `site_id` | string | No | Site to attach device to (uses default if not provided) |
| `display_name` | string | No | Custom display name for device |

### 3.3 Claim Flow

```
   Frontend                      System A                      System B
        │                              │                           │
        │ 1. POST /devices/claim       │                           │
        │   {serial_number, site_id}   │                           │
        │─────────────────────────────>│                           │
        │                              │                           │
        │                              │ 2. Verify user auth       │
        │                              │                           │
        │                              │ 3. Check device status    │
        │                              │    GET /devices/serial/   │
        │                              │──────────────────────────>│
        │                              │                           │
        │                              │ 4. Device info            │
        │                              │<──────────────────────────│
        │                              │                           │
        │                              │ 5. Validate:              │
        │                              │    - Device exists ✓      │
        │                              │    - Status = orphan ✓    │
        │                              │    - Site belongs to user │
        │                              │                           │
        │                              │ 6. If no site:            │
        │                              │    Create default site    │
        │                              │                           │
        │                              │ 7. Claim device           │
        │                              │    PUT /devices/{id}/claim│
        │                              │──────────────────────────>│
        │                              │                           │
        │ 8. Success + device details  │                           │
        │<─────────────────────────────│                           │
```

### 3.4 Claim Response

**Success:**
```json
{
  "success": true,
  "message": "Device claimed successfully",
  "data": {
    "device": {
      "id": "device-uuid",
      "serial_number": "SH-2024-002",
      "device_type": "inverter",
      "manufacturer": "Growatt",
      "protocol": "modbus_tcp",
      "display_name": "Rooftop Inverter",
      "status": "online",
      "site_id": "site-uuid"
    }
  }
}
```

---

## 4. Database Schema

### 4.1 System A Database (PostgreSQL)

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    role VARCHAR(20) DEFAULT 'owner',
    status VARCHAR(20) DEFAULT 'pending',
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sites table
CREATE TABLE sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL DEFAULT 'My Home',
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100) DEFAULT 'Pakistan',
    timezone VARCHAR(50) DEFAULT 'Asia/Karachi',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User devices (System A's view - links to System B)
CREATE TABLE user_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    device_serial VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, device_serial)
);

-- Index for fast serial lookup
CREATE INDEX idx_user_devices_serial ON user_devices(device_serial);
```

### 4.2 System B Database (PostgreSQL + TimescaleDB)

```sql
-- Devices table
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    serial_number VARCHAR(50) UNIQUE NOT NULL,
    device_type VARCHAR(20) NOT NULL,  -- inverter, battery, meter
    firmware_version VARCHAR(20),
    manufacturer VARCHAR(100),          -- Solis, Growatt, Huawei, etc.
    protocol VARCHAR(50),               -- modbus_tcp, modbus_rtu, sunspec
    model VARCHAR(100),

    -- Ownership (synced from System A)
    status VARCHAR(20) DEFAULT 'orphan',  -- orphan, claimed
    owner_id UUID,                         -- User ID from System A
    site_id UUID,                          -- Site ID from System A

    -- Connection state
    connection_status VARCHAR(20) DEFAULT 'offline',  -- online, offline
    last_seen_at TIMESTAMP,
    last_telemetry_at TIMESTAMP,

    -- Metadata
    capabilities JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_devices_serial ON devices(serial_number);
CREATE INDEX idx_devices_status ON devices(status);
CREATE INDEX idx_devices_owner ON devices(owner_id) WHERE owner_id IS NOT NULL;
```

---

## 5. API Endpoints Summary

### 5.1 System A Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register user with optional device claim |
| POST | `/api/v1/devices/claim` | Claim orphan device by serial |
| GET | `/api/v1/devices` | List user's claimed devices |
| GET | `/api/v1/devices/{id}` | Get device details |
| DELETE | `/api/v1/devices/{id}` | Release device (unclaim) |
| GET | `/api/v1/sites` | List user's sites |
| POST | `/api/v1/sites` | Create new site |
| PUT | `/api/v1/sites/{id}` | Update site |
| DELETE | `/api/v1/sites/{id}` | Delete site |

### 5.2 System B Endpoints (Internal)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/devices/register` | Device self-registration |
| GET | `/api/v1/devices/serial/{serial}` | Get device by serial |
| PUT | `/api/v1/devices/{id}/claim` | Mark device as claimed |
| PUT | `/api/v1/devices/{id}/release` | Mark device as orphan |
| GET | `/api/v1/devices/{id}/telemetry` | Get device telemetry |

---

## 6. Security Considerations

1. **Device Registration**: Only accepts connections on internal network or via secure tunnel
2. **Serial Number Validation**: Must match expected format `[A-Z]{2}-[0-9]{4}-[0-9]{3}`
3. **Rate Limiting**: Max 5 claim attempts per minute per user
4. **Audit Logging**: All claim/release operations logged with timestamps

---

## 7. Future Enhancements

1. **Device Transfer**: Allow transferring device ownership between users
2. **QR Code Claim**: Scan QR code on device for easier claiming
3. **Installer Mode**: Allow installers to pre-register devices for customers
4. **Fleet Management**: Bulk device operations for commercial users
