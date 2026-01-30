# Solar Hub E2E Test Plan
## Comprehensive Test Strategy with Priority Classification

**Last Updated:** 2026-01-29
**Framework:** Playwright Test with TypeScript
**Coverage Goal:** 80% of critical user journeys

---

## Priority Definitions

| Priority | Description | Run Frequency | Failure Impact |
|----------|-------------|---------------|----------------|
| **P0 - Critical** | Core functionality that blocks users from using the system | Every PR, Every deploy | Production blocker |
| **P1 - High** | Important features used daily by most users | Daily, Pre-release | Major issue |
| **P2 - Medium** | Secondary features, edge cases, admin functions | Weekly, Pre-release | Minor issue |
| **P3 - Low** | Nice-to-have features, rare scenarios | Monthly | Negligible |

---

## Test Suite Breakdown

### 1. Authentication & Authorization (@auth)

**Priority:** P0 (Critical) - Users cannot access system without working auth

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| AUTH-001 | Login with valid credentials | @smoke @critical | P0 | Standard user login flow |
| AUTH-002 | Login with invalid credentials | @smoke | P0 | Error handling for bad credentials |
| AUTH-003 | Token refresh on expiry | @critical | P0 | Automatic token refresh without logout |
| AUTH-004 | Logout clears session | @smoke | P0 | Complete session cleanup |
| AUTH-005 | Session persistence across tabs | @critical | P1 | Shared session state |
| AUTH-006 | Password reset flow | @regression | P1 | Email-based password reset |
| AUTH-007 | Email verification flow | @regression | P1 | New user email verification |
| AUTH-008 | Concurrent session handling | @regression | P2 | Multiple devices logged in |
| AUTH-009 | Role-based access control | @admin | P1 | Owner/Admin/Viewer permissions |
| AUTH-010 | Protected route redirection | @critical | P0 | Redirect to login when unauthenticated |

**Test Data Requirements:**
- Test users with different roles (owner, admin, viewer, installer)
- Valid/invalid credentials
- Expired tokens
- Multi-factor authentication tokens (future)

---

### 2. User Registration & Onboarding (@onboarding)

**Priority:** P0 (Critical) - First user experience must work flawlessly

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| ONBOARD-001 | New user registration | @smoke @critical | P0 | Complete registration flow |
| ONBOARD-002 | Registration with device serial | @smoke @critical | P0 | Auto-claim device during signup |
| ONBOARD-003 | Setup wizard - welcome step | @critical | P1 | Wizard initiates correctly |
| ONBOARD-004 | Setup wizard - profile step | @critical | P1 | User profile information |
| ONBOARD-005 | Setup wizard - device pairing | @critical | P0 | Device claim via wizard |
| ONBOARD-006 | Setup wizard - DISCO selection | @critical | P1 | Electricity provider selection |
| ONBOARD-007 | Setup wizard - savings goal | @regression | P2 | User goal configuration |
| ONBOARD-008 | Setup wizard - complete flow | @smoke @critical | P0 | End-to-end wizard completion |
| ONBOARD-009 | Setup wizard - skip option | @regression | P2 | Wizard skip functionality |
| ONBOARD-010 | Auto-create organization | @critical | P0 | "{firstname}'s Organization" created |
| ONBOARD-011 | Auto-create site | @critical | P0 | "My Home" site created |
| ONBOARD-012 | Registration validation | @regression | P1 | Email format, password strength |

**Test Data Requirements:**
- Unique email addresses (timestamp-based)
- Valid/invalid device serials
- DISCO provider list
- City/location data

---

### 3. Dashboard (@dashboard)

**Priority:** P0 (Critical) - Primary user interface

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| DASH-001 | Dashboard loads with real data | @smoke @critical | P0 | No mock/dummy data shown |
| DASH-002 | Power flow diagram displays | @smoke @critical | P0 | Animated energy flow |
| DASH-003 | Real-time telemetry updates | @critical | P0 | Values update every 5-10s |
| DASH-004 | Stats cards show accurate data | @critical | P0 | Energy, battery, grid stats |
| DASH-005 | Energy charts render | @smoke | P1 | Daily/weekly/monthly charts |
| DASH-006 | Battery status widget | @critical | P0 | SOC, power, status |
| DASH-007 | Widget customization | @regression | P1 | Add/remove/reorder widgets |
| DASH-008 | Dashboard preferences persistence | @critical | P1 | Layout saved across sessions |
| DASH-009 | Responsive layout (mobile) | @regression | P1 | Mobile viewport rendering |
| DASH-010 | Responsive layout (tablet) | @regression | P2 | Tablet viewport rendering |
| DASH-011 | Multi-device aggregation | @critical | P1 | Total power from all devices |
| DASH-012 | Offline state handling | @regression | P1 | Show last known data when offline |
| DASH-013 | Loading states | @regression | P2 | Skeleton loaders, spinners |
| DASH-014 | Error states | @regression | P1 | Error boundaries, retry options |
| DASH-015 | Empty state (no devices) | @regression | P2 | Onboarding prompt |

