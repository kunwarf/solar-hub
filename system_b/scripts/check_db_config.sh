#!/bin/bash
# Script to check and test database configuration

echo "=== Checking Database Configuration ==="
echo ""

# Check if .env file exists and has database settings
if [ -f /opt/solarhub/app/.env ]; then
    echo "Database settings in .env:"
    grep -E "^TIMESCALE_|^DATABASE_" /opt/solarhub/app/.env | sed 's/password=.*/password=***/'
else
    echo "ERROR: .env file not found at /opt/solarhub/app/.env"
fi

echo ""
echo "=== Testing Database Connection ==="
echo "Attempting to connect to TimescaleDB..."

# Try to connect using psql
cd /opt/solarhub/app/solar-hub/system_b
sudo -u solarhub /opt/solarhub/venv/bin/python << 'EOF'
import asyncio
import sys
from app.config import get_settings

async def test_db():
    try:
        settings = get_settings()
        db_settings = settings.database
        
        print(f"Host: {db_settings.host}")
        print(f"Port: {db_settings.port}")
        print(f"Database: {db_settings.name}")
        print(f"User: {db_settings.user}")
        print(f"Password: {'***' if db_settings.password else 'NOT SET'}")
        print()
        
        # Try to import and test connection
        from app.infrastructure.database.timescale_connection import TimescaleDBManager
        
        print("Testing connection...")
        async with TimescaleDBManager.get_session() as session:
            result = await session.execute("SELECT 1")
            print("✓ Database connection successful!")
            return True
            
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_db())
    sys.exit(0 if result else 1)
EOF

echo ""
echo "=== Checking PostgreSQL Service ==="
sudo systemctl status postgresql --no-pager | head -10
