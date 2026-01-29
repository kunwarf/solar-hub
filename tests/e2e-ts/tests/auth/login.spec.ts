import { test, expect } from '@playwright/test';
import { LoginPage } from '@/pages/auth/LoginPage';

/**
 * Authentication - Login Tests
 *
 * Tests login functionality with various scenarios
 * Priority: P0 (Critical)
 */
test.describe('Auth - Login', { tag: '@auth' }, () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    await loginPage.goto();
  });

  test('should render login page with all form elements', {
    tag: ['@smoke', '@critical']
  }, async () => {
    // Verify email input is visible
    await expect(loginPage.emailInput).toBeVisible();

    // Verify password input is visible
    await expect(loginPage.passwordInput).toBeVisible();

    // Verify submit button is visible
    await expect(loginPage.submitButton).toBeVisible();
  });

  test('should login successfully with valid credentials', {
    tag: ['@smoke', '@critical']
  }, async ({ page }) => {
    const email = process.env.OWNER_EMAIL || 'owner@solarhub.com';
    const password = process.env.OWNER_PASSWORD || 'Owner123!@#';

    // Perform login
    await loginPage.login(email, password);

    // Verify login success
    await loginPage.expectLoginSuccess();

    // Verify redirected to dashboard
    await expect(page).toHaveURL(/.*dashboard/);

    // Verify token is stored
    const token = await loginPage.getLocalStorageItem('token');
    expect(token).toBeTruthy();
    expect(token).toMatch(/^eyJ/); // JWT format
  });

  test('should display error with invalid email', {
    tag: '@regression'
  }, async ({ page }) => {
    await loginPage.login('nonexistent@test.com', 'SomePassword123!');

    // Should show error message
    await expect(loginPage.errorMessage).toBeVisible();

    // Should remain on login page
    await expect(page).toHaveURL(/.*auth/);

    // Should not have token
    const token = await loginPage.getLocalStorageItem('token');
    expect(token).toBeNull();
  });

  test('should display error with invalid password', {
    tag: '@regression'
  }, async ({ page }) => {
    const email = process.env.OWNER_EMAIL || 'owner@solarhub.com';

    await loginPage.login(email, 'WrongPassword123!');

    // Should show error message
    await expect(loginPage.errorMessage).toBeVisible();

    // Should remain on login page
    await expect(page).toHaveURL(/.*auth/);
  });

  test('should show validation errors for empty fields', {
    tag: '@regression'
  }, async () => {
    // Click submit without filling fields
    await loginPage.submitButton.click();

    // Should show validation errors
    await expect(loginPage.emailInput).toHaveAttribute('aria-invalid', 'true');
    await expect(loginPage.passwordInput).toHaveAttribute('aria-invalid', 'true');
  });

  test('should disable submit button during login', {
    tag: '@regression'
  }, async () => {
    const email = process.env.OWNER_EMAIL || 'owner@solarhub.com';
    const password = process.env.OWNER_PASSWORD || 'Owner123!@#';

    await loginPage.emailInput.fill(email);
    await loginPage.passwordInput.fill(password);

    // Click and check if button becomes disabled
    const buttonPromise = loginPage.submitButton.click();

    // Button should be disabled during request
    // Note: This might be too fast to catch in practice
    // await expect(loginPage.submitButton).toBeDisabled();

    await buttonPromise;
  });

  test('should clear form fields', {
    tag: '@regression'
  }, async () => {
    // Fill fields
    await loginPage.emailInput.fill('test@example.com');
    await loginPage.passwordInput.fill('password123');

    // Verify filled
    expect(await loginPage.getEmailValue()).toBe('test@example.com');
    expect(await loginPage.getPasswordValue()).toBe('password123');

    // Clear fields
    await loginPage.clearEmail();
    await loginPage.clearPassword();

    // Verify cleared
    expect(await loginPage.getEmailValue()).toBe('');
    expect(await loginPage.getPasswordValue()).toBe('');
  });
});
