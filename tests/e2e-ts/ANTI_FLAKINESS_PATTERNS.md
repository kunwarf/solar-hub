# Anti-Flakiness Patterns for Playwright Tests

## Overview

Flaky tests are the #1 enemy of reliable E2E test suites. This guide covers patterns to eliminate common sources of flakiness in Playwright tests.

**Definition:** A flaky test is one that passes and fails intermittently without code changes.

**Target:** < 5% flakiness rate (max 1 flaky test per 20 runs)

---

## Core Principles

### 1. **Auto-Wait is Your Friend**
Playwright automatically waits for elements to be actionable before performing actions.

```typescript
// ✅ GOOD: Playwright waits automatically
await page.click('[data-testid="submit"]');
// Automatically waits for:
// - Element exists in DOM
// - Element is visible
// - Element is enabled
// - Element is stable (not animating)

// ❌ BAD: Manual wait defeats auto-wait benefits
await page.waitForTimeout(1000);
await page.click('[data-testid="submit"]');
```

### 2. **Use Stable Locators**
Prefer built-in locators that are resilient to DOM changes.

```typescript
// ✅ BEST: data-testid (explicitly for testing)
await page.getByTestId('submit-button').click();

// ✅ GOOD: Role-based (accessible and semantic)
await page.getByRole('button', { name: 'Login' }).click();

// ✅ GOOD: Text-based (user-facing)
await page.getByText('Submit').click();

// ✅ GOOD: Label-based (form inputs)
await page.getByLabel('Email address').fill('test@example.com');

// ⚠️ OK: Placeholder (less stable than label)
await page.getByPlaceholder('Enter email').fill('test@example.com');

// ❌ BAD: CSS selectors (brittle)
await page.locator('.btn-primary').click();
await page.locator('div > button:nth-child(3)').click();

// ❌ VERY BAD: XPath (extremely brittle)
await page.locator('//div[@class="container"]/button[3]').click();
```

### 3. **Wait for Network Idle**
Use specific network wait strategies, not arbitrary timeouts.

```typescript
// ✅ GOOD: Wait for specific API call
await Promise.all([
  page.waitForResponse(resp =>
    resp.url().includes('/api/v1/dashboard/power-flow') && resp.status() === 200
  ),
  page.goto('/dashboard'),
]);

// ✅ GOOD: Wait for navigation to complete
await page.goto('/dashboard', { waitUntil: 'networkidle' });

// ✅ GOOD: Wait for specific condition
await page.waitForLoadState('networkidle');

// ❌ BAD: Arbitrary timeout
await page.goto('/dashboard');
await page.waitForTimeout(3000); // 🔴 Flaky!
```

### 4. **Explicit Waits Over Timeouts**
Always wait for a specific condition, never an arbitrary time.

```typescript
// ✅ GOOD: Wait for element state
await expect(page.getByTestId('loading-spinner')).toBeHidden();
await expect(page.getByTestId('data-table')).toBeVisible();

// ✅ GOOD: Wait for specific text
await expect(page.getByText('Data loaded successfully')).toBeVisible();

// ✅ GOOD: Wait for count
await expect(page.getByRole('row')).toHaveCount(10);

// ❌ BAD: Wait for arbitrary time
await page.waitForTimeout(2000); // 🔴 Might not be enough, or too much
```

---

## Common Flakiness Patterns & Solutions

### Pattern 1: Race Conditions with API Calls

#### ❌ Problem
```typescript
// Test sometimes fails because data hasn't loaded yet
test('should display device list', async ({ page }) => {
  await page.goto('/devices');

  // 🔴 Race condition! Page might still be loading
  const count = await page.getByRole('row').count();
  expect(count).toBe(3);
});
```

#### ✅ Solution
```typescript
test('should display device list', async ({ page }) => {
  // Wait for API response
  await Promise.all([
    page.waitForResponse(resp => resp.url().includes('/api/v1/devices')),
    page.goto('/devices'),
  ]);

  // Wait for UI to render
  await expect(page.getByTestId('device-list')).toBeVisible();

  // Now safe to count
  await expect(page.getByRole('row')).toHaveCount(3);
});
```

---

### Pattern 2: Animation Interference

#### ❌ Problem
```typescript
// Clicks fail because element is moving
test('should click animated button', async ({ page }) => {
  await page.goto('/dashboard');

  // 🔴 Button might be mid-animation
  await page.getByTestId('widget-settings').click();
});
```

#### ✅ Solution 1: Wait for Animation to Complete
```typescript
test('should click animated button', async ({ page }) => {
  await page.goto('/dashboard');

  // Wait for element to be stable (not moving)
  const button = page.getByTestId('widget-settings');
  await expect(button).toBeVisible();
  await expect(button).toBeEnabled();

  // Playwright auto-waits for stability
  await button.click();
});
```

