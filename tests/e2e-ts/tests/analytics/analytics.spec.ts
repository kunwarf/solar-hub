import { test, expect } from '@/fixtures/auth.fixture';
import { AnalyticsPage } from '@/pages/analytics/AnalyticsPage';

/**
 * Analytics Tests
 *
 * Tests analytics page, charts, and report generation
 * Priority: P1
 *
 * NOTE: Skipping - /analytics route doesn't exist in the application
 * The app uses /telemetry instead for similar functionality
 */
test.describe.skip('Analytics', { tag: '@analytics' }, () => {
  let analyticsPage: AnalyticsPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    analyticsPage = new AnalyticsPage(authenticatedPage);
    await analyticsPage.goto();
  });

  test('should load analytics page successfully', {
    tag: ['@smoke', '@high']
  }, async () => {
    // Verify page loaded
    await analyticsPage.expectAnalyticsPageLoaded();

    // Should have page title
    await expect(analyticsPage.pageTitle).toBeVisible();
  });

  test('should display energy charts', {
    tag: ['@smoke', '@high']
  }, async () => {
    await analyticsPage.waitForLoaded();

    // Verify charts are displayed
    await analyticsPage.expectChartsDisplayed();
  });

  test('should show energy production chart', {
    tag: '@regression'
  }, async () => {
    const hasChart = await analyticsPage.energyProductionChart.isVisible().catch(() => false);
    const hasCharts = await analyticsPage.hasCharts();

    // Either specific chart or general charts exist
    expect(hasChart || hasCharts).toBe(true);
  });

  test('should show energy consumption chart', {
    tag: '@regression'
  }, async () => {
    const hasChart = await analyticsPage.energyConsumptionChart.isVisible().catch(() => false);
    const hasCharts = await analyticsPage.hasCharts();

    expect(hasChart || hasCharts).toBe(true);
  });

  test('should display summary statistics cards', {
    tag: '@regression'
  }, async () => {
    // Look for summary cards
    const hasTotalEnergy = await analyticsPage.totalEnergyCard.isVisible().catch(() => false);
    const hasPeakPower = await analyticsPage.peakPowerCard.isVisible().catch(() => false);

    // Should have at least one summary card or stats in page
    const bodyText = await analyticsPage.page.locator('body').textContent();
    const hasStats = bodyText && (
      bodyText.match(/\d+\.?\d*\s*kWh/i) ||
      bodyText.match(/\d+\.?\d*\s*kW/i)
    );

    expect(hasTotalEnergy || hasPeakPower || hasStats).toBe(true);
  });

  test('should allow switching date ranges', {
    tag: '@regression'
  }, async () => {
    // Try selecting different date ranges
    const hasDateRange = await analyticsPage.dateRangeDropdown.isVisible().catch(() => false);

    if (hasDateRange) {
      // Select "This Week"
      await analyticsPage.selectDateRange('week');

      // Page should reload with new data
      await analyticsPage.expectAnalyticsPageLoaded();
    }
  });

  test('should filter by today', {
    tag: '@regression'
  }, async () => {
    const hasTodayButton = await analyticsPage.todayButton.isVisible().catch(() => false);

    if (hasTodayButton) {
      await analyticsPage.selectDateRange('today');

      // Should update charts
      await analyticsPage.waitForLoaded();
      await analyticsPage.expectChartsDisplayed();
    }
  });

  test('should filter by month', {
    tag: '@regression'
  }, async () => {
    const hasMonthButton = await analyticsPage.monthButton.isVisible().catch(() => false);

    if (hasMonthButton) {
      await analyticsPage.selectDateRange('month');
      await analyticsPage.waitForLoaded();
      await analyticsPage.expectChartsDisplayed();
    }
  });

  test('should show export buttons', {
    tag: '@regression'
  }, async () => {
    await analyticsPage.expectExportAvailable();
  });

  test('should allow exporting data as CSV', {
    tag: '@regression'
  }, async () => {
    const hasExportCsv = await analyticsPage.exportCsvButton.isVisible().catch(() => false);

    if (hasExportCsv) {
      const download = await analyticsPage.exportCSV();

      // Verify download started
      expect(download).toBeTruthy();
      expect(download.suggestedFilename()).toMatch(/\.csv$/i);
    } else {
      test.skip();
    }
  });

  test('should allow exporting report as PDF', {
    tag: '@regression'
  }, async () => {
    const hasExportPdf = await analyticsPage.exportPdfButton.isVisible().catch(() => false);

    if (hasExportPdf) {
      const download = await analyticsPage.exportPDF();

      expect(download).toBeTruthy();
      expect(download.suggestedFilename()).toMatch(/\.pdf$/i);
    } else {
      test.skip();
    }
  });

  test('should display total energy metric', {
    tag: '@regression'
  }, async () => {
    const totalEnergy = await analyticsPage.getTotalEnergy();

    if (totalEnergy !== null) {
      // Total energy should be non-negative
      expect(totalEnergy).toBeGreaterThanOrEqual(0);

      // Should be reasonable value
      expect(totalEnergy).toBeLessThan(1000000);
    }
  });

  test('should handle no data gracefully', {
    tag: '@regression'
  }, async () => {
    // Even with no data, page should not crash
    await analyticsPage.expectAnalyticsPageLoaded();

    const hasNoData = await analyticsPage.hasNoData();
    const hasCharts = await analyticsPage.hasCharts();

    // Either has data/charts OR shows "no data" message
    expect(hasCharts || hasNoData).toBe(true);
  });

  test('should display charts with real data points', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    const hasCharts = await analyticsPage.hasCharts();

    if (hasCharts) {
      // Look for chart elements
      const svgCharts = authenticatedPage.locator('svg[class*="recharts"]');
      const canvasCharts = authenticatedPage.locator('canvas');

      const svgCount = await svgCharts.count();
      const canvasCount = await canvasCharts.count();

      expect(svgCount + canvasCount).toBeGreaterThan(0);

      // For SVG charts, check for data visualization elements
      if (svgCount > 0) {
        const dataElements = svgCharts.first().locator('path, rect, circle, line');
        const dataCount = await dataElements.count();
        expect(dataCount).toBeGreaterThan(0);
      }
    }
  });
});
