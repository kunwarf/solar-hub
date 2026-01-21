#!/usr/bin/env python3
"""
Helper script to get or generate site IDs for testing.

Usage:
    # Generate a test UUID
    python scripts/get_site_id.py --generate

    # List sites from System A (if accessible)
    python scripts/get_site_id.py --list --system-a-url http://127.0.0.1:8000
"""
import argparse
import sys
from uuid import UUID, uuid4

try:
    import httpx
except ImportError:
    httpx = None


def generate_uuid():
    """Generate a random UUID for testing."""
    test_uuid = uuid4()
    print(f"Generated test UUID: {test_uuid}")
    print(f"\nYou can use this UUID with the simulator:")
    print(f"  python scripts/run_inverter_simulator.py --serial PD12K00001 --site-id {test_uuid}")
    return test_uuid


async def list_sites(system_a_url: str):
    """List sites from System A API."""
    if not httpx:
        print("Error: httpx not installed. Install with: pip install httpx")
        return
    
    try:
        async with httpx.AsyncClient(base_url=system_a_url, timeout=10.0) as client:
            # Try to get sites (may require authentication)
            response = await client.get("/api/v1/sites")
            
            if response.status_code == 200:
                data = response.json()
                sites = data.get("items", [])
                
                if sites:
                    print(f"Found {len(sites)} site(s):\n")
                    for site in sites:
                        print(f"  Site: {site.get('name', 'Unknown')}")
                        print(f"    ID: {site.get('id')}")
                        print(f"    Type: {site.get('site_type', 'Unknown')}")
                        print()
                else:
                    print("No sites found.")
            elif response.status_code == 401:
                print("Error: Authentication required. System A API requires login.")
                print("Please get site IDs from System A web interface or database.")
            else:
                print(f"Error: Failed to get sites (status {response.status_code})")
                print("You can generate a test UUID instead:")
                generate_uuid()
                
    except httpx.ConnectError:
        print(f"Error: Could not connect to System A at {system_a_url}")
        print("You can generate a test UUID instead:")
        generate_uuid()
    except Exception as e:
        print(f"Error: {e}")
        print("You can generate a test UUID instead:")
        generate_uuid()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Get or generate site IDs for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a test UUID
  python scripts/get_site_id.py --generate

  # List sites from System A
  python scripts/get_site_id.py --list --system-a-url http://127.0.0.1:8000
        """
    )
    
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate a random UUID for testing"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List sites from System A API"
    )
    parser.add_argument(
        "--system-a-url",
        default="http://127.0.0.1:8000",
        help="System A API URL (for --list option)"
    )
    
    args = parser.parse_args()
    
    if args.generate:
        generate_uuid()
    elif args.list:
        import asyncio
        asyncio.run(list_sites(args.system_a_url))
    else:
        parser.print_help()
        print("\nNote: You need either --generate or --list option")
        sys.exit(1)


if __name__ == "__main__":
    main()
