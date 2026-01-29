import { Page, Locator, expect } from '@playwright/test';

/**
 * Navigation Component (Sidebar/Header)
 * Handles navigation across the application
 */
export class NavigationComponent {
  readonly page: Page;

  // Navigation links
  readonly dashboardLink: Locator;
  readonly devicesLink: Locator;
  readonly analyticsLink: Locator;
  readonly billingLink: Locator;
  readonly outagesLink: Locator;
  readonly settingsLink: Locator;
  readonly adminLink: Locator;

  // User menu
  readonly userMenuButton: Locator;
  readonly profileLink: Locator;
  readonly logoutButton: Locator;

  // Mobile menu
  readonly mobileMenuButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // Navigation links
    this.dashboardLink = page.getByRole('link', { name: /dashboard|home/i });
    this.devicesLink = page.getByRole('link', { name: /devices/i });
    this.analyticsLink = page.getByRole('link', { name: /analytics|reports/i });
    this.billingLink = page.getByRole('link', { name: /billing|tariffs/i });
    this.outagesLink = page.getByRole('link', { name: /outages|grid/i });
    this.settingsLink = page.getByRole('link', { name: /settings/i });
    this.adminLink = page.getByRole('link', { name: /admin/i });

    // User menu
    this.userMenuButton = page.getByTestId('user-menu-button')
      .or(page.getByRole('button', { name: /user menu|profile/i }));
    this.profileLink = page.getByRole('link', { name: /profile/i });
    this.logoutButton = page.getByRole('button', { name: /logout|sign out/i });

    // Mobile
    this.mobileMenuButton = page.getByTestId('mobile-menu-button')
      .or(page.getByRole('button', { name: /menu/i }));
  }

  /**
   * Navigate to Dashboard
   */
  async goToDashboard() {
    await this.dashboardLink.click();
    await this.page.waitForURL('**/dashboard', { timeout: 10000 });
  }

  /**
   * Navigate to Devices
   */
  async goToDevices() {
    await this.devicesLink.click();
    await this.page.waitForURL('**/devices', { timeout: 10000 });
  }

  /**
   * Navigate to Analytics
   */
  async goToAnalytics() {
    await this.analyticsLink.click();
    await this.page.waitForURL('**/analytics', { timeout: 10000 });
  }

  /**
   * Navigate to Billing
   */
  async goToBilling() {
    await this.billingLink.click();
    await this.page.waitForURL('**/billing', { timeout: 10000 });
  }

  /**
   * Navigate to Outages
   */
  async goToOutages() {
    await this.outagesLink.click();
    await this.page.waitForURL('**/outages', { timeout: 10000 });
  }

  /**
   * Navigate to Settings
   */
  async goToSettings() {
    await this.settingsLink.click();
    await this.page.waitForURL('**/settings', { timeout: 10000 });
  }

  /**
   * Navigate to Admin
   */
  async goToAdmin() {
    await this.adminLink.click();
    await this.page.waitForURL('**/admin', { timeout: 10000 });
  }

  /**
   * Open user menu
   */
  async openUserMenu() {
    await this.userMenuButton.click();
  }

  /**
   * Logout
   */
  async logout() {
    if (!await this.logoutButton.isVisible()) {
      await this.openUserMenu();
    }

    await this.logoutButton.click();
    await this.page.waitForURL('**/auth', { timeout: 10000 });
  }

  /**
   * Open mobile menu (on small screens)
   */
  async openMobileMenu() {
    await this.mobileMenuButton.click();
  }

  /**
   * Verify navigation is visible
   */
  async expectNavigationVisible() {
    await expect(this.dashboardLink.or(this.mobileMenuButton)).toBeVisible();
  }

  /**
   * Verify user is on specific page
   */
  async expectOnPage(page: 'dashboard' | 'devices' | 'analytics' | 'billing' | 'outages' | 'settings' | 'admin') {
    await expect(this.page).toHaveURL(new RegExp(page));
  }
}
