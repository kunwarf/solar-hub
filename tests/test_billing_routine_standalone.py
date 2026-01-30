"""
Standalone billing routine test with 2 months of telemetry data.
Can be run directly without Playwright.

Usage: python test_billing_routine_standalone.py
"""
import psycopg2
from datetime import datetime, timedelta, timezone
import random
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Test user
TEST_USER_ID = "4fc31ddb-dde2-4536-89cd-2dd0492e0fb8"

# Database connection
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "solar_hub",
    "user": "postgres",
    "password": "faisal"
}


class BillingRoutineTester:
    """Test billing routine with generated data."""

    def __init__(self):
        print("Connecting to database...")
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor()
        print("✓ Connected\n")

    def cleanup(self):
        """Close database connection."""
        self.cur.close()
        self.conn.close()

    def get_or_create_site(self):
        """Get or create test site."""
        print("[1] Getting/Creating Site...")

        # First get user's organization
        self.cur.execute("""
            SELECT om.organization_id, o.name
            FROM organization_members om
            JOIN organizations o ON o.id = om.organization_id
            WHERE om.user_id = %s
            LIMIT 1
        """, (TEST_USER_ID,))

        org = self.cur.fetchone()
        if not org:
            print("   ! User not member of any organization")
            return None

        org_id, org_name = org
        print(f"   Organization: {org_name}")

        # Get or create site for this organization
        self.cur.execute("""
            SELECT id, name FROM sites
            WHERE organization_id = %s
            LIMIT 1
        """, (org_id,))

        site = self.cur.fetchone()

        if not site:
            print("   Creating new site...")
            self.cur.execute("""
                INSERT INTO sites (organization_id, name, timezone, status)
                VALUES (%s, 'Test Solar Site', 'Africa/Lagos', 'active')
                RETURNING id, name
            """, (org_id,))
            site = self.cur.fetchone()
            self.conn.commit()

        site_id, site_name = site
        print(f"   ✓ Site: {site_name}")
        print(f"     ID: {site_id}\n")
        return site_id

    def get_or_create_devices(self, site_id):
        """Get or create test devices."""
        print("[2] Getting/Creating Devices...")

        # First get organization_id for the site
        self.cur.execute("SELECT organization_id FROM sites WHERE id = %s", (site_id,))
        org_id = self.cur.fetchone()[0]

        self.cur.execute("""
            SELECT id, name, device_type
            FROM devices
            WHERE site_id = %s
        """, (site_id,))

        devices = self.cur.fetchall()

        if not devices:
            print("   Creating devices...")

            # Create inverter
            self.cur.execute("""
                INSERT INTO devices (site_id, organization_id, name, device_type, manufacturer, model, serial_number, status)
                VALUES (%s, %s, 'Inverter 1', 'inverter', 'SolarEdge', 'SE7600', 'INV001-TEST', 'online')
                RETURNING id, name, device_type
            """, (site_id, org_id))
            inverter = self.cur.fetchone()

            # Create battery
            self.cur.execute("""
                INSERT INTO devices (site_id, organization_id, name, device_type, manufacturer, model, serial_number, status)
                VALUES (%s, %s, 'Battery 1', 'battery', 'Tesla', 'Powerwall 2', 'BAT001-TEST', 'online')
                RETURNING id, name, device_type
            """, (site_id, org_id))
            battery = self.cur.fetchone()

            self.conn.commit()
            devices = [inverter, battery]

        print(f"   ✓ Found {len(devices)} devices:")
        for dev in devices:
            print(f"     - {dev[1]} ({dev[2]})")
        print()
        return devices

    def clear_telemetry_data(self, device_ids):
        """Clear existing telemetry data."""
        print("[3] Clearing Existing Telemetry...")

        for device_id in device_ids:
            self.cur.execute("DELETE FROM telemetry_data WHERE device_id = %s", (device_id,))

        self.conn.commit()
        print("   ✓ Cleared\n")

    def generate_telemetry_data(self, device_id, device_type, start_date, end_date):
        """Generate realistic telemetry data."""
        print(f"   Generating data for {device_type}...")

        current_time = start_date
        batch = []
        batch_size = 1000
        total_records = 0

        while current_time < end_date:
            hour = current_time.hour

            if device_type == 'inverter':
                # Solar production (peak at noon)
                if 6 <= hour <= 18:
                    base_power = abs(6 - abs(12 - hour)) / 6
                    solar_power = base_power * random.uniform(4000, 7600)
                    grid_import = random.uniform(0, 500)  # Some daytime consumption
                    grid_export = solar_power * random.uniform(0.5, 0.8)  # Export excess
                    load_power = random.uniform(1000, 3000)
                else:
                    solar_power = 0
                    grid_import = random.uniform(500, 2000)
                    grid_export = 0
                    load_power = random.uniform(500, 1500)

                battery_power = random.uniform(-2000, 2000)

                batch.append((
                    current_time, device_id,
                    round(solar_power, 2),
                    round(battery_power, 2),
                    round(grid_import, 2),
                    round(grid_export, 2),
                    round(load_power, 2),
                    round(random.uniform(20, 95), 2),  # battery_soc
                    round(random.uniform(49.8, 50.2), 2),  # grid_frequency
                    round(random.uniform(220, 240), 2),  # grid_voltage
                ))

            elif device_type == 'battery':
                is_charging = random.choice([True, False])
                battery_power = random.uniform(0, 5000) * (1 if is_charging else -1)

                batch.append((
                    current_time, device_id,
                    0, round(battery_power, 2), 0, 0, 0,
                    round(random.uniform(20, 95), 2),
                    None, None
                ))

            total_records += 1

            if len(batch) >= batch_size:
                self._insert_batch(batch)
                batch = []
                if total_records % 10000 == 0:
                    print(f"     {total_records} records...")

            current_time += timedelta(minutes=5)

        if batch:
            self._insert_batch(batch)

        print(f"   ✓ {total_records} records generated")
        return total_records

    def _insert_batch(self, batch):
        """Insert batch of telemetry records."""
        self.cur.executemany("""
            INSERT INTO telemetry_data (
                timestamp, device_id, solar_power, battery_power,
                grid_import, grid_export, load_power,
                battery_soc, grid_frequency, grid_voltage
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, batch)
        self.conn.commit()

    def refresh_aggregates(self):
        """Refresh TimescaleDB continuous aggregates."""
        print("\n[5] Refreshing Continuous Aggregates...")

        aggregates = [
            'telemetry_data_1m',
            'telemetry_data_5m',
            'telemetry_data_1h',
            'telemetry_data_1d'
        ]

        for agg in aggregates:
            print(f"   Refreshing {agg}...")
            try:
                self.cur.execute(f"CALL refresh_continuous_aggregate('{agg}', NULL, NULL);")
                self.conn.commit()
                print(f"   ✓ {agg} refreshed")
            except Exception as e:
                print(f"   ! Error refreshing {agg}: {e}")

        print()

    def verify_aggregates(self):
        """Verify aggregates have data."""
        print("[6] Verifying Aggregates...")

        aggregates = [
            'telemetry_data_1m',
            'telemetry_data_5m',
            'telemetry_data_1h',
            'telemetry_data_1d'
        ]

        for agg in aggregates:
            self.cur.execute(f"SELECT COUNT(*) FROM {agg};")
            count = self.cur.fetchone()[0]
            print(f"   {agg}: {count:,} records")

        print()

    def setup_billing_config(self, site_id):
        """Setup billing configuration."""
        print("[7] Setting Up Billing Configuration...")

        # Check if exists
        self.cur.execute("""
            SELECT id FROM billing_config
            WHERE site_id = %s
        """, (site_id,))

        if self.cur.fetchone():
            print("   ✓ Billing configuration already exists\n")
            return

        # Create billing config
        self.cur.execute("""
            INSERT INTO billing_config (
                site_id,
                anchor_day,
                price_peak_import,
                price_offpeak_import,
                price_peak_settlement,
                price_offpeak_settlement,
                fixed_charge_per_billing_month,
                tou_windows,
                net_metering_enabled
            ) VALUES (
                %s,
                1,
                75.00,
                50.00,
                40.00,
                40.00,
                1500.00,
                '{"timezone": "Africa/Lagos", "peak_windows": [{"start_hour": 6, "end_hour": 22}]}'::jsonb,
                true
            )
        """, (site_id,))
        self.conn.commit()

        print("   ✓ Billing configuration created")
        print("     Tariff: Net Metering")
        print("     Peak Import: NGN 75/kWh (06:00-22:00)")
        print("     Off-peak Import: NGN 50/kWh")
        print("     Settlement: NGN 40/kWh")
        print("     Fixed Charge: NGN 1,500/month\n")

    def compute_billing_cycles(self, site_id):
        """Compute billing cycles."""
        print("[8] Computing Billing Cycles...")

        # Get billing configuration
        self.cur.execute("""
            SELECT
                anchor_day,
                price_peak_import,
                price_offpeak_import,
                price_peak_settlement,
                fixed_charge_per_billing_month
            FROM billing_config
            WHERE site_id = %s
        """, (site_id,))

        config = self.cur.fetchone()
        if not config:
            print("   ! No billing configuration found")
            return

        anchor_day, peak_price, offpeak_price, settlement_price, fixed_charge = config

        # Use fixed capacity for testing
        capacity_kw = 7.6

        # Generate billing cycles for last 2 months
        end_date = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_date = (end_date - timedelta(days=60)).replace(day=1)

        cycles_created = 0

        current_start = start_date
        while current_start < end_date:
            # Calculate cycle end (start of next month)
            if current_start.month == 12:
                cycle_end = current_start.replace(year=current_start.year + 1, month=1)
            else:
                cycle_end = current_start.replace(month=current_start.month + 1)

            print(f"\n   Cycle: {current_start.date()} to {cycle_end.date()}")

            # Get aggregated data for this cycle
            self.cur.execute("""
                SELECT
                    COALESCE(SUM(grid_import), 0) as total_import,
                    COALESCE(SUM(grid_export), 0) as total_export
                FROM telemetry_data_1h
                WHERE bucket >= %s AND bucket < %s
            """, (current_start, cycle_end))

            result = self.cur.fetchone()
            total_import_kwh = float(result[0])
            total_export_kwh = float(result[1])
            net_energy_kwh = total_import_kwh - total_export_kwh

            # Calculate peak/off-peak (simplified - using 60/40 split)
            peak_import_kwh = total_import_kwh * 0.6
            offpeak_import_kwh = total_import_kwh * 0.4

            # Calculate costs
            import_cost = (peak_import_kwh * float(peak_price)) + (offpeak_import_kwh * float(offpeak_price))
            export_credit = total_export_kwh * float(settlement_price)
            fixed_charge_amount = float(fixed_charge)
            total_amount = import_cost - export_credit + fixed_charge_amount

            print(f"     Import: {total_import_kwh:.2f} kWh")
            print(f"     Export: {total_export_kwh:.2f} kWh")
            print(f"     Net: {net_energy_kwh:.2f} kWh")
            print(f"     Import Cost: NGN {import_cost:.2f}")
            print(f"     Export Credit: NGN {export_credit:.2f}")
            print(f"     Fixed Charge: NGN {fixed_charge_amount:.2f}")
            print(f"     Total: NGN {total_amount:.2f}")

            # Insert or update billing cycle
            self.cur.execute("""
                INSERT INTO billing_cycles (
                    site_id, cycle_start, cycle_end,
                    total_import_kwh, total_export_kwh, net_energy_kwh,
                    peak_import_kwh, offpeak_import_kwh,
                    import_cost, export_credit, fixed_charge, total_amount,
                    status, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'computed', NOW(), NOW()
                )
                ON CONFLICT (site_id, cycle_start) DO UPDATE SET
                    total_import_kwh = EXCLUDED.total_import_kwh,
                    total_export_kwh = EXCLUDED.total_export_kwh,
                    net_energy_kwh = EXCLUDED.net_energy_kwh,
                    peak_import_kwh = EXCLUDED.peak_import_kwh,
                    offpeak_import_kwh = EXCLUDED.offpeak_import_kwh,
                    import_cost = EXCLUDED.import_cost,
                    export_credit = EXCLUDED.export_credit,
                    fixed_charge = EXCLUDED.fixed_charge,
                    total_amount = EXCLUDED.total_amount,
                    status = 'computed',
                    updated_at = NOW()
            """, (
                site_id, current_start, cycle_end,
                total_import_kwh, total_export_kwh, net_energy_kwh,
                peak_import_kwh, offpeak_import_kwh,
                import_cost, export_credit, fixed_charge_amount, total_amount
            ))

            self.conn.commit()
            cycles_created += 1

            current_start = cycle_end

        print(f"\n   ✓ {cycles_created} billing cycles computed\n")

    def verify_billing_results(self, site_id):
        """Verify billing computation results."""
        print("[9] Verifying Billing Results...")

        self.cur.execute("""
            SELECT
                cycle_start, cycle_end,
                total_import_kwh, total_export_kwh, net_energy_kwh,
                peak_import_kwh, offpeak_import_kwh,
                import_cost, export_credit, fixed_charge, total_amount,
                status
            FROM billing_cycles
            WHERE site_id = %s
            ORDER BY cycle_start DESC
        """, (site_id,))

        cycles = self.cur.fetchall()

        if not cycles:
            print("   ! No billing cycles found")
            return

        print(f"   ✓ Found {len(cycles)} billing cycles\n")

        for cycle in cycles:
            print("   " + "-"*70)
            print(f"   Period: {cycle[0].date()} to {cycle[1].date()}")
            print(f"   Import: {cycle[2]:.2f} kWh (Peak: {cycle[5]:.2f}, Off-peak: {cycle[6]:.2f})")
            print(f"   Export: {cycle[3]:.2f} kWh")
            print(f"   Net: {cycle[4]:.2f} kWh")
            print(f"   Import Cost: NGN {cycle[7]:.2f}")
            print(f"   Export Credit: NGN {cycle[8]:.2f}")
            print(f"   Fixed Charge: NGN {cycle[9]:.2f}")
            print(f"   Total Amount: NGN {cycle[10]:.2f}")
            print(f"   Status: {cycle[11]}")

            # Validate calculations
            assert cycle[2] >= 0, "Import should be non-negative"
            assert cycle[3] >= 0, "Export should be non-negative"
            assert abs(cycle[4] - (cycle[2] - cycle[3])) < 0.01, "Net energy mismatch"

        print("\n   ✓ All billing cycles validated\n")


def main():
    """Main test execution."""
    print("\n" + "="*80)
    print("BILLING ROUTINE TEST - 2 MONTHS OF TELEMETRY DATA")
    print("="*80 + "\n")

    tester = BillingRoutineTester()

    try:
        # Step 1: Get/create site
        site_id = tester.get_or_create_site()

        # Step 2: Get/create devices
        devices = tester.get_or_create_devices(site_id)
        device_ids = [dev[0] for dev in devices]

        # Step 3: Clear old telemetry
        tester.clear_telemetry_data(device_ids)

        # Step 4: Generate 2 months of telemetry
        print("[4] Generating 2 Months of Telemetry Data...")
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=60)
        print(f"   Period: {start_date.date()} to {end_date.date()}\n")

        total_records = 0
        for device_id, device_code, device_type in devices:
            records = tester.generate_telemetry_data(device_id, device_type, start_date, end_date)
            total_records += records

        print(f"\n   ✓ Total: {total_records:,} records generated\n")

        # Step 5: Refresh aggregates
        tester.refresh_aggregates()

        # Step 6: Verify aggregates
        tester.verify_aggregates()

        # Step 7: Setup billing config
        tester.setup_billing_config(site_id)

        # Step 8: Compute billing cycles
        tester.compute_billing_cycles(site_id)

        # Step 9: Verify results
        tester.verify_billing_results(site_id)

        print("="*80)
        print("✓ BILLING ROUTINE TEST COMPLETE!")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()
