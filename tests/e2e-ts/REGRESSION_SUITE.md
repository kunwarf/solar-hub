# E2E Regression Test Suite

**Version:** 1.0.0
**Last Updated:** 2026-01-30
**Environment:** Local Development

---

## Overview

Comprehensive end-to-end regression test suite for Solar Hub platform covering all critical user journeys, features, and integrations.

## Test Environment Setup

### Prerequisites

1. **System A (Main API)** running on `http://localhost:8000`
2. **System B (Device Communication)** running on `http://localhost:8001`
3. **Frontend (React App)** running on `http://localhost:8081`
4. **PostgreSQL Database** running on `localhost:5432`
5. **Redis** running on `localhost:6379`

### Quick Start

```bash
# Install dependencies
cd tests/e2e-ts
npm install

# Run full regression suite
npm run regression:local

# Run specific test categories
npm run regression:smoke      # Critical smoke tests only
npm run regression:critical   # High-priority tests
npm run regression:auth       # Authentication tests
npm run regression:devices    # Device management tests
npm run regression:dashboard  # Dashboard tests
npm run regression:billing    # Billing tests

# View results
npm run regression:report
```

---

## Test Categories

### 🔥 Smoke Tests (@smoke)
**Priority:** P0 (Must Pass)
**Duration:** ~5 minutes
**Frequency:** Every commit

Critical tests that verify core functionality works. If these fail, the build is broken.

**Coverage:**
- User can log in
- Dashboard loads
- Devices list displays
- Basic navigation works
- API health checks pass

### ⚡ Critical Tests (@critical)
**Priority:** P1 (High)
**Duration:** ~15 minutes
**Frequency:** Daily

Tests for core business features that users depend on daily.

**Coverage:**
- Device settings (hybrid architecture)
- Real-time telemetry display
- Billing calculations
- Alert notifications
- User management
- Data persistence

### 🔄 Regression Tests (@regression)
**Priority:** P2 (Medium)
**Duration:** ~45 minutes
**Frequency:** Before releases

Comprehensive tests covering all features and edge cases.

**Coverage:**
- All UI components
- All API endpoints
- All user workflows
- Error handling
- Edge cases
- Cross-browser compatibility

---

## Test Suite Breakdown

### 1. Authentication Tests (`tests/auth/`)

| Test File | Tests | Tags | Priority |
|-----------|-------|------|----------|
| `login.spec.ts` | 8 | @smoke, @critical | P0 |
| `signup.spec.ts` | 6 | @regression | P2 |

**Coverage:**
- ✅ User login with valid credentials
- ✅ Login failure with invalid credentials
- ✅ Password reset flow
- ✅ Session persistence
- ✅ Auto-logout on token expiration
- ✅ Multi-factor authentication (if enabled)
- ✅ User signup
- ✅ Email verification

---

### 2. Dashboard Tests (`tests/dashboard/`)

| Test File | Tests | Tags | Priority |
|-----------|-------|------|----------|
| `dashboard.spec.ts` | 12 | @smoke, @critical | P0 |
| `dashboard-data-validation.spec.ts` | 8 | @critical | P1 |
| `dashboard-preferences.spec.ts` | 6 | @regression | P2 |

**Coverage:**
- ✅ Dashboard loads with correct data
- ✅ Energy flow visualization
- ✅ Real-time telemetry updates
- ✅ Chart rendering
- ✅ Widget customization
- ✅ Layout preferences
- ✅ Data refresh
- ✅ Date range filters
- ✅ Export functionality
- ✅ Responsive design

---

### 3. Device Management Tests (`tests/devices/`)

| Test File | Tests | Tags | Priority |
|-----------|-------|------|----------|
| `device-list.spec.ts` | 10 | @smoke | P0 |
| `device-management.spec.ts` | 15 | @critical | P1 |
| `device-settings.spec.ts` | 12 | @critical | P1 |
| `device-settings-hybrid.spec.ts` | 12 | @critical, @cache | P0 |

