import { test, expect } from '@playwright/test';

/**
 * E2E Test Flow 3: Permission-Based Access Control
 *
 * Tests the RBAC (Role-Based Access Control) system:
 * 1. Super admin has full access
 * 2. Ops admin has limited access
 * 3. Firmware admin can only access firmware features
 * 4. Read-only admin cannot modify anything
 * 5. Direct URL navigation is blocked for unauthorized pages
 */
test.describe('Permission-Based Access Control', () => {
  test('super_admin has full access to all features', async ({ page }) => {
    // Login as super admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'admin@solarhub.com');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Verify all navigation links are visible
    await expect(page.locator('a[href="/admin/providers"]')).toBeVisible();
    await expect(page.locator('a[href="/admin/tariffs"]')).toBeVisible();
    await expect(page.locator('a[href="/admin/firmware-versions"]')).toBeVisible();
    await expect(page.locator('a[href="/admin/ota-campaigns"]')).toBeVisible();
    await expect(page.locator('a[href="/admin/users"]')).toBeVisible();
    await expect(page.locator('a[href="/admin/audit-log"]')).toBeVisible();

    // Verify can access providers page
    await page.goto('/admin/providers');
    await expect(page.locator('h1')).toContainText('Electricity Providers');

    // Verify can access firmware page
    await page.goto('/admin/firmware-versions');
    await expect(page.locator('h1')).toContainText('Firmware Versions');

    // Verify action buttons are visible
    await expect(page.locator('button:has-text("Upload Firmware")')).toBeVisible();
  });

  test('ops_admin has limited access', async ({ page }) => {
    // Login as ops_admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'ops@solarhub.com');
    await page.fill('input[name="password"]', 'ops123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Verify can see provider links
    await expect(page.locator('a[href="/admin/providers"]')).toBeVisible();
    await expect(page.locator('a[href="/admin/tariffs"]')).toBeVisible();

    // Verify CANNOT see firmware links
    await expect(page.locator('a[href="/admin/firmware-versions"]')).not.toBeVisible();
    await expect(page.locator('a[href="/admin/ota-campaigns"]')).not.toBeVisible();

    // Verify can access providers
    await page.goto('/admin/providers');
    await expect(page.locator('h1')).toContainText('Electricity Providers');

    // Verify direct navigation to firmware is blocked
    await page.goto('/admin/firmware-versions');

    // Should redirect to dashboard or show access denied
    await expect(page).toHaveURL('/admin');
    await expect(page.locator('text=You don\'t have permission')).toBeVisible({ timeout: 5000 });
  });

  test('firmware_admin can only access firmware features', async ({ page }) => {
    // Login as firmware_admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'firmware@solarhub.com');
    await page.fill('input[name="password"]', 'firmware123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Verify can see firmware links
    await expect(page.locator('a[href="/admin/firmware-versions"]')).toBeVisible();
    await expect(page.locator('a[href="/admin/ota-campaigns"]')).toBeVisible();

    // Verify CANNOT see provider links
    await expect(page.locator('a[href="/admin/providers"]')).not.toBeVisible();
    await expect(page.locator('a[href="/admin/tariffs"]')).not.toBeVisible();

    // Verify can access firmware
    await page.goto('/admin/firmware-versions');
    await expect(page.locator('h1')).toContainText('Firmware Versions');

    // Verify direct navigation to providers is blocked
    await page.goto('/admin/providers');
    await expect(page).toHaveURL('/admin');
    await expect(page.locator('text=You don\'t have permission')).toBeVisible({ timeout: 5000 });
  });

  test('read_only admin cannot modify anything', async ({ page }) => {
    // Login as read_only admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'readonly@solarhub.com');
    await page.fill('input[name="password"]', 'readonly123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Navigate to providers (should be able to view)
    await page.goto('/admin/providers');
    await expect(page.locator('h1')).toContainText('Electricity Providers');

    // Verify create/edit/delete buttons are NOT visible
    await expect(page.locator('button:has-text("Add Provider")')).not.toBeVisible();
    await expect(page.locator('button:has-text("Edit")')).not.toBeVisible();
    await expect(page.locator('button:has-text("Delete")')).not.toBeVisible();

    // Navigate to firmware (if accessible)
    const firmwareLink = page.locator('a[href="/admin/firmware-versions"]');
    if (await firmwareLink.isVisible()) {
      await page.goto('/admin/firmware-versions');

      // Verify upload button is NOT visible
      await expect(page.locator('button:has-text("Upload Firmware")')).not.toBeVisible();
    }
  });

  test('unauthenticated users are redirected to login', async ({ page }) => {
    // Try to access admin dashboard without login
    await page.goto('/admin');

    // Should redirect to login
    await expect(page).toHaveURL('/admin/login');

    // Try to access providers without login
    await page.goto('/admin/providers');

    // Should redirect to login
    await expect(page).toHaveURL('/admin/login');

    // Try to access firmware without login
    await page.goto('/admin/firmware-versions');

    // Should redirect to login
    await expect(page).toHaveURL('/admin/login');
  });

  test('logout clears session and redirects', async ({ page }) => {
    // Login as admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'admin@solarhub.com');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Click logout button
    await page.click('button:has-text("Logout")');

    // Should redirect to login
    await expect(page).toHaveURL('/admin/login');

    // Try to access admin page again
    await page.goto('/admin');

    // Should still be on login (session cleared)
    await expect(page).toHaveURL('/admin/login');
  });

  test('session persists on page reload', async ({ page }) => {
    // Login as admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'admin@solarhub.com');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Reload the page
    await page.reload();

    // Should still be authenticated
    await expect(page).toHaveURL('/admin');
    await expect(page.locator('h1')).toContainText('Admin Dashboard');
  });

  test('different admin roles see different dashboards', async ({ page }) => {
    // Login as ops_admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'ops@solarhub.com');
    await page.fill('input[name="password"]', 'ops123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Count visible navigation items
    const opsNavItems = await page.locator('nav a').count();

    // Logout
    await page.click('button:has-text("Logout")');

    // Login as super_admin
    await page.fill('input[name="email"]', 'admin@solarhub.com');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin');

    // Count visible navigation items
    const adminNavItems = await page.locator('nav a').count();

    // Super admin should have more navigation items
    expect(adminNavItems).toBeGreaterThan(opsNavItems);
  });
});
