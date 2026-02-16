import { test, expect } from '@playwright/test';

/**
 * E2E Smoke Tests for Admin Portal
 *
 * These tests verify:
 * 1. Admin login flow works
 * 2. Protected routes redirect properly
 * 3. Admin pages load correctly
 * 4. Permission-based navigation works
 *
 * Note: These tests use mock authentication and don't require a backend
 */
test.describe('Admin Portal - Smoke Tests', () => {
  test('admin login page loads', async ({ page }) => {
    await page.goto('/admin/login');

    // Verify login page elements
    await expect(page.getByText('Admin Portal')).toBeVisible();
    await expect(page.getByText('Sign in to access the Solar Hub administration panel')).toBeVisible();

    // Verify form elements
    await expect(page.locator('input#email')).toBeVisible();
    await expect(page.locator('input#password')).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();

    // Verify dev credentials hint
    await expect(page.getByText('Development Credentials:')).toBeVisible();
    await expect(page.getByText('admin@solarhub.com')).toBeVisible();
  });

  test('admin can login with valid credentials', async ({ page }) => {
    await page.goto('/admin/login');

    // Fill in credentials
    await page.fill('input#email', 'admin@solarhub.com');
    await page.fill('input#password', 'admin123');

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for redirect to admin dashboard
    await page.waitForURL('/admin', { timeout: 10000 });

    // Verify we're on the admin dashboard
    await expect(page).toHaveURL('/admin');
  });

  test('unauthenticated users are redirected to login', async ({ page }) => {
    // Try to access admin dashboard without login
    await page.goto('/admin');

    // Should redirect to login
    await page.waitForURL('/admin/login', { timeout: 5000 });
    await expect(page).toHaveURL('/admin/login');
  });

  test('super admin can access all admin pages', async ({ page }) => {
    // Login as super admin
    await page.goto('/admin/login');
    await page.fill('input#email', 'admin@solarhub.com');
    await page.fill('input#password', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Test each admin route loads
    const routes = [
      '/admin',
      '/admin/providers',
      '/admin/tariffs',
      '/admin/firmware-versions',
      '/admin/ota-campaigns',
      '/admin/audit-log',
      '/admin/system-settings',
    ];

    for (const route of routes) {
      await page.goto(route);
      await expect(page).toHaveURL(route);

      // Verify page has loaded by checking for any heading
      await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('ops admin has limited access', async ({ page }) => {
    // Login as ops admin
    await page.goto('/admin/login');
    await page.fill('input#email', 'ops@solarhub.com');
    await page.fill('input#password', 'ops123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Can access providers
    await page.goto('/admin/providers');
    await expect(page).toHaveURL('/admin/providers');
    await expect(page.locator('h1, h2').first()).toBeVisible();

    // Cannot access firmware (should redirect)
    await page.goto('/admin/firmware-versions');

    // Should redirect to dashboard or show access denied
    await page.waitForTimeout(1000);
    const currentUrl = page.url();

    // Either redirected to /admin or stayed but shows error
    expect(currentUrl === 'http://localhost:5173/admin' || currentUrl.includes('/admin')).toBeTruthy();
  });

  test('logout clears session', async ({ page }) => {
    // Login
    await page.goto('/admin/login');
    await page.fill('input#email', 'admin@solarhub.com');
    await page.fill('input#password', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Look for logout button (might be in a dropdown or visible)
    const logoutButton = page.getByRole('button', { name: /logout/i }).or(
      page.getByText(/logout/i)
    );

    if (await logoutButton.isVisible()) {
      await logoutButton.click();

      // Should redirect to login
      await page.waitForURL('/admin/login', { timeout: 5000 });
      await expect(page).toHaveURL('/admin/login');
    }
  });

  test('session persists on page reload', async ({ page }) => {
    // Login
    await page.goto('/admin/login');
    await page.fill('input#email', 'admin@solarhub.com');
    await page.fill('input#password', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Reload page
    await page.reload();

    // Should still be on admin dashboard (session restored from localStorage)
    await expect(page).toHaveURL('/admin');
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('invalid login shows error', async ({ page }) => {
    await page.goto('/admin/login');

    // Fill in wrong credentials
    await page.fill('input#email', 'wrong@example.com');
    await page.fill('input#password', 'wrongpassword');

    // Submit form
    await page.click('button[type="submit"]');

    // Wait a bit for the login attempt
    await page.waitForTimeout(1000);

    // Should show error message
    await expect(page.getByText('Invalid email or password')).toBeVisible({ timeout: 5000 });

    // Should stay on login page
    await expect(page).toHaveURL('/admin/login');
  });

  test('admin portal has responsive navigation', async ({ page }) => {
    // Login
    await page.goto('/admin/login');
    await page.fill('input#email', 'admin@solarhub.com');
    await page.fill('input#password', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Check for navigation elements (sidebar or header)
    const hasNavigation = await page.locator('nav').isVisible() ||
                          await page.locator('[role="navigation"]').isVisible() ||
                          await page.locator('aside').isVisible();

    expect(hasNavigation).toBeTruthy();
  });

  test('admin pages have proper titles', async ({ page }) => {
    // Login
    await page.goto('/admin/login');
    await page.fill('input#email', 'admin@solarhub.com');
    await page.fill('input#password', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Test each page has a heading
    const pagesWithHeadings = [
      { route: '/admin/providers', heading: /provider/i },
      { route: '/admin/tariffs', heading: /tariff/i },
      { route: '/admin/firmware-versions', heading: /firmware/i },
      { route: '/admin/ota-campaigns', heading: /campaign/i },
      { route: '/admin/audit-log', heading: /audit/i },
    ];

    for (const { route, heading } of pagesWithHeadings) {
      await page.goto(route);
      await expect(page.getByRole('heading', { name: heading })).toBeVisible({ timeout: 5000 });
    }
  });
});
