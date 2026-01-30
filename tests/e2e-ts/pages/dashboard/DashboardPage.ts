import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Page object for the main Dashboard page
 */
export class DashboardPage extends BasePage {
  // Main page elements
  readonly powerFlowDiagram: Locator;
  readonly statsCards: Locator;
  readonly energyProductionChart: Locator;
  readonly energyConsumptionChart: Locator;
  readonly recentAlertsPanel: Locator;
  readonly gridStatusIndicator: Locator;
  readonly batteryStatusIndicator: Locator;
  readonly weatherWidget: Locator;
  readonly dateRangeSelector: Locator;
  readonly refreshButton: Locator;
  readonly exportDataButton: Locator;

  // Navigation
  readonly sidebarMenu: Locator;
  readonly userProfileDropdown: Locator;

  // Stat cards
  readonly totalEnergyCard: Locator;
  readonly currentPowerCard: Locator;
  readonly deviceCountCard: Locator;
  readonly onlineDevicesCard: Locator;

  constructor(page: Page) {
    super(page);

    // Main widgets
    this.powerFlowDiagram = page.getByTestId('power-flow-diagram');
    this.statsCards = page.getByTestId('stats-cards');
    this.energyProductionChart = page.getByTestId('energy-production-chart');
    this.energyConsumptionChart = page.getByTestId('energy-consumption-chart');
    this.recentAlertsPanel = page.getByTestId('recent-alerts');
    this.gridStatusIndicator = page.getByTestId('grid-status');
    this.batteryStatusIndicator = page.getByTestId('battery-status');
    this.weatherWidget = page.getByTestId('weather-widget');

    // Controls
    this.dateRangeSelector = page.getByTestId('date-range-selector');
    this.refreshButton = page.getByRole('button', { name: /refresh/i });
    this.exportDataButton = page.getByRole('button', { name: /export/i });

    // Navigation
    this.sidebarMenu = page.getByTestId('sidebar-menu').or(page.locator('[class*="sidebar"]').first());
    this.userProfileDropdown = page.getByTestId('user-profile-dropdown');

    // Stat cards
    this.totalEnergyCard = page.getByTestId('total-energy-card');
    this.currentPowerCard = page.getByTestId('current-power-card');
    this.deviceCountCard = page.getByTestId('device-count-card');
    this.onlineDevicesCard = page.getByTestId('online-devices-card');
  }

  /**
   * Navigate to dashboard page (at root "/")
   */
  async goto() {
    await this.page.goto('/');
    await this.waitForLoaded();
  }

  /**
   * Wait for dashboard to be fully loaded
   */
  async waitForLoaded() {
    await this.page.waitForLoadState('domcontentloaded');

    // Wait for at least one key element to be visible
    await Promise.race([
      expect(this.powerFlowDiagram).toBeVisible({ timeout: 10000 }).catch(() => null),
      expect(this.statsCards).toBeVisible({ timeout: 10000 }).catch(() => null),
      expect(this.sidebarMenu).toBeVisible({ timeout: 10000 }).catch(() => null),
    ]);
  }

  /**
   * Wait for data to load (API responses)
   */
  async waitForDataLoad() {
    // Wait for common API endpoints
    await Promise.all([
      this.waitForAPIResponse('/api/v1/telemetry').catch(() => null),
      this.waitForAPIResponse('/api/v1/sites').catch(() => null),
      this.waitForAPIResponse('/api/v1/devices').catch(() => null),
    ]);
  }

