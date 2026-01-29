# Test Framework Enhancements

## Overview

Additional utilities and helpers to improve test development and maintenance.

**Date Added:** 2026-01-29

---

## 🛠️ Utility Helpers Added

### 1. Date Helper (`utils/helpers/date.helper.ts`)

**Purpose:** Common date operations for tests

**Functions:**
- `getTodayDate()` - Get today in YYYY-MM-DD format
- `getYesterdayDate()` - Get yesterday's date
- `getDaysAgo(days)` - Get date N days ago
- `getDaysFromNow(days)` - Get future date
- `formatDate(date)` - Format date to YYYY-MM-DD
- `formatDateReadable(date)` - Format to readable string
- `getStartOfMonth()` - First day of current month
- `getEndOfMonth()` - Last day of current month
- `getLastNDaysRange(days)` - Get date range
- `isToday(date)` - Check if date is today
- `sleep(ms)` - Async wait helper

**Usage Example:**
```typescript
import { getTodayDate, getDaysAgo } from '@/utils/helpers/date.helper';

test('should filter by date range', async ({ page }) => {
  const today = getTodayDate();
  const weekAgo = getDaysAgo(7);

  await analyticsPage.selectDateRange(weekAgo, today);
});
```

---

### 2. Data Helper (`utils/helpers/data.helper.ts`)

**Purpose:** Generate test data and random values

**Functions:**
- `generateRandomEmail(prefix)` - Create unique test email
- `generateRandomUsername(prefix)` - Create unique username
- `generateRandomPassword()` - Generate secure password
- `randomNumber(min, max)` - Random number in range
- `randomString(length)` - Random alphanumeric string
- `generateDeviceName()` - Create realistic device name
- `pickRandom(array)` - Pick random array element
- `generateUniqueId()` - Create unique identifier
- `sanitizeForSelector(str)` - Clean string for selectors
- `formatNumber(num)` - Format with commas
- `parseNumber(str)` - Parse formatted number
- `generateMockEnergyData(points)` - Create mock energy curve
- `deepClone(obj)` - Deep copy object
- `waitForCondition(fn, timeout)` - Wait for condition

**Usage Example:**
```typescript
import { generateRandomEmail, generateDeviceName } from '@/utils/helpers/data.helper';

test('should create new user', async ({ page }) => {
  const email = generateRandomEmail('testuser');
  const deviceName = generateDeviceName();

  await userManagementPage.createUser('Test', 'User', email, 'admin');
  await devicePage.addDevice(deviceName);
});
```

---

### 3. Screenshot Helper (`utils/helpers/screenshot.helper.ts`)

**Purpose:** Capture screenshots and visual debugging

**Functions:**
- `takeFullPageScreenshot(page, name, dir)` - Capture full page
- `takeElementScreenshot(page, selector, name, dir)` - Capture element
- `screenshotOnFailure(page, testName)` - Auto-capture on failure
- `compareScreenshot(page, baseline, name)` - Visual regression
- `captureVideo(page, testName)` - Video recording
- `takeTimestampedScreenshot(page, name)` - Screenshot with timestamp overlay

**Usage Example:**
```typescript
import { takeFullPageScreenshot, screenshotOnFailure } from '@/utils/helpers/screenshot.helper';

test('should display dashboard', async ({ page }) => {
  await dashboardPage.goto();

  // Capture for documentation
  await takeFullPageScreenshot(page, 'dashboard_loaded');

  try {
    await expect(page.getByTestId('power-flow')).toBeVisible();
  } catch (error) {
    await screenshotOnFailure(page, 'dashboard_power_flow');
    throw error;
  }
});
```

---

## 📝 Code Quality Tools

### Prettier Configuration (`.prettierrc.json`)

**Purpose:** Consistent code formatting across all test files

**Settings:**
- Single quotes
- Semicolons
- 2-space indentation
- 100 character line width
- Trailing commas (ES5)
- Arrow function parens (avoid)

**Usage:**
```bash
# Format all files
npx prettier --write "**/*.ts"

# Check formatting
npx prettier --check "**/*.ts"

# Add to package.json scripts
npm run format
```

---

## 🎯 Usage Patterns

