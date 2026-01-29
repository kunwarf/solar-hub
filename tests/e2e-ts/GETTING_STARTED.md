# Getting Started with Playwright E2E Tests

## Quick Start Guide

### 1. Install Dependencies

```bash
cd tests/e2e-ts

# Install Node.js dependencies
npm install

# Install Playwright browsers
npx playwright install
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env.test

# Edit .env.test with your test user credentials
# Make sure you have test users created in your Solar Hub instance
```

Example `.env.test`:
```bash
BASE_URL=http://localhost:8081
API_SYSTEM_A_URL=http://localhost:8000
API_SYSTEM_B_URL=http://localhost:8001

OWNER_EMAIL=owner@solarhub.com
OWNER_PASSWORD=Owner123!@#

ADMIN_EMAIL=admin@solarhub.com
ADMIN_PASSWORD=Admin123!@#

VIEWER_EMAIL=viewer@solarhub.com
VIEWER_PASSWORD=Viewer123!@#
```

### 3. Start Solar Hub Services

Make sure all services are running:

```bash
# Frontend (port 8081)
cd frontend && npm run dev

# System A API (port 8000)
cd system_a && uvicorn app.main:app --reload --port 8000

# System B API (port 8001)
cd system_b && uvicorn app.main:app --reload --port 8001

# Database (port 5433)
# PostgreSQL should be running

# Redis (port 6379)
# Redis should be running
```

Verify services:
- Frontend: http://localhost:8081
- System A: http://localhost:8000/docs
- System B: http://localhost:8001/docs

### 4. Run Your First Test

```bash
# Run all tests
npm test

# Run smoke tests only (5-10 minutes)
npm run test:smoke

# Run with UI mode (recommended for first time)
npm run test:ui

# Run in headed mode (see browser)
npm run test:headed

# Run specific test file
npx playwright test tests/auth/login.spec.ts

# Debug mode
npx playwright test --debug
```

### 5. View Test Results

```bash
# After test run, view HTML report
npm run report

# Report will open in browser automatically
```

## Project Structure Overview

```
tests/e2e-ts/
├── tests/                    # Test files
│   └── auth/
│       └── login.spec.ts    # Example test
├── pages/                    # Page Object Models
│   ├── base/
│   │   └── BasePage.ts      # Base page class
│   └── auth/
│       └── LoginPage.ts     # Login page object
├── fixtures/                 # Custom fixtures
│   └── auth.fixture.ts      # Auth fixtures
├── utils/                    # Utilities
│   └── api/
│       └── auth.api.ts      # API helpers
├── playwright.config.ts      # Main config
├── global-setup.ts          # Global setup
├── global-teardown.ts       # Global teardown
├── package.json             # Dependencies
├── tsconfig.json            # TypeScript config
└── .env.test               # Environment variables
```

## Writing Your First Test

Create a new test file in `tests/` directory:

```typescript
// tests/dashboard/power-flow.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Dashboard - Power Flow', { tag: '@dashboard' }, () => {

  test('should display power flow diagram', {
    tag: ['@smoke', '@critical']
  }, async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard');

    // Wait for power flow diagram
    await expect(page.getByTestId('power-flow-diagram')).toBeVisible();

    // Verify solar panel is shown
    await expect(page.getByTestId('solar-panel-icon')).toBeVisible();
  });
});
```

## Common Commands

### Run tests by tag
```bash
# Smoke tests (critical path)
npm run test:smoke

# Critical tests only
npm run test:critical

# Regression tests
npm run test:regression

# Auth module tests
npx playwright test --grep @auth

# Dashboard tests
npx playwright test --grep @dashboard
```

### Run tests by browser
```bash
# Chromium only
npm run test:chromium

# Firefox only
npm run test:firefox

# WebKit (Safari) only
npm run test:webkit

# Mobile Chrome
npm run test:mobile
```

### Debug tests
```bash
# Debug mode (step through)
npx playwright test --debug

# Debug specific test
npx playwright test tests/auth/login.spec.ts --debug

# Run with trace (record everything)
npx playwright test --trace on

# Show trace viewer
npx playwright show-trace test-results/.../trace.zip
```

## Troubleshooting

### Tests fail with "No auth token found"

**Problem:** Global setup didn't run or failed.

**Solution:**
1. Check that test users exist in database
2. Verify credentials in `.env.test`
3. Check that services are running
4. Run global setup manually:
   ```bash
   npx playwright test --project=setup
   ```

### Browser not launching

**Problem:** Playwright browsers not installed.

**Solution:**
```bash
npx playwright install
```

### Port conflicts

**Problem:** Services running on different ports.

**Solution:** Update ports in `.env.test`:
```bash
BASE_URL=http://localhost:YOUR_FRONTEND_PORT
API_SYSTEM_A_URL=http://localhost:YOUR_API_PORT
```

### Timeout errors

**Problem:** Services are slow or not responding.

**Solution:**
1. Check all services are running
2. Increase timeout in `playwright.config.ts`:
   ```typescript
   timeout: 60 * 1000, // 60 seconds
   ```

## Next Steps

1. **Read Documentation:**
   - [TEST_PLAN.md](./TEST_PLAN.md) - Complete test plan
   - [AUTH_PATTERNS.md](./AUTH_PATTERNS.md) - Authentication patterns
   - [ANTI_FLAKINESS_PATTERNS.md](./ANTI_FLAKINESS_PATTERNS.md) - Avoid flaky tests
   - [NAMING_AND_TAGGING.md](./NAMING_AND_TAGGING.md) - Conventions

2. **Write Page Objects:**
   - Create page objects for each page/component
   - Extend `BasePage` class
   - Follow naming conventions

3. **Add More Tests:**
   - Start with critical user journeys (@smoke @critical)
   - Follow test plan priorities (P0 → P1 → P2)
   - Tag tests appropriately

4. **Setup CI/CD:**
   - Add GitHub Actions workflow
   - Run smoke tests on every PR
   - Run regression tests nightly

## Support

- **Documentation:** See all `.md` files in this directory
- **Examples:** Check `tests/auth/login.spec.ts`
- **Issues:** Report to QA team
- **Questions:** Team Slack channel

---

**Happy Testing!** 🎭
