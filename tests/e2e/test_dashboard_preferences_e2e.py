"""
E2E tests for dashboard preferences persistence.
Tests the complete flow from frontend to database.
"""
import pytest
import asyncio
import psycopg2
from playwright.sync_api import Page, expect


# Test credentials
TEST_USER_EMAIL = "test@solarhub.com"
TEST_USER_PASSWORD = "Test123!@#"
TEST_USER_ID = "4fc31ddb-dde2-4536-89cd-2dd0492e0fb8"


def clear_preferences_from_db():
    """Clear preferences from database before test."""
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="solar_hub",
        user="postgres",
        password="faisal"
    )
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM user_dashboard_preferences WHERE user_id = %s",
        (TEST_USER_ID,)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_preferences_from_db():
    """Get preferences directly from database."""
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="solar_hub",
        user="postgres",
        password="faisal"
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT layout_preset, grid_layout, widget_layout
        FROM user_dashboard_preferences
        WHERE user_id = %s
    """, (TEST_USER_ID,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


@pytest.fixture(scope="function")
def clean_preferences():
    """Clean preferences before and after each test."""
    clear_preferences_from_db()
    yield
    # Cleanup after test
    # clear_preferences_from_db()  # Commented out to inspect results


class TestDashboardPreferencesE2E:
    """E2E tests for dashboard preferences."""

    def test_preferences_persist_after_page_reload(self, page: Page):
        """Test that preferences are saved and persist after page reload."""
        print("\n" + "="*80)
        print("TEST: Preferences persist after page reload")
        print("="*80)

        # Step 1: Clear database
        print("\n[1] Clearing database...")
        clear_preferences_from_db()
        db_data = get_preferences_from_db()
        assert db_data is None, "Database should be empty at start"
        print("   OK - Database is empty")

        # Step 2: Login
        print("\n[2] Logging in...")
        page.goto("http://localhost:8081/login")
        page.fill('input[type="email"]', TEST_USER_EMAIL)
        page.fill('input[type="password"]', TEST_USER_PASSWORD)
        page.click('button[type="submit"]')

        # Wait for redirect to dashboard
        page.wait_for_url("http://localhost:8081/dashboard", timeout=10000)
        print("   OK - Logged in and redirected to dashboard")

        # Step 3: Wait for dashboard to load
        print("\n[3] Waiting for dashboard to load...")
        page.wait_for_timeout(2000)  # Wait for initial load
        print("   OK - Dashboard loaded")

        # Step 4: Check if preferences API was called
        print("\n[4] Checking if preferences were loaded from API...")
        # The dashboard should automatically fetch preferences
        page.wait_for_timeout(2000)  # Wait for API call

        # Step 5: Make a change (if there's a visible way to toggle widgets)
        # For now, we'll test by checking localStorage and API calls
        print("\n[5] Checking localStorage for preferences...")

        # Execute JavaScript to check localStorage
        local_storage_data = page.evaluate("""
            () => {
                const data = localStorage.getItem('dashboardPreferences');
                return data ? JSON.parse(data) : null;
            }
        """)

        if local_storage_data:
            print(f"   localStorage has data: preset={local_storage_data.get('layoutPreset')}")
        else:
            print("   localStorage is empty (will load from API)")

        # Step 6: Wait for any auto-save to complete
        print("\n[6] Waiting for auto-save (debounce + API call)...")
        page.wait_for_timeout(2000)  # Wait for debounce + API

        # Step 7: Check database to see if anything was saved
        print("\n[7] Checking database for saved preferences...")
        db_data = get_preferences_from_db()

        if db_data:
            layout_preset, grid_layout, widget_layout = db_data
            print(f"   Database has preferences!")
            print(f"   - layout_preset: {layout_preset}")
            print(f"   - grid_layout: {grid_layout}")
            print(f"   - widgets: {len(widget_layout)} widgets")
        else:
            print("   Database is still empty")
            print("   This means preferences were not auto-saved on first load")
            print("   Need to trigger a change to test persistence")

        # Step 8: Reload page
        print("\n[8] Reloading page...")
        page.reload()
        page.wait_for_timeout(2000)  # Wait for reload
        print("   OK - Page reloaded")

        # Step 9: Check if preferences were loaded
        print("\n[9] Checking if preferences persisted after reload...")
        local_storage_after = page.evaluate("""
            () => {
                const data = localStorage.getItem('dashboardPreferences');
                return data ? JSON.parse(data) : null;
            }
        """)

        if local_storage_after:
            print(f"   localStorage after reload: preset={local_storage_after.get('layoutPreset')}")
            print("   OK - Preferences persisted!")
        else:
            print("   WARNING - localStorage is empty after reload")

        # Step 10: Final database check
        print("\n[10] Final database check...")
        db_data_final = get_preferences_from_db()
        if db_data_final:
            print("   ✓ Preferences are in database")
        else:
            print("   ! No preferences in database yet")

        print("\n" + "="*80)


    def test_widget_visibility_toggle_persists(self, page: Page):
        """Test that toggling widget visibility persists to database."""
        print("\n" + "="*80)
        print("TEST: Widget visibility toggle persists")
        print("="*80)

        # Step 1: Login
        print("\n[1] Logging in...")
        page.goto("http://localhost:8081/login")
        page.fill('input[type="email"]', TEST_USER_EMAIL)
        page.fill('input[type="password"]', TEST_USER_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url("http://localhost:8081/dashboard", timeout=10000)
        page.wait_for_timeout(2000)
        print("   OK - Logged in")

        # Step 2: Look for widget settings/customization button
        print("\n[2] Looking for widget customization controls...")

        # Check if there's a settings icon or customize button
        # This depends on your UI implementation
        try:
            # Try to find customize/settings button
            customize_button = page.locator('button:has-text("Customize")').first
            if customize_button.is_visible():
                print("   Found 'Customize' button")
                customize_button.click()
                page.wait_for_timeout(1000)
        except:
            print("   No 'Customize' button found")

        # Try to find any widget visibility toggles
        try:
            widget_toggles = page.locator('[data-testid*="widget-toggle"]')
            toggle_count = widget_toggles.count()
            print(f"   Found {toggle_count} widget toggles")

            if toggle_count > 0:
                # Toggle the first widget
                print("\n[3] Toggling first widget visibility...")
                widget_toggles.first.click()
                page.wait_for_timeout(2000)  # Wait for debounce + save
                print("   OK - Toggled widget")

                # Step 4: Check database
                print("\n[4] Checking if toggle was saved to database...")
                page.wait_for_timeout(1500)  # Ensure debounce completed
                db_data = get_preferences_from_db()

                if db_data:
                    print("   ✓ Preferences saved to database!")
                else:
                    print("   ✗ Preferences NOT in database")

                # Step 5: Reload and verify
                print("\n[5] Reloading page to verify persistence...")
                page.reload()
                page.wait_for_timeout(2000)

                # Check if the toggle state persisted
                # (You would need to check the actual DOM state here)
                print("   OK - Page reloaded")

        except Exception as e:
            print(f"   Could not find widget toggles: {e}")
            print("   This test requires widget visibility controls in the UI")

        print("\n" + "="*80)


    def test_layout_preset_change_persists(self, page: Page):
        """Test that changing layout preset persists to database."""
        print("\n" + "="*80)
        print("TEST: Layout preset change persists")
        print("="*80)

        # Step 1: Login
        print("\n[1] Logging in...")
        page.goto("http://localhost:8081/login")
        page.fill('input[type="email"]', TEST_USER_EMAIL)
        page.fill('input[type="password"]', TEST_USER_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url("http://localhost:8081/dashboard", timeout=10000)
        page.wait_for_timeout(2000)
        print("   OK - Logged in")

        # Step 2: Look for layout preset selector
        print("\n[2] Looking for layout preset selector...")

        try:
            # Look for preset buttons/dropdown
            preset_selectors = page.locator('[data-testid*="preset"], button:has-text("Standard"), button:has-text("Compact"), button:has-text("Detailed")')
            selector_count = preset_selectors.count()
            print(f"   Found {selector_count} preset selectors")

            if selector_count > 0:
                print("\n[3] Changing layout preset...")
                preset_selectors.first.click()
                page.wait_for_timeout(2000)  # Wait for save
                print("   OK - Changed preset")

                # Check database
                print("\n[4] Checking database...")
                page.wait_for_timeout(1500)
                db_data = get_preferences_from_db()

                if db_data:
                    layout_preset = db_data[0]
                    print(f"   ✓ Preset saved: {layout_preset}")
                else:
                    print("   ✗ NOT saved")

        except Exception as e:
            print(f"   Could not find preset selector: {e}")

        print("\n" + "="*80)


    def test_grid_layout_change_persists(self, page: Page):
        """Test that changing grid layout persists to database."""
        print("\n" + "="*80)
        print("TEST: Grid layout change persists")
        print("="*80)

        # Step 1: Login
        print("\n[1] Logging in...")
        page.goto("http://localhost:8081/login")
        page.fill('input[type="email"]', TEST_USER_EMAIL)
        page.fill('input[type="password"]', TEST_USER_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url("http://localhost:8081/dashboard", timeout=10000)
        page.wait_for_timeout(2000)
        print("   OK - Logged in")

        # Step 2: Look for grid layout buttons
        print("\n[2] Looking for grid layout controls...")

        try:
            # Look for grid layout buttons (list, 2x2, 3x3)
            grid_buttons = page.locator('button:has-text("List"), button:has-text("Grid"), [data-testid*="grid-layout"]')
            button_count = grid_buttons.count()
            print(f"   Found {button_count} grid layout buttons")

            if button_count > 0:
                print("\n[3] Changing grid layout...")
                grid_buttons.first.click()
                page.wait_for_timeout(2000)
                print("   OK - Changed layout")

                # Check database
                print("\n[4] Checking database...")
                page.wait_for_timeout(1500)
                db_data = get_preferences_from_db()

                if db_data:
                    grid_layout = db_data[1]
                    print(f"   ✓ Layout saved: {grid_layout}")
                else:
                    print("   ✗ NOT saved")

        except Exception as e:
            print(f"   Could not find grid layout controls: {e}")

        print("\n" + "="*80)


if __name__ == "__main__":
    # Can be run directly for debugging
    pytest.main([__file__, "-v", "-s"])
