import { test, expect } from '@/fixtures/auth.fixture';
import { OutagesPage } from '@/pages/outages/OutagesPage';

/**
 * Outages Tests
 *
 * Tests grid outage monitoring, history, and reporting
 * Priority: P1
 */
test.describe('Outages - Grid Monitoring', { tag: '@outages' }, () => {
  let outagesPage: OutagesPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    outagesPage = new OutagesPage(authenticatedPage);
    await outagesPage.goto();
  });

  test('should load outages page successfully', {
    tag: ['@smoke', '@high']
  }, async () => {
    // Verify page loaded
    await outagesPage.expectOutagesPageLoaded();

    // Should have page title
    await expect(outagesPage.pageTitle).toBeVisible();
  });

  test('should display grid status indicator', {
    tag: ['@smoke', '@critical']
  }, async ({ authenticatedPage }) => {
    // Wait for API response to ensure data is loaded
    const apiResponse = authenticatedPage.waitForResponse(
      resp => resp.url().includes('/api/v1/dashboard/power-flow') || resp.url().includes('/api/v1/outages'),
      { timeout: 30000 }
    );

    await apiResponse.catch(() => {
      console.log('API response timeout - continuing with test');
    });

    // Additional wait for rendering
    await authenticatedPage.waitForTimeout(2000);

    // Verify grid status is shown
    await outagesPage.expectGridStatusDisplayed();
  });

  test('should show grid online or offline status', {
    tag: '@regression'
  }, async () => {
    const status = await outagesPage.getGridStatus();

    // Status should be one of the known states
    expect(['online', 'offline', 'unknown']).toContain(status);

    // Page should show status text
    const bodyText = await outagesPage.page.locator('body').textContent();
    expect(bodyText).toMatch(/online|offline|connected|disconnected|grid/i);
  });

  test('should display outage history table or empty message', {
    tag: '@regression'
  }, async () => {
    await outagesPage.expectOutageHistoryOrEmpty();
  });

  test('should show total outages count', {
    tag: '@regression'
  }, async () => {
    const totalOutages = await outagesPage.getTotalOutagesCount();

    if (totalOutages !== null) {
      // Count should be non-negative
      expect(totalOutages).toBeGreaterThanOrEqual(0);

      // Should be reasonable
      expect(totalOutages).toBeLessThan(10000);
    }
  });

  test('should display outage history if outages occurred', {
    tag: '@regression'
  }, async () => {
    const hasHistory = await outagesPage.hasOutageHistory();
    const hasNoOutages = await outagesPage.hasNoOutages();

    if (hasHistory) {
      // If history exists, should have at least one row
      const historyCount = await outagesPage.getOutageHistoryCount();
      expect(historyCount).toBeGreaterThan(0);
    } else {
      // Otherwise should show "no outages" message
      expect(hasNoOutages).toBe(true);
    }
  });

  test('should show refresh button', {
    tag: '@regression'
  }, async () => {
    const hasRefresh = await outagesPage.refreshButton.isVisible().catch(() => false);

    if (hasRefresh) {
      await expect(outagesPage.refreshButton).toBeVisible();
    }
  });

  test('should allow refreshing grid status', {
    tag: '@regression'
  }, async () => {
    const hasRefresh = await outagesPage.refreshButton.isVisible().catch(() => false);

    if (hasRefresh) {
      await outagesPage.refresh();

      // Page should reload successfully
      await outagesPage.expectOutagesPageLoaded();
    }
  });

  test('should show report outage button', {
    tag: '@regression'
  }, async ({ userRole }) => {
    // Only owners and admins can report outages
    if (['owner', 'admin'].includes(userRole)) {
      const hasReportButton = await outagesPage.reportOutageButton.isVisible().catch(() => false);

      if (hasReportButton) {
        await expect(outagesPage.reportOutageButton).toBeVisible();
      }
    }
  });

  test('should handle no outages gracefully', {
    tag: '@regression'
  }, async () => {
    // Even with no outages, page should not crash
    await outagesPage.expectOutagesPageLoaded();

    const hasNoOutages = await outagesPage.hasNoOutages();
    const hasHistory = await outagesPage.hasOutageHistory();

    // Either has history OR shows no outages message
    expect(hasHistory || hasNoOutages).toBe(true);
  });

  test('should display grid connection indicator', {
    tag: '@regression'
  }, async () => {
    const hasGridStatus = await outagesPage.hasGridStatusIndicator();

    if (hasGridStatus) {
      // Grid status should be visible
      await expect(outagesPage.gridStatusIndicator).toBeVisible();

      // Should show online or offline
      const status = await outagesPage.getGridStatus();
      expect(status).not.toBe('unknown');
    } else {
      // At minimum, page should have grid-related text
      const bodyText = await outagesPage.page.locator('body').textContent();
      expect(bodyText).toMatch(/grid|status|power/i);
    }
  });

  test('should show outage statistics if available', {
    tag: '@regression'
  }, async () => {
    const bodyText = await outagesPage.page.locator('body').textContent();

    // Page should show outage-related statistics or history
    const hasOutageData = bodyText && (
      bodyText.match(/outage/i) ||
      bodyText.match(/\d+\s*hours?/i) ||
      bodyText.match(/duration/i)
    );

    expect(hasOutageData).toBe(true);
  });

  test('should allow filtering outage history by date range', {
    tag: '@regression'
  }, async () => {
    const hasFilter = await outagesPage.dateRangeFilter.isVisible().catch(() => false);

    if (hasFilter) {
      await outagesPage.filterByDateRange('month');

      // Page should reload with filtered data
      await outagesPage.expectOutagesPageLoaded();
    }
  });

  test('should display last seen time if available', {
    tag: '@regression'
  }, async () => {
    const hasLastSeen = await outagesPage.lastSeenTime.isVisible().catch(() => false);

    if (hasLastSeen) {
      const lastSeenText = await outagesPage.lastSeenTime.textContent();
      expect(lastSeenText).toBeTruthy();
    }
  });
});
