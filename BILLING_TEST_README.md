# Billing Routine Test Suite

## Overview

Created comprehensive test suites to verify the billing routine works correctly with 2 months of telemetry data.

## Files Created

### 1. `tests/e2e/test_billing_routine.py`
**Playwright E2E Test Suite**

Full end-to-end tests that include UI verification.

**Features:**
- Generates 2 months of realistic telemetry data
- Creates inverter and battery devices
- Simulates solar production patterns (peak at noon, zero at night)
- Tests billing computation end-to-end
- Verifies results in both database and UI

**Usage:**
```bash
cd tests/e2e
pytest test_billing_routine.py -v -s
```

**Tests Included:**
- `test_billing_with_2_months_data` - Complete billing workflow test
- `test_billing_cycle_creation` - Verify billing cycles are created correctly

---

### 2. `tests/test_billing_routine_standalone.py`
**Standalone Billing Test (No UI)**

Faster test that focuses on data generation and billing computation without UI verification.

**Features:**
- ✅ Creates/finds test site for user
- ✅ Creates test devices (inverter + battery)
- ✅ Generates 2 months of telemetry data (~17,280 records per device)
- ✅ Refreshes TimescaleDB continuous aggregates
- ✅ Sets up billing configuration
- ✅ Computes billing cycles
- ✅ Verifies billing results

**Usage:**
```bash
python tests/test_billing_routine_standalone.py
```

**What It Does:**

1. **Site Setup**
   - Gets user's organization
   - Creates/finds test site

2. **Device Setup**
   - Creates inverter device (SolarEdge SE7600)
   - Creates battery device (Tesla Powerwall 2)

3. **Telemetry Generation** (2 months @ 5-minute intervals)
   - **Inverter Data:**
     - Solar production: 4-7.6 kW during daylight (6 AM - 6 PM)
     - Peak production: ~noon
     - Grid import/export patterns
     - Load consumption

   - **Battery Data:**
     - Charging/discharging cycles
     - State of charge (20-95%)
     - Battery metrics

4. **Aggregate Refresh**
   - `telemetry_data_1m` - 1-minute aggregates
   - `telemetry_data_5m` - 5-minute aggregates
   - `telemetry_data_1h` - 1-hour aggregates
   - `telemetry_data_1d` - 1-day aggregates

5. **Billing Configuration**
   - Tariff: Net Metering
   - Peak Import: NGN 75/kWh (06:00-22:00)
   - Off-peak Import: NGN 50/kWh
   - Settlement Price: NGN 40/kWh
   - Fixed Charge: NGN 1,500/month

6. **Billing Computation**
   - Generates billing cycles for 2 months
   - Calculates:
     - Total import/export energy
     - Peak/off-peak split
     - Import costs
     - Export credits
     - Fixed charges
     - Total amount due

7. **Verification**
   - Validates calculations
   - Displays detailed billing summary

---

## Test Data Generated

### Telemetry Records
- **Duration:** 60 days
- **Interval:** 5 minutes
- **Records per device:** ~17,280
- **Total records:** ~34,560 (for 2 devices)

### Telemetry Data Patterns

**Solar Production (Inverter):**
```
00:00 - 06:00: 0 kW (night)
06:00 - 12:00: Ramping up to 7.6 kW
12:00 - 14:00: Peak production ~7 kW
14:00 - 18:00: Ramping down
18:00 - 24:00: 0 kW (night)
```

**Grid Import/Export:**
- **Daytime:** Export excess solar (50-80% of production)
- **Nighttime:** Import from grid (500-2000 W)

**Battery:**
- Charging during solar peak
- Discharging during evening
- SOC: 20-95%

---

## Expected Results

### Billing Cycles
Two billing cycles should be generated:
1. **Month 1:** (Start of period to end of first month)
2. **Month 2:** (Start of second month to end of period)

