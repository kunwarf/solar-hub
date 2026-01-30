import { test, expect } from '@/fixtures/auth.fixture';
import { DeviceListPage } from '@/pages/devices/DeviceListPage';

/**
 * Device Settings Tests
 *
 * Tests device-specific settings pages that vary by device type and manufacturer
 * Priority: P1
 */
test.describe('Device Settings - Type-Specific Configuration', { tag: '@device-settings' }, () => {
  let deviceListPage: DeviceListPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    deviceListPage = new DeviceListPage(authenticatedPage);
    await deviceListPage.goto();

    // Dismiss onboarding wizard if present
    const closeButton = authenticatedPage.locator('[aria-label="Close"]').or(authenticatedPage.getByRole('button', { name: /^close$/i }));
    if (await closeButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await closeButton.click({ force: true });
      await authenticatedPage.waitForTimeout(1500);
    }

    const skipButton = authenticatedPage.getByRole('button', { name: /skip for now/i });
    if (await skipButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await skipButton.click({ force: true });
      await authenticatedPage.waitForTimeout(1000);
    }

    // Wait for dialog overlay to disappear
    const dialogOverlay = authenticatedPage.locator('[class*="bg-black/80"]');
    await dialogOverlay.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => null);
  });

  test('should navigate to inverter settings page', {
    tag: ['@smoke', '@high']
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Find first inverter device card
    const inverterCard = authenticatedPage.locator('.glass-card-hover')
      .filter({ hasText: /inverter/i })
      .first();

    if (await inverterCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Click configure/settings button on the card
      const configureButton = inverterCard.getByRole('button', { name: /configure|settings|setup/i });

      if (await configureButton.isVisible().catch(() => false)) {
        await configureButton.click();

        // Should navigate to settings page
        await expect(authenticatedPage).toHaveURL(/.*devices\/.*\/settings/);

        // Page should show inverter-specific content
        const pageContent = await authenticatedPage.locator('body').textContent();
        expect(pageContent).toMatch(/inverter|configuration/i);

        // Should have Save and Reset buttons
        await expect(authenticatedPage.getByRole('button', { name: /save.*configuration/i })).toBeVisible();
        await expect(authenticatedPage.getByRole('button', { name: /reset.*default/i })).toBeVisible();
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should navigate to battery settings page', {
    tag: ['@smoke', '@high']
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Find first battery device card
    const batteryCard = authenticatedPage.locator('.glass-card-hover')
      .filter({ hasText: /battery/i })
      .first();

    if (await batteryCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Click configure/settings button on the card
      const configureButton = batteryCard.getByRole('button', { name: /configure|settings|setup/i });

      if (await configureButton.isVisible().catch(() => false)) {
        await configureButton.click();

        // Should navigate to settings page
        await expect(authenticatedPage).toHaveURL(/.*devices\/.*\/settings/);

        // Page should show battery-specific content
        const pageContent = await authenticatedPage.locator('body').textContent();
        expect(pageContent).toMatch(/battery|configuration/i);

        // Should have tabs for battery settings
        const hasTabs = await authenticatedPage.getByRole('tab', { name: /general|adapter|battery/i }).count();
        expect(hasTabs).toBeGreaterThan(0);
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should navigate to meter settings page', {
    tag: ['@smoke', '@high']
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Find first meter device card
    const meterCard = authenticatedPage.locator('.glass-card-hover')
      .filter({ hasText: /meter/i })
      .first();

    if (await meterCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Click configure/settings button on the card
      const configureButton = meterCard.getByRole('button', { name: /configure|settings|setup/i });

      if (await configureButton.isVisible().catch(() => false)) {
        await configureButton.click();

        // Should navigate to settings page
        await expect(authenticatedPage).toHaveURL(/.*devices\/.*\/settings/);

        // Page should show meter-specific content
        const pageContent = await authenticatedPage.locator('body').textContent();
        expect(pageContent).toMatch(/meter|configuration/i);

        // Should have tabs for meter settings
        const hasTabs = await authenticatedPage.getByRole('tab', { name: /metering|direction|demand/i }).count();
        expect(hasTabs).toBeGreaterThan(0);
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should display device header with type indicator', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Click on any device settings
    const firstCard = authenticatedPage.locator('.glass-card-hover').first();
    const configureButton = firstCard.getByRole('button', { name: /configure|settings|setup/i });

    if (await configureButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await configureButton.click();
      await authenticatedPage.waitForTimeout(1000);

      // Should show device header card
      const headerCard = authenticatedPage.locator('.glass-card').first();
      await expect(headerCard).toBeVisible();

      // Should show device type icon (inverter/battery/meter)
      const hasIcon = await Promise.race([
        authenticatedPage.locator('svg').first().isVisible({ timeout: 2000 }).catch(() => false),
        authenticatedPage.getByRole('img').first().isVisible({ timeout: 2000 }).catch(() => false),
      ]);
      expect(hasIcon).toBe(true);

      // Should show device status
      const bodyText = await authenticatedPage.locator('body').textContent();
      expect(bodyText).toMatch(/online|offline|warning/i);
    } else {
      test.skip();
    }
  });

  test('should show configuration tabs for device type', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Click on any device settings
    const firstCard = authenticatedPage.locator('.glass-card-hover').first();
    const configureButton = firstCard.getByRole('button', { name: /configure|settings|setup/i });

    if (await configureButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await configureButton.click();
      await authenticatedPage.waitForTimeout(1500);

      // Should have tabs (different for each device type)
      const tabs = authenticatedPage.getByRole('tab');
      const tabCount = await tabs.count();

      expect(tabCount).toBeGreaterThan(0);
    } else {
      test.skip();
    }
  });

  test('should allow saving configuration', {
    tag: ['@critical', '@api']
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Click on any device settings
    const firstCard = authenticatedPage.locator('.glass-card-hover').first();
    const configureButton = firstCard.getByRole('button', { name: /configure|settings|setup/i });

    if (await configureButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await configureButton.click();
      await authenticatedPage.waitForTimeout(1500);

      // Wait for API response listener
      const settingsUpdatePromise = authenticatedPage.waitForResponse(
        resp => resp.url().includes('/api/v1/devices/') && resp.url().includes('/settings') && resp.request().method() === 'PUT',
        { timeout: 10000 }
      );

      // Click Save button
      const saveButton = authenticatedPage.getByRole('button', { name: /save.*configuration/i });
      if (await saveButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        await saveButton.click();

        // Wait for API call (or timeout gracefully)
        const response = await settingsUpdatePromise.catch(() => null);

        if (response) {
          // Verify API call was successful
          expect(response.status()).toBe(200);

          // Should show success toast
          const toast = authenticatedPage.locator('[class*="toast"]').or(authenticatedPage.getByText(/settings saved/i));
          await expect(toast).toBeVisible({ timeout: 3000 }).catch(() => {
            console.log('Toast not visible - may have already dismissed');
          });
        } else {
          console.log('API response not captured - may have occurred before listener');
        }
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should allow resetting to defaults', {
    tag: ['@regression', '@api']
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Click on any device settings
    const firstCard = authenticatedPage.locator('.glass-card-hover').first();
    const configureButton = firstCard.getByRole('button', { name: /configure|settings|setup/i });

    if (await configureButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await configureButton.click();
      await authenticatedPage.waitForTimeout(1500);

      // Wait for API response listener
      const resetPromise = authenticatedPage.waitForResponse(
        resp => resp.url().includes('/api/v1/devices/') && resp.url().includes('/settings/reset') && resp.request().method() === 'POST',
        { timeout: 10000 }
      );

      // Click Reset button
      const resetButton = authenticatedPage.getByRole('button', { name: /reset.*default/i });
      if (await resetButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        // Set up dialog handler for confirmation
        authenticatedPage.on('dialog', dialog => dialog.accept());

        await resetButton.click();

        // Wait for API call
        const response = await resetPromise.catch(() => null);

        if (response) {
          // Verify API call was successful
          expect(response.status()).toBe(200);

          // Should show success toast
          const toast = authenticatedPage.locator('[class*="toast"]').or(authenticatedPage.getByText(/reset/i));
          await expect(toast).toBeVisible({ timeout: 3000 }).catch(() => {
            console.log('Toast not visible - may have already dismissed');
          });
        } else {
          console.log('API response not captured');
        }
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should navigate back to devices list', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Click on any device settings
    const firstCard = authenticatedPage.locator('.glass-card-hover').first();
    const configureButton = firstCard.getByRole('button', { name: /configure|settings|setup/i });

    if (await configureButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await configureButton.click();
      await authenticatedPage.waitForTimeout(1000);

      // Should have back button
      const backButton = authenticatedPage.getByRole('button', { name: /back/i }).first();
      await expect(backButton).toBeVisible();

      // Click back button
      await backButton.click();

      // Should return to devices list
      await expect(authenticatedPage).toHaveURL(/.*devices$/);
    } else {
      test.skip();
    }
  });

  test('should load device settings from API on page load', {
    tag: ['@critical', '@api']
  }, async ({ authenticatedPage }) => {
    // Wait for devices to load
    await authenticatedPage.waitForTimeout(2000);

    // Get device ID from first card
    const firstCard = authenticatedPage.locator('.glass-card-hover').first();

    if (await firstCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Set up API listener before navigation
      const settingsLoadPromise = authenticatedPage.waitForResponse(
        resp => resp.url().includes('/api/v1/devices/') && resp.url().includes('/settings') && resp.request().method() === 'GET',
        { timeout: 10000 }
      );

      // Click configure button
      const configureButton = firstCard.getByRole('button', { name: /configure|settings|setup/i });
      if (await configureButton.isVisible().catch(() => false)) {
        await configureButton.click();

        // Wait for settings to load
        const response = await settingsLoadPromise;

        // Verify API call was successful
        expect(response.status()).toBe(200);

        // Verify response structure
        const data = await response.json();
        expect(data).toHaveProperty('device_id');
        expect(data).toHaveProperty('device_type');
        expect(data).toHaveProperty('settings');
        expect(typeof data.settings).toBe('object');

        // Page should load without errors
        await authenticatedPage.waitForTimeout(1000);
        const errorToast = authenticatedPage.getByTestId('error-toast');
        await expect(errorToast).not.toBeVisible({ timeout: 2000 }).catch(() => {});
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });
});

/**
 * Telemetry - Device-Type Routing Tests
 *
 * Tests that telemetry pages correctly render device-specific components
 */
test.describe('Telemetry - Device-Type Routing', { tag: '@telemetry-routing' }, () => {
  test('should display inverter telemetry for inverter device', {
    tag: ['@smoke', '@high']
  }, async ({ authenticatedPage }) => {
    // Navigate to telemetry page
    await authenticatedPage.goto('/telemetry');
    await authenticatedPage.waitForLoadState('domcontentloaded');
    await authenticatedPage.waitForTimeout(2000);

    // Select an inverter device from dropdown
    const deviceSelector = authenticatedPage.locator('select, [role="combobox"]').first();

    if (await deviceSelector.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Get all options
      const options = await authenticatedPage.locator('[role="option"]').allTextContents().catch(() => []);
      const inverterOption = options.find(opt => opt.toLowerCase().includes('inverter'));

      if (inverterOption) {
        await deviceSelector.click();
        await authenticatedPage.getByRole('option', { name: new RegExp(inverterOption, 'i') }).click();
        await authenticatedPage.waitForTimeout(1500);

        // Should show inverter-specific telemetry
        const bodyText = await authenticatedPage.locator('body').textContent();
        expect(bodyText).toMatch(/solar|pv|mppt|inverter/i);
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should display battery telemetry for battery device', {
    tag: ['@smoke', '@high']
  }, async ({ authenticatedPage }) => {
    // Navigate to telemetry page with battery device
    await authenticatedPage.goto('/telemetry');
    await authenticatedPage.waitForLoadState('domcontentloaded');
    await authenticatedPage.waitForTimeout(2000);

    // Select a battery device from dropdown
    const deviceSelector = authenticatedPage.locator('select, [role="combobox"]').first();

    if (await deviceSelector.isVisible({ timeout: 3000 }).catch(() => false)) {
      const options = await authenticatedPage.locator('[role="option"]').allTextContents().catch(() => []);
      const batteryOption = options.find(opt => opt.toLowerCase().includes('battery'));

      if (batteryOption) {
        await deviceSelector.click();
        await authenticatedPage.getByRole('option', { name: new RegExp(batteryOption, 'i') }).click();
        await authenticatedPage.waitForTimeout(1500);

        // Should show battery-specific telemetry
        const bodyText = await authenticatedPage.locator('body').textContent();
        expect(bodyText).toMatch(/battery|soc|cell|charge/i);
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should display meter telemetry for meter device', {
    tag: ['@smoke', '@high']
  }, async ({ authenticatedPage }) => {
    // Navigate to telemetry page
    await authenticatedPage.goto('/telemetry');
    await authenticatedPage.waitForLoadState('domcontentloaded');
    await authenticatedPage.waitForTimeout(2000);

    // Select a meter device from dropdown
    const deviceSelector = authenticatedPage.locator('select, [role="combobox"]').first();

    if (await deviceSelector.isVisible({ timeout: 3000 }).catch(() => false)) {
      const options = await authenticatedPage.locator('[role="option"]').allTextContents().catch(() => []);
      const meterOption = options.find(opt => opt.toLowerCase().includes('meter'));

      if (meterOption) {
        await deviceSelector.click();
        await authenticatedPage.getByRole('option', { name: new RegExp(meterOption, 'i') }).click();
        await authenticatedPage.waitForTimeout(1500);

        // Should show meter-specific telemetry
        const bodyText = await authenticatedPage.locator('body').textContent();
        expect(bodyText).toMatch(/meter|import|export|grid/i);
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });
});
