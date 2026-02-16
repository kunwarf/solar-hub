## OTA Firmware Management System

Centralized firmware update management for ESP32 data logger fleet.

## Architecture

```
┌─────────────────┐
│   System B API  │  ← Administrators upload firmware
│                 │  ← Administrators create campaigns
└────────┬────────┘
         │
         │ HTTP API
         │
┌────────▼────────┐
│   PostgreSQL    │  ← Stores firmware files and status
│   Database      │  ← Tracks device update progress
└────────┬────────┘
         │
         │ Periodic checks (every 5 min)
         │
┌────────▼────────┐
│   ESP32 Devices │  ← Check for updates
│   (Data Loggers)│  ← Download & apply updates
└─────────────────┘  ← Report status back
```

## Features

- ✅ **Centralized Management**: Upload firmware once, deploy to all devices
- ✅ **Staged Rollouts**: Deploy to subset of devices first (canary/staged)
- ✅ **Status Tracking**: Real-time monitoring of update progress
- ✅ **Automatic Updates**: Devices auto-check and apply updates
- ✅ **Rollback Support**: Track history, identify problematic versions
- ✅ **File Verification**: SHA256 checksums ensure integrity
- ✅ **Campaign Management**: Organize updates by device groups

## Database Schema

### Tables

1. **firmware_versions**: Version metadata
   - version, description, device_type, is_active

2. **firmware_files**: Actual file content
   - filename, content, checksum, file_type

3. **device_firmware_status**: Per-device status
   - current_version, target_version, update_status, progress

4. **firmware_update_campaigns**: Rollout management
   - name, target_devices, rollout_strategy, status

5. **firmware_update_history**: Audit trail
   - device_serial, from_version, to_version, status

## Quick Start

### 1. Run Database Migration

```bash
cd system_b
alembic upgrade head
```

### 2. Upload Firmware (CLI)

```bash
# Upload new version with files
python -m system_b.scripts.ota_manager upload \\
    --version 1.2.0 \\
    --description "Fixed Modbus timeout issue" \\
    --files esp32_datalogger/main.py,esp32_datalogger/modbus_rtu.py

# Or upload entire directory
python -m system_b.scripts.ota_manager upload \\
    --version 1.2.0 \\
    --files esp32_datalogger/*.py
```

### 3. Deploy Update

```bash
# Deploy to all devices immediately
python -m system_b.scripts.ota_manager deploy \\
    --version 1.2.0 \\
    --name "Fix Modbus Timeout" \\
    --devices all

# Staged rollout (10% of devices first)
python -m system_b.scripts.ota_manager deploy \\
    --version 1.2.0 \\
    --name "Canary Deployment" \\
    --rollout 10

# Deploy to specific devices
python -m system_b.scripts.ota_manager deploy \\
    --version 1.2.0 \\
    --name "Beta Test" \\
    --devices "SH01IN123,SH01IN456,SH01IN789"
```

### 4. Monitor Progress

```bash
# Show campaign status
python -m system_b.scripts.ota_manager status --campaign <campaign-id>

# List all versions
python -m system_b.scripts.ota_manager list versions

# List device statuses
python -m system_b.scripts.ota_manager list devices
```

## API Endpoints

### For Administrators

- `POST /api/v1/firmware/versions` - Create firmware version
- `POST /api/v1/firmware/versions/{id}/files` - Upload file
- `GET /api/v1/firmware/versions` - List versions
- `POST /api/v1/firmware/campaigns` - Create campaign
- `POST /api/v1/firmware/campaigns/{id}/activate` - Start rollout
- `GET /api/v1/firmware/campaigns/{id}/status` - Monitor progress

### For ESP32 Devices

- `POST /api/v1/firmware/check-update` - Check if update available
- `GET /api/v1/firmware/versions/{id}/files` - Download files
- `POST /api/v1/firmware/update-status` - Report progress

## ESP32 Integration

### 1. Add OTA Client to main.py

```python
from ota_client import OTAClient

# Initialize OTA client
ota = OTAClient(config)

# In main loop (every iteration)
if ota.run_background_check():
    # Update applied, device will reboot
    pass
```

### 2. Configure Check Interval

In `config.json`:

```json
{
  "ota": {
    "check_interval": 300  // Check every 5 minutes
  }
}
```

### 3. Upload Required Files

Upload these files to ESP32:
- `ota_client.py` - OTA update client
- Updated `main.py` with OTA integration

## Update Flow

### Step 1: Administrator Uploads Firmware

```
1. Admin creates version "1.2.0"
2. Admin uploads files: main.py, modbus_rtu.py, config.json
3. System calculates SHA256 checksums
4. Files stored in database
```

### Step 2: Administrator Creates Campaign

```
1. Admin creates campaign "Production Rollout"
2. Selects version 1.2.0
3. Chooses target devices (all or specific)
4. Sets rollout strategy (immediate/staged)
5. Activates campaign
```

### Step 3: System Assigns Updates

```
1. System finds target devices
2. Applies rollout percentage (e.g., 10%)
3. Sets device.target_version = 1.2.0
4. Sets device.update_status = "pending"
```

### Step 4: Device Checks for Update

```
1. ESP32 calls /check-update every 5 minutes
2. Receives update_available=true
3. Gets version info and file list URL
```

### Step 5: Device Downloads & Applies