#### ✅ Solution 2: Disable Animations in Tests
```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    contextOptions: {
      reducedMotion: 'reduce', // Disable animations
    },
  },
});

// Or in specific test
test.use({
  contextOptions: {
    reducedMotion: 'reduce',
  },
});
```

#### ✅ Solution 3: Force Click (Last Resort)
```typescript
// Only use when absolutely necessary
await page.getByTestId('widget-settings').click({ force: true });
```

---

### Pattern 3: Stale Element References

#### ❌ Problem
```typescript
// Element reference becomes stale after re-render
test('should update device name', async ({ page }) => {
  await page.goto('/devices');

  const row = page.getByRole('row').first();
  await row.click();

  // 🔴 Row might have re-rendered, reference is stale
  await row.getByTestId('edit-button').click();
});
```

#### ✅ Solution
```typescript
test('should update device name', async ({ page }) => {
  await page.goto('/devices');

  // Always get fresh reference
  await page.getByRole('row').first().click();

  // Get edit button relative to page, not stale row
  await page.getByTestId('edit-button').click();

  // Or re-query if needed
  const editButton = page.getByRole('row').first().getByTestId('edit-button');
  await editButton.click();
});
```

---

### Pattern 4: Timing Issues with Real-Time Data

#### ❌ Problem
```typescript
// Telemetry updates might not happen in time
test('should display real-time telemetry', async ({ page }) => {
  await page.goto('/dashboard');

  // 🔴 Telemetry might update 0-10 seconds from now
  const power = await page.getByTestId('solar-power').textContent();
  expect(power).not.toBe('0 W');
});
```

#### ✅ Solution 1: Wait for Non-Zero Value
```typescript
test('should display real-time telemetry', async ({ page }) => {
  await page.goto('/dashboard');

  // Wait for telemetry to be non-zero
  await expect(page.getByTestId('solar-power')).not.toHaveText('0 W', {
    timeout: 15000, // Telemetry updates every 10s
  });
});
```

#### ✅ Solution 2: Mock Telemetry Data
```typescript
test('should display telemetry', async ({ page }) => {
  // Intercept API and return mock data
  await page.route('**/api/v1/dashboard/power-flow', route => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        solar_power: 5500,
        battery_power: -1200,
        grid_power: 300,
        load_power: 4600,
      }),
    });
  });

  await page.goto('/dashboard');

  // Now predictable
  await expect(page.getByTestId('solar-power')).toHaveText('5.5 kW');
});
```

#### ✅ Solution 3: Use Device Simulator
```typescript
// utils/mock/device-simulator.ts
export async function startMockTelemetry(page: Page) {
  await page.route('**/api/v1/dashboard/power-flow', async route => {
    // Simulate changing telemetry values
    const data = generateRealisticTelemetry();
    await route.fulfill({ json: data });
  });
}
```

---

### Pattern 5: Flaky Network Requests

#### ❌ Problem
```typescript
// Sometimes API times out or returns 500
test('should load billing data', async ({ page }) => {
  await page.goto('/billing');

  // 🔴 Might timeout, might return error
  await expect(page.getByTestId('billing-amount')).toBeVisible();
});
```

#### ✅ Solution 1: Retry Failed Requests
```typescript
// playwright.config.ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,

  use: {
    // Retry network requests
    contextOptions: {
      serviceWorkers: 'block',
    },
  },
});
```

#### ✅ Solution 2: Mock Flaky Endpoints
```typescript
test('should load billing data', async ({ page }) => {
  // Ensure billing API always succeeds
  await page.route('**/api/v1/billing/**', async route => {
    const response = await route.fetch();

    if (!response.ok()) {
      // Return mock data on failure
      await route.fulfill({
        status: 200,
        body: JSON.stringify({ amount: 1500, currency: 'NGN' }),
      });
    } else {
      await route.fulfill({ response });
    }
  });

  await page.goto('/billing');
  await expect(page.getByTestId('billing-amount')).toBeVisible();
});
```

#### ✅ Solution 3: Increase Timeout for Specific API
```typescript
test('should load billing data', async ({ page }) => {
  // Billing API is slow, give it more time
  await Promise.all([
    page.waitForResponse(
      resp => resp.url().includes('/api/v1/billing'),
      { timeout: 30000 } // 30s instead of default 15s
    ),
    page.goto('/billing'),
  ]);

  await expect(page.getByTestId('billing-amount')).toBeVisible();
});
```

---

### Pattern 6: Date/Time-Dependent Tests

