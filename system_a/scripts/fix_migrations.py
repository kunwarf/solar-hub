#!/usr/bin/env python3
"""
Script to fix migration state when tables are missing.

This script checks which tables exist and resets the alembic_version
table to match the actual database state.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.infrastructure.database.connection import get_db_session
from app.config import get_settings


async def check_tables():
    """Check which tables exist in the database."""
    settings = get_settings()
    
    try:
        async with get_db_session() as session:
            # Check if alembic_version table exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                );
            """))
            alembic_exists = result.scalar()
            
            if alembic_exists:
                # Get current version
                result = await session.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar()
                print(f"Current Alembic version: {current_version}")
            else:
                print("Alembic version table does not exist")
            
            # Check for key tables
            tables_to_check = [
                'users', 'organizations', 'sites', 'devices',
                'telemetry_hourly_summary', 'billing_simulations'
            ]
            
            print("\nTable existence check:")
            for table in tables_to_check:
                result = await session.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                    );
                """))
                exists = result.scalar()
                status = "✓" if exists else "✗"
                print(f"  {status} {table}")
            
            # If sites table doesn't exist, we need to reset
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'sites'
                );
            """))
            sites_exists = result.scalar()
            
            if not sites_exists and alembic_exists:
                print("\n⚠️  WARNING: sites table missing but Alembic version exists!")
                print("   This means migrations are out of sync.")
                print("\n   Resetting Alembic version...")
                
                # Drop alembic_version table to reset
                await session.execute(text("DROP TABLE IF EXISTS alembic_version"))
                await session.commit()
                print("   ✓ Dropped alembic_version table")
                print("\n   Now run: alembic upgrade head")
                return False
            
            return True
            
    except Exception as e:
        print(f"Error checking tables: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(check_tables())
    sys.exit(0 if result else 1)
