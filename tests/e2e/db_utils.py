"""
Database utilities for E2E tests.

Provides functions to query the database directly for test validation.
"""
import psycopg2
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta


# Database connection settings
SYSTEM_A_DB = {
    "host": "localhost",
    "port": 5433,
    "user": "postgres",
    "password": "faisal",
    "database": "solar_hub"
}

SYSTEM_B_DB = {
    "host": "localhost",
    "port": 5433,
    "user": "postgres",
    "password": "faisal",
    "database": "solar_hub_telemetry"
}


def get_system_a_connection():
    """Get connection to System A database."""
    return psycopg2.connect(**SYSTEM_A_DB)


def get_system_b_connection():
    """Get connection to System B database."""
    return psycopg2.connect(**SYSTEM_B_DB)


# ============================================================================
# Organization Queries
# ============================================================================

def get_organizations() -> List[Dict]:
    """Get all organizations from database."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, slug, status FROM organizations")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": str(r[0]), "name": r[1], "slug": r[2], "status": r[3]} for r in rows]


def get_organization_by_id(org_id: str) -> Optional[Dict]:
    """Get organization by ID."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, slug, status FROM organizations WHERE id = %s", (org_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"id": str(row[0]), "name": row[1], "slug": row[2], "status": row[3]}
    return None


# ============================================================================
# Site Queries
# ============================================================================

def get_sites() -> List[Dict]:
    """Get all sites from database."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, organization_id, name, status, timezone, site_type
        FROM sites
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        "id": str(r[0]),
        "organization_id": str(r[1]),
        "name": r[2],
        "status": r[3],
        "timezone": r[4],
        "site_type": r[5]
    } for r in rows]


def get_site_by_id(site_id: str) -> Optional[Dict]:
    """Get site by ID."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, organization_id, name, status, timezone, site_type, latitude, longitude
        FROM sites WHERE id = %s
    """, (site_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            "id": str(row[0]),
            "organization_id": str(row[1]),
            "name": row[2],
            "status": row[3],
            "timezone": row[4],
            "site_type": row[5],
            "latitude": float(row[6]) if row[6] else None,
            "longitude": float(row[7]) if row[7] else None
        }
    return None


# ============================================================================
# Device Queries
# ============================================================================

def get_devices() -> List[Dict]:
    """Get all devices from database."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, site_id, organization_id, name, device_type, manufacturer,
               model, serial_number, status
        FROM devices
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        "id": str(r[0]),
        "site_id": str(r[1]),
        "organization_id": str(r[2]),
        "name": r[3],
        "device_type": r[4],
        "manufacturer": r[5],
        "model": r[6],
        "serial_number": r[7],
        "status": r[8]
    } for r in rows]


def get_devices_by_site(site_id: str) -> List[Dict]:
    """Get devices for a specific site."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, site_id, name, device_type, manufacturer, model, serial_number, status
        FROM devices WHERE site_id = %s
    """, (site_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        "id": str(r[0]),
        "site_id": str(r[1]),
        "name": r[2],
        "device_type": r[3],
        "manufacturer": r[4],
        "model": r[5],
        "serial_number": r[6],
        "status": r[7]
    } for r in rows]


def get_device_count() -> int:
    """Get total device count."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM devices")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_online_device_count() -> int:
    """Get count of online devices."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM devices WHERE status = 'online'")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


# ============================================================================
# User Queries
# ============================================================================

def get_users() -> List[Dict]:
    """Get all users from database."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, first_name, last_name, role, status FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        "id": str(r[0]),
        "email": r[1],
        "first_name": r[2],
        "last_name": r[3],
        "role": r[4],
        "status": r[5]
    } for r in rows]


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email."""
    conn = get_system_a_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, email, first_name, last_name, role, status
        FROM users WHERE email = %s
    """, (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            "id": str(row[0]),
            "email": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "role": row[4],
            "status": row[5]
        }
    return None


# ============================================================================
# Telemetry Queries (System B)
# ============================================================================

def get_latest_telemetry(device_id: str, metric_name: str) -> Optional[Dict]:
    """Get latest telemetry value for a device and metric."""
    conn = get_system_b_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT time, device_id, metric_name, metric_value, quality
        FROM telemetry_raw
        WHERE device_id = %s AND metric_name = %s
        ORDER BY time DESC
        LIMIT 1
    """, (device_id, metric_name))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            "time": row[0],
            "device_id": str(row[1]),
            "metric_name": row[2],
            "metric_value": float(row[3]) if row[3] else 0,
            "quality": row[4]
        }
    return None


def get_telemetry_for_site(site_id: str, hours_back: int = 1) -> List[Dict]:
    """Get recent telemetry for all devices in a site."""
    conn = get_system_b_connection()
    cur = conn.cursor()
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    cur.execute("""
        SELECT time, device_id, metric_name, metric_value
        FROM telemetry_raw
        WHERE site_id = %s AND time >= %s
        ORDER BY time DESC
    """, (site_id, since))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        "time": r[0],
        "device_id": str(r[1]),
        "metric_name": r[2],
        "metric_value": float(r[3]) if r[3] else 0
    } for r in rows]


def get_latest_power_metrics(site_id: str) -> Dict[str, float]:
    """Get latest power metrics for a site."""
    metrics = {}
    conn = get_system_b_connection()
    cur = conn.cursor()

    for metric in ['pv_power', 'grid_power', 'load_power', 'battery_power', 'battery_soc']:
        cur.execute("""
            SELECT metric_value
            FROM telemetry_raw
            WHERE site_id = %s AND metric_name = %s
            ORDER BY time DESC
            LIMIT 1
        """, (site_id, metric))
        row = cur.fetchone()
        metrics[metric] = float(row[0]) if row and row[0] else 0

    cur.close()
    conn.close()
    return metrics


def get_energy_today(site_id: str) -> float:
    """Get total energy generated today for a site."""
    conn = get_system_b_connection()
    cur = conn.cursor()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    cur.execute("""
        SELECT SUM(metric_value)
        FROM telemetry_raw
        WHERE site_id = %s
          AND metric_name = 'energy_today'
          AND time >= %s
    """, (site_id, today_start))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return float(row[0]) if row and row[0] else 0


def get_telemetry_count(site_id: str, hours_back: int = 1) -> int:
    """Get count of telemetry records for a site in the last N hours."""
    conn = get_system_b_connection()
    cur = conn.cursor()
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    cur.execute("""
        SELECT COUNT(*)
        FROM telemetry_raw
        WHERE site_id = %s AND time >= %s
    """, (site_id, since))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


# ============================================================================
# Summary Queries
# ============================================================================

def get_test_data_summary() -> Dict:
    """Get summary of all test data in the database."""
    return {
        "organizations": len(get_organizations()),
        "sites": len(get_sites()),
        "devices": get_device_count(),
        "users": len(get_users()),
        "online_devices": get_online_device_count(),
    }


if __name__ == "__main__":
    # Test the utilities
    print("Test Data Summary:")
    summary = get_test_data_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print("\nOrganizations:")
    for org in get_organizations():
        print(f"  - {org['name']} ({org['id']})")

    print("\nSites:")
    for site in get_sites():
        print(f"  - {site['name']} ({site['id']})")

    print("\nDevices:")
    for device in get_devices():
        print(f"  - {device['name']} ({device['device_type']}) - {device['status']}")
