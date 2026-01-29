# Authentication Patterns & Role-Based Sessions

## Overview

This document describes best practices for handling authentication in Playwright tests, including:
1. Reusing authenticated sessions (storageState)
2. Role-based test fixtures (owner, admin, viewer, installer)
3. Avoiding repeated logins
4. Fast test execution
5. Isolated test state

---

## The Problem

**Naive Approach** (slow, brittle):
```typescript
// ❌ DON'T: Login in every test
test('should view dashboard', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[data-testid="email"]', 'test@example.com');
  await page.fill('[data-testid="password"]', 'password');
  await page.click('[data-testid="submit"]');
  await page.waitForURL('/dashboard');

  // Actual test starts here...
});

// Problems:
// 1. Every test waits for login (5-10s overhead each)
// 2. Login failure breaks unrelated tests
// 3. Lots of duplicated code
// 4. Slow test execution (100 tests = 10 minutes just for login)
```

---

## Solution 1: StorageState (Recommended)

### Concept
1. Login **once** in a global setup script
2. Save authentication state (cookies, localStorage, sessionStorage)
3. Reuse saved state in all tests
4. Each test starts already authenticated

### Implementation

#### Step 1: Global Setup (global-setup.ts)
```typescript
import { chromium, FullConfig } from '@playwright/test';
import path from 'path';

async function globalSetup(config: FullConfig) {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Login as different user roles
  await setupAuthState(page, 'owner', {
    email: 'owner@solarhub.com',
    password: 'Owner123!@#',
    storageStatePath: 'test-results/.auth/owner.json'
  });

  await setupAuthState(page, 'admin', {
    email: 'admin@solarhub.com',
    password: 'Admin123!@#',
    storageStatePath: 'test-results/.auth/admin.json'
  });

  await setupAuthState(page, 'viewer', {
    email: 'viewer@solarhub.com',
    password: 'Viewer123!@#',
    storageStatePath: 'test-results/.auth/viewer.json'
  });

  await browser.close();
}

async function setupAuthState(page, role: string, credentials: any) {
  console.log(`Setting up ${role} authentication...`);

  // Navigate to login page
  await page.goto(process.env.BASE_URL + '/login');

  // Fill credentials
  await page.fill('[data-testid="email"]', credentials.email);
  await page.fill('[data-testid="password"]', credentials.password);

  // Submit login
  await page.click('[data-testid="submit"]');

  // Wait for successful login (check for dashboard or redirect)
  await page.waitForURL('**/dashboard', { timeout: 10000 });

  // Verify token exists in localStorage
  const token = await page.evaluate(() => localStorage.getItem('token'));
  if (!token) {
    throw new Error(`${role} login failed: no auth token found`);
  }

  // Save authentication state
  await page.context().storageState({ path: credentials.storageStatePath });

  console.log(`✓ ${role} authentication saved to ${credentials.storageStatePath}`);
}

export default globalSetup;
```

#### Step 2: Configure Projects (playwright.config.ts)
```typescript
export default defineConfig({
  globalSetup: require.resolve('./global-setup'),

  projects: [
    // Setup project runs first
    {
      name: 'setup',
      testMatch: /global-setup\.ts/,
    },

    // Owner role tests
    {
      name: 'chromium-owner',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'test-results/.auth/owner.json',
      },
      dependencies: ['setup'],
    },

    // Admin role tests
    {
      name: 'chromium-admin',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'test-results/.auth/admin.json',
      },
      dependencies: ['setup'],
    },

    // Viewer role tests
    {
      name: 'chromium-viewer',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'test-results/.auth/viewer.json',
      },
      dependencies: ['setup'],
    },
  ],
});
```

#### Step 3: Use in Tests
```typescript
// tests/dashboard/power-flow.spec.ts
import { test, expect } from '@playwright/test';

// This test automatically uses owner.json storageState
test('should display power flow diagram', async ({ page }) => {
  // ✅ Already authenticated! No login needed
  await page.goto('/dashboard');

  // Test actual functionality
  await expect(page.getByTestId('power-flow-diagram')).toBeVisible();
});
```

---

## Solution 2: Custom Fixtures for Roles