```
1. Device downloads all files
2. Verifies checksums
3. Reports progress: downloading (0-90%)
4. Saves files to flash
5. Reports progress: applying (90-100%)
6. Updates config.json with new version
7. Reports success
8. Reboots
```

### Step 6: Device Reports Success

```
1. After reboot, device checks in
2. Reports current_version = "1.2.0"
3. System marks update as complete
4. Device.update_status = "up_to_date"
```

## Update Statuses

| Status | Description |
|--------|-------------|
| `up_to_date` | Device running latest assigned version |
| `pending` | Update assigned, waiting for device check |
| `downloading` | Device downloading files (0-90%) |
| `applying` | Device saving files and rebooting (90-100%) |
| `success` | Update completed (transitions to up_to_date) |
| `failed` | Update failed, error logged |
| `rollback` | Rolled back to previous version |

## Rollout Strategies

### Immediate (100%)
- Deploy to all target devices at once
- Use for critical bug fixes
- Monitor closely for first hour

### Staged (10-50%)
- Deploy to percentage of fleet
- Monitor for issues
- Gradually increase percentage
- Good for new features

### Canary (1-5%)
- Deploy to very small subset
- Test in production with real data
- Catch issues before wide rollout
- Best practice for major changes

## Best Practices

### 1. Version Naming
```
- Use semantic versioning: MAJOR.MINOR.PATCH
- Example: 1.2.3
  - MAJOR: Breaking changes
  - MINOR: New features
  - PATCH: Bug fixes
```

### 2. Testing Before Deployment
```
1. Test on development device
2. Upload to System B
3. Deploy to 1-2 test devices (canary)
4. Monitor for 1-24 hours
5. Gradually increase rollout
6. Monitor device health (memory, errors)
```

### 3. Rollback Plan
```
- Keep previous version active
- If issues detected:
  1. Pause campaign
  2. Create new campaign with old version
  3. Deploy to affected devices
  4. Investigate and fix issue
```

### 4. Monitoring
```
- Check campaign status every 30 minutes
- Monitor device error rates
- Watch for memory issues
- Track update success rate
- Set up alerts for failed updates
```

## Troubleshooting

### Device Not Receiving Update

**Check:**
1. Device is connected and checking in
   ```bash
   python -m system_b.scripts.ota_manager list devices
   ```

2. Campaign is active
   ```bash
   python -m system_b.scripts.ota_manager status --campaign <id>
   ```

3. Device is in target list
4. Device `last_check_at` is recent (< 10 minutes)

### Update Failing

**Check:**
1. Device error message:
   ```sql
   SELECT device_serial, error_message, update_status
   FROM device_firmware_status
   WHERE update_status = 'failed';
   ```

2. Common issues:
   - Insufficient memory (check device_info.free_memory)
   - Network timeout (increase check_interval)
   - Checksum mismatch (re-upload files)
   - File too large (split into smaller files)

### Slow Rollout

**Check:**
1. Device check interval (default 5 min)
2. Number of devices online
3. Network conditions
4. Rollout percentage setting

## Security Considerations

1. **File Integrity**: SHA256 checksums verify file authenticity
2. **HTTPS**: Use HTTPS in production (update ESP32 to support SSL)
3. **Authentication**: Add API key authentication for devices
4. **Access Control**: Restrict OTA management API to admins only
5. **Audit Trail**: All updates logged in firmware_update_history

## Performance

- **Database**: Files stored as TEXT (consider compression for large deployments)
- **Network**: ~100KB average update size, ~30 seconds download time
- **Concurrency**: Support 100+ devices updating simultaneously
- **Check Interval**: 5 minutes = ~12 checks/hour = low overhead

## Future Enhancements

- [ ] Delta updates (only changed files)
- [ ] Compressed firmware bundles
- [ ] Scheduled rollouts (deploy at specific time)
- [ ] Auto-rollback on failure rate threshold
- [ ] WebSocket notifications for real-time updates
- [ ] Web UI for campaign management
- [ ] A/B testing support
- [ ] Multi-region support

## Example: Complete Deployment

```bash
# 1. Create version and upload files
python -m system_b.scripts.ota_manager upload \\
    --version 2.0.0 \\
    --description "Major update: Added battery optimization" \\
    --files "esp32_datalogger/main.py,esp32_datalogger/modbus_bridge.py,esp32_datalogger/ota_client.py"

# 2. Canary deployment (2 devices)
CAMPAIGN_ID=$(python -m system_b.scripts.ota_manager deploy \\
    --version 2.0.0 \\
    --name "v2.0.0 Canary" \\
    --devices "SH01IN001,SH01IN002" | grep "ID:" | awk '{print $2}')

# 3. Monitor for 1 hour
for i in {1..12}; do
    python -m system_b.scripts.ota_manager status --campaign $CAMPAIGN_ID
    sleep 300  # 5 minutes
done

# 4. If successful, staged rollout (10%)
python -m system_b.scripts.ota_manager deploy \\
    --version 2.0.0 \\
    --name "v2.0.0 Staged 10%" \\
    --devices all \\
    --rollout 10

# 5. Monitor and gradually increase to 50%, then 100%
```

## Support

For issues or questions:
- Check device logs: http://<ESP32_IP>/logs
- Review campaign status: `ota_manager status --campaign <id>`
- Check database: Query `device_firmware_status` table
- Review audit trail: Query `firmware_update_history` table