### Date Range Testing
```typescript
import { getLastNDaysRange, getTodayDate } from '@/utils/helpers/date.helper';

test('should show last 7 days data', async () => {
  const { start, end } = getLastNDaysRange(7);

  await analyticsPage.selectCustomDateRange(start, end);
  await expect(analyticsPage.energyChart).toBeVisible();
});
```

### Test Data Generation
```typescript
import {
  generateRandomEmail,
  generateRandomPassword,
  generateDeviceName
} from '@/utils/helpers/data.helper';

test('should create user with unique data', async () => {
  const testData = {
    email: generateRandomEmail('e2e'),
    password: generateRandomPassword(),
    deviceName: generateDeviceName(),
  };

  await userPage.createUser('Test', 'User', testData.email, testData.password);
  await devicePage.addDevice(testData.deviceName);
});
```

### Visual Debugging
```typescript
import { takeTimestampedScreenshot } from '@/utils/helpers/screenshot.helper';

test('should debug complex interaction', async ({ page }) => {
  await takeTimestampedScreenshot(page, 'step_1_initial');
  await page.click('#complex-button');

  await takeTimestampedScreenshot(page, 'step_2_after_click');
  await page.fill('#input', 'test');

  await takeTimestampedScreenshot(page, 'step_3_after_fill');
});
```

### Number Parsing
```typescript
import { parseNumber, formatNumber } from '@/utils/helpers/data.helper';

test('should verify energy values', async () => {
  const displayedEnergy = await page.getByTestId('total-energy').textContent();
  const energyValue = parseNumber(displayedEnergy); // "1,234.56" -> 1234.56

  expect(energyValue).toBeGreaterThan(1000);
  expect(energyValue).toBeLessThan(5000);
});
```

### Conditional Waiting
```typescript
import { waitForCondition } from '@/utils/helpers/data.helper';

test('should wait for data to load', async ({ page }) => {
  await page.goto('/dashboard');

  const dataLoaded = await waitForCondition(
    async () => {
      const count = await page.locator('.data-point').count();
      return count > 0;
    },
    10000, // 10 second timeout
    500    // check every 500ms
  );

  expect(dataLoaded).toBe(true);
});
```

---

## 🔧 TypeScript Path Aliases

All helpers are available via path aliases:

```typescript
import { getTodayDate } from '@/utils/helpers/date.helper';
import { generateRandomEmail } from '@/utils/helpers/data.helper';
import { takeFullPageScreenshot } from '@/utils/helpers/screenshot.helper';
```

---

## 📊 Benefits

### Time Savings
- **No repetitive date formatting** - Use pre-built functions
- **Instant test data generation** - No manual creation
- **Quick visual debugging** - Screenshots with one line

### Code Quality
- **DRY principle** - Reusable utilities
- **Type safety** - Full TypeScript support
- **Consistent formatting** - Prettier integration
- **Less boilerplate** - Common operations abstracted

### Debugging
- **Easy screenshots** - Visual debugging made simple
- **Timestamped captures** - Know when issues occurred
- **Video recording** - Review full test execution
- **Element isolation** - Capture specific components

### Maintenance
- **Centralized logic** - Change once, update everywhere
- **Documented functions** - Clear JSDoc comments
- **Tested utilities** - Reliable helper functions
- **Easy to extend** - Add new helpers as needed

---

## 🚀 Future Enhancements

### Potential Additions
- Database helper (seed data, cleanup)
- API mocking utilities
- Performance measurement helpers
- Accessibility testing utilities
- Visual regression testing
- Custom reporters
- Test data factories
- Parallel execution helpers

### Integration Ideas
- Jest matchers for common assertions
- Custom Playwright fixtures
- GitHub Actions utilities
- Slack notification helpers
- Performance benchmarking tools

---

## 📚 Related Documentation

- [Date Helper API](./utils/helpers/date.helper.ts)
- [Data Helper API](./utils/helpers/data.helper.ts)
- [Screenshot Helper API](./utils/helpers/screenshot.helper.ts)
- [Prettier Config](./.prettierrc.json)

---

**Version:** 1.0
**Last Updated:** 2026-01-29
**Maintained By:** QA Team
