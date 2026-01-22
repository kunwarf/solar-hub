#!/bin/bash
# Test database connection with correct method

cd /opt/solarhub/app/solar-hub/system_b
sudo -u solarhub /opt/solarhub/venv/bin/python << 'EOF'
import asyncio
from app.config import get_settings
from app.infrastructure.database.timescale_connection import get_db_session
from sqlalchemy import text

async def test():
    try:
        settings = get_settings()
        db = settings.database
        print(f"Connecting as: {db.user} to {db.name}@{db.host}:{db.port}")
        print(f"Connection URL: postgresql+asyncpg://{db.user}:***@{db.host}:{db.port}/{db.name}")
        print("")
        
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1"))
            print("✓ Connection successful!")
            print(f"Result: {result.scalar()}")
            return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

result = asyncio.run(test())
exit(0 if result else 1)
EOF
