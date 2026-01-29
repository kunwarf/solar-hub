import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Page object for the Analytics/Reports page
 * Handles energy analytics, charts, and report generation
 */
export class AnalyticsPage extends BasePage {
  // Main elements
  readonly pageTitle: Locator;
  readonly energyProductionChart: Locator;
  readonly energyConsumptionChart: Locator;
  readonly comparisonChart: Locator;
  readonly efficiencyChart: Locator;

  // Date range selector
  readonly dateRangeDropdown: Locator;
  readonly startDatePicker: Locator;
  readonly endDatePicker: Locator;
  readonly applyDateButton: Locator;

  // Quick date ranges
  readonly todayButton: Locator;
  readonly weekButton: Locator;
  readonly monthButton: Locator;
  readonly yearButton: Locator;
  readonly customRangeButton: Locator;

  // Summary cards
  readonly totalEnergyCard: Locator;
  readonly peakPowerCard: Locator;
  readonly averageEfficiencyCard: Locator;
  readonly carbonSavingsCard: Locator;

  // Chart types
  readonly lineChartButton: Locator;
  readonly barChartButton: Locator;
  readonly pieChartButton: Locator;

  // Export/Download
  readonly exportPdfButton: Locator;
  readonly exportCsvButton: Locator;
  readonly exportExcelButton: Locator;
  readonly printReportButton: Locator;

  // Filters
  readonly deviceFilter: Locator;
  readonly metricFilter: Locator;
  readonly granularityFilter: Locator;

  // Chart container
  readonly chartsContainer: Locator;
  readonly noDataMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Main elements
    this.pageTitle = page.getByRole('heading', { name: /analytics|reports/i });
    this.energyProductionChart = page.getByTestId('energy-production-chart');
    this.energyConsumptionChart = page.getByTestId('energy-consumption-chart');
    this.comparisonChart = page.getByTestId('comparison-chart');
    this.efficiencyChart = page.getByTestId('efficiency-chart');

    // Date range
    this.dateRangeDropdown = page.getByTestId('date-range-selector')
      .or(page.getByRole('button', { name: /date range/i }));
    this.startDatePicker = page.getByLabel(/start date/i);
    this.endDatePicker = page.getByLabel(/end date/i);
    this.applyDateButton = page.getByRole('button', { name: /apply/i });

    // Quick ranges
    this.todayButton = page.getByRole('button', { name: /^today$/i });
    this.weekButton = page.getByRole('button', { name: /week|7 days/i });
    this.monthButton = page.getByRole('button', { name: /month|30 days/i });
    this.yearButton = page.getByRole('button', { name: /year|12 months/i });
    this.customRangeButton = page.getByRole('button', { name: /custom/i });

    // Summary cards
    this.totalEnergyCard = page.getByTestId('total-energy-card');
    this.peakPowerCard = page.getByTestId('peak-power-card');
    this.averageEfficiencyCard = page.getByTestId('average-efficiency-card');
    this.carbonSavingsCard = page.getByTestId('carbon-savings-card');

    // Chart types
    this.lineChartButton = page.getByRole('button', { name: /line chart/i })
      .or(page.getByTestId('line-chart-toggle'));
    this.barChartButton = page.getByRole('button', { name: /bar chart/i })
      .or(page.getByTestId('bar-chart-toggle'));
    this.pieChartButton = page.getByRole('button', { name: /pie chart/i })
      .or(page.getByTestId('pie-chart-toggle'));

    // Export
    this.exportPdfButton = page.getByRole('button', { name: /export.*pdf|pdf/i });
    this.exportCsvButton = page.getByRole('button', { name: /export.*csv|csv/i });
    this.exportExcelButton = page.getByRole('button', { name: /export.*excel|xlsx/i });
    this.printReportButton = page.getByRole('button', { name: /print/i });

    // Filters
    this.deviceFilter = page.getByTestId('device-filter');
    this.metricFilter = page.getByTestId('metric-filter');
    this.granularityFilter = page.getByTestId('granularity-filter');

