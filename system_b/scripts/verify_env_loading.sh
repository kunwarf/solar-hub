#!/bin/bash
# Verify environment variable loading for the service

echo "=== Checking .env file locations ==="
echo ""
echo "1. Main .env file:"
ls -la /opt/solarhub/app/.env

echo ""
echo "2. Working directory .env (symlink):"
ls -la /opt/solarhub/app/solar-hub/system_b/.env

echo ""
echo "=== Checking environment variables ==="
echo "Testing as solarhub user:"
sudo -u solarhub bash << 'EOF'
cd /opt/solarhub/app/solar-hub/system_b
echo "Working directory: $(pwd)"
echo "TIMESCALE_USER from env: ${TIMESCALE_USER:-NOT SET}"
echo "TIMESCALE_PASSWORD from env: ${TIMESCALE_PASSWORD:+SET}"
echo ""
echo "Testing config loading:"
/opt/solarhub/venv/bin/python << 'PYEOF'
import os
from app.config import get_settings

print("Environment variables:")
print(f"  TIMESCALE_USER: {os.getenv('TIMESCALE_USER', 'NOT SET')}")
print(f"  TIMESCALE_PASSWORD: {os.getenv('TIMESCALE_PASSWORD', 'NOT SET')[:3] + '***' if os.getenv('TIMESCALE_PASSWORD') else 'NOT SET'}")

settings = get_settings()
db = settings.database
print(f"\nLoaded config:")
print(f"  User: {db.user}")
print(f"  Password: {db.password[:3] + '***' if db.password else 'NOT SET'}")
print(f"  Host: {db.host}")
print(f"  Database: {db.name}")
PYEOF
EOF

echo ""
echo "=== Checking systemd environment ==="
sudo systemctl show solarhub-telemetry -p Environment -p EnvironmentFile
