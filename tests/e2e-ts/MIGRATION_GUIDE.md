# Migration Guide: Python/Playwright → TypeScript/Playwright

## Overview

This guide helps migrate existing E2E tests from Python/Playwright to TypeScript/Playwright Test framework.

**Current State:** `tests/e2e/*.py` (Python)
**Target State:** `tests/e2e-ts/**/*.spec.ts` (TypeScript)

---

## Migration Strategy

### Phase 1: Setup (Week 1)
1. ✅ Install Playwright Test with TypeScript
2. ✅ Create folder structure
3. ✅ Setup configuration files
4. ✅ Create base page objects
5. ✅ Create authentication fixtures

### Phase 2: Migrate Critical Tests (Week 2-3)
1. Migrate authentication tests (@critical @smoke)
2. Migrate dashboard tests (@critical @smoke)
3. Migrate device management tests (@critical)
4. Run both Python and TypeScript in parallel

### Phase 3: Migrate Remaining Tests (Week 4-5)
1. Migrate billing tests
2. Migrate analytics tests
3. Migrate admin tests
4. Migrate integration tests

### Phase 4: Cleanup (Week 6)
1. Remove Python tests
2. Update CI/CD pipelines
3. Update documentation
4. Train team on TypeScript tests

---

## Installation & Setup

### Prerequisites
```bash
cd tests/e2e-ts
npm init -y
npm install -D @playwright/test typescript
npm install -D @types/node dotenv
npx playwright install
```

### TypeScript Configuration
```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"],
      "@pages/*": ["./pages/*"],
      "@tests/*": ["./tests/*"],
      "@fixtures/*": ["./fixtures/*"],
      "@utils/*": ["./utils/*"]
    }
  },
  "include": ["**/*.ts"],
  "exclude": ["node_modules", "dist", "test-results"]
}
```

---

## Syntax Migration Examples

### Test Structure

#### Python (Before)
```python
class TestLoginPage:
    """Tests for login page."""

    def test_login_page_loads(self, page: Page):
        """Test that login page renders."""
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_load_state("networkidle")

        email_input = page.locator("input[type='email']").first
        expect(email_input).to_be_visible()
```

#### TypeScript (After)
```typescript
import { test, expect } from '@playwright/test';

test.describe('Auth - Login', () => {
  test('should render login page with email input', async ({ page }) => {
    await page.goto('/auth');
    await page.waitForLoadState('networkidle');

    const emailInput = page.locator('input[type="email"]').first();
    await expect(emailInput).toBeVisible();
  });
});
```

### Locators

#### Python (Before)
```python
# Chaining .first
email_input = page.locator("input[type='email']").first
email_input.fill("test@example.com")

# Complex selector
submit_btn = page.locator("button[type='submit'], button:has-text('Login')").first
submit_btn.click()
```

#### TypeScript (After)
```typescript
// Better: Use specific locators
const emailInput = page.getByRole('textbox', { name: /email/i });
await emailInput.fill('test@example.com');

// Or with data-testid
const emailInput = page.getByTestId('email-input');
await emailInput.fill('test@example.com');

// Button with role
const submitBtn = page.getByRole('button', { name: /login|sign in/i });
await submitBtn.click();
```

### Assertions

#### Python (Before)
```python
from playwright.sync_api import expect

expect(email_input).to_be_visible()
expect(page).to_have_url(f"{BASE_URL}/dashboard")

body_text = page.locator("body").text_content() or ""
assert "error" in body_text.lower()
```

#### TypeScript (After)
```typescript
import { expect } from '@playwright/test';

await expect(emailInput).toBeVisible();
await expect(page).toHaveURL('/dashboard');

await expect(page.getByText(/error/i)).toBeVisible();
// Or
await expect(page.locator('body')).toContainText('error', { ignoreCase: true });
```

### Waits