    // Chart container
    this.chartsContainer = page.getByTestId('charts-container')
      .or(page.locator('[class*="chart"]').first());
    this.noDataMessage = page.getByText(/no data|no results/i);
  }

  /**
   * Navigate to analytics page
   */
  async goto() {
    await this.page.goto('/analytics');
    await this.waitForLoaded();
  }

  /**
   * Wait for analytics page to load
   */
  async waitForLoaded() {
    await this.page.waitForLoadState('domcontentloaded');
    await this.waitForAPIResponse('/api/v1/analytics').catch(() => null);
    await this.waitForAPIResponse('/api/v1/telemetry').catch(() => null);
  }

  /**
   * Select date range preset
   */
  async selectDateRange(range: 'today' | 'week' | 'month' | 'year') {
    let button: Locator;

    switch (range) {
      case 'today':
        button = this.todayButton;
        break;
      case 'week':
        button = this.weekButton;
        break;
      case 'month':
        button = this.monthButton;
        break;
      case 'year':
        button = this.yearButton;
        break;
    }

    if (await button.isVisible()) {
      await button.click();
    } else {
      // Try dropdown
      await this.dateRangeDropdown.click();
      const option = this.page.getByRole('option', { name: new RegExp(range, 'i') });
      await option.click();
    }

    await this.waitForLoaded();
  }

  /**
   * Select custom date range
   */
  async selectCustomDateRange(startDate: string, endDate: string) {
    // Open custom range picker
    if (await this.customRangeButton.isVisible()) {
      await this.customRangeButton.click();
    }

    // Fill dates
    await this.startDatePicker.fill(startDate);
    await this.endDatePicker.fill(endDate);

    // Apply
    await this.applyDateButton.click();
    await this.waitForLoaded();
  }

  /**
   * Check if charts are displayed
   */
  async hasCharts(): Promise<boolean> {
    const chartElements = this.page.locator('canvas, svg[class*="recharts"], [class*="chart"]');
    const count = await chartElements.count();
    return count > 0;
  }

  /**
   * Get total energy value
   */
  async getTotalEnergy(): Promise<number | null> {
    try {
      const energyText = await this.totalEnergyCard.textContent();
      if (!energyText) return null;

      const match = energyText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get peak power value
   */
  async getPeakPower(): Promise<number | null> {
    try {
      const powerText = await this.peakPowerCard.textContent();
      if (!powerText) return null;

      const match = powerText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Export report as PDF
   */
  async exportPDF() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportPdfButton.click();
    return await downloadPromise;
  }

  /**
   * Export data as CSV
   */
  async exportCSV() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportCsvButton.click();
    return await downloadPromise;
  }

  /**
   * Export data as Excel
   */
  async exportExcel() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportExcelButton.click();
    return await downloadPromise;
  }

  /**
   * Print report
   */
  async printReport() {
    // Listen for print dialog
    this.page.once('dialog', dialog => dialog.dismiss());
    await this.printReportButton.click();
  }

  /**
   * Switch chart type
   */
  async switchToLineChart() {
    if (await this.lineChartButton.isVisible()) {
      await this.lineChartButton.click();
      await this.page.waitForTimeout(1000);
    }
  }

  /**
   * Switch to bar chart
   */
  async switchToBarChart() {
    if (await this.barChartButton.isVisible()) {
      await this.barChartButton.click();
      await this.page.waitForTimeout(1000);
    }
  }

  /**
   * Filter by device
   */
  async filterByDevice(deviceName: string) {
    if (await this.deviceFilter.isVisible()) {
      await this.deviceFilter.click();
      const option = this.page.getByRole('option', { name: new RegExp(deviceName, 'i') });
      await option.click();
      await this.waitForLoaded();
    }
  }

  /**
   * Check if no data message is shown
   */
  async hasNoData(): Promise<boolean> {
    return await this.noDataMessage.isVisible();
  }

  /**
   * Verify analytics page loaded successfully
   */
  async expectAnalyticsPageLoaded() {
    await expect(this.page).toHaveURL(/.*analytics/);

    // Should not show error
    const errorToast = this.page.getByTestId('error-toast');
    await expect(errorToast).not.toBeVisible();

    // Should have analytics-related content
    const bodyText = await this.page.locator('body').textContent();
    expect(bodyText).toMatch(/analytics|reports|energy|chart/i);
  }

  /**
   * Verify charts are displayed
   */
  async expectChartsDisplayed() {
    const hasCharts = await this.hasCharts();
    const hasNoData = await this.hasNoData();

    // Either charts are displayed or "no data" message
    expect(hasCharts || hasNoData).toBe(true);
  }

  /**
   * Verify export button is available
   */
  async expectExportAvailable() {
    const hasExport = await this.exportPdfButton.isVisible().catch(() => false) ||
                      await this.exportCsvButton.isVisible().catch(() => false);

    expect(hasExport).toBe(true);
  }
}