#### ❌ Problem
```typescript
// Test passes/fails depending on time of day
test('should show peak pricing', async ({ page }) => {
  await page.goto('/billing');

  // 🔴 Depends on current time!
  await expect(page.getByText('Peak Rate')).toBeVisible();
});
```

#### ✅ Solution: Mock Clock
```typescript
test('should show peak pricing during peak hours', async ({ page }) => {
  // Set time to 6 PM (peak hours)
  const peakTime = new Date('2026-01-29T18:00:00');
  await page.clock.setFixedTime(peakTime);

  await page.goto('/billing');

  // Now deterministic
  await expect(page.getByText('Peak Rate')).toBeVisible();
});

test('should show off-peak pricing during off-peak hours', async ({ page }) => {
  // Set time to 2 AM (off-peak)
  const offPeakTime = new Date('2026-01-29T02:00:00');
  await page.clock.setFixedTime(offPeakTime);

  await page.goto('/billing');
  await expect(page.getByText('Off-Peak Rate')).toBeVisible();
});
```

---

### Pattern 7: Test Order Dependencies

#### ❌ Problem
```typescript
// Test B depends on Test A running first
test('test A creates user', async ({ page }) => {
  // Creates user "testuser@example.com"
});

test('test B uses user', async ({ page }) => {
  // 🔴 Assumes testuser@example.com exists
  // Fails if run alone or if A fails
});
```

#### ✅ Solution: Make Tests Independent
```typescript
test('test A creates user', async ({ page, request }) => {
  const email = `user-${Date.now()}@example.com`;
  await createUser(request, email);
  // Test uses its own user
});

test('test B uses user', async ({ page, request }) => {
  const email = `user-${Date.now()}@example.com`;
  await createUser(request, email);
  // Test creates its own user
});
```

---

### Pattern 8: Shared State Between Tests

#### ❌ Problem
```typescript
// Test A modifies state that Test B expects
test('test A updates site name', async ({ page }) => {
  await page.goto('/settings');
  await page.fill('[data-testid="site-name"]', 'New Name');
  await page.click('[data-testid="save"]');
});

test('test B checks site name', async ({ page }) => {
  await page.goto('/dashboard');

  // 🔴 Expects original name, but A changed it
  await expect(page.getByText('My Home')).toBeVisible();
});
```

#### ✅ Solution 1: Isolate Test Data
```typescript
test('test A updates site name', async ({ page }) => {
  // Create unique site for this test
  const siteName = `Site-${Date.now()}`;
  await createSite(page, siteName);

  await page.goto('/settings');
  await page.fill('[data-testid="site-name"]', 'New Name');
  await page.click('[data-testid="save"]');
});

test('test B checks site name', async ({ page }) => {
  // Use its own site
  const siteName = `Site-${Date.now()}`;
  await createSite(page, siteName);

  await page.goto('/dashboard');
  await expect(page.getByText(siteName)).toBeVisible();
});
```

#### ✅ Solution 2: Reset State in beforeEach
```typescript
test.beforeEach(async ({ page, request }) => {
  // Reset to known state
  await resetDatabase(request);
  await seedTestData(request);
});
```

---

### Pattern 9: Screenshot Comparison Flakiness

#### ❌ Problem
```typescript
// Screenshots differ due to animations, timestamps, etc.
test('should match dashboard screenshot', async ({ page }) => {
  await page.goto('/dashboard');

  // 🔴 Fails due to:
  // - Timestamps showing current time
  // - Animations in different states
  // - Font rendering differences
  await expect(page).toHaveScreenshot();
});
```

#### ✅ Solution
```typescript
test('should match dashboard screenshot', async ({ page }) => {
  await page.goto('/dashboard');

  // 1. Hide dynamic content
  await page.addStyleTag({
    content: `
      [data-testid="current-time"],
      [data-testid="last-update"],
      .blinking-cursor {
        visibility: hidden !important;
      }
    `
  });

  // 2. Wait for animations to complete
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500); // Let animations settle

  // 3. Use relaxed comparison
  await expect(page).toHaveScreenshot({
    maxDiffPixelRatio: 0.05, // Allow 5% difference
    animations: 'disabled',
  });
});
```

---

### Pattern 10: Browser-Specific Rendering

#### ❌ Problem
```typescript
// Test passes in Chrome, fails in Firefox/Safari
test('should render correctly', async ({ page }) => {
  await page.goto('/dashboard');

  // 🔴 Different fonts/rendering across browsers
  await expect(page).toHaveScreenshot();
});
```

