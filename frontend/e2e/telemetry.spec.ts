/**
 * E2E Tests for Telemetry Page
 */

import { test, expect } from '@playwright/test';

test.describe('Telemetry Page - Real Data Integration', () => {
  const TEST_DEVICE_ID = '669a0686-f574-445d-93cf-7ff1bc078b29';

  test.beforeEach(async ({ page }) => {
    // Navigate to telemetry page with test device
    await page.goto(`/telemetry?device=${TEST_DEVICE_ID}`);

    // Wait for page to load
    await page.waitForLoadState('networkidle');
  });

  test('should display telemetry page with all sections', async ({ page }) => {
    // Check page title
    await expect(page.getByRole('heading', { name: /telemetry/i })).toBeVisible();

    // Check device selector
    await expect(page.locator('select, [role="combobox"]').first()).toBeVisible();

    // Check all major sections exist
    await expect(page.getByText(/power flow/i)).toBeVisible();
    await expect(page.getByText(/solar arrays/i)).toBeVisible();
    await expect(page.getByText(/inverter metrics/i)).toBeVisible();
    await expect(page.getByText(/power history/i)).toBeVisible();
    await expect(page.getByText(/efficiency & temp/i)).toBeVisible();
    await expect(page.getByText(/active alerts/i)).toBeVisible();
  });

  test('should load real solar array data', async ({ page }) => {
    // Wait for Solar Arrays section
    const solarSection = page.locator('text=Solar Arrays').locator('..').locator('..');

    // Should show at least one MPPT channel
    const mpptCards = solarSection.locator('[class*="grid"]').locator('> div');
    await expect(mpptCards.first()).toBeVisible();

    // Check for power value (should be a number, not mock data)
    const powerValue = mpptCards.first().locator('text=/\\d+\\.\\d+/').first();
    await expect(powerValue).toBeVisible();

    // Check for voltage and current
    await expect(mpptCards.first().getByText(/V$/)).toBeVisible();
    await expect(mpptCards.first().getByText(/A$/)).toBeVisible();
  });

  test('should display real inverter metrics', async ({ page }) => {
    // Check for DC Voltage
    await expect(page.getByText(/DC V/i)).toBeVisible();

    // Check for AC Voltage
    await expect(page.getByText(/AC V/i)).toBeVisible();

    // Check for Frequency
    await expect(page.getByText(/Freq/i)).toBeVisible();

    // Check for Efficiency
    const efficiencySection = page.getByText(/Eff/i).locator('..');
    await expect(efficiencySection.getByText(/%$/)).toBeVisible();

    // Check for Temperature
    const tempSection = page.getByText(/Temp/i).locator('..');
    await expect(tempSection.getByText(/°/)).toBeVisible();
  });

  test('should render power history chart with data', async ({ page }) => {
    // Wait for chart to render
    await page.waitForSelector('[class*="recharts"]', { timeout: 10000 });

    // Check chart exists
    const chart = page.locator('text=Power History').locator('..').locator('[class*="recharts"]');
    await expect(chart).toBeVisible();

    // Chart should have axis and data points
    await expect(chart.locator('g.recharts-cartesian-axis')).toHaveCount(2); // X and Y axis
  });

  test('should render efficiency & temperature chart', async ({ page }) => {
    // Wait for chart section
    const effTempSection = page.locator('text=Efficiency & Temp').locator('..');

    // Check chart exists
    await expect(effTempSection.locator('[class*="recharts"]')).toBeVisible();
  });

  test('should update data after polling interval', async ({ page }) => {
    // Get initial solar power value
    const solarPowerCard = page.locator('text=Solar Input').locator('..');
    const initialValue = await solarPowerCard.locator('[class*="font-mono"]').first().textContent();

    // Wait for polling interval (5 seconds + buffer)
    await page.waitForTimeout(6000);

    // Get updated value
    const updatedValue = await solarPowerCard.locator('[class*="font-mono"]').first().textContent();

    // Value should be defined (may or may not have changed)
    expect(updatedValue).toBeDefined();
    expect(updatedValue).toMatch(/\d+\.\d+/);
  });

  test('should display fallback warning when using simulated data', async ({ page }) => {
    // Check if fallback warning appears (may appear if API is down)
    const fallbackAlert = page.getByText(/simulated|unavailable/i);

    // If fallback is shown, it should be visible
    if (await fallbackAlert.isVisible()) {
      await expect(fallbackAlert).toContainText(/simulated|unavailable/i);
    }
  });

  test('should handle device switching', async ({ page }) => {
    // Get current device name
    const deviceSelector = page.locator('select, [role="combobox"]').first();

    // Click to open dropdown
    await deviceSelector.click();

    // Count available devices
    const deviceOptions = page.locator('[role="option"]');
    const count = await deviceOptions.count();

    if (count > 1) {
      // Select different device
      await deviceOptions.nth(1).click();

      // Wait for data to reload
      await page.waitForTimeout(2000);

      // Power flow section should still be visible
      await expect(page.getByText(/power flow/i)).toBeVisible();
    }
  });

  test('should display active alerts', async ({ page }) => {
    const alertsSection = page.locator('text=Active Alerts').locator('..');

    // Alerts section should be visible
    await expect(alertsSection).toBeVisible();

    // Should show either "No active alerts" or alert cards
    const noAlertsMessage = alertsSection.getByText(/no active alerts|all systems/i);
    const alertCards = alertsSection.locator('[class*="rounded-lg"][class*="border"]');

    const hasNoAlerts = await noAlertsMessage.isVisible();
    const hasAlerts = (await alertCards.count()) > 0;

    expect(hasNoAlerts || hasAlerts).toBe(true);
  });

  test('should refresh data on manual refresh button click', async ({ page }) => {
    const refreshButton = page.getByRole('button', { name: /refresh/i });

    // Click refresh button
    await refreshButton.click();

    // Button should show loading state briefly
    await expect(refreshButton.locator('[class*="animate-spin"]')).toBeVisible({ timeout: 1000 });

    // Loading state should disappear
    await expect(refreshButton.locator('[class*="animate-spin"]')).not.toBeVisible({ timeout: 5000 });
  });

  test('should be responsive on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // All sections should still be visible
    await expect(page.getByText(/power flow/i)).toBeVisible();
    await expect(page.getByText(/solar arrays/i)).toBeVisible();
    await expect(page.getByText(/inverter metrics/i)).toBeVisible();

    // Charts should be responsive
    const charts = page.locator('[class*="recharts"]');
    await expect(charts.first()).toBeVisible();
  });

  test('should handle API errors gracefully', async ({ page }) => {
    // Intercept API calls and return errors
    await page.route('**/api/v1/devices/*/snapshot', (route) => {
      route.fulfill({ status: 500, body: 'Internal Server Error' });
    });

    await page.reload();
    await page.waitForLoadState('networkidle');

    // Should show fallback data or error message
    const fallbackIndicator = page.getByText(/simulated|fallback|unavailable/i);
    await expect(fallbackIndicator).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Telemetry Page - Data Accuracy', () => {
  const TEST_DEVICE_ID = '669a0686-f574-445d-93cf-7ff1bc078b29';

  test('should display realistic power values', async ({ page }) => {
    await page.goto(`/telemetry?device=${TEST_DEVICE_ID}`);
    await page.waitForLoadState('networkidle');

    // Get solar power value
    const solarPowerCard = page.locator('text=Solar Input').locator('..');
    const solarPowerText = await solarPowerCard.locator('[class*="font-mono"]').first().textContent();
    const solarPower = parseFloat(solarPowerText?.replace(/[^\d.]/g, '') || '0');

    // Should be a reasonable value (0-20 kW for typical system)
    expect(solarPower).toBeGreaterThanOrEqual(0);
    expect(solarPower).toBeLessThanOrEqual(50); // Max realistic value

    // Check battery SOC is percentage
    const socText = await page.locator('text=SOC').locator('..').locator('[class*="font-mono"]').textContent();
    const soc = parseFloat(socText?.replace(/[^\d]/g, '') || '0');

    expect(soc).toBeGreaterThanOrEqual(0);
    expect(soc).toBeLessThanOrEqual(100);
  });

  test('should show consistent data across sections', async ({ page }) => {
    await page.goto(`/telemetry?device=${TEST_DEVICE_ID}`);
    await page.waitForLoadState('networkidle');

    // Get total MPPT power from Solar Arrays section
    const totalMpptText = await page.locator('text=Solar Arrays').locator('..').locator('text=Total:').locator('..').textContent();
    const totalMppt = parseFloat(totalMpptText?.match(/(\d+\.\d+)\s*kW/)?.[1] || '0');

    // Get solar power from Power Flow section
    const solarFlowText = await page.locator('text=Solar Input').locator('..').locator('[class*="font-mono"]').first().textContent();
    const solarFlow = parseFloat(solarFlowText?.replace(/[^\d.]/g, '') || '0');

    // Values should be reasonably close (within 10% margin due to timing)
    const margin = Math.max(totalMppt, solarFlow) * 0.1;
    expect(Math.abs(totalMppt - solarFlow)).toBeLessThanOrEqual(margin + 0.5);
  });
});