**Test Data Requirements:**
- Site with 1-3 devices
- Live telemetry stream
- Historical energy data (7-30 days)
- Various widget configurations

---

### 4. Device Management (@devices)

**Priority:** P1 (High) - Core functionality for managing solar systems

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| DEV-001 | List all devices | @smoke | P1 | Device inventory page |
| DEV-002 | Device detail view | @smoke | P1 | Individual device dashboard |
| DEV-003 | Claim orphan device | @critical | P0 | Link new device to site |
| DEV-004 | Release device | @admin | P1 | Unlink device from site |
| DEV-005 | Device status indicators | @critical | P1 | Online/offline/error states |
| DEV-006 | Device configuration | @regression | P2 | Settings and parameters |
| DEV-007 | Device commissioning | @critical | P1 | QR code/serial entry |
| DEV-008 | Multi-device site | @regression | P1 | Multiple inverters/batteries |
| DEV-009 | Device move between sites | @admin | P2 | Transfer device ownership |
| DEV-010 | Device telemetry history | @regression | P2 | Historical data access |
| DEV-011 | Device firmware info | @regression | P3 | Version, model, manufacturer |
| DEV-012 | Device alerts | @critical | P1 | Error notifications |

**Test Data Requirements:**
- Orphan devices (unclaimed)
- Devices in different states (online, offline, error)
- Multiple device types (inverter, battery, meter)
- QR codes and serial numbers

---

### 5. Billing & Tariffs (@billing)

**Priority:** P1 (High) - Key monetization and value proposition

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| BILL-001 | View current bill estimate | @smoke | P1 | Monthly bill projection |
| BILL-002 | Billing cycle creation | @critical | P1 | Monthly cycle generation |
| BILL-003 | Net metering calculations | @critical | P1 | Import/export credit |
| BILL-004 | Peak/off-peak pricing | @critical | P1 | Time-of-use rates |
| BILL-005 | Tariff plan selection | @smoke | P1 | DISCO tariff configuration |
| BILL-006 | Savings calculations | @smoke | P1 | Solar savings vs grid-only |
| BILL-007 | Export credit tracking | @regression | P1 | kWh exported value |
| BILL-008 | Billing history | @regression | P2 | Past billing cycles |
| BILL-009 | Custom tariff rates | @admin | P2 | Manual rate overrides |
| BILL-010 | Billing simulation | @regression | P2 | What-if scenarios |
| BILL-011 | Multi-currency support | @regression | P3 | NGN, PKR, USD |
| BILL-012 | Billing reports export | @regression | P3 | PDF/CSV downloads |

**Test Data Requirements:**
- 2-3 months of telemetry data
- DISCO tariff configurations
- Billing cycles with various import/export patterns
- Credit pool data

---

### 6. Analytics & Reports (@analytics)

**Priority:** P1 (High) - User insights and data visualization

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| ANAL-001 | Energy production chart | @smoke | P1 | Daily/weekly/monthly production |
| ANAL-002 | Energy consumption chart | @smoke | P1 | Load consumption patterns |
| ANAL-003 | Period comparison | @regression | P1 | Current vs previous period |
| ANAL-004 | Self-consumption rate | @regression | P1 | % of solar used vs exported |
| ANAL-005 | Grid dependency chart | @regression | P1 | Import/export trends |
| ANAL-006 | Battery performance | @regression | P2 | Charge/discharge cycles |
| ANAL-007 | Environmental impact | @regression | P2 | CO2 savings calculation |
| ANAL-008 | System efficiency | @regression | P2 | Performance metrics |
| ANAL-009 | Weather correlation | @regression | P3 | Generation vs weather |
| ANAL-010 | Export reports (CSV/PDF) | @regression | P2 | Data export functionality |

**Test Data Requirements:**
- 30+ days of historical telemetry
- Complete charge/discharge cycles
- Import/export data
- Weather data (future)

---

### 7. Alerts & Notifications (@alerts)