#### ✅ Solution
```typescript
// 1. Use CSS to normalize rendering
test.beforeEach(async ({ page }) => {
  await page.addStyleTag({
    content: `
      * {
        font-family: Arial, sans-serif !important;
        -webkit-font-smoothing: antialiased !important;
      }
    `
  });
});

// 2. Skip visual regression on certain browsers
test('should render correctly', async ({ page, browserName }) => {
  test.skip(browserName !== 'chromium', 'Visual test for Chrome only');

  await page.goto('/dashboard');
  await expect(page).toHaveScreenshot();
});
```

---

## Best Practices Checklist

### ✅ Do's

1. **Use Playwright's Built-in Waits**
   - Trust auto-wait for actions (click, fill, etc.)
   - Use `expect()` with built-in matchers
   - Wait for specific conditions, not arbitrary times

2. **Use Stable Locators**
   - Prefer `data-testid` attributes
   - Use role-based locators (`getByRole`)
   - Use text-based locators (`getByText`)

3. **Isolate Tests**
   - Each test should be independent
   - Create unique test data per test
   - Clean up after each test

4. **Handle Async Operations Properly**
   - Wait for API responses
   - Wait for elements to be visible/hidden
   - Use `Promise.all()` for concurrent operations

5. **Mock Unreliable Dependencies**
   - Mock flaky external APIs
   - Mock time-dependent logic
   - Mock random data

6. **Use Timeouts Strategically**
   - Set higher timeouts for slow operations
   - Use `expect` timeouts, not `waitForTimeout`
   - Document why timeout is needed

7. **Test in Isolation**
   - Use `test.only()` during development
   - Run tests in random order (`--shard`)
   - Run tests multiple times to catch flakiness

8. **Configure Retries Appropriately**
   - Retry on CI (network/infrastructure flakiness)
   - Don't retry locally (fix the test instead)

### ❌ Don'ts

1. **Never Use Arbitrary Waits**
   ```typescript
   // ❌ DON'T
   await page.waitForTimeout(3000);
   ```

2. **Don't Use Fragile Selectors**
   ```typescript
   // ❌ DON'T
   await page.locator('div > div > button:nth-child(3)').click();
   ```

3. **Don't Share State Between Tests**
   ```typescript
   // ❌ DON'T
   let sharedData = {};

   test('A', async () => {
     sharedData.value = 'foo';
   });

   test('B', async () => {
     expect(sharedData.value).toBe('foo'); // Depends on A
   });
   ```

4. **Don't Depend on Test Order**
   ```typescript
   // ❌ DON'T
   // Test 1 must run before Test 2
   ```

5. **Don't Ignore Flakiness**
   ```typescript
   // ❌ DON'T
   test.skip('flaky test', async () => {
     // Fix it instead!
   });
   ```

6. **Don't Mix Test Data**
   ```typescript
   // ❌ DON'T use same user in multiple tests
   const SHARED_USER = 'test@example.com';
   ```

7. **Don't Test Implementation Details**
   ```typescript
   // ❌ DON'T test internal state
   const internalState = await page.evaluate(() => window.__internalState);

   // ✅ DO test user-visible behavior
   await expect(page.getByText('Logged in')).toBeVisible();
   ```

---

## Debugging Flaky Tests

### Step 1: Reproduce Locally
```bash
# Run test 10 times to catch flakiness
for i in {1..10}; do npx playwright test flaky.spec.ts; done

# Run with retries
npx playwright test flaky.spec.ts --retries=3

# Run in headed mode to see what's happening
npx playwright test flaky.spec.ts --headed --slowmo=500
```

### Step 2: Enable Debugging
```typescript
test('flaky test', async ({ page }) => {
  // Pause on failure
  test.fail();

  // Enable verbose logging
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err));

  // Take screenshot before assertion
  await page.screenshot({ path: 'before-assert.png' });

  // Your test code
});
```

### Step 3: Add Trace on Failure
```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    trace: 'retain-on-failure', // Keep trace for failed tests
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
```

### Step 4: Analyze Trace
```bash
# View trace for failed test
npx playwright show-trace test-results/.../trace.zip
```

---

## Monitoring Flakiness

### CI Configuration
```yaml
# .github/workflows/e2e.yml
- name: Run Playwright tests
  run: npx playwright test

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: playwright-report/

- name: Calculate flakiness rate
  run: |
    TOTAL=$(jq '.suites[].specs | length' test-results/results.json | paste -sd+ | bc)
    FLAKY=$(jq '.suites[].specs[] | select(.tests[].results | length > 1) | .title' test-results/results.json | wc -l)
    RATE=$(bc <<< "scale=2; $FLAKY / $TOTAL * 100")
    echo "Flakiness rate: $RATE%"

    if (( $(bc <<< "$RATE > 5") )); then
      echo "::error::Flakiness rate too high: $RATE%"
      exit 1
    fi
```

---

**Version:** 1.0
**Last Updated:** 2026-01-29
