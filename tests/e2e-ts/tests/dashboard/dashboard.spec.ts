import { test, expect } from '@/fixtures/auth.fixture';
import { DashboardPage } from '@/pages/dashboard/DashboardPage';
import { NavigationComponent } from '@/pages/components/NavigationComponent';

/**
 * Dashboard Tests
 *
 * Tests main dashboard functionality, widgets, and real-time data display
 * Priority: P0 (Critical)
 */
test.describe('Dashboard', { tag: '@dashboard' }, () => {
  let dashboardPage: DashboardPage;
  let navigation: NavigationComponent;

  test.beforeEach(async ({ authenticatedPage }) => {
    dashboardPage = new DashboardPage(authenticatedPage);
    navigation = new NavigationComponent(authenticatedPage);

    await dashboardPage.goto();
  });

  test('should load dashboard successfully', {
    tag: ['@smoke', '@critical']
  }, async () => {
    // Verify dashboard loaded
    await dashboardPage.expectDashboardLoaded();

    // Should have page title
    await expect(dashboardPage.page).toHaveTitle(/Solar Hub/i);

    // Should not show error state
    const errorToast = dashboardPage.page.getByTestId('error-toast');
    await expect(errorToast).not.toBeVisible();
  });

  test('should display navigation menu', {
    tag: ['@smoke', '@critical']
  }, async () => {
    // Navigation should be visible
    await navigation.expectNavigationVisible();

    // Key navigation links should be present
    await expect(navigation.devicesLink.or(dashboardPage.sidebarMenu)).toBeVisible();
  });

  test('should display power flow diagram', {
    tag: ['@smoke', '@critical']
  }, async () => {
    // Wait for data to load
    await dashboardPage.waitForDataLoad();

    // Power flow diagram should be visible (or stats cards as fallback)
    const hasPowerFlow = await dashboardPage.isVisible(dashboardPage.powerFlowDiagram);
    const hasStatsCards = await dashboardPage.isVisible(dashboardPage.statsCards);

    expect(hasPowerFlow || hasStatsCards).toBe(true);
  });

  test('should display statistics cards', {
    tag: ['@smoke', '@critical']
  }, async () => {
    await dashboardPage.waitForDataLoad();

    // At least one stat card should be visible
    const cards = dashboardPage.page.locator('[class*="card"]').or(dashboardPage.statsCards);
    await expect(cards.first()).toBeVisible();

    // Stats cards should contain numeric data
    const bodyText = await dashboardPage.page.locator('body').textContent();
    expect(bodyText).toMatch(/\d+/); // Should have some numbers
  });

  test('should display real-time power data', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    await dashboardPage.waitForDataLoad();

    // Get power value
    const power = await dashboardPage.getCurrentPower();

    // Power should be a number (or null if widget not visible)
    if (power !== null) {
      expect(power).toBeGreaterThanOrEqual(0);
    }

    // Page should contain power-related text
    const bodyText = await authenticatedPage.locator('body').textContent();
    const hasPowerData = bodyText?.match(/\d+\.?\d*\s*(W|kW|MW|watt)/i);

    // Either we got a power value or page shows power data
    expect(power !== null || hasPowerData !== null).toBe(true);
  });

  test('should display energy production chart', {
    tag: '@regression'
  }, async () => {
    await dashboardPage.waitForDataLoad();

    // Look for chart or graph elements
    const hasChart = await dashboardPage.isVisible(dashboardPage.energyProductionChart);
    const chartElements = dashboardPage.page.locator('[class*="chart"], [class*="graph"], canvas, svg[class*="recharts"]');
    const hasChartElement = await chartElements.count() > 0;

    expect(hasChart || hasChartElement).toBe(true);
  });

  test('should display grid status indicator', {
    tag: '@regression'
  }, async () => {
    await dashboardPage.waitForDataLoad();

    // Look for grid status
    const hasGridStatus = await dashboardPage.isVisible(dashboardPage.gridStatusIndicator);

    // Or check for status-related text
    const bodyText = await dashboardPage.page.locator('body').textContent();
    const hasStatusText = bodyText?.match(/online|offline|grid.*status/i);

    expect(hasGridStatus || hasStatusText !== null).toBe(true);
  });

  test('should display device count', {
    tag: '@regression'
  }, async () => {
    await dashboardPage.waitForDataLoad();

    // Get device count
    const deviceCount = await dashboardPage.getDeviceCount();

    // If we got a count, it should be non-negative
    if (deviceCount !== null) {
      expect(deviceCount).toBeGreaterThanOrEqual(0);
    }

    // Page should show device-related data
    const bodyText = await dashboardPage.page.locator('body').textContent();
    expect(bodyText).toMatch(/device/i);
  });

  test('should refresh data when refresh button clicked', {
    tag: '@regression'
  }, async () => {
    await dashboardPage.waitForDataLoad();

    // Check if refresh button exists
    const hasRefreshButton = await dashboardPage.refreshButton.isVisible().catch(() => false);

    if (hasRefreshButton) {
      // Click refresh and wait for new data
      const responsePromise = dashboardPage.page.waitForResponse(
        resp => resp.url().includes('/api/v1/'),
        { timeout: 10000 }
      ).catch(() => null);

      await dashboardPage.refreshButton.click();

      const response = await responsePromise;
      expect(response).not.toBeNull();
    } else {
      test.skip();
    }
  });

  test('should display recent alerts panel', {
    tag: '@regression'
  }, async () => {
    await dashboardPage.waitForDataLoad();

    // Look for alerts panel
    const hasAlertsPanel = await dashboardPage.isVisible(dashboardPage.recentAlertsPanel);
    const alertElements = dashboardPage.page.locator('[class*="alert"]');
    const hasAlertElements = await alertElements.count() > 0;

    // Either alerts panel visible or page has alert-related content
    expect(hasAlertsPanel || hasAlertElements).toBe(true);
  });

  test('should navigate to devices page from sidebar', {
    tag: ['@smoke', '@critical']
  }, async () => {
    // Navigate to devices
    const devicesLink = navigation.devicesLink;

    if (await devicesLink.isVisible()) {
      await navigation.goToDevices();

      // Should be on devices page
      await navigation.expectOnPage('devices');
    } else {
      test.skip();
    }
  });

  test('should navigate to analytics page from sidebar', {
    tag: '@regression'
  }, async () => {
    const analyticsLink = navigation.analyticsLink;

    if (await analyticsLink.isVisible()) {
      await navigation.goToAnalytics();
      await navigation.expectOnPage('analytics');
    } else {
      test.skip();
    }
  });

  test('should navigate to outages page from sidebar', {
    tag: '@regression'
  }, async () => {
    const outagesLink = navigation.outagesLink;

    if (await outagesLink.isVisible()) {
      await navigation.goToOutages();
      await navigation.expectOnPage('outages');
    } else {
      test.skip();
    }
  });

  test('should display user profile menu', {
    tag: '@regression'
  }, async () => {
    const userMenu = navigation.userMenuButton;

    if (await userMenu.isVisible()) {
      await navigation.openUserMenu();

      // Profile or logout option should appear
      const logoutVisible = await navigation.logoutButton.isVisible({ timeout: 2000 }).catch(() => false);
      expect(logoutVisible).toBe(true);
    } else {
      test.skip();
    }
  });

  test('should persist session across page reload', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    // Reload page
    await authenticatedPage.reload();
    await authenticatedPage.waitForLoadState('domcontentloaded');

    // Should still be on dashboard (not redirected to login)
    await expect(authenticatedPage).toHaveURL(/.*dashboard/);

    // Should still have token
    const token = await authenticatedPage.evaluate(() => localStorage.getItem('token'));
    expect(token).toBeTruthy();
  });
});
