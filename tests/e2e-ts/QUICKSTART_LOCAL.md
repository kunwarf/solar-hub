# Quick Start: Running E2E Tests Locally

**Created:** 2026-01-30
**Purpose:** Run the full E2E regression suite against your local development environment

---

## ⚡ TL;DR - Get Started in 5 Minutes

```bash
# 1. Ensure services are running
curl http://localhost:8000/health  # System A (API)
curl http://localhost:8081          # Frontend

# 2. Fix frontend API configuration
# Edit frontend/.env and set:
#   VITE_API_BASE_URL=http://localhost:8000/api/v1
# Then restart frontend server

# 3. Install test dependencies
cd tests/e2e-ts
npm install

# 4. Run smoke tests
npm run regression:local:smoke

# 5. View results
npm run regression:report
```

---

## 📋 Prerequisites Checklist

Before running tests, ensure:

- [ ] **System A** is running on `http://localhost:8000`
  ```bash
  curl http://localhost:8000/health
  # Should return: {"status":"healthy",...}
  ```

- [ ] **Frontend** is running on `http://localhost:8081`
  ```bash
  curl http://localhost:8081
  # Should return HTML
  ```

- [ ] **System B** (optional, for device tests) on `http://localhost:8001`

- [ ] **Frontend API configuration** is correct:
  ```bash
  # In frontend/.env:
  VITE_API_BASE_URL=http://localhost:8000/api/v1
  VITE_WS_URL=ws://localhost:8000/ws
  ```
  ⚠️ **IMPORTANT:** Restart frontend after changing .env

- [ ] **Test user** exists in database

---

## 🔧 Initial Setup

### Step 1: Install Dependencies

```bash
cd tests/e2e-ts
npm install
npx playwright install  # Install browsers
```

### Step 2: Configure Test Environment

```bash
# Copy local environment template
cp .env.local .env.test

# Verify configuration
cat .env.test | grep BASE_URL
# Should show: BASE_URL=http://localhost:8081
```

### Step 3: Create Test User

The test user credentials are:

```
Email: e2e.test@testing.com
Password: Test@123456
Role: owner
```

This user has already been created. If needed, recreate with:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email":"e2e.test@testing.com",
    "password":"Test@123456",
    "first_name":"E2E",
    "last_name":"Tester"
  }'
```

Verify login works:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e.test@testing.com","password":"Test@123456"}'
# Should return access_token
```

---

## 🚀 Running Tests

### Run Full Regression Suite

```bash
npm run regression:local
```

**Expected Duration:** ~45 minutes
**Tests:** ~110 tests
**Coverage:** All features

### Run Smoke Tests (Recommended for Quick Validation)

```bash
npm run regression:local:smoke
```

**Expected Duration:** ~5 minutes
**Tests:** ~27 critical smoke tests
**Coverage:** Core functionality

### Run Critical Tests

```bash
npm run regression:local:critical
```

**Expected Duration:** ~15 minutes
**Tests:** ~50 high-priority tests
**Coverage:** Main features

### Run Specific Test Modules

```bash
# Authentication tests
npm run regression:auth

# Device management tests
npm run regression:devices

# Dashboard tests
npm run regression:dashboard

# Billing tests
npm run regression:billing

# Settings tests
npm run regression:settings

# Outages tests
npm run regression:outages

# Analytics tests
npm run regression:analytics

# Admin/user management tests
npm run regression:admin
```

### Run with UI (for Debugging)

```bash
# Show browser while tests run
npm run regression:local:headed

# Interactive Playwright UI mode
npm run regression:local:ui
```

---

## 📊 Viewing Results

### HTML Report (Recommended)

```bash
npm run regression:report
```

Opens interactive HTML report in browser showing:
- Test results with pass/fail status
- Screenshots of failures
- Video recordings
- Execution timeline
- Error stack traces

### Console Output

Results are printed to console during test run:
```
Running 27 tests using 4 workers

  ✓ [chromium] › auth/login.spec.ts:31 should login successfully (5s)
  ✗ [chromium] › devices/device-list.spec.ts:22 should load device list (10s)
  ...

25 passed (2.1m)
2 failed
```

### Artifacts Location

All test artifacts are saved to:

```
tests/e2e-ts/test-results/
├── regression-artifacts/     # Screenshots, videos, traces
├── regression-report/         # HTML report
├── regression-results.json   # Machine-readable results
└── regression-junit.xml      # CI-compatible format
```

---

## 🐛 Troubleshooting

### ❌ Network Error During Login

**Symptoms:**
- Tests fail with "Network Error"
- Screenshot shows red "Network Error" message on login page