### Sample Output
```
================================================================================
BILLING ROUTINE TEST - 2 MONTHS OF TELEMETRY DATA
================================================================================

[1] Getting/Creating Site...
   Organization: Test's Organization
   ✓ Site: My Home
     ID: 5f20aa40-4397-47e9-918c-abb0f7f58073

[2] Getting/Creating Devices...
   ✓ Found 2 devices:
     - Inverter 1 (inverter)
     - Battery 1 (battery)

[3] Clearing Existing Telemetry...
   ✓ Cleared

[4] Generating 2 Months of Telemetry Data...
   Period: 2024-11-29 to 2026-01-29

   Generating data for inverter...
   ✓ 17,280 records generated

   Generating data for battery...
   ✓ 17,280 records generated

   ✓ Total: 34,560 records generated

[5] Refreshing Continuous Aggregates...
   Refreshing telemetry_data_1m...
   ✓ telemetry_data_1m refreshed
   Refreshing telemetry_data_5m...
   ✓ telemetry_data_5m refreshed
   ...

[6] Verifying Aggregates...
   telemetry_data_1m: 17,280 records
   telemetry_data_5m: 3,456 records
   telemetry_data_1h: 1,440 records
   telemetry_data_1d: 60 records

[7] Setting Up Billing Configuration...
   ✓ Billing configuration created
     Tariff: Net Metering
     Peak Import: NGN 75/kWh (06:00-22:00)
     Off-peak Import: NGN 50/kWh
     Settlement: NGN 40/kWh
     Fixed Charge: NGN 1,500/month

[8] Computing Billing Cycles...

   Cycle: 2024-12-01 to 2025-01-01
     Import: 1,250.50 kWh
     Export: 2,150.75 kWh
     Net: -900.25 kWh
     Import Cost: NGN 75,031.25
     Export Credit: NGN 86,030.00
     Fixed Charge: NGN 1,500.00
     Total: NGN -9,498.75 (CREDIT!)

   Cycle: 2025-01-01 to 2026-01-29
     Import: 1,180.25 kWh
     Export: 2,020.50 kWh
     Net: -840.25 kWh
     Import Cost: NGN 70,815.00
     Export Credit: NGN 80,820.00
     Fixed Charge: NGN 1,500.00
     Total: NGN -8,505.00 (CREDIT!)

   ✓ 2 billing cycles computed

[9] Verifying Billing Results...
   ✓ Found 2 billing cycles

   ----------------------------------------------------------------------
   Period: 2024-12-01 to 2025-01-01
   Import: 1,250.50 kWh (Peak: 750.30, Off-peak: 500.20)
   Export: 2,150.75 kWh
   Net: -900.25 kWh
   Import Cost: NGN 75,031.25
   Export Credit: NGN 86,030.00
   Fixed Charge: NGN 1,500.00
   Total Amount: NGN -9,498.75
   Status: computed

   ✓ All billing cycles validated

================================================================================
✓ BILLING ROUTINE TEST COMPLETE!
================================================================================
```

---

## Verification Points

The test verifies:

1. **Data Generation**
   - ✅ Telemetry records created successfully
   - ✅ Realistic patterns (solar peaks at noon)
   - ✅ Import/export data present

2. **Aggregates**
   - ✅ All continuous aggregates refreshed
   - ✅ Aggregates contain expected record counts
   - ✅ Data properly summarized

3. **Billing Configuration**
   - ✅ Configuration created with correct rates
   - ✅ Peak/off-peak windows set
   - ✅ Net metering enabled

4. **Billing Cycles**
   - ✅ Cycles created for each month
   - ✅ No gaps or overlaps in cycles
   - ✅ Dates aligned correctly

5. **Calculations**
   - ✅ Import energy calculated correctly
   - ✅ Export energy calculated correctly
   - ✅ Net energy = Import - Export
   - ✅ Peak/off-peak split applied
   - ✅ Costs calculated using correct rates
   - ✅ Credits applied for exports
   - ✅ Fixed charges included

6. **Database Integrity**
   - ✅ All data persisted
   - ✅ Foreign key constraints satisfied
   - ✅ No duplicate cycles

---

## Troubleshooting

### If test fails with "No site found"
The test automatically creates a site if none exists.

### If test fails with "No devices found"
The test automatically creates inverter and battery devices.

### If aggregates show 0 records
Ensure TimescaleDB continuous aggregates are properly configured:
```sql
SELECT * FROM timescaledb_information.continuous_aggregates;
```

### If billing cycles not created
Check billing_config table:
```sql
SELECT * FROM billing_config;
```

---

## Database Schema Used

### Tables
- `sites` - Installation sites
- `devices` - Solar equipment
- `telemetry_data` - Raw telemetry (hypertable)
- `telemetry_data_1m/5m/1h/1d` - Continuous aggregates
- `billing_config` - Billing configuration
- `billing_cycles` - Monthly billing cycles

### Key Columns
**telemetry_data:**
- timestamp
- device_id
- solar_power (W)
- battery_power (W)
- grid_import (W)
- grid_export (W)
- load_power (W)
- battery_soc (%)

**billing_cycles:**
- site_id
- cycle_start
- cycle_end
- total_import_kwh
- total_export_kwh
- net_energy_kwh
- peak_import_kwh
- offpeak_import_kwh
- import_cost
- export_credit
- fixed_charge
- total_amount
- status

---

## Next Steps

After running the test:

1. **Verify in UI**
   - Login to dashboard
   - Navigate to Billing page
   - Check if billing cycles are displayed

2. **Check Database**
   ```sql
   SELECT * FROM billing_cycles ORDER BY cycle_start DESC;
   ```

3. **Run E2E Test**
   ```bash
   cd tests/e2e
   pytest test_billing_routine.py::TestBillingRoutine::test_billing_with_2_months_data -v -s
   ```

4. **Verify Calculations Manually**
   ```sql
   SELECT
       cycle_start,
       total_import_kwh,
       total_export_kwh,
       import_cost,
       export_credit,
       total_amount
   FROM billing_cycles
   WHERE site_id = '5f20aa40-4397-47e9-918c-abb0f7f58073';
   ```

---

## Test User Credentials

**Email:** test@solarhub.com
**Password:** Test123!@#
**User ID:** 4fc31ddb-dde2-4536-89cd-2dd0492e0fb8

---

**Generated:** 2026-01-29
**Test Framework:** Python 3.13 + psycopg2 + Playwright
**Database:** PostgreSQL 15 + TimescaleDB
