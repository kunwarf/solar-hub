# Hybrid Device Settings Architecture

**Last Updated:** 2026-01-30
**Status:** ✅ **IMPLEMENTED**
**Version:** 2.0 (Hybrid Mode)

---

## Overview

The device settings system uses a **3-tier hybrid architecture** that combines the speed of localStorage caching, the reliability of database backup, and the accuracy of real-time device queries.

### Architecture Goals

- ✅ **Fast**: Instant load from browser cache
- ✅ **Accurate**: Real-time values from physical devices
- ✅ **Reliable**: Database fallback when devices offline
- ✅ **Resilient**: Graceful degradation, no data loss
- ✅ **User-Friendly**: Clear status indicators, helpful warnings

---

## 3-Tier Priority System

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  1. localStorage (CACHE - Instant)              │
│     ↓ if missing or stale                       │
│  2. Device Commands (PRIMARY - Authoritative)   │
│     ↓ if device offline                         │
│  3. Database (FALLBACK - Backup)                │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Tier 1: localStorage (Cache)
- **Purpose**: Instant page load, offline access
- **Storage**: Browser localStorage (per-origin, 5-10MB)
- **Lifetime**: 7 days TTL, auto-cleanup when quota exceeded
- **Synced**: Updated when device responds
- **Stale Detection**: Marked stale if device query fails

### Tier 2: Device Commands (Primary)
- **Purpose**: Real-time, authoritative settings from hardware
- **Protocol**: HTTP commands via System B → Device (Modbus/MQTT/HTTP)
- **Timeout**: 30 seconds for query, 30 seconds for update
- **Polling**: Background refresh every 30 seconds
- **Response**: Settings JSON from actual device registers

### Tier 3: Database (Fallback)
- **Purpose**: Backup when device offline, multi-user coordination
- **Storage**: PostgreSQL `device_settings` table (JSONB)
- **Updated**: Automatically when device responds
- **Usage**: Fallback when device unreachable
- **Audit**: Tracks created_by, updated_by, timestamps

---

## Data Flow Diagrams

### LOAD Settings Flow

```
User Opens Settings Page
         ↓
┌────────────────────────┐
│  1. Check localStorage │ → Found? → Display Instantly ✓
└────────────────────────┘                ↓
         ↓ Not Found                Background: Query Device
┌────────────────────────┐                ↓
│  2. Check Database     │ → Found? → Display Fallback (stale warning)
└────────────────────────┘                ↓
         ↓ Not Found                Background: Query Device
┌────────────────────────┐                ↓
│  3. Query Device       │ → Success? → Display + Cache + Update DB ✓
└────────────────────────┘
         ↓ Failed
   Show Error + Empty State
```

### SAVE Settings Flow

```
User Clicks "Save"
         ↓
┌─────────────────────────────────────────────┐
│  1. Update localStorage (Optimistic)        │ ← Instant UI update
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│  2. Save to Database (Async, don't wait)    │ ← Backup created
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│  3. Send Command to Device (Wait for ACK)   │
└─────────────────────────────────────────────┘
         ↓                          ↓
    ✓ Success                   ✗ Failed
         ↓                          ↓
Mark localStorage as synced    Rollback localStorage
Update DB with device values   Keep DB backup
Show success toast             Show error + "saved to DB" toast
Navigate away                  Stay on page (user can retry)
```

### Background Polling Flow

```
Settings Page Open & Visible
         ↓
Every 30 seconds:
         ↓
┌────────────────────────┐
│  Query Device          │
└────────────────────────┘
         ↓                          ↓
    ✓ Success                   ✗ Failed
         ↓                          ↓
Compare with localStorage      Mark as stale
         ↓                     Load from DB (fallback)
Different? → Show warning      Show "device offline" alert
Update cache + DB
```

---

## API Endpoints

### Device Commands API (System A)

#### 1. Query Settings from Device
```http
POST /api/v1/devices/{device_id}/commands/query-settings
Content-Type: application/json

{
  "setting_keys": ["max_charge_power_w", "grid_voltage_upper_limit_v"]  // optional
}

Response:
{
  "command_id": "uuid",
  "status": "pending",
  "message": "Settings query command sent to device"
}
```

