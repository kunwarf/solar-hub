"""
Debug test for dashboard preferences persistence issue.
"""
import asyncio
import sys
import pytest
from uuid import UUID
from sqlalchemy import select, text
from httpx import AsyncClient

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Test user credentials
TEST_USER_EMAIL = "test@solarhub.com"
TEST_USER_PASSWORD = "Test123!@#"
TEST_USER_ID = "4fc31ddb-dde2-4536-89cd-2dd0492e0fb8"

# Database connection
DATABASE_URL = "postgresql+asyncpg://postgres:faisal@localhost:5433/solar_hub"


async def get_auth_token():
    """Get JWT token for test user."""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["tokens"]["access_token"]


async def test_dashboard_preferences_persistence():
    """Test that dashboard preferences are actually saved to database."""
    print("\n" + "="*80)
    print("DASHBOARD PREFERENCES PERSISTENCE TEST")
    print("="*80)

    # Step 1: Get auth token
    print("\n[1] Getting auth token...")
    token = await get_auth_token()
    print(f"✓ Got token: {token[:20]}...")

    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Clear existing preferences from database
    print("\n[2] Clearing existing preferences from database...")
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM user_dashboard_preferences WHERE user_id = :user_id"),
            {"user_id": TEST_USER_ID}
        )
        print(f"✓ Deleted {result.rowcount} existing preference records")
    await engine.dispose()

    # Step 3: Verify database is empty
    print("\n[3] Verifying database is empty...")
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM user_dashboard_preferences WHERE user_id = :user_id"),
            {"user_id": TEST_USER_ID}
        )
        count = result.scalar()
        print(f"✓ Database has {count} records (should be 0)")
        assert count == 0, "Database should be empty after delete"
    await engine.dispose()

    # Step 4: Create new preferences via API
    print("\n[4] Creating new preferences via API PUT...")
    async with AsyncClient(base_url="http://localhost:8000") as client:
        preferences_data = {
            "layout_preset": "standard",
            "grid_layout": "2x2",
            "widget_layout": [
                {
                    "id": "power_flow",
                    "visible": True,
                    "size": "large",
                    "settings": {}
                },
                {
                    "id": "energy_today",
                    "visible": True,
                    "size": "medium",
                    "settings": {}
                },
                {
                    "id": "battery_status",
                    "visible": False,
                    "size": "small",
                    "settings": {}
                }
            ]
        }

        print(f"   Sending PUT request with {len(preferences_data['widget_layout'])} widgets...")
        response = await client.put(
            "/api/v1/users/me/dashboard/preferences",
            headers=headers,
            json=preferences_data
        )

        print(f"   Response status: {response.status_code}")
        print(f"   Response body: {response.text[:500]}")

        assert response.status_code == 200, f"PUT failed: {response.text}"
        response_data = response.json()
        print(f"✓ API returned {len(response_data['widget_layout'])} widgets")

    # Step 5: Check if data was saved to database
    print("\n[5] Checking if data was saved to database...")
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    user_id,
                    layout_preset,
                    grid_layout,
                    widget_layout,
                    created_at,
                    updated_at
                FROM user_dashboard_preferences
                WHERE user_id = :user_id
            """),
            {"user_id": TEST_USER_ID}
        )
        row = result.fetchone()

        if row is None:
            print("❌ CRITICAL: No data found in database!")
            print("   The API returned 200 OK but nothing was saved!")
            assert False, "Data was not saved to database despite 200 OK response"
        else:
            print(f"✓ Data found in database!")
            print(f"   user_id: {row[0]}")
            print(f"   layout_preset: {row[1]}")
            print(f"   grid_layout: {row[2]}")
            print(f"   widget_layout: {len(row[3])} widgets")
            print(f"   created_at: {row[4]}")
            print(f"   updated_at: {row[5]}")

            # Verify the data matches what we sent
            assert row[1] == "standard", f"layout_preset mismatch: {row[1]}"
            assert row[2] == "2x2", f"grid_layout mismatch: {row[2]}"
            assert len(row[3]) == 3, f"widget_layout count mismatch: {len(row[3])}"

            print("\n✓ ALL DATA MATCHES!")
    await engine.dispose()

    # Step 6: Test GET endpoint to verify it returns saved data
    print("\n[6] Testing GET endpoint to verify it returns saved data...")
    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get(
            "/api/v1/users/me/dashboard/preferences",
            headers=headers
        )

        assert response.status_code == 200, f"GET failed: {response.text}"
        get_data = response.json()
        print(f"✓ GET returned {len(get_data['widget_layout'])} widgets")
        print(f"   layout_preset: {get_data['layout_preset']}")
        print(f"   grid_layout: {get_data['grid_layout']}")

        assert get_data['layout_preset'] == "standard"
        assert get_data['grid_layout'] == "2x2"
        assert len(get_data['widget_layout']) == 3

    # Step 7: Test UPDATE (not create) - modify existing preferences
    print("\n[7] Testing UPDATE of existing preferences...")
    async with AsyncClient(base_url="http://localhost:8000") as client:
        update_data = {
            "layout_preset": "compact",
            "grid_layout": "list",
            "widget_layout": [
                {
                    "id": "power_flow",
                    "visible": False,  # Changed from True
                    "size": "small",   # Changed from large
                    "settings": {}
                }
            ]
        }

        print(f"   Sending PUT request to UPDATE existing preferences...")
        response = await client.put(
            "/api/v1/users/me/dashboard/preferences",
            headers=headers,
            json=update_data
        )

        assert response.status_code == 200, f"UPDATE failed: {response.text}"
        print(f"✓ UPDATE API call successful")

    # Step 8: Verify UPDATE was saved
    print("\n[8] Verifying UPDATE was saved to database...")
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    layout_preset,
                    grid_layout,
                    widget_layout
                FROM user_dashboard_preferences
                WHERE user_id = :user_id
            """),
            {"user_id": TEST_USER_ID}
        )
        row = result.fetchone()

        if row is None:
            print("❌ CRITICAL: Data was deleted during update!")
            assert False, "Data disappeared during update"
        else:
            print(f"✓ Data still exists after update")
            print(f"   layout_preset: {row[0]} (should be 'compact')")
            print(f"   grid_layout: {row[1]} (should be 'list')")
            print(f"   widget_layout: {len(row[2])} widgets (should be 1)")

            assert row[0] == "compact", f"layout_preset not updated: {row[0]}"
            assert row[1] == "list", f"grid_layout not updated: {row[1]}"
            assert len(row[2]) == 1, f"widget_layout not updated: {len(row[2])}"

            print("\n✓ UPDATE VERIFIED - ALL DATA CORRECT!")
    await engine.dispose()

    print("\n" + "="*80)
    print("✓ ALL TESTS PASSED - PREFERENCES ARE BEING SAVED CORRECTLY!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_dashboard_preferences_persistence())