### Create Auth Fixtures (fixtures/auth.fixture.ts)
```typescript
import { test as base } from '@playwright/test';
import { LoginPage } from '@/pages/auth/LoginPage';
import { DashboardPage } from '@/pages/dashboard/DashboardPage';

type AuthenticatedFixtures = {
  authenticatedPage: Page;
  dashboardPage: DashboardPage;
  userRole: 'owner' | 'admin' | 'viewer' | 'installer';
};

// Base authenticated fixture
export const test = base.extend<AuthenticatedFixtures>({
  // Automatically navigate to dashboard after authentication
  authenticatedPage: async ({ page }, use) => {
    // StorageState already loaded from global setup
    await page.goto('/dashboard');
    await use(page);
  },

  // Dashboard page object
  dashboardPage: async ({ page }, use) => {
    const dashboardPage = new DashboardPage(page);
    await use(dashboardPage);
  },

  // User role from config
  userRole: async ({}, use, testInfo) => {
    const project = testInfo.project.name;
    if (project.includes('owner')) await use('owner');
    else if (project.includes('admin')) await use('admin');
    else if (project.includes('viewer')) await use('viewer');
    else if (project.includes('installer')) await use('installer');
    else await use('viewer'); // default
  },
});

export { expect } from '@playwright/test';
```

### Use Custom Fixtures
```typescript
import { test, expect } from '@/fixtures/auth.fixture';

test('should display correct features for role', async ({ authenticatedPage, userRole }) => {
  // Already on dashboard, already authenticated
  if (userRole === 'owner') {
    await expect(authenticatedPage.getByTestId('admin-panel')).toBeVisible();
    await expect(authenticatedPage.getByTestId('billing-settings')).toBeVisible();
  } else if (userRole === 'viewer') {
    await expect(authenticatedPage.getByTestId('admin-panel')).not.toBeVisible();
    await expect(authenticatedPage.getByTestId('billing-settings')).not.toBeVisible();
  }
});
```

---

## Solution 3: API-Based Authentication (Fastest)

### Why API Login?
- **10x faster** than UI login (50ms vs 5s)
- No browser rendering needed
- No flaky UI interactions
- Perfect for setup/teardown

### Implementation (utils/api/auth.api.ts)
```typescript
import { APIRequestContext } from '@playwright/test';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

/**
 * Login via API and return tokens
 */
export async function loginViaAPI(
  request: APIRequestContext,
  credentials: LoginCredentials
): Promise<AuthTokens> {
  const response = await request.post('/api/v1/auth/login', {
    data: credentials,
  });

  if (!response.ok()) {
    throw new Error(`API login failed: ${response.status()} ${await response.text()}`);
  }

  const data = await response.json();
  return data.tokens;
}

/**
 * Set authentication tokens in browser storage
 */
export async function setAuthTokens(page: Page, tokens: AuthTokens) {
  await page.goto('/'); // Need to be on the domain

  await page.evaluate((tokens) => {
    localStorage.setItem('token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);
    localStorage.setItem('token_type', tokens.token_type);
  }, tokens);
}

/**
 * Full API login flow: login + set tokens
 */
export async function authenticateViaAPI(
  page: Page,
  credentials: LoginCredentials
): Promise<void> {
  const tokens = await loginViaAPI(page.request, credentials);
  await setAuthTokens(page, tokens);
}
```

### Use in Fixtures
```typescript
// fixtures/fast-auth.fixture.ts
import { test as base } from '@playwright/test';
import { authenticateViaAPI } from '@/utils/api/auth.api';

export const test = base.extend({
  authenticatedPage: async ({ page }, use) => {
    // Super fast API login
    await authenticateViaAPI(page, {
      email: 'owner@solarhub.com',
      password: 'Owner123!@#',
    });

    await page.goto('/dashboard');
    await use(page);
  },
});
```

---

## Role-Based Test Organization

### Option A: Separate Test Files
```
tests/
├── owner/
│   ├── billing-settings.spec.ts
│   ├── user-management.spec.ts
│   └── organization-settings.spec.ts
├── admin/
│   ├── device-management.spec.ts
│   └── alert-rules.spec.ts
└── viewer/
    ├── dashboard-view.spec.ts
    └── reports-view.spec.ts
```

### Option B: Filtered by Project
```typescript
// tests/dashboard.spec.ts
import { test } from '@/fixtures/auth.fixture';

test('owner can edit dashboard layout', { tag: '@owner' }, async ({ page, userRole }) => {
  test.skip(userRole !== 'owner', 'Owner-only test');
  // Test code
});

test('viewer cannot edit dashboard layout', { tag: '@viewer' }, async ({ page, userRole }) => {
  test.skip(userRole !== 'viewer', 'Viewer-only test');
  // Test code
});
```

### Option C: Parameterized Tests
```typescript
const roles = ['owner', 'admin', 'viewer'] as const;

for (const role of roles) {
  test(`${role} can view dashboard`, async ({ page }) => {
    // Use role-specific storageState
    await page.goto('/dashboard');
    // Test code
  });
}
```

---

## Advanced Patterns

### Per-Test Authentication State
```typescript
test.use({
  // Override storageState for specific test
  storageState: 'test-results/.auth/special-user.json',
});

test('special user test', async ({ page }) => {
  // Uses special-user.json instead of project default
});
```

