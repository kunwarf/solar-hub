#!/bin/bash
# Debug what the service sees when it starts

echo "=== Testing config loading as service user ==="
sudo -u solarhub bash << 'EOF'
cd /opt/solarhub/app/solar-hub/system_b
export PATH=/opt/solarhub/venv/bin:/usr/local/bin:/usr/bin:/bin

# Load environment from .env file (simulating systemd EnvironmentFile)
if [ -f /opt/solarhub/app/.env ]; then
    set -a
    source /opt/solarhub/app/.env
    set +a
fi

echo "Environment variables:"
echo "  TIMESCALE_USER: ${TIMESCALE_USER:-NOT SET}"
echo "  TIMESCALE_PASSWORD: ${TIMESCALE_PASSWORD:+SET (hidden)}"

/opt/solarhub/venv/bin/python << 'PYEOF'
import os
import sys
print("\nPython environment check:")
print(f"  TIMESCALE_USER env: {os.getenv('TIMESCALE_USER', 'NOT SET')}")
print(f"  TIMESCALE_PASSWORD env: {'SET' if os.getenv('TIMESCALE_PASSWORD') else 'NOT SET'}")

# Change to working directory
import os
os.chdir('/opt/solarhub/app/solar-hub/system_b')
sys.path.insert(0, '/opt/solarhub/app/solar-hub/system_b')

print(f"\nWorking directory: {os.getcwd()}")
print(f".env file exists: {os.path.exists('.env')}")
print(f".env file readable: {os.access('.env', os.R_OK)}")

from app.config import get_settings
settings = get_settings()
db = settings.database

print(f"\nLoaded database config:")
print(f"  User: {db.user}")
print(f"  Password: {db.password[:3] + '***' if db.password else 'NOT SET'}")
print(f"  Host: {db.host}")
print(f"  Database: {db.name}")
print(f"  URL: postgresql+asyncpg://{db.user}:***@{db.host}:{db.port}/{db.name}")
PYEOF
EOF