**Priority:** P1 (High) - Critical system monitoring

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| ALERT-001 | Alert list page | @smoke | P1 | View all alerts |
| ALERT-002 | Create alert rule | @admin | P1 | Configure alert conditions |
| ALERT-003 | Alert triggering | @critical | P1 | Alert fires when condition met |
| ALERT-004 | Alert notifications | @critical | P1 | In-app notifications |
| ALERT-005 | Alert acknowledgment | @regression | P1 | Mark alert as seen |
| ALERT-006 | Alert resolution | @regression | P1 | Mark alert as resolved |
| ALERT-007 | Alert severity levels | @regression | P2 | Info/warning/critical/error |
| ALERT-008 | Email alerts | @regression | P2 | Email notification delivery |
| ALERT-009 | SMS alerts | @regression | P3 | SMS notification (future) |
| ALERT-010 | Alert rule templates | @admin | P2 | Predefined alert conditions |
| ALERT-011 | Alert history | @regression | P2 | Past alerts log |
| ALERT-012 | Alert muting | @regression | P3 | Temporary alert suppression |

**Test Data Requirements:**
- Device with error conditions
- Alert rules with various thresholds
- Email/SMS delivery testing

---

### 8. Outages & Grid Monitoring (@outages)

**Priority:** P1 (High) - Pakistan-specific differentiator

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| OUTAGE-001 | Grid status indicator | @smoke | P1 | Online/offline display |
| OUTAGE-002 | Outage detection | @critical | P1 | Automatic outage logging |
| OUTAGE-003 | Outage duration tracking | @critical | P1 | Time tracking |
| OUTAGE-004 | Battery backup estimation | @critical | P1 | Remaining backup time |
| OUTAGE-005 | Outage history | @smoke | P1 | Past outages log |
| OUTAGE-006 | Monthly outage statistics | @regression | P1 | Aggregated outage metrics |
| OUTAGE-007 | Load shedding schedule | @regression | P2 | Predicted outages |
| OUTAGE-008 | Outage alerts | @critical | P1 | Notification when grid fails |
| OUTAGE-009 | Recovery notifications | @regression | P2 | Grid restored alert |
| OUTAGE-010 | Export outage reports | @regression | P3 | Outage data export |

**Test Data Requirements:**
- Simulated grid outages
- Battery discharge during outages
- Historical outage data

---

### 9. User & Role Management (@admin @users)

**Priority:** P1 (High) for admins, P2 for multi-user features

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| USER-001 | Invite user to organization | @admin | P1 | Send invitation email |
| USER-002 | Accept organization invitation | @regression | P1 | Join organization flow |
| USER-003 | Assign user role | @admin | P1 | Owner/admin/viewer/installer |
| USER-004 | Remove user from organization | @admin | P2 | Revoke access |
| USER-005 | Update user profile | @smoke | P1 | Edit name, email, preferences |
| USER-006 | Change password | @regression | P1 | Password update flow |
| USER-007 | Role-based dashboard views | @admin | P1 | Viewer sees read-only |
| USER-008 | Installer time-limited access | @admin | P2 | Auto-expiring installer role |
| USER-009 | User activity log | @admin | P3 | Audit trail |
| USER-010 | Multi-organization membership | @admin | P2 | User in multiple orgs |

**Test Data Requirements:**
- Users with different roles
- Organization with multiple members
- Invitation tokens
- Access expiry dates

---

### 10. Settings & Configuration (@settings)

**Priority:** P2 (Medium) - Important but not blocking core functionality

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| SETT-001 | Site configuration | @admin | P1 | Edit site details |
| SETT-002 | Notification preferences | @regression | P1 | Email/SMS/push settings |
| SETT-003 | Theme selection | @regression | P3 | Light/dark mode |
| SETT-004 | Language selection | @regression | P2 | Urdu/English (Phase 2) |
| SETT-005 | Unit preferences | @regression | P2 | kW/kWh vs W/Wh |
| SETT-006 | Timezone configuration | @regression | P2 | Correct time display |
| SETT-007 | Export user data | @regression | P3 | GDPR compliance |
| SETT-008 | Account deletion | @regression | P2 | Delete account flow |
| SETT-009 | Subscription management | @admin | P1 | Plan upgrade/downgrade |
| SETT-010 | Payment method | @admin | P1 | JazzCash/EasyPaisa |

**Test Data Requirements:**
- Site configurations
- User preferences
- Subscription plans
- Payment methods

---

### 11. Performance & Reliability (@performance @reliability)