**Coverage:**
- ✅ Device list display
- ✅ Device search and filters
- ✅ Device details view
- ✅ Device status indicators
- ✅ Device commissioning
- ✅ Device claiming
- ✅ **Hybrid Settings Architecture:**
  - ✅ localStorage caching
  - ✅ Device command queries
  - ✅ Database fallback
  - ✅ Offline graceful degradation
  - ✅ Status indicators (Live/Offline/Backup)
  - ✅ Background polling
  - ✅ Multi-tab sync
  - ✅ Settings persistence
- ✅ Configuration by device type
- ✅ Settings save/reset
- ✅ Device deletion

---

### 4. Billing Tests (`tests/billing/`)

| Test File | Tests | Tags | Priority |
|-----------|-------|------|----------|
| `billing.spec.ts` | 14 | @critical | P1 |

**Coverage:**
- ✅ Billing summary display
- ✅ Net metering calculations
- ✅ Monthly bill breakdown
- ✅ Energy credits tracking
- ✅ Tariff configuration
- ✅ Usage history
- ✅ Cost projections
- ✅ Export billing reports
- ✅ Payment history
- ✅ Invoice generation

---

### 5. Settings Tests (`tests/settings/`)

| Test File | Tests | Tags | Priority |
|-----------|-------|------|----------|
| `settings.spec.ts` | 10 | @regression | P2 |

**Coverage:**
- ✅ User profile management
- ✅ System preferences
- ✅ Notification settings
- ✅ Theme switching (light/dark)
- ✅ Language selection
- ✅ Timezone configuration
- ✅ Password change
- ✅ Account deletion
- ✅ Privacy settings

---

### 6. Outages Tests (`tests/outages/`)

| Test File | Tests | Tags | Priority |
|-----------|-------|------|----------|
| `outages.spec.ts` | 8 | @regression | P2 |

**Coverage:**
- ✅ Outage history display
- ✅ Outage notifications
- ✅ Outage detection
- ✅ Duration tracking
- ✅ Frequency analysis
- ✅ Financial impact calculation
- ✅ Outage alerts

---

### 7. Analytics Tests (`tests/analytics/`)

| Test File | Tests | Tags | Priority |
|-----------|-------|------|----------|
| `analytics.spec.ts` | 10 | @regression | P2 |

**Coverage:**
- ✅ Energy production trends
- ✅ Consumption patterns
- ✅ Efficiency metrics
- ✅ Cost savings analysis
- ✅ Environmental impact
- ✅ Comparative analysis
- ✅ Report generation
- ✅ Chart interactions

---

### 8. Admin Tests (`tests/admin/`)

| Test File | Tests | Tags | Priority |
|-----------|-------|------|----------|
| `user-management.spec.ts` | 12 | @critical | P1 |

**Coverage:**
- ✅ User list display
- ✅ User creation
- ✅ Role assignment
- ✅ Permission management
- ✅ User deactivation
- ✅ Bulk operations
- ✅ Audit logs
- ✅ Access control

---

## Test Execution Strategy

### Local Development

```bash
# Full regression suite (all tests)
npm run regression:local

# Smoke tests only (quick validation)
npm run regression:local:smoke

# Critical tests (core features)
npm run regression:local:critical

# Run with UI mode (debugging)
npm run regression:local:ui

# Run specific module
npm run regression:devices
```

### Test Execution Order

1. **Setup Phase** (`global-setup.ts`)
   - Create test users
   - Seed test data
   - Authenticate users
   - Generate auth tokens

2. **Test Execution**
   - Tests run in parallel across workers
   - Each test is independent
   - Shared authentication state

3. **Teardown Phase** (`global-teardown.ts`)
   - Clean up test data
   - Close connections
   - Generate reports

---

## Test Data Management

### Seeding Test Data

```bash
# Seed devices, users, and sample data
npm run seed:test-data
```

### Test Data Cleanup

```bash
# Clean up test data after suite
npm run cleanup:test-data
```

### Test Database

