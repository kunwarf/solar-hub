# Solar Hub E2E Test Cases

This document describes all end-to-end test cases for the Solar Hub frontend application using Playwright.

## Test Environment

- **Frontend URL:** http://localhost:8080
- **System A API:** http://localhost:8000
- **System B API:** http://localhost:8001
- **Database:** PostgreSQL on localhost:5433

## Test Categories

---

## 1. Authentication Tests

Tests for login, signup, and session management.

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| 1.1 | `test_login_page_loads` | Verify login page renders with email/password fields | Login form visible with email, password inputs and submit button |
| 1.2 | `test_login_with_valid_credentials` | Login with valid credentials (admin@demo.com) | Redirect to dashboard, user session created |
| 1.3 | `test_login_with_invalid_email` | Login with non-existent email | Error message displayed |
| 1.4 | `test_login_with_invalid_password` | Login with wrong password | Error message displayed |
| 1.5 | `test_login_empty_fields_validation` | Submit empty login form | Validation errors for required fields |
| 1.6 | `test_login_stores_token` | After successful login | JWT token stored in localStorage |
| 1.7 | `test_logout_clears_session` | Click logout button | Tokens cleared, redirect to login page |
| 1.8 | `test_signup_page_loads` | Navigate to signup tab | Signup form with all fields visible |
| 1.9 | `test_signup_password_validation` | Enter weak password | Password complexity error shown |

---

## 2. Setup Wizard Tests

Tests for the onboarding setup wizard flow.

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| 2.1 | `test_wizard_welcome_step` | Verify welcome step loads | Welcome message, "Get Started" and "Skip" buttons visible |
| 2.2 | `test_wizard_profile_step` | Fill profile information | First name, last name, city dropdown, contact preference options |
| 2.3 | `test_wizard_device_step` | Enter device code manually | Device code input accepts alphanumeric code |
| 2.4 | `test_wizard_connection_test` | Run connection test | 3-step progress: connecting, verifying, establishing |
| 2.5 | `test_wizard_tariff_step` | Select electricity provider | DISCO dropdown with 10 options, rate displayed |
| 2.6 | `test_wizard_goal_step` | Set monthly savings goal | Slider from Rs. 1,000 to Rs. 50,000 |
| 2.7 | `test_wizard_complete_flow` | Complete all wizard steps | Wizard closes, dashboard shown |
| 2.8 | `test_wizard_skip_option` | Skip wizard from welcome | Wizard closes immediately |
| 2.9 | `test_wizard_city_disco_suggestion` | Select city in profile | Matching DISCO auto-suggested in tariff step |

---

## 3. Dashboard Data Validation Tests

Tests to verify dashboard displays real data from backend database (no mock/dummy data).

| Test ID | Test Name | Description | DB Validation |
|---------|-----------|-------------|---------------|
| 3.1 | `test_dashboard_shows_real_site_name` | Site name matches database | Query `sites.name` |
| 3.2 | `test_dashboard_device_count_matches_db` | Device count is accurate | Count from `devices` table |
| 3.3 | `test_dashboard_device_names_match_db` | Device names displayed correctly | Query `devices.name` |
| 3.4 | `test_power_flow_shows_real_data` | Power values from real telemetry | Query `telemetry_raw` in System B |
| 3.5 | `test_stats_energy_today_matches_db` | Today's energy matches aggregation | Sum energy metrics |
| 3.6 | `test_battery_soc_matches_db` | Battery SOC matches telemetry | Query latest `battery_soc` |
| 3.7 | `test_devices_page_lists_all_db_devices` | All DB devices shown | Compare device list |
| 3.8 | `test_device_status_matches_db` | Online/offline status correct | Query `devices.status` |

---

## 3b. System Overview Widget Tests

Tests to verify the System Overview stats cards display correct data.

| Test ID | Test Name | Description | Validation |
|---------|-----------|-------------|------------|
| 3.9 | `test_system_overview_shows_production` | Today's production is displayed | kWh production value visible |
| 3.10 | `test_system_overview_shows_savings` | Savings information displayed | $ or bill estimate visible |
| 3.11 | `test_system_overview_shows_battery_backup` | Backup time is displayed | Hours/battery backup visible |
| 3.12 | `test_system_overview_shows_environmental_impact` | CO2 saved is displayed | kg CO2 or environmental stats visible |
| 3.13 | `test_system_overview_shows_self_consumption` | Self-consumption % displayed | Percentage value visible |
| 3.14 | `test_system_overview_shows_all_stat_cards` | All stat cards rendered | At least 3 stat cards visible |

---

## 4. Outages Page Data Validation

Tests for the Outages management page.

| Test ID | Test Name | Description | Validation |
|---------|-----------|-------------|------------|
| 4.1 | `test_outages_page_shows_grid_status` | Grid status indicator displayed | Online/Offline state visible |
| 4.2 | `test_outages_monthly_stats_displayed` | Monthly statistics shown | Total outages, duration, etc. |
| 4.3 | `test_outages_history_table_loads` | History table renders | Table with outage records |

---

## 5. Analytics Page Data Validation

Tests for the Analytics page charts and data.

| Test ID | Test Name | Description | Validation |
|---------|-----------|-------------|------------|
| 5.1 | `test_analytics_energy_chart_has_data` | Energy chart shows data | Chart has data points |
| 5.2 | `test_analytics_comparison_chart_loads` | Comparison chart renders | Current vs previous period |
| 5.3 | `test_analytics_period_selector_works` | Period selector changes data | Day/Week/Month options |

---

## 6. Billing Page Data Validation

Tests for the Billing page.

| Test ID | Test Name | Description | Validation |
|---------|-----------|-------------|------------|
| 6.1 | `test_billing_shows_tariff_rate` | Tariff rate displayed | Rate in PKR/kWh |
| 6.2 | `test_billing_estimated_savings` | Estimated savings shown | Monthly savings amount |
| 6.3 | `test_billing_export_credits` | Export credits displayed | kWh exported value |

---

## 7. Real-Time Data Tests

Tests for real-time data updates.

| Test ID | Test Name | Description | Validation |
|---------|-----------|-------------|------------|
| 7.1 | `test_dashboard_updates_with_new_telemetry` | UI updates with new data | Values change after simulator sends data |
| 7.2 | `test_power_values_change_over_time` | Power readings are dynamic | Values not static over 30 seconds |

---

## Running Tests

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific test category
pytest tests/e2e/test_auth.py -v
pytest tests/e2e/test_wizard.py -v
pytest tests/e2e/test_dashboard_data.py -v

# Run with headed browser (visible)
pytest tests/e2e/ -v --headed

# Run with slow motion for debugging
pytest tests/e2e/ -v --headed --slowmo=500
```

## Prerequisites

1. All services running:
   - Frontend (localhost:8080)
   - System A (localhost:8000)
   - System B (localhost:8001)
   - PostgreSQL (localhost:5433)
   - Redis (localhost:6379)

2. Demo data seeded in database

3. Device simulator running for real-time tests

## Test Data

- **Test User:** admin@demo.com
- **Test Organization:** Demo Organization
- **Test Site:** Demo Solar Site
- **Test Devices:** Inverter 1 (DEMO001), Inverter 2 (DEMO002)
