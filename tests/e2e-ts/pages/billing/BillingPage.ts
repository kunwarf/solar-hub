import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Page object for the Billing page
 * Handles tariffs, billing history, and net metering calculations
 */
export class BillingPage extends BasePage {
  // Main elements
  readonly pageTitle: Locator;
  readonly currentBillCard: Locator;
  readonly tariffRateDisplay: Locator;
  readonly estimatedSavingsCard: Locator;
  readonly exportCreditsCard: Locator;

  // Billing summary
  readonly totalConsumption: Locator;
  readonly totalGeneration: Locator;
  readonly netMetering: Locator;
  readonly billAmount: Locator;
  readonly dueDate: Locator;

  // Tariff information
  readonly tariffType: Locator;
  readonly ratePerKwh: Locator;
  readonly peakRate: Locator;
  readonly offPeakRate: Locator;

  // Net metering
  readonly exportedEnergy: Locator;
  readonly importedEnergy: Locator;
  readonly netEnergy: Locator;
  readonly exportCredits: Locator;

  // Billing history
  readonly billingHistoryTable: Locator;
  readonly viewHistoryButton: Locator;
  readonly downloadInvoiceButton: Locator;

  // Actions
  readonly payBillButton: Locator;
  readonly viewDetailsButton: Locator;
  readonly exportDataButton: Locator;

  // Date range
  readonly billingPeriodSelector: Locator;
  readonly monthSelector: Locator;
  readonly yearSelector: Locator;

  constructor(page: Page) {
    super(page);

    // Main elements
    this.pageTitle = page.getByRole('heading', { name: /billing|tariff/i });
    this.currentBillCard = page.getByTestId('current-bill-card');
    this.tariffRateDisplay = page.getByTestId('tariff-rate');
    this.estimatedSavingsCard = page.getByTestId('estimated-savings');
    this.exportCreditsCard = page.getByTestId('export-credits');

    // Billing summary
    this.totalConsumption = page.getByTestId('total-consumption');
    this.totalGeneration = page.getByTestId('total-generation');
    this.netMetering = page.getByTestId('net-metering');
    this.billAmount = page.getByTestId('bill-amount');
    this.dueDate = page.getByTestId('due-date');

    // Tariff information
    this.tariffType = page.getByTestId('tariff-type');
    this.ratePerKwh = page.getByTestId('rate-per-kwh');
    this.peakRate = page.getByTestId('peak-rate');
    this.offPeakRate = page.getByTestId('off-peak-rate');

    // Net metering
    this.exportedEnergy = page.getByTestId('exported-energy');
    this.importedEnergy = page.getByTestId('imported-energy');
    this.netEnergy = page.getByTestId('net-energy');
    this.exportCredits = page.getByTestId('export-credits-value');

    // Billing history
    this.billingHistoryTable = page.getByTestId('billing-history-table');
    this.viewHistoryButton = page.getByRole('button', { name: /view history|billing history/i });
    this.downloadInvoiceButton = page.getByRole('button', { name: /download|invoice/i });

    // Actions
    this.payBillButton = page.getByRole('button', { name: /pay bill|make payment/i });
    this.viewDetailsButton = page.getByRole('button', { name: /view details/i });
    this.exportDataButton = page.getByRole('button', { name: /export/i });

    // Date range
    this.billingPeriodSelector = page.getByTestId('billing-period-selector');
    this.monthSelector = page.getByLabel(/month/i);
    this.yearSelector = page.getByLabel(/year/i);
  }

  /**
   * Navigate to billing page
   */
  async goto() {
    await this.page.goto('/billing');
    await this.waitForLoaded();
  }

  /**
   * Wait for billing page to load
   */
  async waitForLoaded() {
    await this.page.waitForLoadState('domcontentloaded');
    await this.waitForAPIResponse('/api/v1/billing').catch(() => null);
  }