#### Python (Before) - Anti-patterns
```python
# ❌ Arbitrary timeout
page.wait_for_timeout(3000)

# ❌ networkidle for everything
page.wait_for_load_state("networkidle")
```

#### TypeScript (After) - Best practices
```typescript
// ✅ Wait for specific element
await expect(page.getByTestId('dashboard-loaded')).toBeVisible();

// ✅ Wait for API response
await Promise.all([
  page.waitForResponse(resp => resp.url().includes('/api/v1/auth/login')),
  page.getByRole('button', { name: 'Login' }).click(),
]);

// ✅ Wait for navigation
await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
```

### Page Objects

#### Python (Before) - No page objects
```python
def test_login(self, page: Page):
    page.goto(f"{BASE_URL}/auth")
    email = page.locator("input[type='email']").first
    password = page.locator("input[type='password']").first
    email.fill("test@example.com")
    password.fill("password")
    page.locator("button[type='submit']").first.click()
```

#### TypeScript (After) - Page object model
```typescript
// pages/auth/LoginPage.ts
export class LoginPage extends BasePage {
  readonly emailInput = this.page.getByTestId('email-input');
  readonly passwordInput = this.page.getByTestId('password-input');
  readonly submitButton = this.page.getByRole('button', { name: /login/i });
  readonly errorMessage = this.page.getByTestId('error-message');

  async goto() {
    await this.page.goto('/auth');
    await this.waitForLoaded();
  }

  async waitForLoaded() {
    await expect(this.emailInput).toBeVisible();
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async expectLoginSuccess() {
    await expect(this.page).toHaveURL('/dashboard');
  }

  async expectErrorMessage(message: string | RegExp) {
    await expect(this.errorMessage).toContainText(message);
  }
}

// test file
test('should login successfully', async ({ page }) => {
  const loginPage = new LoginPage(page);

  await loginPage.goto();
  await loginPage.login('test@example.com', 'Test123!@#');
  await loginPage.expectLoginSuccess();
});
```

### Fixtures

#### Python (Before) - pytest fixtures
```python
# conftest.py
@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    page = context.new_page()
    yield page
    page.close()
```

#### TypeScript (After) - Playwright fixtures
```typescript
// fixtures/auth.fixture.ts
import { test as base } from '@playwright/test';
import { LoginPage } from '@/pages/auth/LoginPage';

type AuthFixtures = {
  authenticatedPage: Page;
  loginPage: LoginPage;
};

export const test = base.extend<AuthFixtures>({
  loginPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await use(loginPage);
  },

  authenticatedPage: async ({ page }, use) => {
    // Auto-login using storageState
    await page.goto('/dashboard');
    await use(page);
  },
});

export { expect } from '@playwright/test';
```

---

## Example Migration: Auth Tests

### Python Original (test_auth.py)
```python
class TestLoginPage:
    def test_login_page_loads(self, page: Page):
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_load_state("networkidle")

        email_input = page.locator("input[type='email']").first
        expect(email_input).to_be_visible()

        password_input = page.locator("input[type='password']").first
        expect(password_input).to_be_visible()

        submit_btn = page.locator("button[type='submit']").first
        expect(submit_btn).to_be_visible()

    def test_login_with_valid_credentials(self, page: Page):
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_load_state("networkidle")

        email_input = page.locator("input[type='email']").first
        password_input = page.locator("input[type='password']").first

        email_input.fill(TEST_USER_EMAIL)
        password_input.fill(TEST_USER_PASSWORD)

        submit_btn = page.locator("button[type='submit']").first
        submit_btn.click()

        page.wait_for_timeout(3000)

        # Check if redirected
        assert "/auth" not in page.url or "dashboard" in page.url

    def test_login_with_invalid_email(self, page: Page):
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_load_state("networkidle")

        email_input = page.locator("input[type='email']").first
        password_input = page.locator("input[type='password']").first

        email_input.fill("nonexistent@test.com")
        password_input.fill("SomePassword123!")

        submit_btn = page.locator("button[type='submit']").first
        submit_btn.click()

        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""
        assert "error" in body_text.lower() or "/auth" in page.url
```

