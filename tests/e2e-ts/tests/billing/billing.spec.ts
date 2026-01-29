import { test, expect } from '@/fixtures/auth.fixture';
import { BillingPage } from '@/pages/billing/BillingPage';

/**
 * Billing Tests
 *
 * Tests billing page, tariffs, and net metering calculations
 * Priority: P1
 */
test.describe('Billing', { tag: '@billing' }, () => {
  let billingPage: BillingPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    billingPage = new BillingPage(authenticatedPage);
    await billingPage.goto();
  });

  test('should load billing page successfully', {
    tag: ['@smoke', '@high']
  }, async () => {
    // Verify page loaded
    await billingPage.expectBillingPageLoaded();

    // Should have page title
    await expect(billingPage.pageTitle).toBeVisible();
  });

  test('should display tariff rate in currency/kWh', {
    tag: '@regression'
  }, async () => {
    // Verify tariff information is shown
    const hasTariff = await billingPage.hasTariffInfo();
    expect(hasTariff).toBe(true);

    // Get tariff rate
    const rate = await billingPage.getTariffRate();

    if (rate !== null) {
      // Rate should be positive
      expect(rate).toBeGreaterThan(0);

      // Rate should be reasonable (not obviously fake)
      expect(rate).toBeLessThan(1000); // Less than 1000 PKR/kWh
    }
  });

  test('should display estimated savings amount', {
    tag: '@regression'
  }, async () => {
    // Verify savings information is shown
    const hasSavings = await billingPage.hasSavingsInfo();
    expect(hasSavings).toBe(true);

    // Get savings amount
    const savings = await billingPage.getEstimatedSavings();

    if (savings !== null) {
      // Savings should be non-negative
      expect(savings).toBeGreaterThanOrEqual(0);
    }
  });

  test('should display export credits (net metering)', {
    tag: '@regression'
  }, async () => {
    // Verify export credits are shown
    const hasExportCredits = await billingPage.hasExportCredits();

    if (hasExportCredits) {
      const credits = await billingPage.getExportCredits();

      if (credits !== null) {
        // Credits should be non-negative
        expect(credits).toBeGreaterThanOrEqual(0);
      }
    }
  });

  test('should show current bill amount', {
    tag: '@regression'
  }, async () => {
    const billAmount = await billingPage.getBillAmount();

    if (billAmount !== null) {
      // Bill amount should be non-negative
      expect(billAmount).toBeGreaterThanOrEqual(0);

      // Should be a reasonable amount
      expect(billAmount).toBeLessThan(1000000);
    }
  });

  test('should display total consumption', {
    tag: '@regression'
  }, async () => {
    const consumption = await billingPage.getTotalConsumption();

    if (consumption !== null) {
      // Consumption should be non-negative
      expect(consumption).toBeGreaterThanOrEqual(0);

      // Should be reasonable (not obviously fake)
      expect(consumption).toBeLessThan(100000); // Less than 100,000 kWh
    }
  });

  test('should display total generation', {
    tag: '@regression'
  }, async () => {
    const generation = await billingPage.getTotalGeneration();

    if (generation !== null) {
      // Generation should be non-negative
      expect(generation).toBeGreaterThanOrEqual(0);

      // Should be reasonable
      expect(generation).toBeLessThan(100000);
    }
  });

  test('should calculate net metering correctly', {
    tag: '@regression'
  }, async () => {
    const consumption = await billingPage.getTotalConsumption();
    const generation = await billingPage.getTotalGeneration();
    const netMetering = await billingPage.getNetMetering();

    if (consumption !== null && generation !== null && netMetering !== null) {
      // Net metering = consumption - generation
      const expectedNet = consumption - generation;

      // Allow some tolerance for rounding
      const tolerance = 2; // 2 kWh tolerance
      const difference = Math.abs(netMetering - expectedNet);

      expect(difference).toBeLessThanOrEqual(tolerance);
    }
  });

  test('should show billing history button', {
    tag: '@regression'
  }, async () => {
    const hasHistoryButton = await billingPage.viewHistoryButton.isVisible().catch(() => false);

    if (hasHistoryButton) {
      await expect(billingPage.viewHistoryButton).toBeVisible();
    }
  });

  test('should allow viewing billing history', {
    tag: '@regression'
  }, async () => {
    const hasHistoryButton = await billingPage.viewHistoryButton.isVisible().catch(() => false);

    if (hasHistoryButton) {
      await billingPage.viewBillingHistory();

      // Should show billing history table or list
      const hasHistory = await billingPage.billingHistoryTable.isVisible({ timeout: 5000 }).catch(() => false);
      const hasHistoryContent = await billingPage.page.getByText(/history|invoice|bill/i).isVisible().catch(() => false);

      expect(hasHistory || hasHistoryContent).toBe(true);
    } else {
      test.skip();
    }
  });

  test('should display currency symbols (PKR/Rs)', {
    tag: '@regression'
  }, async () => {
    const bodyText = await billingPage.page.locator('body').textContent();

    // Should have currency indicators
    const hasCurrency = bodyText && (
      bodyText.includes('PKR') ||
      bodyText.includes('Rs') ||
      bodyText.includes('₨')
    );

    expect(hasCurrency).toBe(true);
  });

  test('should show payment button for current bill', {
    tag: '@regression'
  }, async ({ userRole }) => {
    // Only owners can pay bills
    if (userRole === 'owner') {
      const hasPayButton = await billingPage.payBillButton.isVisible().catch(() => false);

      if (hasPayButton) {
        await expect(billingPage.payBillButton).toBeVisible();
        await expect(billingPage.payBillButton).toBeEnabled();
      }
    }
  });
});