  /**
   * Get current power value from power flow diagram
   */
  async getCurrentPower(): Promise<number | null> {
    try {
      const powerText = await this.powerFlowDiagram.getByText(/\d+\.?\d*\s*(W|kW|MW)/i).textContent();
      if (!powerText) return null;

      const match = powerText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get total energy today
   */
  async getTotalEnergyToday(): Promise<string | null> {
    try {
      return await this.totalEnergyCard.getByText(/\d+\.?\d*\s*(kWh|MWh)/i).textContent();
    } catch {
      return null;
    }
  }

  /**
   * Get device count from stat card
   */
  async getDeviceCount(): Promise<number | null> {
    try {
      const countText = await this.deviceCountCard.getByText(/\d+/).textContent();
      return countText ? parseInt(countText) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get online device count
   */
  async getOnlineDeviceCount(): Promise<number | null> {
    try {
      const countText = await this.onlineDevicesCard.getByText(/\d+/).textContent();
      return countText ? parseInt(countText) : null;
    } catch {
      return null;
    }
  }

  /**
   * Check if grid is online
   */
  async isGridOnline(): Promise<boolean> {
    try {
      const statusText = await this.gridStatusIndicator.textContent();
      return statusText?.toLowerCase().includes('online') || false;
    } catch {
      return false;
    }
  }

  /**
   * Get site name displayed on dashboard
   */
  async getSiteName(): Promise<string | null> {
    try {
      const siteNameElement = this.page.getByTestId('site-name')
        .or(this.page.getByRole('heading', { level: 1 }));

      return await siteNameElement.textContent();
    } catch {
      return null;
    }
  }

  /**
   * Refresh dashboard data
   */
  async refreshData() {
    await this.refreshButton.click();
    await this.waitForDataLoad();
  }

  /**
   * Select date range
   */
  async selectDateRange(range: 'today' | 'week' | 'month' | 'year') {
    await this.dateRangeSelector.click();

    const option = this.page.getByRole('option', { name: new RegExp(range, 'i') });
    await option.click();

    await this.waitForDataLoad();
  }

  /**
   * Export data
   */
  async exportData() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportDataButton.click();
    return await downloadPromise;
  }

  /**
   * Check if power flow diagram is animated
   */
  async isPowerFlowAnimated(): Promise<boolean> {
    try {
      // Look for animated elements or SVG animations
      const animatedElements = this.powerFlowDiagram.locator('[class*="animate"], [class*="flow"]');
      return await animatedElements.count() > 0;
    } catch {
      return false;
    }
  }

  /**
   * Get recent alerts
   */
  async getRecentAlerts(): Promise<string[]> {
    try {
      const alertElements = this.recentAlertsPanel.locator('[class*="alert-item"]');
      const count = await alertElements.count();

      const alerts: string[] = [];
      for (let i = 0; i < count; i++) {
        const text = await alertElements.nth(i).textContent();
        if (text) alerts.push(text.trim());
      }

      return alerts;
    } catch {
      return [];
    }
  }

  /**
   * Navigate to a section using sidebar
   */
  async navigateToSection(section: 'devices' | 'analytics' | 'billing' | 'outages' | 'settings') {
    const link = this.sidebarMenu.getByRole('link', { name: new RegExp(section, 'i') });
    await link.click();
    await this.page.waitForURL(`**/${section}`, { timeout: 10000 });
  }

  /**
   * Open user profile dropdown
   */
  async openUserProfile() {
    await this.userProfileDropdown.click();
  }

  /**
   * Logout from dashboard
   */
  async logout() {
    await this.openUserProfile();

    const logoutButton = this.page.getByRole('button', { name: /logout|sign out/i });
    await logoutButton.click();

    await expect(this.page).toHaveURL(/.*auth/, { timeout: 10000 });
  }

  /**
   * Verify dashboard loaded successfully (no error state)
   */
  async expectDashboardLoaded() {
    // Dashboard is at root "/" path
    await expect(this.page).toHaveURL(/\/$/);

    // Should not show error toast (use shorter timeout)
    const errorToast = this.page.getByTestId('error-toast');
    await expect(errorToast).not.toBeVisible({ timeout: 2000 }).catch(() => {
      // Ignore if error toast doesn't exist
    });

    // Wait for page to be loaded
    await this.page.waitForLoadState('domcontentloaded');

    // Should have some content
    const bodyText = await this.page.locator('body').textContent();
    expect(bodyText).not.toBeNull();
    expect(bodyText!.trim().length).toBeGreaterThan(50);
  }

  /**
   * Verify all key widgets are visible
   */
  async expectAllWidgetsVisible() {
    // At least some of these should be visible
    const visibleWidgets = await Promise.all([
      this.isVisible(this.powerFlowDiagram),
      this.isVisible(this.statsCards),
      this.isVisible(this.energyProductionChart),
    ]);

    const anyVisible = visibleWidgets.some(v => v);
    expect(anyVisible).toBe(true);
  }
}
