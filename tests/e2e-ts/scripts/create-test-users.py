#!/usr/bin/env python3
"""
Create Test Users for E2E Testing

This script creates test users in the local database for E2E testing.
It uses the registration API endpoint to create users.

Usage:
    python scripts/create-test-users.py
"""

import requests
import json
from typing import Dict, List

# API Configuration
API_URL = "http://localhost:8000/api/v1"

# Test Users to Create
TEST_USERS = [
    {
        "email": "test.owner@solarhub.local",
        "password": "Test@123456",
        "full_name": "Test Owner",
        "role": "owner"
    },
    {
        "email": "test.admin@solarhub.local",
        "password": "Test@123456",
        "full_name": "Test Admin",
        "role": "admin"
    },
    {
        "email": "test.viewer@solarhub.local",
        "password": "Test@123456",
        "full_name": "Test Viewer",
        "role": "viewer"
    },
    {
        "email": "test.installer@solarhub.local",
        "password": "Test@123456",
        "full_name": "Test Installer",
        "role": "installer"
    }
]


def create_user(user_data: Dict) -> bool:
    """Create a single user via the registration API."""
    print(f"\n Creating user: {user_data['email']}...")

    try:
        # Call the register endpoint
        response = requests.post(
            f"{API_URL}/auth/register",
            json={
                "email": user_data["email"],
                "password": user_data["password"],
                "full_name": user_data["full_name"]
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code in [200, 201]:
            print(f"   ✓ User created successfully: {user_data['email']}")
            print(f"   → Response: {response.json()}")
            return True
        elif response.status_code == 400:
            error_data = response.json()
            if "already" in str(error_data).lower():
                print(f"   ℹ User already exists: {user_data['email']}")
                return True
            else:
                print(f"   ✗ Failed to create user: {error_data}")
                return False
        else:
            print(f"   ✗ Unexpected status code: {response.status_code}")
            print(f"   → Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"   ✗ Connection error: Is the API running at {API_URL}?")
        return False
    except requests.exceptions.Timeout:
        print(f"   ✗ Request timeout")
        return False
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        return False


def verify_user(email: str, password: str) -> bool:
    """Verify that a user can log in."""
    print(f"\n🔐 Verifying login for: {email}...")

    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={
                "email": email,
                "password": password
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if "access_token" in data:
                print(f"   ✓ Login successful! Token received.")
                return True
            else:
                print(f"   ✗ Login response missing access_token")
                return False
        else:
            print(f"   ✗ Login failed: {response.status_code}")
            print(f"   → Response: {response.text}")
            return False

    except Exception as e:
        print(f"   ✗ Error during login: {str(e)}")
        return False


def main():
    """Main function to create all test users."""
    print("=" * 60)
    print("🌱 Creating Test Users for E2E Testing")
    print("=" * 60)
    print(f"\nAPI URL: {API_URL}")
    print(f"Users to create: {len(TEST_USERS)}\n")

    # Check if API is reachable
    try:
        health_response = requests.get(f"http://localhost:8000/health", timeout=5)
        if health_response.status_code == 200:
            print("✓ API is reachable\n")
        else:
            print(f"⚠ API health check returned: {health_response.status_code}\n")
    except Exception as e:
        print(f"✗ Cannot reach API: {str(e)}")
        print("  Make sure System A is running on http://localhost:8000\n")
        return

    # Create users
    created_count = 0
    for user in TEST_USERS:
        if create_user(user):
            created_count += 1

    print("\n" + "=" * 60)
    print(f"📊 Summary: {created_count}/{len(TEST_USERS)} users created/verified")
    print("=" * 60)

    # Verify login for all users
    print("\n🧪 Verifying user logins...\n")
    verified_count = 0
    for user in TEST_USERS:
        if verify_user(user["email"], user["password"]):
            verified_count += 1

    print("\n" + "=" * 60)
    print(f"✅ Login Verification: {verified_count}/{len(TEST_USERS)} successful")
    print("=" * 60)

    # Print credentials summary
    print("\n📝 Test User Credentials:\n")
    for user in TEST_USERS:
        print(f"  {user['role']:10} → {user['email']:35} / {user['password']}")

    print("\n💡 Update your .env.local file with these credentials:")
    print(f"\n  OWNER_EMAIL={TEST_USERS[0]['email']}")
    print(f"  OWNER_PASSWORD={TEST_USERS[0]['password']}\n")

    if created_count == len(TEST_USERS) and verified_count == len(TEST_USERS):
        print("✅ All test users are ready for E2E testing!\n")
    else:
        print("⚠ Some users could not be created or verified. Check errors above.\n")


if __name__ == "__main__":
    main()