### TypeScript Migrated (login.spec.ts)
```typescript
import { test, expect } from '@playwright/test';
import { LoginPage } from '@/pages/auth/LoginPage';

test.describe('Auth - Login', { tag: '@auth' }, () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    await loginPage.goto();
  });

  test('should render login page with all form elements', {
    tag: ['@smoke', '@critical']
  }, async ({ page }) => {
    await expect(loginPage.emailInput).toBeVisible();
    await expect(loginPage.passwordInput).toBeVisible();
    await expect(loginPage.submitButton).toBeVisible();
  });

  test('should login successfully with valid credentials', {
    tag: ['@smoke', '@critical']
  }, async ({ page }) => {
    await loginPage.login(
      process.env.TEST_USER_EMAIL!,
      process.env.TEST_USER_PASSWORD!
    );

    await loginPage.expectLoginSuccess();
    await expect(page.getByTestId('dashboard-loaded')).toBeVisible();
  });

  test('should display error with invalid email', {
    tag: '@regression'
  }, async ({ page }) => {
    await loginPage.login('nonexistent@test.com', 'SomePassword123!');

    await loginPage.expectErrorMessage(/invalid credentials|user not found/i);
    await expect(page).toHaveURL(/\/auth/);
  });

  test('should display error with invalid password', {
    tag: '@regression'
  }, async ({ page }) => {
    await loginPage.login(
      process.env.TEST_USER_EMAIL!,
      'WrongPassword123!'
    );

    await loginPage.expectErrorMessage(/invalid credentials|incorrect password/i);
  });

  test('should show validation errors for empty fields', {
    tag: '@regression'
  }, async ({ page }) => {
    await loginPage.submitButton.click();

    await expect(loginPage.emailInput).toHaveAttribute('aria-invalid', 'true');
    await expect(loginPage.passwordInput).toHaveAttribute('aria-invalid', 'true');
  });

  test('should store auth token after successful login', {
    tag: '@critical'
  }, async ({ page }) => {
    await loginPage.login(
      process.env.TEST_USER_EMAIL!,
      process.env.TEST_USER_PASSWORD!
    );

    await loginPage.expectLoginSuccess();

    const token = await page.evaluate(() => localStorage.getItem('token'));
    expect(token).toBeTruthy();
    expect(token).toMatch(/^eyJ/); // JWT format
  });

  test('should clear session on logout', {
    tag: '@critical'
  }, async ({ page }) => {
    await loginPage.login(
      process.env.TEST_USER_EMAIL!,
      process.env.TEST_USER_PASSWORD!
    );

    await loginPage.expectLoginSuccess();

    await page.getByRole('button', { name: /logout/i }).click();

    const token = await page.evaluate(() => localStorage.getItem('token'));
    expect(token).toBeNull();
    await expect(page).toHaveURL(/\/auth/);
  });
});
```

---

## Common Migration Patterns

### Pattern 1: Handling Dynamic URLs

#### Python
```python
BASE_URL = "http://localhost:8080"
page.goto(f"{BASE_URL}/auth")
```

#### TypeScript
```typescript
// playwright.config.ts has baseURL
await page.goto('/auth');

// Full URL if needed
await page.goto(process.env.BASE_URL + '/auth');
```

### Pattern 2: Waiting for Content

#### Python
```python
page.wait_for_timeout(3000)
body_text = page.locator("body").text_content()
assert "success" in body_text
```

#### TypeScript
```typescript
await expect(page.getByText('success')).toBeVisible({ timeout: 5000 });
```

### Pattern 3: API Calls in Tests

#### Python
```python
# Usually not done in Python E2E tests
```

#### TypeScript
```typescript
import { loginViaAPI } from '@/utils/api/auth.api';

test('should create device after login', async ({ page }) => {
  // Fast API login
  await loginViaAPI(page.request, {
    email: 'test@example.com',
    password: 'Test123!@#',
  });

  await page.goto('/devices');
  // Test device creation
});
```