#### 2. Update Settings on Device
```http
POST /api/v1/devices/{device_id}/commands/update-settings
Content-Type: application/json

{
  "settings": {
    "max_charge_power_w": 5000,
    "grid_voltage_upper_limit_v": 253,
    ...
  },
  "apply_immediately": true
}

Response:
{
  "command_id": "uuid",
  "status": "pending",
  "message": "Settings update command sent to device successfully"
}
```

#### 3. Check Command Status
```http
GET /api/v1/devices/{device_id}/commands/{command_id}/status

Response:
{
  "command_id": "uuid",
  "status": "completed",  // pending, sent, acknowledged, completed, failed, timeout
  "progress": 100,
  "result": {
    "settings": { ... }
  },
  "error": null,
  "created_at": "2026-01-30T12:00:00Z",
  "updated_at": "2026-01-30T12:00:15Z"
}
```

### Device Settings API (System A) - Fallback

#### 1. Get Settings from Database
```http
GET /api/v1/devices/{device_id}/settings

Response:
{
  "id": "uuid",
  "device_id": "uuid",
  "device_type": "inverter",
  "manufacturer": "Growatt",
  "model": "SPF 5000 ES",
  "settings": { ... },
  "is_default": false,
  "updated_at": "2026-01-30T11:45:00Z"
}
```

#### 2. Save Settings to Database
```http
PUT /api/v1/devices/{device_id}/settings
Content-Type: application/json

{
  "settings": { ... }
}

Response:
{
  "id": "uuid",
  "device_id": "uuid",
  "settings": { ... },
  "updated_at": "2026-01-30T12:00:30Z"
}
```

---

## Frontend Implementation

### useDeviceSettings Hook

**Location**: `frontend/src/hooks/useDeviceSettings.ts`

**Usage**:
```tsx
const {
  settings,              // Current settings object
  isLoading,            // Initial load
  isQuerying,           // Querying device in background
  isUpdating,           // Saving to device
  isStale,              // Settings may be outdated
  isDeviceOffline,      // Device unreachable
  usingFallback,        // Using database instead of device
  lastSyncedAt,         // Last successful device sync
  error,                // Last error
  queryDevice,          // Manually query device
  updateDevice,         // Save settings to device
  refresh,              // Refresh from device
} = useDeviceSettings({
  deviceId: "uuid",
  deviceType: "inverter",
  enabled: true,
  pollInterval: 30000,  // 30 seconds
});
```

**Features**:
- ✅ Automatic load priority (localStorage → DB → Device)
- ✅ Background polling every 30s
- ✅ Multi-tab synchronization via BroadcastChannel
- ✅ Page visibility handling (pause when hidden)
- ✅ Optimistic updates with rollback
- ✅ Automatic database backup

### localStorage Manager

**Location**: `frontend/src/lib/device-settings-storage.ts`

**Functions**:
```ts
// Save settings to localStorage
saveDeviceSettings(deviceId, deviceType, settings, isSynced)

// Load settings from localStorage
loadDeviceSettings(deviceId) → DeviceSettingsCache | null

// Mark settings as stale (device query failed)
markSettingsAsStale(deviceId)

// Update with fresh device values
updateSettingsFromDevice(deviceId, deviceType, settings)

// Delete settings
deleteDeviceSettings(deviceId)

// Cleanup old entries (auto-called on quota exceeded)
cleanupOldSettings()

// Export/import for backup
exportAllSettings() → JSON
importSettings(JSON)
```

**Cache Structure**:
```ts
interface DeviceSettingsCache {
  deviceId: string;
  deviceType: string;
  settings: Record<string, any>;
  lastSyncedAt: string;    // ISO timestamp of last device sync
  lastQueriedAt: string;   // ISO timestamp of last query attempt
  version: string;         // Schema version
  isStale: boolean;        // True if device query failed
}
```

### DeviceSettingsHybrid Page

