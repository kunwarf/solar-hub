#!/usr/bin/env bash
# push_esp32_firmware.sh
# ─────────────────────────────────────────────────────────────────────────────
# Upload the current esp32_datalogger/ files to System B as a new firmware
# version and deploy a canary-first OTA campaign.
#
# Run this ON THE SERVER (faisal-home) from anywhere; it cd's into the repo.
#
# The ESP32s check for updates every ~5 minutes via ota_client.py, then
# download → verify SHA256 → save → machine.reset().  Nothing is pushed at
# the device from the server side — devices pull from System B on their
# existing outbound connection, so this works even for the LAN-fragmented
# .246/.247/.251 that direct-LAN can't reach.
#
# Usage:
#   ./push_esp32_firmware.sh <VERSION>              # canary to default battery
#   ./push_esp32_firmware.sh <VERSION> <SERIAL>     # canary to a specific device
#   ./push_esp32_firmware.sh <VERSION> all          # skip canary, fleet-wide
#
# Examples:
#   ./push_esp32_firmware.sh 1.1.0
#   ./push_esp32_firmware.sh 1.1.0 SH01GWF42L5D4L00
#   ./push_esp32_firmware.sh 1.1.0 all
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO="${SOLARHUB_REPO:-/opt/solarhub/app}"
VENV="${SOLARHUB_VENV:-/opt/solarhub/venv}"

# JK MB280 battery @ 192.168.88.245.  Chosen as default canary because:
# - Batteries have never appeared in the disconnect/desync incident logs
# - Failure of the battery datalogger does NOT interrupt PV generation
# - Serial-bridge mode exercises the same command_client + watchdog code
#   paths as modbus_bridge, so it's a valid canary for both modes
DEFAULT_CANARY="SH01GWAT9Q7YDV90"

VERSION="${1:-}"
TARGET="${2:-$DEFAULT_CANARY}"

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <VERSION> [<DEVICE_SERIAL>|all]" >&2
    echo "" >&2
    echo "Example: $0 1.1.0                        # canary $DEFAULT_CANARY" >&2
    echo "Example: $0 1.1.0 SH01GWF42L5D4L00       # canary Pylontech" >&2
    echo "Example: $0 1.1.0 all                    # fleet-wide (skip canary)" >&2
    exit 1
fi

cd "$REPO"

# ─────────────────────────────────────────────────────────────────────────────
# Files to push.  Only the actually-changed files — the ESP32 OTA client
# overwrites what's in the payload and leaves the rest of the flash alone,
# so partial payloads are safe and much faster.  Keep this list in sync
# with what you changed in esp32_datalogger/.
# ─────────────────────────────────────────────────────────────────────────────
FIRMWARE_FILES=(
    "esp32_datalogger/main.py"
    "esp32_datalogger/modbus_bridge.py"
    "esp32_datalogger/serial_bridge.py"
    "esp32_datalogger/command_client.py"
    "esp32_datalogger/watchdog.py"
)

echo "═══════════════════════════════════════════════════════════════════════"
echo " Push ESP32 firmware v$VERSION"
echo "═══════════════════════════════════════════════════════════════════════"
echo "Repo:    $REPO"
echo "Version: $VERSION"
echo "Target:  $TARGET"
echo ""

# ─── Step 1: verify files exist and show sizes ───────────────────────────────
echo "─── [1/4] Verifying firmware files ─────────────────────────────────────"
for f in "${FIRMWARE_FILES[@]}"; do
    if [ ! -f "$f" ]; then
        echo "✗ MISSING: $f" >&2
        exit 1
    fi
    size=$(wc -c < "$f")
    printf "  ✓ %-45s %6s bytes\n" "$f" "$size"
done
echo ""

# ─── Step 2: upload firmware version ─────────────────────────────────────────
echo "─── [2/4] Uploading v$VERSION to System B ──────────────────────────────"
FILE_CSV=$(IFS=,; echo "${FIRMWARE_FILES[*]}")
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DESC="v$VERSION @ $GIT_SHA — reboot_datalogger command + firmware self-watchdog"

"$VENV/bin/python" -m system_b.scripts.ota_manager upload \
    --version "$VERSION" \
    --description "$DESC" \
    --files "$FILE_CSV"
echo ""

# ─── Step 3: deploy campaign ─────────────────────────────────────────────────
echo "─── [3/4] Creating deploy campaign ──────────────────────────────────────"
if [ "$TARGET" = "all" ]; then
    CAMPAIGN_NAME="v${VERSION}-fleet-$(date +%Y%m%d-%H%M)"
    echo "⚠  Fleet-wide deploy — all devices will pick up on next 5-min poll."
    read -r -p "   Type 'FLEET' to confirm: " confirm
    if [ "$confirm" != "FLEET" ]; then
        echo "Aborted."
        exit 1
    fi
    "$VENV/bin/python" -m system_b.scripts.ota_manager deploy \
        --version "$VERSION" \
        --name "$CAMPAIGN_NAME" \
        --devices all
else
    CAMPAIGN_NAME="v${VERSION}-canary-${TARGET}-$(date +%Y%m%d-%H%M)"
    "$VENV/bin/python" -m system_b.scripts.ota_manager deploy \
        --version "$VERSION" \
        --name "$CAMPAIGN_NAME" \
        --devices "$TARGET"
fi
echo ""

# ─── Step 4: what to do next ─────────────────────────────────────────────────
echo "─── [4/4] Next steps ────────────────────────────────────────────────────"
echo ""
echo "▶ Watch the device pick up the update (up to 5 min):"
echo ""
echo "    $VENV/bin/python -m system_b.scripts.ota_manager list devices"
echo ""
echo "  Expected status transitions on the target device:"
echo "    pending → downloading → applying → success  (then it reboots)"
echo ""
echo "▶ Confirm the device came back and the new loops started:"
echo ""
echo "    # Server side — device reconnects on port 8502"
echo "    grep 'Connection.*established' /opt/solarhub/logs/polling-manager.log \\"
echo "        /opt/solarhub/logs/polling-manager.log.1 2>/dev/null | tail -5"
echo ""
echo "    # Device side — new v$VERSION log lines"
echo "    # (replace .245 with the target device's LAN IP)"
echo "    curl -s http://192.168.88.245/api/status | jq '.log_buffer[-30:]'"
echo ""
echo "  Look for these lines in the device log_buffer:"
echo "    '[Main] Datalogger command poll loop started'"
echo "    '[Main] Firmware watchdog started'"
echo "    '[Watchdog] enabled=True threshold=600s cooldown=1800s'"
echo ""
if [ "$TARGET" != "all" ]; then
    echo "▶ If canary is healthy after ~15 min, roll to fleet:"
    echo ""
    echo "    $0 $VERSION all"
    echo ""
fi
echo "▶ If anything goes wrong, the device will still be reachable via its"
echo "  own web UI at http://192.168.88.<ip>/ — you can push files manually"
echo "  via /api/files/upload or trigger a reboot via /reboot."
echo ""
