#!/bin/bash
# Script to fix .env file permissions for solarhub service

ENV_FILE="/opt/solarhub/app/.env"
LOG_DIR="/opt/solarhub/logs"
APP_DIR="/opt/solarhub/app/solar-hub/system_b"

echo "=== Fixing permissions ==="

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE"
    exit 1
fi

# Fix .env file permissions (readable by solarhub user)
echo "Setting permissions on .env file..."
sudo chown solarhub:solarhub "$ENV_FILE"
sudo chmod 640 "$ENV_FILE"  # Readable by owner and group, not world

# Ensure log directory exists and has correct permissions
echo "Setting permissions on log directory..."
sudo mkdir -p "$LOG_DIR"
sudo chown -R solarhub:solarhub "$LOG_DIR"
sudo chmod 755 "$LOG_DIR"

# Ensure app directory is accessible
echo "Checking app directory permissions..."
sudo chown -R solarhub:solarhub "$APP_DIR" 2>/dev/null || echo "Note: Some files may not be owned by solarhub"

echo ""
echo "=== Verifying permissions ==="
ls -la "$ENV_FILE"
ls -ld "$LOG_DIR"

echo ""
echo "=== Testing if solarhub user can read .env ==="
sudo -u solarhub test -r "$ENV_FILE" && echo "✓ solarhub can read .env" || echo "✗ solarhub CANNOT read .env"

echo ""
echo "=== Restarting service ==="
sudo systemctl restart solarhub-telemetry
sleep 2
sudo systemctl status solarhub-telemetry --no-pager -l