### Dynamic Role Switching
```typescript
import { loginViaAPI } from '@/utils/api/auth.api';

test('owner can transfer ownership to admin', async ({ page }) => {
  // Start as owner
  await authenticateViaAPI(page, { email: 'owner@...', password: '...' });
  await page.goto('/settings/organization');

  // Perform transfer
  await page.click('[data-testid="transfer-ownership"]');

  // Logout and login as admin
  await page.evaluate(() => localStorage.clear());
  await authenticateViaAPI(page, { email: 'admin@...', password: '...' });
  await page.reload();

  // Verify admin is now owner
  await expect(page.getByText('Owner')).toBeVisible();
});
```

### Session Expiry Testing
```typescript
test('should handle token expiry gracefully', async ({ page }) => {
  await page.goto('/dashboard');

  // Manually expire token
  await page.evaluate(() => {
    const token = localStorage.getItem('token');
    // Set token expiry to past
    localStorage.setItem('token', token.replace(/"exp":\d+/g, '"exp":1000000000'));
  });

  // Trigger an API call
  await page.reload();

  // Should redirect to login
  await expect(page).toHaveURL(/.*login/);
});
```

---

## Performance Comparison

| Method | Time per Test | 100 Tests |
|--------|--------------|-----------|
| UI Login Every Test | 5-10s | 8-16 minutes |
| StorageState | 0.5s | 50 seconds |
| API Login | 0.05s | 5 seconds |

**Recommendation:** Use storageState for most tests, API login for edge cases.

---

## Testing Unauthenticated State

### Option 1: Separate Project
```typescript
// playwright.config.ts
{
  name: 'unauthenticated',
  use: {
    ...devices['Desktop Chrome'],
    // No storageState!
  },
}
```

### Option 2: Clear State in Test
```typescript
test('unauthenticated user redirects to login', async ({ page, context }) => {
  // Clear all storage
  await context.clearCookies();
  await context.clearPermissions();
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  // Now truly unauthenticated
  await page.goto('/dashboard');

  // Should redirect to login
  await expect(page).toHaveURL(/.*login/);
});
```

---

## Common Pitfalls

### ❌ Pitfall 1: Sharing State Between Tests
```typescript
// BAD: Token from previous test affects this test
test('test A', async ({ page }) => {
  await page.evaluate(() => localStorage.setItem('custom', 'value'));
});

test('test B', async ({ page }) => {
  // 'custom' value still exists! 😱
});
```

**Solution:** Use `test.use({ storageState: undefined })` or clear in beforeEach.

### ❌ Pitfall 2: Token Expiry During Test
```typescript
// BAD: Long test might exceed token TTL
test('very long test', async ({ page }) => {
  await page.waitForTimeout(900_000); // 15 minutes
  // Token expired! Test fails
});
```

**Solution:** Refresh token mid-test or use longer-lived test tokens.

### ❌ Pitfall 3: Hardcoded Credentials
```typescript
// BAD: Credentials in source code
const PASSWORD = 'SuperSecret123!';
```

**Solution:** Use environment variables.
```typescript
const PASSWORD = process.env.TEST_USER_PASSWORD!;
```

---

## Environment Variables

### .env.test
```bash
# API Endpoints
BASE_URL=http://localhost:8081
API_URL=http://localhost:8000

# Test Users
OWNER_EMAIL=owner@solarhub.com
OWNER_PASSWORD=Owner123!@#

ADMIN_EMAIL=admin@solarhub.com
ADMIN_PASSWORD=Admin123!@#

VIEWER_EMAIL=viewer@solarhub.com
VIEWER_PASSWORD=Viewer123!@#

INSTALLER_EMAIL=installer@solarhub.com
INSTALLER_PASSWORD=Installer123!@#

# Database
DB_HOST=localhost
DB_PORT=5433
DB_NAME=solar_hub_test
DB_USER=postgres
DB_PASSWORD=postgres
```

### Load in Tests
```typescript
import dotenv from 'dotenv';
dotenv.config({ path: '.env.test' });

const credentials = {
  owner: {
    email: process.env.OWNER_EMAIL!,
    password: process.env.OWNER_PASSWORD!,
  },
  admin: {
    email: process.env.ADMIN_EMAIL!,
    password: process.env.ADMIN_PASSWORD!,
  },
};
```

---

## Best Practices

### ✅ Do's
- Use storageState for 90% of tests
- Login once in global setup
- Use API login for speed
- Separate projects for roles
- Clear sensitive data after tests
- Use environment variables for credentials
- Test both authenticated and unauthenticated states

### ❌ Don'ts
- Don't login via UI in every test
- Don't share auth state between unrelated tests
- Don't hardcode passwords
- Don't ignore token expiry
- Don't test auth logic in non-auth tests
- Don't mix roles in same test file

---

**Version:** 1.0
**Last Updated:** 2026-01-29