  /**
   * Get tariff rate (PKR/kWh or other currency)
   */
  async getTariffRate(): Promise<number | null> {
    try {
      const rateText = await this.ratePerKwh.textContent()
        .catch(() => this.tariffRateDisplay.textContent());

      if (!rateText) return null;

      const match = rateText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get estimated savings amount
   */
  async getEstimatedSavings(): Promise<number | null> {
    try {
      const savingsText = await this.estimatedSavingsCard.textContent();
      if (!savingsText) return null;

      const match = savingsText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get export credits (kWh exported to grid)
   */
  async getExportCredits(): Promise<number | null> {
    try {
      const creditsText = await this.exportCreditsCard.textContent()
        .catch(() => this.exportCredits.textContent());

      if (!creditsText) return null;

      const match = creditsText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get current bill amount
   */
  async getBillAmount(): Promise<number | null> {
    try {
      const amountText = await this.billAmount.textContent();
      if (!amountText) return null;

      const match = amountText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get total consumption (kWh)
   */
  async getTotalConsumption(): Promise<number | null> {
    try {
      const consumptionText = await this.totalConsumption.textContent();
      if (!consumptionText) return null;

      const match = consumptionText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get total generation (kWh)
   */
  async getTotalGeneration(): Promise<number | null> {
    try {
      const generationText = await this.totalGeneration.textContent();
      if (!generationText) return null;

      const match = generationText.match(/(\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get net metering value (imported - exported)
   */
  async getNetMetering(): Promise<number | null> {
    try {
      const netText = await this.netMetering.textContent()
        .catch(() => this.netEnergy.textContent());

      if (!netText) return null;

      const match = netText.match(/(-?\d+\.?\d*)/);
      return match ? parseFloat(match[1]) : null;
    } catch {
      return null;
    }
  }

  /**
   * Check if tariff information is displayed
   */
  async hasTariffInfo(): Promise<boolean> {
    const bodyText = await this.page.locator('body').textContent();
    return !!(bodyText && (
      bodyText.toLowerCase().includes('tariff') ||
      bodyText.toLowerCase().includes('rate') ||
      bodyText.toLowerCase().includes('pkr') ||
      bodyText.toLowerCase().includes('kwh')
    ));
  }

  /**
   * Check if savings information is displayed
   */
  async hasSavingsInfo(): Promise<boolean> {
    const bodyText = await this.page.locator('body').textContent();
    return !!(bodyText && (
      bodyText.toLowerCase().includes('saving') ||
      bodyText.toLowerCase().includes('saved') ||
      bodyText.toLowerCase().includes('estimated')
    ));
  }

  /**
   * Check if export credits are displayed
   */
  async hasExportCredits(): Promise<boolean> {
    const bodyText = await this.page.locator('body').textContent();
    return !!(bodyText && (
      bodyText.toLowerCase().includes('export') ||
      bodyText.toLowerCase().includes('credit')
    ));
  }

  /**
   * Select billing period/month
   */
  async selectBillingPeriod(month: string, year?: string) {
    if (await this.billingPeriodSelector.isVisible()) {
      await this.billingPeriodSelector.click();
      const option = this.page.getByRole('option', { name: new RegExp(month, 'i') });
      await option.click();
    } else if (await this.monthSelector.isVisible()) {
      await this.monthSelector.selectOption({ label: month });
      if (year && await this.yearSelector.isVisible()) {
        await this.yearSelector.selectOption({ label: year });
      }
    }

    await this.waitForLoaded();
  }

  /**
   * View billing history
   */
  async viewBillingHistory() {
    await this.viewHistoryButton.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Download invoice
   */
  async downloadInvoice() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.downloadInvoiceButton.click();
    return await downloadPromise;
  }

  /**
   * Pay bill
   */
  async payBill() {
    await this.payBillButton.click();
    await this.page.waitForLoadState('domcontentloaded');
  }

  /**
   * Verify billing page loaded successfully
   */
  async expectBillingPageLoaded() {
    await expect(this.page).toHaveURL(/.*billing/);

    // Should not show error
    const errorToast = this.page.getByTestId('error-toast');
    await expect(errorToast).not.toBeVisible();

    // Should have billing-related content
    const bodyText = await this.page.locator('body').textContent();
    expect(bodyText).toMatch(/billing|tariff|invoice|payment/i);
  }

  /**
   * Verify tariff rate is displayed
   */
  async expectTariffRateDisplayed() {
    const hasTariff = await this.hasTariffInfo();
    expect(hasTariff).toBe(true);

    // Should have numeric rate
    const rate = await this.getTariffRate();
    if (rate !== null) {
      expect(rate).toBeGreaterThan(0);
    }
  }

  /**
   * Verify net metering calculations
   */
  async expectNetMeteringCalculation() {
    const consumption = await this.getTotalConsumption();
    const generation = await this.getTotalGeneration();
    const net = await this.getNetMetering();

    // If we have values, verify calculation
    if (consumption !== null && generation !== null && net !== null) {
      // Net = Consumption - Generation (approximately)
      const expectedNet = consumption - generation;
      const tolerance = 1; // Allow 1 kWh tolerance

      expect(Math.abs(net - expectedNet)).toBeLessThanOrEqual(tolerance);
    }
  }
}