**Location**: `frontend/src/pages/DeviceSettingsHybrid.tsx`

**UI Features**:
- **Status Indicators**:
  - 🟢 "Live" - Synced with device
  - 🔴 "Offline" - Device unreachable
  - ⚪ "Backup" - Using database fallback

- **Alert Banners**:
  - ⚠️ Device Offline (red)
  - ⚠️ Settings Outdated (yellow)
  - ℹ️ Using Database Backup (blue)
  - 🔄 Querying Device (info)

- **Action Buttons**:
  - "Save to Device" / "Save to Database" (adaptive text)
  - "Reset to Defaults"
  - "Refresh from Device"

---

## System B Integration

### Command Execution Flow

```
System A (Device Commands API)
         ↓
System B Client (send_command)
         ↓
System B (/api/v1/commands/ endpoint)
         ↓
Command Queue (priority-based)
         ↓
Device Communication Layer
         ↓
Protocol Adapter (Modbus RTU/TCP, MQTT, HTTP)
         ↓
Physical Device (Inverter/Battery/Meter)
         ↓
Response Parser
         ↓
Command Status Update
         ↓
System A polls for status
```

### Command Types

| Command Type | Direction | Purpose |
|-------------|-----------|---------|
| `query_settings` | Device → System | Read current settings from device |
| `update_settings` | System → Device | Write new settings to device |
| `reset_settings` | System → Device | Reset to factory defaults |
| `validate_settings` | Device → System | Validate settings without applying |

### Command Lifecycle

1. **Created** - Command created in System A
2. **Sent** - Forwarded to System B
3. **Queued** - In System B command queue
4. **Acknowledged** - Device received command
5. **Executing** - Device processing command
6. **Completed** - Success, result available
7. **Failed** - Error, error message available
8. **Timeout** - Exceeded expiration time

---

## Error Handling & Edge Cases

### Device Offline Scenarios

| Scenario | Behavior | User Experience |
|----------|----------|-----------------|
| Device offline on load | Load from DB fallback | Shows "Using Database Backup" alert |
| Device offline on save | Save to DB only | Shows "Saved to database (device offline)" toast |
| Device timeout mid-query | Use cached/DB settings | Shows "Device query timeout" alert |
| Device fails during save | Rollback localStorage | Shows error, settings not changed |

### Multi-User Scenarios

| Scenario | Resolution | User Experience |
|----------|------------|-----------------|
| Two users edit same device | Last-write-wins in DB | Device always has latest |
| User A edits while B views | B sees stale warning on next poll | B can refresh to get latest |
| Concurrent device updates | Command queue serializes | Commands processed in order |

### localStorage Quota Exceeded

| Action | Trigger | Outcome |
|--------|---------|---------|
| Auto-cleanup | Save fails with QuotaExceededError | Delete oldest 25% of entries |
| Retry save | After cleanup | Should succeed |
| Manual export | User action | Download JSON backup |

### Network Failures

| Failure Point | Fallback | Recovery |
|---------------|----------|----------|
| Device query API | Use localStorage/DB | Auto-retry on reconnect |
| Device update API | Save to DB only | Retry manually or wait for sync |
| Database API | Use localStorage only | Show warning, limited functionality |

---

## Performance Characteristics

### Load Times

| Source | Cold Start | Warm Start | Notes |
|--------|-----------|------------|-------|
| localStorage | <10ms | <10ms | Synchronous |
| Database API | 50-200ms | 50-200ms | HTTP round-trip |
| Device Query | 2-30s | 2-30s | Depends on device/protocol |

### Background Polling Impact

- **Network**: ~1-2 KB per poll (JSON payload)
- **CPU**: Minimal (async polling)
- **Battery**: Low (pauses when page hidden)
- **User Perception**: Zero (happens in background)

### Storage Limits

- **localStorage**: 5-10 MB per origin (browser-dependent)
- **Settings per device**: ~1-5 KB (uncompressed)
- **Estimated capacity**: 1,000-5,000 devices
- **Auto-cleanup**: Removes oldest 25% when full

