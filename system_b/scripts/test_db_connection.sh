#!/bin/bash
# Test database connection with the correct credentials

echo "=== Testing Database Connection ==="
echo ""

# Get credentials from .env
TIMESCALE_HOST=$(grep "^TIMESCALE_HOST=" /opt/solarhub/app/.env | cut -d'=' -f2)
TIMESCALE_PORT=$(grep "^TIMESCALE_PORT=" /opt/solarhub/app/.env | cut -d'=' -f2)
TIMESCALE_NAME=$(grep "^TIMESCALE_NAME=" /opt/solarhub/app/.env | cut -d'=' -f2)
TIMESCALE_USER=$(grep "^TIMESCALE_USER=" /opt/solarhub/app/.env | cut -d'=' -f2)
TIMESCALE_PASSWORD=$(grep "^TIMESCALE_PASSWORD=" /opt/solarhub/app/.env | cut -d'=' -f2)

echo "Host: $TIMESCALE_HOST"
echo "Port: $TIMESCALE_PORT"
echo "Database: $TIMESCALE_NAME"
echo "User: $TIMESCALE_USER"
echo "Password: ${TIMESCALE_PASSWORD:0:3}***"
echo ""

# Test connection with psql
echo "Testing connection with psql..."
PGPASSWORD="$TIMESCALE_PASSWORD" psql -h "$TIMESCALE_HOST" -p "$TIMESCALE_PORT" -U "$TIMESCALE_USER" -d "$TIMESCALE_NAME" -c "SELECT 1;" 2>&1

if [ $? -eq 0 ]; then
    echo "✓ psql connection successful!"
else
    echo "✗ psql connection failed"
    echo ""
    echo "=== Checking if user exists ==="
    sudo -u postgres psql -c "\du" | grep "$TIMESCALE_USER"
    
    if [ $? -ne 0 ]; then
        echo "User $TIMESCALE_USER does not exist!"
        echo ""
        echo "To create the user, run:"
        echo "sudo -u postgres psql -c \"CREATE USER $TIMESCALE_USER WITH PASSWORD '$TIMESCALE_PASSWORD';\""
        echo "sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE $TIMESCALE_NAME TO $TIMESCALE_USER;\""
    fi
fi

echo ""
echo "=== Testing from Python ==="
cd /opt/solarhub/app/solar-hub/system_b
sudo -u solarhub /opt/solarhub/venv/bin/python << EOF
import asyncio
import sys
from app.config import get_settings
from app.infrastructure.database.timescale_connection import TimescaleDBManager

async def test():
    try:
        settings = get_settings()
        db = settings.database
        print(f"Config - Host: {db.host}, User: {db.user}, DB: {db.name}")
        print("Attempting connection...")
        
        async with TimescaleDBManager.get_session() as session:
            result = await session.execute("SELECT 1")
            print("✓ Python connection successful!")
            return True
    except Exception as e:
        print(f"✗ Python connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

result = asyncio.run(test())
sys.exit(0 if result else 1)
EOF
