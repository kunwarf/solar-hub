# OTA Firmware Management System - Design Document

**Project**: Solar Hub
**Feature**: Centralized OTA (Over-The-Air) Firmware Updates
**Date**: 2026-02-16
**Author**: System B Development Team
**Version**: 1.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals and Non-Goals](#goals-and-non-goals)
4. [System Architecture](#system-architecture)
5. [Database Design](#database-design)
6. [API Design](#api-design)
7. [Component Design](#component-design)
8. [Data Flow](#data-flow)
9. [Security Design](#security-design)
10. [Scalability Considerations](#scalability-considerations)
11. [Deployment Strategy](#deployment-strategy)
12. [Monitoring and Observability](#monitoring-and-observability)
13. [Future Enhancements](#future-enhancements)
14. [Appendix](#appendix)

---

## Executive Summary

The OTA Firmware Management System provides centralized control for deploying firmware updates to a fleet of ESP32-based data logger devices. The system enables:

- **Remote Updates**: No physical access required
- **Staged Rollouts**: Deploy to subsets first, then expand
- **Real-time Monitoring**: Track update progress across fleet
- **Safe Deployments**: Checksum verification, rollback capability
- **Audit Compliance**: Complete history of all updates

### Key Metrics
- **Target Fleet Size**: 100-1000 devices (initially)
- **Update Frequency**: 1-2 times per month
- **Update Size**: 50-200 KB typical
- **Update Duration**: 30-60 seconds per device
- **Success Rate Target**: >99%

---

## Problem Statement

### Current State
- Firmware updates require physical USB access to each ESP32 device
- No visibility into what firmware version each device is running
- Deploying updates to fleet of 100+ devices takes days/weeks
- No rollback mechanism if update causes issues
- No audit trail of update history

### Challenges
1. **Scale**: Managing updates for growing fleet
2. **Reliability**: Ensure updates don't brick devices
3. **Visibility**: Track update status in real-time
4. **Safety**: Minimize risk of fleet-wide issues
5. **Compliance**: Maintain audit trail

---

## Goals and Non-Goals

### Goals
✅ **Centralized Management**: Single interface to manage all firmware
✅ **Automatic Updates**: Devices self-update without manual intervention
✅ **Staged Rollouts**: Deploy to percentage of fleet (canary/staged)
✅ **Status Tracking**: Real-time visibility into update progress
✅ **File Integrity**: Verify files with checksums
✅ **Audit Trail**: Complete history for compliance
✅ **Simple Integration**: Minimal changes to ESP32 code
✅ **HTTP-based**: Simple, reliable, MicroPython-compatible

### Non-Goals
❌ **Binary Patching**: Full file replacement only (no delta updates)
❌ **Real-time Push**: Devices poll periodically (5-min intervals)
❌ **HTTPS Support**: Phase 2 enhancement
❌ **Multi-stage Bootloader**: Single-stage update only
❌ **Over-the-Air Recovery**: Manual recovery if update fails

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        System B (Backend)                        │
│                                                                   │
│  ┌────────────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │  FastAPI App   │    │  PostgreSQL  │    │  CLI Manager   │  │
│  │  - REST API    │◄──►│  - Firmware  │◄──►│  - Upload      │  │
│  │  - Validation  │    │  - Status    │    │  - Deploy      │  │
│  │  - Business    │    │  - History   │    │  - Monitor     │  │
│  │    Logic       │    │              │    │                │  │
│  └────────┬───────┘    └──────────────┘    └────────────────┘  │
│           │                                                      │
└───────────┼──────────────────────────────────────────────────────┘
            │
            │ HTTP REST API
            │ (Port 8001)
            │
┌───────────▼──────────────────────────────────────────────────────┐
│                       Internet / Network                          │
└───────────┬──────────────────────────────────────────────────────┘
            │
            │ Periodic HTTP Requests
            │ (Every 5 minutes)
            │
┌───────────▼──────────────────────────────────────────────────────┐
│                    ESP32 Data Logger Fleet                        │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   ESP32 #1  │  │   ESP32 #2  │  │   ESP32 #N  │             │
│  │             │  │             │  │             │             │
│  │  OTA Client │  │  OTA Client │  │  OTA Client │   ...       │
│  │  - Check    │  │  - Check    │  │  - Check    │             │
│  │  - Download │  │  - Download │  │  - Download │             │
│  │  - Apply    │  │  - Apply    │  │  - Apply    │             │
│  │  - Report   │  │  - Report   │  │  - Report   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         System B API                             │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    API Endpoints                          │   │
│  │  /firmware/versions          - Version CRUD               │   │
│  │  /firmware/versions/{id}/files - File upload/download     │   │
│  │  /firmware/check-update      - Device update check        │   │
│  │  /firmware/update-status     - Status reporting           │   │
│  │  /firmware/campaigns         - Campaign management        │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │                Business Logic Layer                       │   │
│  │  - Version Management                                     │   │
│  │  - File Storage & Retrieval                               │   │
│  │  - Campaign Orchestration                                 │   │
│  │  - Device Status Tracking                                 │   │
│  │  - Checksum Calculation                                   │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │                  Data Access Layer                        │   │
│  │  - SQLAlchemy ORM                                         │   │
│  │  - Async PostgreSQL                                       │   │
│  │  - Transaction Management                                 │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
└──────────────────────┼───────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────┐
│                      PostgreSQL Database                          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  firmware_   │  │  firmware_   │  │  device_firmware_    │  │
│  │  versions    │  │  files       │  │  status              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │  firmware_   │  │  firmware_   │                             │
│  │  update_     │  │  update_     │                             │
│  │  campaigns   │  │  history     │                             │
│  └──────────────┘  └──────────────┘                             │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│                         ESP32 Device                              │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     Main Application                      │   │
│  │  - Modbus Bridge                                          │   │
│  │  - Device Registration                                    │   │
│  │  - Telemetry Collection                                   │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │                    OTA Client                             │   │
│  │  - Periodic Check Timer (5 min)                           │   │
│  │  - HTTP Client (check-update)                             │   │
│  │  - File Downloader                                        │   │
│  │  - Checksum Verifier (SHA256)                             │   │
│  │  - File Writer                                            │   │
│  │  - Progress Reporter                                      │   │
│  │  - Reboot Handler                                         │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │                  File Manager                             │   │
│  │  - File CRUD Operations                                   │   │
│  │  - Disk Space Management                                  │   │
│  │  - Protected File List                                    │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │                MicroPython Filesystem                     │   │
│  │  - main.py, modbus_rtu.py, config.json, etc.             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## Database Design

### Schema Overview

```
firmware_versions (1) ─────< (M) firmware_files
        │
        │ (1)
        │
        ▼ (M)
firmware_update_campaigns
        │
        │ (1)
        │
        ▼ (M)
firmware_update_history

device_firmware_status ───< (1) firmware_versions (target)
```

### Table: firmware_versions

**Purpose**: Store metadata for each firmware version

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique version ID |
| version | VARCHAR(50) | UNIQUE, NOT NULL | Version string (e.g., "1.2.0") |
| description | TEXT | NULL | Human-readable description |
| device_type | VARCHAR(50) | NOT NULL, DEFAULT 'datalogger' | Device type filter |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Is version available? |
| created_at | TIMESTAMP | NOT NULL | Creation timestamp |
| created_by | VARCHAR(100) | NULL | Creator username/ID |
| metadata | JSONB | NULL | Additional metadata |

**Indexes**:
- `ix_firmware_versions_version` on (version)
- `ix_firmware_versions_device_type` on (device_type)

**Design Rationale**:
- UUID primary key for global uniqueness
- Version string for human readability
- `is_active` allows deprecating versions without deletion
- JSONB metadata for extensibility (future: min_memory_required, etc.)

---

### Table: firmware_files

**Purpose**: Store actual file content for each version

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique file ID |
| firmware_version_id | UUID | FK, NOT NULL | Parent version |
| filename | VARCHAR(255) | NOT NULL | File name (e.g., "main.py") |
| content | TEXT | NOT NULL | File content (text or base64) |
| file_size | INTEGER | NOT NULL | Size in bytes |
| checksum | VARCHAR(64) | NOT NULL | SHA256 hash |
| file_type | VARCHAR(20) | NOT NULL, DEFAULT 'python' | python/config/binary |
| is_required | BOOLEAN | NOT NULL, DEFAULT true | Must this file be applied? |
| created_at | TIMESTAMP | NOT NULL | Upload timestamp |

**Indexes**:
- `ix_firmware_files_version_id` on (firmware_version_id)
- `ix_firmware_files_filename` on (filename)

**Design Rationale**:
- TEXT storage for simplicity (consider bytea for binaries in future)
- SHA256 checksum for integrity verification
- `is_required` allows optional files (e.g., documentation)
- `file_type` enables special handling (binary vs text)

**Scalability Considerations**:
- Average file: 10-50 KB
- Typical version: 5-10 files = 50-500 KB total
- 100 versions stored = 5-50 MB
- PostgreSQL handles this easily; consider object storage for larger scale

---

### Table: device_firmware_status

**Purpose**: Track current and target firmware for each device

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique status ID |
| device_serial | VARCHAR(50) | UNIQUE, NOT NULL | Device serial number |
| current_version | VARCHAR(50) | NULL | Currently running version |
| target_version_id | UUID | FK, NULL | Target version (if update pending) |
| update_status | VARCHAR(20) | NOT NULL, DEFAULT 'up_to_date' | Current update status |
| update_progress | INTEGER | NOT NULL, DEFAULT 0 | Progress 0-100 |
| last_check_at | TIMESTAMP | NULL | Last check-in time |
| update_started_at | TIMESTAMP | NULL | Update start time |
| update_completed_at | TIMESTAMP | NULL | Update completion time |
| error_message | TEXT | NULL | Error details if failed |
| metadata | JSONB | NULL | Device info (memory, uptime) |
| updated_at | TIMESTAMP | NOT NULL | Last update timestamp |

**Indexes**:
- `ix_device_firmware_status_device_serial` on (device_serial) UNIQUE
- `ix_device_firmware_status_update_status` on (update_status)

**Update Status Values**:
- `up_to_date`: Device on latest assigned version
- `pending`: Update assigned, waiting for check-in
- `downloading`: Downloading files (0-90%)
- `applying`: Applying update (90-100%)
- `success`: Update completed (transitions to up_to_date)
- `failed`: Update failed

**Design Rationale**:
- One row per device (unique constraint)
- `target_version_id` NULL when no update pending
- Progress tracking enables UI progress bars
- `last_check_at` identifies offline/stale devices
- JSONB metadata for device health monitoring

---

### Table: firmware_update_campaigns

**Purpose**: Manage rollout campaigns for organized deployments

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique campaign ID |
| name | VARCHAR(100) | NOT NULL | Campaign name |
| firmware_version_id | UUID | FK, NOT NULL | Version to deploy |
| target_devices | ARRAY(VARCHAR) | NULL | Specific device serials |
| target_filter | JSONB | NULL | Filter criteria |
| rollout_strategy | VARCHAR(20) | NOT NULL, DEFAULT 'immediate' | Rollout strategy |
| rollout_percentage | INTEGER | NOT NULL, DEFAULT 100 | Percentage (1-100) |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'draft' | Campaign status |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| started_at | TIMESTAMP | NULL | Activation time |
| completed_at | TIMESTAMP | NULL | Completion time |
| created_by | VARCHAR(100) | NULL | Creator ID |
| metadata | JSONB | NULL | Additional data |

**Indexes**:
- `ix_firmware_update_campaigns_status` on (status)

**Rollout Strategies**:
- `immediate`: All devices at once (100%)
- `staged`: Gradual percentage-based rollout
- `canary`: Small subset first (1-5%)
- `scheduled`: Deploy at specific time (future)

**Campaign Status Values**:
- `draft`: Created but not activated
- `active`: Currently rolling out
- `paused`: Temporarily stopped
- `completed`: All devices updated
- `cancelled`: Manually cancelled

**Design Rationale**:
- Separate campaigns from versions (one version, many campaigns)
- `target_devices` for explicit list
- `target_filter` for dynamic selection (e.g., {"current_version": "1.0.0"})
- Rollout percentage enables staged deployments
- Status tracking enables pause/resume

---

### Table: firmware_update_history

**Purpose**: Complete audit trail of all updates

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique history ID |
| device_serial | VARCHAR(50) | NOT NULL | Device serial |
| from_version | VARCHAR(50) | NULL | Previous version |
| to_version | VARCHAR(50) | NOT NULL | New version |
| campaign_id | UUID | FK, NULL | Associated campaign |
| status | VARCHAR(20) | NOT NULL | Final status |
| started_at | TIMESTAMP | NOT NULL | Update start |
| completed_at | TIMESTAMP | NULL | Update completion |
| error_message | TEXT | NULL | Error if failed |
| metadata | JSONB | NULL | Additional context |

**Indexes**:
- `ix_firmware_update_history_device_serial` on (device_serial)
- `ix_firmware_update_history_started_at` on (started_at)

**Design Rationale**:
- Immutable audit log (insert-only)
- Links to campaign for traceability
- Includes both success and failure records
- Enables compliance reporting
- Enables rollback decisions

---

## API Design

### REST API Endpoints

#### 1. Create Firmware Version

```http
POST /api/v1/firmware/versions
Content-Type: application/json

{
  "version": "1.2.0",
  "description": "Fixed Modbus timeout bug",
  "device_type": "datalogger",
  "created_by": "admin@solarhub.com"
}
```

**Response**: 200 OK
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "version": "1.2.0",
  "created_at": "2026-02-16T10:30:00Z"
}
```

**Error Cases**:
- 400: Version already exists
- 500: Database error

---

#### 2. Upload Firmware File

```http
POST /api/v1/firmware/versions/{version_id}/files
Content-Type: application/json

{
  "filename": "main.py",
  "content": "import time\nprint('Hello')...",
  "file_type": "python",
  "is_required": true
}
```

**Response**: 200 OK
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "filename": "main.py",
  "size": 15234,
  "checksum": "a1b2c3d4e5f6..."
}
```

**Design Decisions**:
- Content sent as plain text (not multipart/form-data) for simplicity
- Checksum calculated server-side for consistency
- Base64 encoding for binary files (future)

---

#### 3. Device Check for Update

```http
POST /api/v1/firmware/check-update
Content-Type: application/json

{
  "device_serial": "SH01INWWAJJSCKX0",
  "current_version": "1.1.0",
  "device_info": {
    "free_memory": 45000,
    "uptime": 86400
  }
}
```

**Response (Update Available)**: 200 OK
```json
{
  "update_available": true,
  "target_version": "1.2.0",
  "version_id": "550e8400-e29b-41d4-a716-446655440000",
  "description": "Fixed Modbus timeout bug",
  "files_url": "/api/v1/firmware/versions/550e8400.../files"
}
```

**Response (No Update)**: 200 OK
```json
{
  "update_available": false
}
```

**Side Effects**:
- Updates `device_firmware_status.last_check_at`
- Creates status record if device is new
- Stores device_info in metadata

**Design Decisions**:
- Device pulls (not pushed) for simplicity
- Check frequency controlled by device (5 min default)
- Server-side logic determines if update needed

---

#### 4. Download Firmware Files

```http
GET /api/v1/firmware/versions/{version_id}/files
```

**Response**: 200 OK
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "filename": "main.py",
    "size": 15234,
    "checksum": "a1b2c3d4e5f6...",
    "file_type": "python",
    "is_required": true,
    "content": "import time\n..."
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440002",
    "filename": "modbus_rtu.py",
    "size": 8123,
    "checksum": "b2c3d4e5f6a7...",
    "file_type": "python",
    "is_required": true,
    "content": "class ModbusRTU:\n..."
  }
]
```

**Design Decisions**:
- Return all files in single response (typical: 5-10 files)
- Include content directly (no separate file download endpoint)
- Trade-off: Larger response size for fewer HTTP requests
- Alternative: Paginated or file-by-file download for large files

---

#### 5. Report Update Status

```http
POST /api/v1/firmware/update-status
Content-Type: application/json

{
  "device_serial": "SH01INWWAJJSCKX0",
  "update_status": "downloading",
  "progress": 45,
  "error_message": null
}
```

**Response**: 200 OK
```json
{
  "success": true
}
```

**State Transitions**:
```
pending → downloading → applying → success → up_to_date
                                 ↘ failed
```

**Side Effects**:
- Updates `device_firmware_status` record
- On success: Creates history record, clears target_version
- On failure: Logs error message

---

#### 6. Create Campaign

```http
POST /api/v1/firmware/campaigns
Content-Type: application/json

{
  "name": "Production Rollout v1.2.0",
  "firmware_version_id": "550e8400-e29b-41d4-a716-446655440000",
  "target_devices": null,
  "target_filter": {"current_version": "1.1.0"},
  "rollout_strategy": "staged",
  "rollout_percentage": 10,
  "created_by": "admin@solarhub.com"
}
```

**Response**: 200 OK
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "name": "Production Rollout v1.2.0",
  "status": "draft",
  "created_at": "2026-02-16T11:00:00Z"
}
```

---

#### 7. Activate Campaign

```http
POST /api/v1/firmware/campaigns/{campaign_id}/activate
```

**Response**: 200 OK
```json
{
  "success": true,
  "target_device_count": 15,
  "target_devices": ["SH01IN001", "SH01IN002", ...]
}
```

**Logic**:
1. Find target devices (by list or filter)
2. Apply rollout percentage
3. For each device: Set target_version, status=pending
4. Update campaign: status=active, started_at=now

---

### API Design Principles

1. **RESTful**: Resource-based URLs, standard HTTP methods
2. **JSON Only**: Simple, universal format
3. **Idempotent**: Safe to retry (check-update, report-status)
4. **Async Database**: Non-blocking for scalability
5. **Error Handling**: Consistent error response format
6. **Versioned**: `/api/v1/` for future compatibility

---

## Component Design

### ESP32 OTA Client

```python
class OTAClient:
    """
    Responsibilities:
    - Periodic update checking (every 5 minutes)
    - File downloading with progress tracking
    - Checksum verification (SHA256)
    - File saving via FileManager
    - Status reporting to System B
    - Config update and reboot
    """

    def __init__(self, config):
        self.check_interval = 300  # 5 minutes
        self.updating = False  # Prevent concurrent updates
        self.last_check = 0

    def should_check(self) -> bool:
        """Time-based check trigger"""
        return (time.time() - self.last_check) >= self.check_interval

    def check_for_update(self) -> dict:
        """
        POST /check-update with device info
        Returns: Update info dict or None
        """

    def apply_update(self, update_info) -> bool:
        """
        Main update workflow:
        1. Report downloading (0%)
        2. Download all files
        3. Verify checksums
        4. Report progress per file
        5. Save files
        6. Report applying (95%)
        7. Update config
        8. Report success (100%)
        9. Reboot
        """

    def _report_status(self, status, progress, error=None):
        """POST /update-status with progress"""

    def run_background_check(self) -> bool:
        """
        Called from main loop:
        if ota.run_background_check():
            # Device will reboot, this returns true
        """
```

**Design Decisions**:
- **Pull-based**: Device polls instead of server push (simpler, NAT-friendly)
- **Single-threaded**: No concurrent updates (ESP32 resource constraints)
- **Blocking update**: Pause main application during update (safety)
- **Immediate reboot**: Apply changes immediately after success

**Error Handling**:
- Network errors: Retry on next check interval
- Checksum mismatch: Fail immediately, report error
- Insufficient memory: Fail immediately, report error
- File save error: Fail immediately, report error

---

### CLI Manager Tool

```python
# Responsibilities:
# - Upload firmware from local files
# - Create and activate campaigns
# - Monitor campaign progress
# - List versions and device statuses

# Commands:
ota_manager upload --version X --files A,B,C
ota_manager deploy --version X --name Y --devices all
ota_manager status --campaign ID
ota_manager list versions|devices
```

**Design Decisions**:
- **Async CLI**: Uses asyncio for database operations
- **Interactive**: Color-coded output, progress indicators
- **File batching**: Upload multiple files in one command
- **Safe defaults**: Confirm before destructive operations

---

## Data Flow

### Update Deployment Flow

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│  Admin  │                    │System B │                    │  ESP32  │
└────┬────┘                    └────┬────┘                    └────┬────┘
     │                              │                              │
     │ 1. Upload Firmware           │                              │
     │─────────────────────────────>│                              │
     │                              │                              │
     │ 2. Create Campaign           │                              │
     │─────────────────────────────>│                              │
     │                              │                              │
     │ 3. Activate Campaign         │                              │
     │─────────────────────────────>│                              │
     │                              │                              │
     │                              │ 4. Mark devices: pending     │
     │                              │      target_version = X      │
     │                              │                              │
     │                              │                              │
     │                              │    5. Check for update       │
     │                              │<─────────────────────────────│
     │                              │                              │
     │                              │ 6. Update available: true    │
     │                              │      version = X, files_url  │
     │                              │─────────────────────────────>│
     │                              │                              │
     │                              │   7. Download files          │
     │                              │<─────────────────────────────│
     │                              │                              │
     │                              │ 8. Files + checksums         │
     │                              │─────────────────────────────>│
     │                              │                              │
     │                              │   9. Report: downloading 10% │
     │                              │<─────────────────────────────│
     │                              │                              │
     │                              │  10. Report: downloading 50% │
     │                              │<─────────────────────────────│
     │                              │                              │
     │                              │  11. Report: applying 95%    │
     │                              │<─────────────────────────────│
     │                              │                              │
     │                              │  12. Report: success 100%    │
     │                              │<─────────────────────────────│
     │                              │                              │
     │                              │ 13. Update status: up_to_date│
     │                              │     current_version = X      │
     │                              │     Create history record    │
     │                              │                              │
     │ 14. Monitor progress         │                              │
     │─────────────────────────────>│                              │
     │                              │                              │
     │ 15. Campaign status          │                              │
     │<─────────────────────────────│                              │
     │     {success: 1, pending: 0} │                              │
     │                              │                              │
     │                              │                          [Reboot]
     │                              │                              │
     │                              │  16. Check-in with new       │
     │                              │      current_version = X     │
     │                              │<─────────────────────────────│
     │                              │                              │
```

### Staged Rollout Flow

```
Day 1: Canary (2 devices)
  ├─ Admin: Create campaign, rollout=2 devices
  ├─ System: Assign to 2 devices
  ├─ Devices: Update automatically
  └─ Admin: Monitor for 24 hours

Day 2: Staged 10% (15 devices)
  ├─ Admin: Create campaign, rollout=10%
  ├─ System: Calculate 10% of 150 = 15 devices
  ├─ System: Randomly select 15 devices
  ├─ Devices: Update automatically
  └─ Admin: Monitor for 12 hours

Day 3: Staged 50% (75 devices)
  ├─ Admin: Create campaign, rollout=50%
  ├─ System: Select remaining 75 devices
  ├─ Devices: Update automatically
  └─ Admin: Monitor for 6 hours

Day 4: Full rollout (58 devices remaining)
  ├─ Admin: Create campaign, rollout=100%
  ├─ System: Assign to all remaining devices
  ├─ Devices: Update automatically
  └─ Admin: Monitor until complete

Result: Zero-downtime rollout with early issue detection
```

---

## Security Design

### Threat Model

| Threat | Mitigation | Priority |
|--------|-----------|----------|
| **File Tampering** | SHA256 checksums | HIGH |
| **Malicious Firmware** | Admin authentication, audit trail | HIGH |
| **Man-in-the-Middle** | HTTPS (Phase 2) | MEDIUM |
| **Replay Attacks** | Version checks | LOW |
| **DoS (Too many updates)** | Rate limiting (Phase 2) | LOW |
| **Unauthorized Access** | API authentication (Phase 2) | MEDIUM |

### Current Security Measures

1. **File Integrity**:
   - SHA256 checksum calculated on upload
   - ESP32 verifies checksum before applying
   - Prevents corrupted/tampered files

2. **Audit Trail**:
   - All uploads logged with creator ID
   - Complete update history
   - Campaign tracking

3. **Protected Files**:
   - boot.py, webrepl_cfg.py cannot be deleted
   - Prevents bricking device

### Phase 2 Security Enhancements

1. **HTTPS/TLS**:
   - Encrypt communication
   - Requires SSL support in ESP32 (memory constraints)

2. **Device Authentication**:
   - API keys per device
   - JWT tokens for API access

3. **Code Signing**:
   - Digital signatures on firmware
   - Public/private key verification

4. **Rate Limiting**:
   - Prevent DoS attacks
   - Limit check-update frequency

---

## Scalability Considerations

### Current Capacity

| Metric | Current | Target | Scalability Plan |
|--------|---------|--------|------------------|
| **Devices** | 100 | 1000 | Horizontal scaling, connection pooling |
| **Update Size** | 100 KB | 500 KB | Consider compression, delta updates |
| **Concurrent Updates** | 20 | 200 | Async workers, queue-based processing |
| **Database Size** | 50 MB | 5 GB | Partitioning, archival of old versions |
| **API Throughput** | 100 req/s | 1000 req/s | Load balancer, caching |

### Bottlenecks and Solutions

1. **Database Storage**:
   - **Issue**: Firmware files in TEXT columns
   - **Solution**: Move to object storage (S3, MinIO) for files >1MB
   - **Trigger**: When DB size > 1 GB

2. **Concurrent Device Checks**:
   - **Issue**: 1000 devices checking every 5 min = 3-4 req/s
   - **Solution**: Stagger check intervals, add jitter
   - **Implementation**: check_interval = 300 + random(0, 60)

3. **File Download Bandwidth**:
   - **Issue**: 100 devices × 100 KB = 10 MB burst
   - **Solution**: Content delivery network (CDN), staged rollouts
   - **Implementation**: rollout_percentage = 10% initially

4. **Database Connections**:
   - **Issue**: Connection pool exhaustion
   - **Solution**: Async connection pooling (asyncpg)
   - **Configuration**: pool_size=20, max_overflow=10

### Horizontal Scaling

```
                        ┌──────────────┐
                        │ Load Balancer│
                        └───────┬──────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
         ┌─────▼────┐     ┌─────▼────┐     ┌─────▼────┐
         │ API Node │     │ API Node │     │ API Node │
         │    #1    │     │    #2    │     │    #3    │
         └─────┬────┘     └─────┬────┘     └─────┬────┘
               │                │                │
               └────────────────┼────────────────┘
                                │
                        ┌───────▼──────┐
                        │  PostgreSQL  │
                        │   (Primary)  │
                        └───────┬──────┘
                                │
                        ┌───────▼──────┐
                        │  PostgreSQL  │
                        │  (Read Rep)  │
                        └──────────────┘
```

**Implementation**:
- API nodes: Stateless FastAPI containers
- Database: Primary for writes, replicas for reads
- Session affinity: Not required (stateless)

---

## Deployment Strategy

### Phase 1: Initial Rollout (Week 1)

```bash
# Step 1: Deploy database schema
cd system_b
alembic upgrade head

# Step 2: Register API endpoints
# (Already included in main.py)

# Step 3: Upload OTA-enabled firmware
python -m system_b.scripts.ota_manager upload \
    --version 1.0.0-ota \
    --files esp32_datalogger/*.py

# Step 4: Test with 2 devices
python -m system_b.scripts.ota_manager deploy \
    --version 1.0.0-ota \
    --name "OTA Test" \
    --devices "DEV001,DEV002"

# Step 5: Monitor for 48 hours
# Step 6: Deploy to 10% of fleet
# Step 7: Deploy to remaining fleet
```

### Phase 2: Production Deployment (Week 2-3)

```bash
# All devices now have OTA capability
# Future updates via OTA only (no USB required)

# Example: Bug fix deployment
python -m system_b.scripts.ota_manager upload \
    --version 1.1.0 \
    --description "Fixed Modbus timeout" \
    --files esp32_datalogger/modbus_rtu.py

python -m system_b.scripts.ota_manager deploy \
    --version 1.1.0 \
    --name "Modbus Fix" \
    --rollout 100
```

### Rollback Procedure

```bash
# If version 1.1.0 causes issues:

# Step 1: Create rollback campaign
python -m system_b.scripts.ota_manager deploy \
    --version 1.0.0 \
    --name "Rollback to 1.0.0" \
    --target-filter '{"current_version": "1.1.0"}'

# Step 2: Monitor rollback
python -m system_b.scripts.ota_manager status --campaign <id>

# Step 3: Deactivate problematic version
UPDATE firmware_versions
SET is_active = false
WHERE version = '1.1.0';
```

---

## Monitoring and Observability

### Key Metrics

1. **Update Success Rate**:
   ```sql
   SELECT
     COUNT(*) FILTER (WHERE status = 'success') * 100.0 / COUNT(*) as success_rate
   FROM firmware_update_history
   WHERE started_at >= NOW() - INTERVAL '24 hours';
   ```

2. **Device Health**:
   ```sql
   SELECT
     COUNT(*) FILTER (WHERE last_check_at >= NOW() - INTERVAL '10 minutes') as online,
     COUNT(*) FILTER (WHERE last_check_at < NOW() - INTERVAL '10 minutes') as offline
   FROM device_firmware_status;
   ```

3. **Update Duration**:
   ```sql
   SELECT
     AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
   FROM firmware_update_history
   WHERE status = 'success';
   ```

4. **Version Distribution**:
   ```sql
   SELECT
     current_version,
     COUNT(*) as device_count
   FROM device_firmware_status
   GROUP BY current_version
   ORDER BY device_count DESC;
   ```

### Alerts

1. **High Failure Rate**:
   - Threshold: >5% failures in campaign
   - Action: Pause campaign, investigate

2. **Stale Devices**:
   - Threshold: No check-in for >1 hour
   - Action: Alert operations team

3. **Slow Updates**:
   - Threshold: Update duration >5 minutes
   - Action: Check network, device memory

### Dashboard (Future)

```
┌─────────────────────────────────────────────────────┐
│              OTA Management Dashboard                │
├─────────────────────────────────────────────────────┤
│  Fleet Status                                        │
│  ● Online: 145/150 (97%)                             │
│  ● Current Versions: 1.2.0 (140), 1.1.0 (10)        │
│                                                      │
│  Active Campaigns                                    │
│  Campaign: "v1.2.0 Rollout"                          │
│  ├─ Status: Active                                   │
│  ├─ Progress: 140/150 (93%)                          │
│  └─ Success Rate: 99.3%                              │
│                                                      │
│  Recent Failures                                     │
│  ├─ SH01IN045: Checksum mismatch                     │
│  └─ SH01IN078: Insufficient memory                   │
│                                                      │
│  Update History (24h)                                │
│  ├─ Successful: 142                                  │
│  ├─ Failed: 1                                        │
│  └─ Avg Duration: 38s                                │
└─────────────────────────────────────────────────────┘
```

---

## Future Enhancements

### Phase 2 (Next 3 months)

1. **Delta Updates**:
   - Only send changed files
   - Reduce bandwidth and update time
   - Requires version diff calculation

2. **Compressed Firmware**:
   - Gzip compression for text files
   - Reduce download size by ~70%
   - Decompress on ESP32 (memory overhead)

3. **HTTPS Support**:
   - Encrypt communication
   - Requires ESP32 SSL (memory constraints)
   - Consider TLS termination at load balancer

4. **Web Dashboard**:
   - Real-time monitoring UI
   - Campaign creation wizard
   - Device health visualization

### Phase 3 (6-12 months)

1. **Scheduled Rollouts**:
   - Deploy at specific date/time
   - Maintenance window support
   - Timezone-aware scheduling

2. **Auto-Rollback**:
   - Detect high failure rate
   - Automatically revert to previous version
   - Requires health checks

3. **A/B Testing**:
   - Deploy two versions simultaneously
   - Compare metrics (uptime, errors)
   - Automatic winner selection

4. **Multi-Region Support**:
   - Regional firmware servers
   - Reduce latency for global deployments
   - CDN integration

5. **Binary Patching**:
   - bsdiff/courgette for binary deltas
   - Further reduce update size
   - Complex implementation

---

## Appendix

### A. Technology Choices

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Database | PostgreSQL | JSONB, arrays, UUID support; ACID guarantees |
| API Framework | FastAPI | Async, auto-docs, type safety, high performance |
| ORM | SQLAlchemy | Mature, async support, migration tools |
| ESP32 Language | MicroPython | Simple, interpreted, rapid development |
| File Format | JSON | Universal, human-readable, MicroPython native |
| Checksum | SHA256 | Strong security, standard library support |

### B. Design Alternatives Considered

1. **Push vs Pull**:
   - **Chosen**: Pull (device polls every 5 min)
   - **Alternative**: Server push via WebSocket/MQTT
   - **Rationale**: Pull is simpler, NAT-friendly, lower complexity

2. **File Storage**:
   - **Chosen**: PostgreSQL TEXT columns
   - **Alternative**: Object storage (S3, MinIO)
   - **Rationale**: Simplicity for <100KB files; will migrate if files grow

3. **Update Mechanism**:
   - **Chosen**: Full file replacement
   - **Alternative**: Binary patching (bsdiff)
   - **Rationale**: Simpler implementation; optimize later if needed

4. **Authentication**:
   - **Chosen**: Phase 2 feature
   - **Alternative**: Immediate implementation
   - **Rationale**: Internal network, accelerate MVP; add security layer later

### C. Performance Benchmarks

**Target Performance** (single API node):
- Requests/second: 100
- P95 latency: <200ms
- Database connections: 20
- Concurrent updates: 50

**Measured Performance** (estimated):
- `/check-update`: ~50ms (DB query + JSON response)
- `/versions/{id}/files`: ~200ms (5 files, ~100KB total)
- `Upload file`: ~100ms (DB insert)

### D. Database Sizing

**Storage Estimates**:
```
Firmware Versions:
- 100 versions × 1 KB = 100 KB

Firmware Files:
- 100 versions × 10 files × 10 KB = 10 MB

Device Status:
- 1000 devices × 2 KB = 2 MB

Update History:
- 1000 devices × 10 updates × 1 KB = 10 MB

Total: ~25 MB (very manageable)
```

### E. Error Codes

| Code | Message | Action |
|------|---------|--------|
| OTA-001 | Checksum mismatch | Re-download file |
| OTA-002 | Insufficient memory | Free space, retry |
| OTA-003 | Network timeout | Retry on next check |
| OTA-004 | File save failed | Check filesystem |
| OTA-005 | Invalid version | Contact support |

### F. Testing Strategy

1. **Unit Tests**:
   - API endpoints (FastAPI TestClient)
   - OTA client functions (mock HTTP)
   - File manager operations

2. **Integration Tests**:
   - End-to-end update flow
   - Database transactions
   - Error scenarios

3. **Load Tests**:
   - 100 concurrent device checks
   - 50 concurrent file downloads
   - Database connection pool

4. **Device Tests**:
   - ESP32 update on real hardware
   - Network failure handling
   - Checksum verification
   - Rollback scenarios

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-16 | System B Team | Initial design document |

---

**End of Design Document**