**Priority:** P1 (High) - System must be fast and stable

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| PERF-001 | Dashboard load time | @performance | P1 | < 3s initial load |
| PERF-002 | API response times | @performance | P1 | < 1s for most endpoints |
| PERF-003 | Real-time data latency | @performance @critical | P0 | < 10s telemetry delay |
| PERF-004 | Large data set handling | @performance | P2 | 1 year of telemetry |
| PERF-005 | Concurrent user load | @performance | P2 | 100 concurrent users |
| PERF-006 | Network resilience | @reliability | P1 | 2G/3G performance |
| PERF-007 | Offline mode | @reliability | P1 | PWA offline functionality |
| PERF-008 | Cache effectiveness | @performance | P2 | Redis hit rate |
| PERF-009 | Memory leaks | @reliability | P2 | Extended session stability |
| PERF-010 | Database query optimization | @performance | P2 | Query execution time |

**Test Data Requirements:**
- Large telemetry datasets
- Slow network simulation
- Cache invalidation scenarios

---

### 12. Integration Tests (@integration)

**Priority:** P1 (High) - System-to-system communication

| Test ID | Test Name | Tags | Priority | Description |
|---------|-----------|------|----------|-------------|
| INTEG-001 | System A ↔ System B device claim | @critical | P0 | Cross-system device claiming |
| INTEG-002 | Redis telemetry cache | @critical | P0 | System B writes, System A reads |
| INTEG-003 | ESP32 device registration | @critical | P0 | Device self-registration |
| INTEG-004 | Modbus data ingestion | @critical | P1 | Protocol adapter communication |
| INTEG-005 | TimescaleDB aggregation | @critical | P1 | Continuous aggregate refresh |
| INTEG-006 | WebSocket live updates | @regression | P1 | Real-time push notifications |
| INTEG-007 | Email service integration | @regression | P2 | Transactional emails |
| INTEG-008 | Payment gateway | @admin | P1 | JazzCash/EasyPaisa |
| INTEG-009 | Weather API | @regression | P3 | Weather data integration |
| INTEG-010 | SMS gateway | @regression | P3 | SMS notifications |

**Test Data Requirements:**
- Mock device connections
- Simulated Modbus traffic
- Email/SMS service mocks
- Payment gateway sandbox

---

## Test Execution Strategy

### Smoke Tests (@smoke)
- **When:** Every PR, every deploy
- **Duration:** 5-10 minutes
- **Coverage:** P0 critical paths only
- **Test Count:** ~20 tests

### Regression Tests (@regression)
- **When:** Daily, pre-release
- **Duration:** 30-60 minutes
- **Coverage:** P0 + P1 + P2
- **Test Count:** ~150 tests

### Full Test Suite
- **When:** Weekly, major releases
- **Duration:** 2-3 hours
- **Coverage:** All tests (P0 + P1 + P2 + P3)
- **Test Count:** ~200+ tests

### Critical Tests (@critical)
- **When:** After critical bug fixes
- **Duration:** 15-20 minutes
- **Coverage:** P0 + selected P1
- **Test Count:** ~40 tests

---

## Test Environment Matrix

| Environment | Purpose | Data | Frequency |
|-------------|---------|------|-----------|
| **Local** | Development | Seeded demo data | On-demand |
| **CI** | Pull request validation | Fresh seed per run | Every PR |
| **Staging** | Pre-production validation | Production-like data | Daily |
| **Production** | Smoke tests only | Real data | Post-deploy |

---

## Test Data Management

### Seed Data Requirements
- 3 test users (owner, admin, viewer)
- 1 organization with 3 members
- 2 sites (single-device, multi-device)
- 4-5 devices (inverters, batteries, meters)
- 60 days of telemetry data
- 3 months of billing cycles
- Alert rules and triggered alerts
- Outage history

### Data Cleanup Strategy
- **Before each test:** Reset to known state (fixtures)
- **After test suite:** Full database cleanup
- **Isolated tests:** Use unique identifiers (timestamp, UUID)
- **Shared fixtures:** Reusable base data (DISCO list, tariffs)

---

## Success Criteria

✅ **80% test coverage** of critical user journeys
✅ **< 5% flakiness rate** (max 1 flaky test per 20 runs)
✅ **All P0 tests pass** before any production deploy
✅ **< 30 min regression suite** execution time
✅ **Zero P0/P1 test debt** (no disabled critical tests)
✅ **Cross-browser compatibility** (Chrome, Firefox, Safari)

---

## Risk Assessment

| Area | Risk Level | Mitigation |
|------|------------|------------|
| Real-time telemetry tests | High | Use mock device simulator |
| Database state management | Medium | Isolated test transactions |
| Network-dependent tests | Medium | Mock external APIs |
| Time-dependent tests | Medium | Use controllable time mocks |
| Payment gateway tests | Low | Use sandbox environment |

---

**Document Version:** 1.0
**Review Cycle:** Quarterly
**Owner:** QA Team Lead