---

## Testing Strategy

### Manual Testing Checklist

- [ ] Load settings with device online
- [ ] Load settings with device offline
- [ ] Save settings with device online
- [ ] Save settings with device offline
- [ ] Background polling updates settings
- [ ] Multi-tab synchronization works
- [ ] Offline mode (disconnect network)
- [ ] Device timeout handling
- [ ] localStorage quota exceeded
- [ ] Database fallback when device fails
- [ ] Status indicators show correct state
- [ ] Alert banners appear appropriately

### E2E Test Scenarios

1. **Happy Path**:
   - Open settings → Shows cached instantly
   - Device query succeeds → Updates with fresh values
   - Modify settings → Save to device succeeds
   - Navigate away → Settings persist

2. **Device Offline Path**:
   - Open settings → Shows database fallback
   - Device query fails → Shows "device offline" alert
   - Modify settings → Saves to database only
   - Device comes online → Auto-syncs on next poll

3. **Network Failure Path**:
   - Load from localStorage
   - Device query times out
   - Database query fails
   - Shows appropriate error messages
   - User can still view cached settings

---

## Migration Guide

### From Database-Only to Hybrid

**No breaking changes** - Existing database settings remain functional.

**Automatic Migration**:
1. First load reads from database
2. Caches to localStorage
3. Queries device in background
4. Future loads use hybrid flow

**User Impact**:
- First load: Same speed (database)
- Subsequent loads: Much faster (localStorage)
- Settings accuracy: Improved (device-backed)

---

## Monitoring & Observability

### Key Metrics to Track

| Metric | Importance | Threshold |
|--------|-----------|-----------|
| Device query success rate | High | >90% |
| Device query latency (p95) | Medium | <10s |
| localStorage hit rate | Low | >80% |
| Database fallback rate | Medium | <10% |
| Multi-tab sync latency | Low | <1s |

### Logging

**Client-Side** (Console):
```
[DeviceSettings] Loaded from localStorage (stale=false)
[DeviceSettings] Querying device for fresh values...
[DeviceSettings] Device query succeeded, updating cache
[DeviceSettings] Database backup updated
```

**Server-Side** (System A):
```
INFO: Device command sent: query_settings for device=uuid
INFO: Command status: completed (15s)
INFO: Database backup updated for device=uuid
```

**System B**:
```
INFO: Command queued: query_settings, priority=7
INFO: Sending to device via Modbus RTU
INFO: Device response received: 1250 bytes
INFO: Command marked as completed
```

---

## Future Enhancements

### Planned Features

1. **Settings Diff Viewer**
   - Show differences between cached/DB/device
   - Highlight conflicts
   - Allow user to choose version

2. **Settings History**
   - Track changes over time
   - Revert to previous configuration
   - Audit trail per setting

3. **Bulk Device Updates**
   - Apply settings to multiple devices
   - Template-based configuration
   - Staged rollout

4. **Offline Edit Queue**
   - Queue setting changes while offline
   - Auto-apply when device comes online
   - Conflict resolution

5. **Real-Time Sync**
   - WebSocket for instant updates
   - Push notifications when device changes settings
   - Live collaboration indicators

---

## References

### Related Documentation
- [System B Command API](../system_b/docs/COMMANDS_API.md)
- [Device Communication Protocols](./DEVICE_PROTOCOLS.md)
- [localStorage Best Practices](./STORAGE_GUIDELINES.md)

### Code Locations
- Backend API: `system_a/app/api/v1/device_commands.py`
- Frontend Hook: `frontend/src/hooks/useDeviceSettings.ts`
- Storage Manager: `frontend/src/lib/device-settings-storage.ts`
- UI Page: `frontend/src/pages/DeviceSettingsHybrid.tsx`

### External Dependencies
- System B Client: `system_a/app/infrastructure/external/system_b_client.py`
- React Query: For API state management
- BroadcastChannel API: For multi-tab sync
- Page Visibility API: For background polling

---

**Document Status**: ✅ Current as of commit `6bf355a`
**Next Review**: After real device testing
