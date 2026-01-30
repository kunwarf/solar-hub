"""
Test the exact scenario that the frontend is experiencing.
"""
import sys
import requests
import json

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Login
print("1. Logging in...")
login_response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "test@solarhub.com", "password": "Test123!@#"}
)
print(f"   Login status: {login_response.status_code}")

token = login_response.json()["tokens"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Simulate frontend saving preferences (like when user moves a widget)
print("\n2. Simulating frontend saving preferences (14 widgets like in the logs)...")
preferences = {
    "layout_preset": "standard",
    "grid_layout": "2x2",
    "widget_layout": [
        {"id": "power_flow", "visible": True, "size": "large", "settings": {}},
        {"id": "energy_today", "visible": True, "size": "medium", "settings": {}},
        {"id": "energy_week", "visible": True, "size": "medium", "settings": {}},
        {"id": "energy_month", "visible": True, "size": "medium", "settings": {}},
        {"id": "battery_status", "visible": True, "size": "medium", "settings": {}},
        {"id": "grid_status", "visible": True, "size": "small", "settings": {}},
        {"id": "solar_production", "visible": True, "size": "medium", "settings": {}},
        {"id": "consumption", "visible": True, "size": "medium", "settings": {}},
        {"id": "self_sufficiency", "visible": True, "size": "small", "settings": {}},
        {"id": "carbon_offset", "visible": True, "size": "small", "settings": {}},
        {"id": "cost_savings", "visible": True, "size": "medium", "settings": {}},
        {"id": "weather", "visible": True, "size": "small", "settings": {}},
        {"id": "alerts", "visible": True, "size": "medium", "settings": {}},
        {"id": "system_health", "visible": True, "size": "small", "settings": {}}
    ]
}

put_response = requests.put(
    "http://localhost:8000/api/v1/users/me/dashboard/preferences",
    headers=headers,
    json=preferences
)

print(f"   PUT status: {put_response.status_code}")
if put_response.status_code == 200:
    print(f"   ✓ API returned 200 OK")
    resp_data = put_response.json()
    print(f"   Response widget count: {len(resp_data['widget_layout'])}")
else:
    print(f"   ✗ PUT failed: {put_response.text}")
    exit(1)

# Simulate page reload - GET preferences
print("\n3. Simulating page reload - fetching preferences...")
get_response = requests.get(
    "http://localhost:8000/api/v1/users/me/dashboard/preferences",
    headers=headers
)

print(f"   GET status: {get_response.status_code}")
if get_response.status_code == 200:
    get_data = get_response.json()
    print(f"   ✓ Got preferences")
    print(f"   layout_preset: {get_data['layout_preset']}")
    print(f"   grid_layout: {get_data['grid_layout']}")
    print(f"   widget_count: {len(get_data['widget_layout'])}")

    # Verify it matches what we saved
    if len(get_data['widget_layout']) == 14:
        print("\n   ✓ SUCCESS! All 14 widgets were saved and retrieved!")
    else:
        print(f"\n   ✗ MISMATCH! Expected 14 widgets, got {len(get_data['widget_layout'])}")
else:
    print(f"   ✗ GET failed: {get_response.text}")

# Check database directly
print("\n4. Checking database directly...")
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="solar_hub",
    user="postgres",
    password="faisal"
)
cur = conn.cursor()
cur.execute("""
    SELECT layout_preset, grid_layout, jsonb_array_length(widget_layout) as widget_count
    FROM user_dashboard_preferences
    WHERE user_id = '4fc31ddb-dde2-4536-89cd-2dd0492e0fb8'
""")
row = cur.fetchone()
if row:
    print(f"   Database shows: preset={row[0]}, grid={row[1]}, widgets={row[2]}")
    if row[2] == 14:
        print("   ✓ Database has all 14 widgets!")
    else:
        print(f"   ✗ Database has {row[2]} widgets instead of 14!")
else:
    print("   ✗ No data in database!")

cur.close()
conn.close()

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
