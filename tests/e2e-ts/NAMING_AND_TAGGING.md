# Naming Conventions & Tagging Strategy

## Test File Naming

### Pattern
```
<feature>-<subfeature>.spec.ts
```

### Examples
```typescript
// Good
login.spec.ts
device-claiming.spec.ts
billing-cycles.spec.ts
real-time-data.spec.ts

// Bad
test_login.ts          // Don't use Python naming
loginTest.spec.ts      // Don't use camelCase
Login.spec.ts          // Don't capitalize
```

### Rules
- Use kebab-case (lowercase with hyphens)
- Must end with `.spec.ts`
- Be descriptive but concise
- Group related tests in same file (max 15-20 tests per file)

---

## Test Suite Naming

### Pattern
```typescript
test.describe('<Module> - <Feature>', () => {
  // tests
});
```

### Examples
```typescript
test.describe('Auth - Login', () => {
  // Login-related tests
});

test.describe('Dashboard - Power Flow Widget', () => {
  // Power flow widget tests
});

test.describe('Billing - Net Metering Calculations', () => {
  // Net metering tests
});
```

### Nested Suites
```typescript
test.describe('Device Management', () => {
  test.describe('Device Claiming', () => {
    test.describe('Orphan Device Claiming', () => {
      // Highly specific tests
    });
  });
});
```

---

## Test Case Naming

### Pattern
```typescript
test('<action> <expected result> [<condition>]', async ({ page }) => {
  // test code
});
```

### Examples
```typescript
// Good - Clear, descriptive
test('should login successfully with valid credentials', async ({ page }) => {});
test('should display error message with invalid password', async ({ page }) => {});
test('should redirect to dashboard after successful login', async ({ page }) => {});
test('should persist user session across page reloads', async ({ page }) => {});

// Better - Even more specific
test('should login as owner and access admin features', async ({ page }) => {});
test('should fail login after 3 invalid attempts and lock account', async ({ page }) => {});

// Bad - Too vague
test('login test', async ({ page }) => {});  // What about login?
test('test user can login', async ({ page }) => {});  // Redundant "test"
test('check if dashboard loads', async ({ page }) => {});  // Unclear expectation
```

### Action Verbs
- `should <verb>` - Preferred format
- `can <verb>` - Alternative for capability tests
- `verify <noun>` - For validation tests
- `ensure <condition>` - For requirement tests

### Good Action Verbs
- display, show, render, load
- create, update, delete, save
- navigate, redirect, route
- calculate, compute, aggregate
- validate, verify, check
- enable, disable, toggle
- send, receive, transmit
- filter, sort, search

---

## Tagging Strategy

### Tag Format
```typescript
test('test name', { tag: '@tagname' }, async ({ page }) => {});

// Multiple tags
test('test name', { tag: ['@smoke', '@critical'] }, async ({ page }) => {});
```

### Core Tags

#### Priority Tags
```typescript
@critical   // P0 - Must pass before deploy
@high       // P1 - Important features
@medium     // P2 - Secondary features
@low        // P3 - Nice-to-have features
```

#### Test Type Tags
```typescript
@smoke      // Quick critical path tests (5-10 min)
@regression // Full regression suite (30-60 min)
@integration // Cross-system integration tests
@performance // Performance benchmarks
@security   // Security-related tests
@accessibility // A11y compliance tests
```

#### Module Tags
```typescript
@auth       // Authentication & authorization
@onboarding // User registration & setup wizard
@dashboard  // Main dashboard
@devices    // Device management
@billing    // Billing & tariffs
@analytics  // Analytics & reports
@alerts     // Alerts & notifications
@outages    // Grid outages & monitoring
@admin      // Admin features
@settings   // User/site settings
```

#### Role Tags
```typescript
@owner      // Requires owner role
@admin      // Requires admin role
@viewer     // Requires viewer role
@installer  // Requires installer role
@guest      // Unauthenticated user
```

#### Environment Tags
```typescript
@local      // Only runs locally
@ci         // Only runs in CI
@staging    // Only runs in staging
@production // Safe for production smoke tests
```

#### Data Tags
```typescript
@seed-data  // Requires seeded test data
@mock-data  // Uses mock data
@real-data  // Requires real device data
@clean-db   // Requires clean database
```

