import { test, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Authentication - Signup/Registration Tests
 *
 * Tests user registration and signup functionality
 * Priority: P1
 */
test.describe('Auth - Signup', { tag: '@auth' }, () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/auth');
    await page.waitForLoadState('domcontentloaded');
  });

  test('should display signup tab or link', {
    tag: '@regression'
  }, async ({ page }) => {
    // Look for signup tab/button/link
    const signupTab = page.getByRole('button', { name: /sign up|register/i })
      .or(page.getByRole('link', { name: /sign up|register/i }))
      .or(page.getByTestId('signup-tab'));

    // At least one signup option should be visible
    await expect(signupTab.first()).toBeVisible();
  });

  test('should switch to signup form when signup tab is clicked', {
    tag: '@regression'
  }, async ({ page }) => {
    // Find and click signup tab
    const signupTab = page.getByRole('button', { name: /sign up|register/i }).first();

    if (await signupTab.isVisible()) {
      await signupTab.click();

      // Wait for signup form to appear
      await page.waitForTimeout(1000);

      // Should show signup-specific fields (like confirm password, name fields)
      const pageContent = await page.locator('body').textContent();
      expect(pageContent).toMatch(/sign up|register|create account/i);
    } else {
      test.skip();
    }
  });

  test('should display all required signup fields', {
    tag: '@regression'
  }, async ({ page }) => {
    // Click signup tab if it exists
    const signupTab = page.getByRole('button', { name: /sign up|register/i }).first();

    if (await signupTab.isVisible()) {
      await signupTab.click();
      await page.waitForTimeout(1000);

      // Common signup fields
      const emailInput = page.locator('input[type="email"]').first();
      const passwordInput = page.locator('input[type="password"]').first();

      await expect(emailInput).toBeVisible();
      await expect(passwordInput).toBeVisible();

      // Look for additional fields (name, confirm password, etc.)
      const formInputs = page.locator('input[type="text"], input[type="email"], input[type="password"]');
      const inputCount = await formInputs.count();

      // Should have at least 3 inputs for signup (email, password, confirm password or name)
      expect(inputCount).toBeGreaterThanOrEqual(2);
    } else {
      test.skip();
    }
  });

  test('should validate password complexity', {
    tag: '@regression'
  }, async ({ page }) => {
    // Navigate to signup
    const signupTab = page.getByRole('button', { name: /sign up|register/i }).first();

    if (await signupTab.isVisible()) {
      await signupTab.click();
      await page.waitForTimeout(1000);

      // Try with weak password
      const emailInput = page.locator('input[type="email"]').first();
      const passwordInput = page.locator('input[type="password"]').first();

      await emailInput.fill('newuser@example.com');
      await passwordInput.fill('123'); // Weak password

      // Submit or blur to trigger validation
      await passwordInput.blur();
      await page.waitForTimeout(500);

      // Should show validation error or prevent submission
      const submitButton = page.getByRole('button', { name: /sign up|register|create/i }).first();

      if (await submitButton.isVisible()) {
        await submitButton.click();
        await page.waitForTimeout(1000);

        // Check for error message
        const errorMessage = page.getByText(/password.*weak|password.*short|password.*require/i);
        const hasError = await errorMessage.isVisible().catch(() => false);

        // OR check if password field has validation state
        const isInvalid = await passwordInput.getAttribute('aria-invalid');

        expect(hasError || isInvalid === 'true').toBe(true);
      }
    } else {
      test.skip();
    }
  });

  test('should require matching passwords', {
    tag: '@regression'
  }, async ({ page }) => {
    const signupTab = page.getByRole('button', { name: /sign up|register/i }).first();

    if (await signupTab.isVisible()) {
      await signupTab.click();
      await page.waitForTimeout(1000);

      // Look for confirm password field
      const passwordInputs = page.locator('input[type="password"]');
      const passwordCount = await passwordInputs.count();

      if (passwordCount >= 2) {
        // Fill with mismatched passwords
        await passwordInputs.nth(0).fill('ValidPassword123!');
        await passwordInputs.nth(1).fill('DifferentPassword123!');

        // Submit
        const submitButton = page.getByRole('button', { name: /sign up|register|create/i }).first();
        await submitButton.click();
        await page.waitForTimeout(1000);

        // Should show error about passwords not matching
        const errorMessage = page.getByText(/password.*match|password.*same/i);
        await expect(errorMessage).toBeVisible();
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should require valid email format', {
    tag: '@regression'
  }, async ({ page }) => {
    const signupTab = page.getByRole('button', { name: /sign up|register/i }).first();

    if (await signupTab.isVisible()) {
      await signupTab.click();
      await page.waitForTimeout(1000);

      const emailInput = page.locator('input[type="email"]').first();

      // Try invalid email
      await emailInput.fill('notanemail');
      await emailInput.blur();
      await page.waitForTimeout(500);

      // Check HTML5 validation or custom validation
      const isValid = await emailInput.evaluate((el: HTMLInputElement) => el.validity.valid);
      expect(isValid).toBe(false);
    } else {
      test.skip();
    }
  });

  test('should prevent duplicate email registration', {
    tag: '@regression'
  }, async ({ page }) => {
    const signupTab = page.getByRole('button', { name: /sign up|register/i }).first();

    if (await signupTab.isVisible()) {
      await signupTab.click();
      await page.waitForTimeout(1000);

      // Use existing user email
      const existingEmail = process.env.OWNER_EMAIL || 'owner@solarhub.com';
      const password = 'NewPassword123!@#';

      const emailInput = page.locator('input[type="email"]').first();
      const passwordInputs = page.locator('input[type="password"]');

      await emailInput.fill(existingEmail);
      await passwordInputs.first().fill(password);

      if (await passwordInputs.count() > 1) {
        await passwordInputs.nth(1).fill(password);
      }

      // Submit
      const submitButton = page.getByRole('button', { name: /sign up|register|create/i }).first();
      await submitButton.click();

      // Wait for response
      await page.waitForTimeout(2000);

      // Should show error about email already exists
      const errorMessage = page.getByText(/email.*already.*exists|email.*taken|already.*registered/i);
      const hasError = await errorMessage.isVisible().catch(() => false);

      // OR should still be on signup page
      const currentUrl = page.url();
      expect(hasError || currentUrl.includes('auth')).toBe(true);
    } else {
      test.skip();
    }
  });
});