### Pattern 4: Test Data

#### Python
```python
TEST_USER_EMAIL = "admin@demo.com"
TEST_USER_PASSWORD = "Admin123!"
```

#### TypeScript
```typescript
// .env.test
TEST_USER_EMAIL=admin@demo.com
TEST_USER_PASSWORD=Admin123!@#

// In code
const credentials = {
  email: process.env.TEST_USER_EMAIL!,
  password: process.env.TEST_USER_PASSWORD!,
};
```

---

## Migration Checklist

For each test file:

- [ ] Convert class-based tests to `test.describe` blocks
- [ ] Convert method names to descriptive test names
- [ ] Replace `page.locator().first` with specific locators
- [ ] Add `data-testid` attributes to frontend components
- [ ] Remove `page.wait_for_timeout()` - use explicit waits
- [ ] Create page object for the feature
- [ ] Add proper tags (@smoke, @critical, etc.)
- [ ] Use environment variables for credentials
- [ ] Add TypeScript types for all variables
- [ ] Update assertions to use Playwright's `expect`
- [ ] Add API helpers for fast setup
- [ ] Use fixtures instead of raw page object

---

## Running Tests

### Python (Old)
```bash
pytest tests/e2e/test_auth.py -v
pytest tests/e2e/test_auth.py::TestLoginPage::test_login_page_loads
```

### TypeScript (New)
```bash
npx playwright test tests/auth/login.spec.ts
npx playwright test tests/auth/login.spec.ts:10 # Run test at line 10
npx playwright test --grep @smoke
npx playwright test --project=chromium
```

---

## Parallel Execution

### Python (Old)
```bash
pytest tests/e2e/ -n 4 # pytest-xdist
```

### TypeScript (New)
```bash
npx playwright test --workers=4
npx playwright test --workers=50% # Use 50% of CPU cores
```

---

## CI/CD Changes

### GitHub Actions (Before)
```yaml
- name: Run E2E tests
  run: |
    pytest tests/e2e/ -v --headed
```

### GitHub Actions (After)
```yaml
- name: Install dependencies
  run: |
    cd tests/e2e-ts
    npm ci
    npx playwright install --with-deps

- name: Run E2E tests
  run: |
    cd tests/e2e-ts
    npx playwright test --reporter=html

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: tests/e2e-ts/playwright-report/
```

---

## Quick Reference

| Python | TypeScript |
|--------|-----------|
| `pytest` | `npx playwright test` |
| `@pytest.fixture` | `test.extend()` |
| `page.goto(f"{BASE_URL}/path")` | `await page.goto('/path')` |
| `page.locator("selector").first` | `page.locator('selector').first()` |
| `expect(el).to_be_visible()` | `await expect(el).toBeVisible()` |
| `page.wait_for_timeout(3000)` | `await expect(el).toBeVisible()` |
| `class TestLoginPage:` | `test.describe('Login', () => {})` |
| `def test_login(self):` | `test('should login', async () => {})` |
| `assert x == y` | `expect(x).toBe(y)` |
| No page objects | Page Object Model |
| Global setup in conftest | `global-setup.ts` |

---

## Training Resources

1. **Playwright TypeScript Docs:** https://playwright.dev/docs/intro
2. **Page Object Model:** https://playwright.dev/docs/pom
3. **Best Practices:** https://playwright.dev/docs/best-practices
4. **API Testing:** https://playwright.dev/docs/api-testing
5. **Fixtures:** https://playwright.dev/docs/test-fixtures

---

## Support

- **Questions:** Slack #qa-automation
- **Code Reviews:** Tag @qa-team-lead
- **Pair Programming:** Schedule with QA team

---

**Migration Timeline:** 6 weeks
**Status:** In Progress
**Last Updated:** 2026-01-29