#### Platform Tags
```typescript
@desktop    // Desktop-specific tests
@mobile     // Mobile-specific tests
@tablet     // Tablet-specific tests
@pwa        // PWA-specific features
```

#### Stability Tags
```typescript
@stable     // Consistently passing
@flaky      // Known to be flaky
@skip       // Temporarily disabled
@wip        // Work in progress
```

### Tag Usage Examples

```typescript
// Critical smoke test for authentication
test('should login successfully with valid credentials', {
  tag: ['@smoke', '@critical', '@auth']
}, async ({ page }) => {
  // test code
});

// Admin-only regression test
test('should invite new user to organization', {
  tag: ['@regression', '@admin', '@high', '@seed-data']
}, async ({ page }) => {
  // test code
});

// Mobile-specific dashboard test
test('should display responsive dashboard on mobile', {
  tag: ['@mobile', '@dashboard', '@regression', '@medium']
}, async ({ page }) => {
  // test code
});

// Flaky test marked for investigation
test('should update telemetry in real-time', {
  tag: ['@flaky', '@dashboard', '@real-data', '@critical']
}, async ({ page }) => {
  // test code
});
```

---

## Running Tests by Tags

### Command Line
```bash
# Run all smoke tests
npx playwright test --grep @smoke

# Run critical tests only
npx playwright test --grep @critical

# Run auth module tests
npx playwright test --grep @auth

# Run smoke AND critical tests
npx playwright test --grep "@smoke.*@critical"

# Run smoke OR critical tests
npx playwright test --grep "@smoke|@critical"

# Run tests excluding flaky ones
npx playwright test --grep-invert @flaky

# Run admin tests that are not flaky
npx playwright test --grep @admin --grep-invert @flaky

# Run multiple tags with AND logic
npx playwright test --grep "(?=.*@dashboard)(?=.*@critical)"
```

### In Code (playwright.config.ts)
```typescript
export default defineConfig({
  // Run only smoke tests by default
  grep: /@smoke/,

  // Exclude flaky and WIP tests
  grepInvert: /@flaky|@wip/,
});
```

---

## Page Object Naming

### Class Names
```typescript
// Pattern: <Page/Component>Page
class LoginPage {}
class DashboardPage {}
class DeviceDetailPage {}

// Components within pages
class PowerFlowComponent {}
class StatsCardComponent {}
class EnergyChartComponent {}

// Base classes
class BasePage {}
class AuthenticatedPage extends BasePage {}
```

### Method Names
```typescript
class LoginPage extends BasePage {
  // Actions: verb + noun
  async enterEmail(email: string) {}
  async enterPassword(password: string) {}
  async clickSubmit() {}
  async login(email: string, password: string) {}

  // Getters: get + noun
  getEmailInput() {}
  getPasswordInput() {}
  getErrorMessage() {}

  // Assertions: expect/verify + condition
  async expectLoginSuccess() {}
  async expectErrorMessage(message: string) {}
  async verifyOnLoginPage() {}

  // Navigations: goto/navigate + destination
  async goto() {}
  async navigateToDashboard() {}

  // Waiters: wait + condition
  async waitForRedirect() {}
  async waitForErrorMessage() {}
}
```

---

## Fixture Naming

### File Names
```typescript
auth.fixture.ts        // Authentication fixtures
user.fixture.ts        // User data fixtures
device.fixture.ts      // Device fixtures
telemetry.fixture.ts   // Telemetry data
```

### Fixture Names
```typescript
// Pattern: <adjective><noun>
const authenticatedUser = test.extend({});
const ownerUser = test.extend({});
const adminUser = test.extend({});
const viewerUser = test.extend({});

const orphanDevice = test.extend({});
const claimedDevice = test.extend({});
const onlineDevice = test.extend({});

const emptyDashboard = test.extend({});
const populatedDashboard = test.extend({});
```

---

## Utility Function Naming

