#!/bin/bash
# Script to set up .env file for System B service

ENV_SOURCE="/opt/solarhub/app/.env"
WORK_DIR="/opt/solarhub/app/solar-hub/system_b"
ENV_TARGET="$WORK_DIR/.env"

echo "=== Setting up .env file ==="

# Check if source .env exists
if [ ! -f "$ENV_SOURCE" ]; then
    echo "ERROR: Source .env file not found at $ENV_SOURCE"
    exit 1
fi

# Option 1: Create symlink (recommended - single source of truth)
echo "Creating symlink from $ENV_TARGET to $ENV_SOURCE..."
sudo ln -sf "$ENV_SOURCE" "$ENV_TARGET"

# Option 2: Copy file (uncomment if you prefer a copy)
# echo "Copying .env file..."
# sudo cp "$ENV_SOURCE" "$ENV_TARGET"

# Set permissions
echo "Setting permissions..."
sudo chown solarhub:solarhub "$ENV_TARGET"
sudo chmod 640 "$ENV_TARGET"

# Verify
echo ""
echo "=== Verifying ==="
ls -la "$ENV_TARGET"
sudo -u solarhub test -r "$ENV_TARGET" && echo "✓ solarhub can read .env" || echo "✗ solarhub CANNOT read .env"

echo ""
echo "=== Testing import ==="
cd "$WORK_DIR"
sudo -u solarhub /opt/solarhub/venv/bin/python -c "from app.main import app; print('✓ Import successful')" 2>&1 | tail -5

echo ""
echo "=== Restarting service ==="
sudo systemctl restart solarhub-telemetry
sleep 3
sudo systemctl status solarhub-telemetry --no-pager -l | head -15