**Root Cause:**
Frontend is trying to connect to wrong API port (e.g., 8002 instead of 8000)

**Fix:**
1. Edit `frontend/.env`:
   ```env
   VITE_API_BASE_URL=http://localhost:8000/api/v1
   VITE_WS_URL=ws://localhost:8000/ws
   ```
2. Restart frontend server:
   ```bash
   cd frontend
   npm run dev  # or however you start it
   ```
3. Rerun tests

---

### ❌ "Not authenticated: No token found in localStorage"

**Symptoms:**
- All tests fail immediately
- Error message: "Not authenticated: No token found"

**Root Cause:**
Global setup failed to authenticate test user

**Fix:**
1. Verify test user exists:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"e2e.test@testing.com","password":"Test@123456"}'
   ```
2. If login fails, recreate user (see Step 3 above)
3. Clear auth state:
   ```bash
   cd tests/e2e-ts
   rm -rf test-results/.auth
   ```
4. Rerun tests

---

### ❌ "Invalid email or password"

**Symptoms:**
- Global setup fails
- Error shows "Invalid email or password"

**Root Cause:**
Test user doesn't exist or has different password

**Fix:**
1. Create/recreate test user (see Step 3 above)
2. Update `tests/e2e-ts/.env.test` with correct credentials
3. Rerun tests

---

### ❌ Tests Timeout

**Symptoms:**
- Tests hang and timeout after 30+ seconds
- No progress shown

**Root Cause:**
- Services not running
- Services too slow
- Network issues

**Fix:**
1. Check all services are running:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8081
   ```
2. Reduce parallel workers in `.env.test`:
   ```env
   WORKERS=2
   ```
3. Increase timeout in `regression-suite.config.ts` (line 23):
   ```typescript
   timeout: 120 * 1000, // 2 minutes
   ```

---

### ❌ "Device Not Found" in Device Tests

**Symptoms:**
- Device tests fail with "Device Not Found" error

**Root Cause:**
No devices exist in the test database

**Fix:**
- This is expected if you have no devices in local DB
- Tests will skip gracefully
- To add devices, use the frontend device commissioning flow

---

## 📈 Test Coverage

### Smoke Tests (@smoke) - 27 tests

Critical tests that must pass:
- User can log in ✓
- Dashboard loads ✓
- Devices list displays ✓
- Navigation works ✓
- API health checks pass ✓

### Critical Tests (@critical) - 50+ tests

Core business features:
- Device settings (hybrid architecture) ✓
- Real-time telemetry display ✓
- Billing calculations ✓
- Alert notifications ✓
- User management ✓

### Regression Tests (@regression) - 110+ tests

Comprehensive coverage:
- All UI components ✓
- All API endpoints ✓
- All user workflows ✓
- Error handling ✓
- Edge cases ✓

---

## 📁 Important Files

### Configuration
- `regression-suite.config.ts` - Regression test configuration
- `.env.test` / `.env.local` - Environment variables
- `global-setup.ts` - Pre-test authentication
- `playwright.config.ts` - Main Playwright config

### Documentation
- `REGRESSION_SUITE.md` - Comprehensive test suite documentation
- `QUICKSTART_LOCAL.md` - This file

### Scripts
- `scripts/create-test-users.py` - Create test users
- `scripts/seed-test-users.ts` - Alternative seed script

---

## 🎯 Next Steps

### After First Successful Run

1. ✅ Review test results in HTML report
2. ✅ Fix any failing tests (if applicable)
3. ✅ Add regression tests to your workflow

### Daily Development Workflow

```bash
# Before committing code
npm run regression:local:smoke

# Before pushing to main
npm run regression:local:critical

# Before releases
npm run regression:local
```

### CI/CD Integration

Add to `.github/workflows/e2e-tests.yml`:

```yaml
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
          path: tests/e2e-ts/test-results/
```

---

## 🆘 Getting Help

**Test Failures:**
1. Check HTML report for screenshots and error details
2. Check trace files for step-by-step execution
3. Run specific test in debug mode:
   ```bash
   npm run regression:local:debug -- tests/path/to/test.spec.ts
   ```

**Setup Issues:**
1. Verify all prerequisites are met
2. Check service health endpoints
3. Review troubleshooting section above

**Questions:**
- See comprehensive documentation: `REGRESSION_SUITE.md`
- Create GitHub issue with test name and trace

---

**Status:** ✅ Ready for Local Testing
**Last Updated:** 2026-01-30
**Test User:** e2e.test@testing.com / Test@123456