- **Name:** `solar_hub_dev`
- **Isolated:** Yes (no production data)
- **Reset:** Before each full regression run
- **Backup:** Automated before destructive tests

---

## Reporting & Artifacts

### Test Reports

**HTML Report:** `test-results/regression-report/index.html`
- Visual test results
- Screenshots on failure
- Test execution timeline
- Failure analysis

**JSON Report:** `test-results/regression-results.json`
- Machine-readable results
- CI/CD integration
- Metrics tracking

**JUnit XML:** `test-results/regression-junit.xml`
- Standard format
- CI tool compatibility

### Artifacts

**Screenshots:** `test-results/regression-artifacts/`
- Captured on test failure
- Shows exact UI state

**Videos:** `test-results/regression-artifacts/`
- Full test playback
- Enabled for failed tests

**Traces:** `test-results/regression-artifacts/`
- Detailed execution trace
- Network activity
- Console logs
- DOM snapshots

---

## Performance Benchmarks

### Expected Test Duration

| Suite | Tests | Duration | Browsers |
|-------|-------|----------|----------|
| Smoke | ~15 | 5 min | 1 |
| Critical | ~50 | 15 min | 1 |
| Regression | ~110 | 45 min | 1 |
| Full Suite | ~110 | 120 min | 3 |

### Pass Rate Targets

- **Smoke Tests:** 100% pass required
- **Critical Tests:** ≥95% pass required
- **Regression Tests:** ≥90% pass acceptable

---

## Troubleshooting

### Common Issues

**1. Tests fail with "baseURL not responding"**
```bash
# Ensure all services are running
# System A: http://localhost:8000/health
# System B: http://localhost:8001/health
# Frontend: http://localhost:8081
```

**2. Authentication failures**
```bash
# Check test user credentials in .env.local
# Ensure users exist in database
# Regenerate auth tokens
```

**3. Device tests fail with "Device Not Found"**
```bash
# Seed test devices
npm run seed:devices
```

**4. Timeouts**
```bash
# Increase timeout in regression-suite.config.ts
# Check network connectivity
# Verify API response times
```

**5. Flaky tests**
```bash
# Run specific test in debug mode
npm run regression:local:debug -- tests/path/to/test.spec.ts

# Check for race conditions
# Add explicit waits
# Review test isolation
```

---

## Test Maintenance

### Adding New Tests

1. Create test file in appropriate directory
2. Add test tags (@smoke, @critical, @regression)
3. Follow page object pattern
4. Update this document
5. Add to CI pipeline

### Updating Tests

1. When feature changes, update corresponding tests
2. Keep page objects in sync with UI
3. Update test data if schema changes
4. Maintain backward compatibility

### Deprecating Tests

1. Mark test with `test.skip()` and reason
2. Create ticket for removal/update
3. Remove after feature removal confirmed

---

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Regression Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npm ci
      - run: npm run regression:local
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: test-results
          path: test-results/
```

---

## Metrics & KPIs

### Track Over Time

- ✅ Test execution time
- ✅ Pass/fail rates
- ✅ Flaky test identification
- ✅ Code coverage (frontend)
- ✅ API endpoint coverage
- ✅ Bug detection rate
- ✅ Time to detection (TTD)

---

## Best Practices

1. ✅ **Independence:** Each test should be independent
2. ✅ **Idempotence:** Tests can run multiple times safely
3. ✅ **Speed:** Keep tests fast, use parallel execution
4. ✅ **Clarity:** Test names describe what they verify
5. ✅ **Stability:** Avoid flaky tests, use proper waits
6. ✅ **Maintainability:** Use page objects, avoid duplication
7. ✅ **Coverage:** Test happy paths AND edge cases
8. ✅ **Data:** Clean up test data, don't pollute DB

---

## Support

**Questions?** Contact QA team
**Bug Reports:** Create GitHub issue with test name and trace
**Feature Requests:** Discuss in team meeting

---

**Last Regression Run:** TBD
**Status:** ✅ Ready for execution
**Next Review:** After first full run
