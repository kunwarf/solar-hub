import { test as base, Page } from '@playwright/test';
import { LoginPage } from '@/pages/auth/LoginPage';
import path from 'path';

/**
 * Extended fixtures for authentication
 */
type AuthFixtures = {
  authenticatedPage: Page;
  loginPage: LoginPage;
  userRole: 'owner' | 'admin' | 'viewer' | 'installer' | 'none';
};

/**
 * Custom test fixture with authentication support
 */
export const test = base.extend<AuthFixtures>({
  /**
   * Login page object fixture
   */
  loginPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await use(loginPage);
  },

  /**
   * Authenticated page fixture
   * Automatically navigates to dashboard after authentication
   */
  authenticatedPage: async ({ page }, use) => {
    // StorageState is already loaded from global setup
    // Just navigate to dashboard (root path) to verify authentication
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // Verify token exists (using the correct key)
    const token = await page.evaluate(() => localStorage.getItem('solar_hub_access_token'));
    if (!token) {
      throw new Error('Not authenticated: No token found in localStorage');
    }

    await use(page);
  },

  /**
   * User role fixture
   * Determines role based on project name
   */
  userRole: async ({}, use, testInfo) => {
    const projectName = testInfo.project.name.toLowerCase();

    let role: 'owner' | 'admin' | 'viewer' | 'installer' | 'none' = 'none';

    if (projectName.includes('owner')) {
      role = 'owner';
    } else if (projectName.includes('admin')) {
      role = 'admin';
    } else if (projectName.includes('viewer')) {
      role = 'viewer';
    } else if (projectName.includes('installer')) {
      role = 'installer';
    }

    await use(role);
  },
});

export { expect } from '@playwright/test';
