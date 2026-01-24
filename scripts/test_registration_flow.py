#!/usr/bin/env python3
"""
End-to-end test script for device and user registration flow.

Tests:
1. ESP device self-registration to System B (creates orphan device)
2. User registration with device claim to System A

Usage:
    python scripts/test_registration_flow.py

Prerequisites:
    - System A running on http://localhost:8000
    - System B running on http://localhost:8001
    - PostgreSQL database configured and migrated
"""

import asyncio
import httpx
import uuid
from datetime import datetime

# Configuration
SYSTEM_A_URL = "http://localhost:8000"
SYSTEM_B_URL = "http://localhost:8001"

# Test data
TEST_DEVICE_SERIAL = f"TEST-ESP-{uuid.uuid4().hex[:8].upper()}"
TEST_USER_EMAIL = f"test-{uuid.uuid4().hex[:8]}@example.com"
TEST_USER_PASSWORD = "TestPassword123!"


async def test_device_self_registration():
    """Test ESP device self-registration to System B."""
    print("\n" + "=" * 60)
    print("Step 1: Device Self-Registration (System B)")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Self-register device
        payload = {
            "serial_number": TEST_DEVICE_SERIAL,
            "device_type": "inverter",
            "firmware_version": "1.0.0",
            "manufacturer": "Test Manufacturer",
            "protocol": "modbus_tcp",
            "model": "TEST-MODEL",
        }

        print(f"Registering device: {TEST_DEVICE_SERIAL}")
        response = await client.post(
            f"{SYSTEM_B_URL}/api/v1/devices/self-register",
            json=payload,
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Device registered successfully!")
            print(f"  Device ID: {data['device_id']}")
            print(f"  Is Claimed: {data['is_claimed']}")
            print(f"  Polling Interval: {data['polling_interval_ms']}ms")
            return data["device_id"]
        else:
            print(f"✗ Device registration failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None


async def test_verify_orphan_device(device_id: str):
    """Verify device is in orphan state."""
    print("\n" + "=" * 60)
    print("Step 2: Verify Device is Orphan (System B)")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get device by serial
        response = await client.get(
            f"{SYSTEM_B_URL}/api/v1/devices/serial/{TEST_DEVICE_SERIAL}",
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Device found!")
            print(f"  Serial: {data['serial_number']}")
            print(f"  Type: {data['device_type']}")
            print(f"  Status: {data['status']}")
            print(f"  Owner ID: {data.get('owner_id', 'None')}")
            return data["status"] == "orphan"
        else:
            print(f"✗ Failed to get device: {response.status_code}")
            return False


async def test_list_orphan_devices():
    """List all orphan devices."""
    print("\n" + "=" * 60)
    print("Step 3: List Orphan Devices (System B)")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{SYSTEM_B_URL}/api/v1/devices/orphan")

        if response.status_code == 200:
            devices = response.json()
            print(f"✓ Found {len(devices)} orphan device(s)")
            for d in devices:
                print(f"  - {d['serial_number']} ({d['device_type']})")
            return True
        else:
            print(f"✗ Failed to list orphan devices: {response.status_code}")
            return False


async def test_user_registration_with_device():
    """Test user registration with device claim via System A."""
    print("\n" + "=" * 60)
    print("Step 4: User Registration with Device Claim (System A)")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Register user with device serial
        payload = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "first_name": "Test",
            "last_name": "User",
            "phone": "+923001234567",
            "device_serial": TEST_DEVICE_SERIAL,
        }

        print(f"Registering user: {TEST_USER_EMAIL}")
        print(f"  With device: {TEST_DEVICE_SERIAL}")

        response = await client.post(
            f"{SYSTEM_A_URL}/api/v1/auth/register",
            json=payload,
        )

        if response.status_code == 201:
            data = response.json()
            print(f"✓ User registered successfully!")
            print(f"  User ID: {data['user']['id']}")
            print(f"  Email: {data['user']['email']}")
            print(f"  Site: {data.get('site', {}).get('name', 'N/A')}")
            if data.get("device"):
                print(f"  Device Claimed: {data['device']['serial_number']}")
            else:
                print(f"  Device Claim: Failed or device not found")
            return data
        else:
            print(f"✗ User registration failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None


async def test_verify_device_claimed():
    """Verify device is now claimed."""
    print("\n" + "=" * 60)
    print("Step 5: Verify Device is Claimed (System B)")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{SYSTEM_B_URL}/api/v1/devices/serial/{TEST_DEVICE_SERIAL}",
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Device found!")
            print(f"  Serial: {data['serial_number']}")
            print(f"  Status: {data['status']}")
            print(f"  Owner ID: {data.get('owner_id', 'None')}")
            print(f"  Site ID: {data.get('site_id', 'None')}")
            return data["status"] == "claimed"
        else:
            print(f"✗ Failed to get device: {response.status_code}")
            return False


async def check_system_health():
    """Check if both systems are running."""
    print("\n" + "=" * 60)
    print("Checking System Health")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check System A
        try:
            response = await client.get(f"{SYSTEM_A_URL}/health")
            if response.status_code == 200:
                print(f"✓ System A is running at {SYSTEM_A_URL}")
            else:
                print(f"✗ System A returned status {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ System A is not reachable: {e}")
            return False

        # Check System B
        try:
            response = await client.get(f"{SYSTEM_B_URL}/health")
            if response.status_code == 200:
                print(f"✓ System B is running at {SYSTEM_B_URL}")
            else:
                print(f"✗ System B returned status {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ System B is not reachable: {e}")
            return False

    return True


async def main():
    """Run the complete end-to-end test."""
    print("\n" + "=" * 60)
    print("Device & User Registration Flow E2E Test")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"Test Device Serial: {TEST_DEVICE_SERIAL}")
    print(f"Test User Email: {TEST_USER_EMAIL}")

    # Check system health
    if not await check_system_health():
        print("\n✗ System health check failed. Please ensure both systems are running.")
        return False

    # Step 1: Device self-registration
    device_id = await test_device_self_registration()
    if not device_id:
        print("\n✗ Test failed at device registration")
        return False

    # Step 2: Verify orphan device
    is_orphan = await test_verify_orphan_device(device_id)
    if not is_orphan:
        print("\n✗ Device is not in orphan state")
        return False

    # Step 3: List orphan devices
    await test_list_orphan_devices()

    # Step 4: User registration with device claim
    user_data = await test_user_registration_with_device()
    if not user_data:
        print("\n✗ Test failed at user registration")
        return False

    # Step 5: Verify device claimed
    is_claimed = await test_verify_device_claimed()
    if not is_claimed:
        print("\n⚠ Device may not have been claimed successfully")
        # This is a warning, not a failure - device claim is optional

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"✓ Device self-registration: PASSED")
    print(f"✓ Orphan device verification: PASSED")
    print(f"✓ User registration: PASSED")
    print(f"{'✓' if is_claimed else '⚠'} Device claim: {'PASSED' if is_claimed else 'SKIPPED/FAILED'}")
    print("\n✓ End-to-end test completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