### Helper Functions
```typescript
// utils/helpers/wait.ts
export async function waitForTelemetry() {}
export async function waitForBillingCycle() {}
export async function waitUntilVisible() {}

// utils/helpers/assertions.ts
export async function expectDashboardLoaded() {}
export async function expectDeviceOnline() {}

// utils/helpers/data-generator.ts
export function generateUniqueEmail() {}
export function generateDeviceSerial() {}
export function generateTelemetryData() {}
```

### API Helpers
```typescript
// utils/api/auth.api.ts
export async function loginViaAPI() {}
export async function logoutViaAPI() {}
export async function createUserViaAPI() {}

// utils/api/devices.api.ts
export async function claimDeviceViaAPI() {}
export async function getDeviceStatusViaAPI() {}
```

---

## Constant Naming

### Test Data Constants
```typescript
// ALL_CAPS_SNAKE_CASE for constants
export const DEFAULT_USER_EMAIL = 'test@solarhub.com';
export const DEFAULT_USER_PASSWORD = 'Test123!@#';
export const API_BASE_URL = 'http://localhost:8000';

export const TIMEOUTS = {
  SHORT: 5_000,
  MEDIUM: 15_000,
  LONG: 30_000,
  TELEMETRY_UPDATE: 10_000,
} as const;

export const USER_ROLES = {
  OWNER: 'owner',
  ADMIN: 'admin',
  VIEWER: 'viewer',
  INSTALLER: 'installer',
} as const;
```

---

## Selector Naming

### Data-testid Attributes (Recommended)
```typescript
// In React components:
<button data-testid="login-submit-button">Login</button>
<input data-testid="email-input" />
<div data-testid="power-flow-diagram" />

// In tests:
await page.getByTestId('login-submit-button').click();
await page.getByTestId('email-input').fill('test@example.com');
```

### Selector Constants
```typescript
// utils/selectors.ts
export const SELECTORS = {
  AUTH: {
    EMAIL_INPUT: '[data-testid="email-input"]',
    PASSWORD_INPUT: '[data-testid="password-input"]',
    SUBMIT_BUTTON: '[data-testid="login-submit-button"]',
  },
  DASHBOARD: {
    POWER_FLOW: '[data-testid="power-flow-diagram"]',
    STATS_CARDS: '[data-testid="stats-card"]',
  },
} as const;
```

---

## Comment Standards

### Test Descriptions
```typescript
test('should login successfully with valid credentials', async ({ page }) => {
  // Arrange: Navigate to login page
  await loginPage.goto();

  // Act: Enter credentials and submit
  await loginPage.login('test@example.com', 'Test123!@#');

  // Assert: Verify redirect to dashboard
  await expect(page).toHaveURL('/dashboard');
  await dashboardPage.expectLoaded();
});
```

### Complex Logic Comments
```typescript
// Wait for telemetry update (10s polling interval + 2s buffer)
await page.waitForTimeout(12_000);

// Retry clicking due to animation overlay
await page.getByTestId('submit-button').click({ force: true, trial: true });
```

---

## Error Message Naming

### Custom Error Classes
```typescript
class AuthenticationError extends Error {}
class DeviceNotFoundError extends Error {}
class TelemetryTimeoutError extends Error {}
```

### Error Messages
```typescript
// Clear, specific error messages
throw new Error(`Expected user to be logged in, but found login page`);
throw new Error(`Device ${serial} not found in database`);
throw new Error(`Telemetry data not updated within ${timeout}ms`);

// Include context for debugging
throw new Error(
  `Dashboard failed to load:\n` +
  `  URL: ${page.url()}\n` +
  `  Expected: /dashboard\n` +
  `  Actual: ${await page.title()}`
);
```

---

## Best Practices Summary

### ✅ Do's
- Use kebab-case for files
- Use descriptive, action-oriented test names
- Tag tests with multiple relevant tags
- Group related tests in describe blocks
- Use data-testid for selectors
- Comment complex logic
- Use TypeScript types everywhere

### ❌ Don'ts
- Don't use Python naming (test_*, snake_case)
- Don't use vague test names ("test 1", "check login")
- Don't over-nest describe blocks (max 3 levels)
- Don't use brittle selectors (nth-child, absolute XPath)
- Don't leave commented-out code
- Don't use magic numbers (use named constants)

---

**Version:** 1.0
**Last Updated:** 2026-01-29
