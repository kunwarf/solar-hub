import { test, expect } from '@/fixtures/auth.fixture';
import { DeviceListPage } from '@/pages/devices/DeviceListPage';

test.describe('Investigate Device Settings Page', () => {
  test('should check which component is rendering and capture console logs', async ({ authenticatedPage: page }) => {
    // Capture console logs
    const consoleLogs: string[] = [];
    page.on('console', msg => {
      consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
    });

    // Navigate to devices page
    const deviceListPage = new DeviceListPage(page);
    await deviceListPage.goto();
    await page.waitForLoadState('networkidle');

    // Dismiss onboarding
    const closeButton = page.locator('[aria-label="Close"]').or(page.getByRole('button', { name: /^close$/i }));
    if (await closeButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await closeButton.click({ force: true });
      await page.waitForTimeout(500);
    }
    const skipButton = page.getByRole('button', { name: /skip for now/i });
    if (await skipButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await skipButton.click({ force: true });
      await page.waitForTimeout(500);
    }

    // Click on Setup button on the first device card
    await page.waitForTimeout(2000);
    const setupButton = page.locator('button:has-text("Setup")').first();

    if (!(await setupButton.isVisible())) {
      throw new Error('No Setup button found on devices page');
    }

    console.log('Found Setup button, clicking it...');
    await setupButton.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(8000); // Wait for polling to complete

    // Check URL
    const currentUrl = page.url();
    console.log('Current URL:', currentUrl);

    // Check page title or heading
    const headings = await page.locator('h1, h2, [class*="title"]').all();
    const headingTexts = await Promise.all(headings.map(h => h.textContent()));
    console.log('Page Headings:', headingTexts.filter(t => t).slice(0, 3));

    // Look for specific elements that indicate which page is rendering
    const hasUseDeviceSettingsLog = consoleLogs.some(log =>
      log.includes('[useDeviceSettings]')
    );
    const hasInverterConfigPageLog = consoleLogs.some(log =>
      log.includes('[InverterConfigPage]')
    );
    const hasMeterConfigPageLog = consoleLogs.some(log =>
      log.includes('[MeterConfigPage]')
    );
    const hasBatteryConfigPageLog = consoleLogs.some(log =>
      log.includes('[BatteryConfigPage]')
    );
    const hasOldApiCall = consoleLogs.some(log =>
      log.includes('deviceSettingsService')
    );

    // Check for specific UI elements
    const hasHybridAlerts = await page.locator('[role="alert"]').count() > 0;
    const hasRefreshButton = await page.locator('button:has-text("Refresh")').count() > 0;
    const hasSaveButton = await page.locator('button:has-text("Save")').count() > 0;

    // Print all console logs that contain our debug markers
    console.log('\n=== Console Logs (filtered) ===');
    const relevantLogs = consoleLogs.filter(log =>
      log.includes('[useDeviceSettings]') ||
      log.includes('[InverterConfigPage]') ||
      log.includes('[MeterConfigPage]') ||
      log.includes('[BatteryConfigPage]') ||
      log.includes('query-settings') ||
      log.includes('command-status') ||
      log.includes('SUCCESS') ||
      log.includes('Initializing')
    );

    if (relevantLogs.length > 0) {
      relevantLogs.forEach(log => console.log(log));
    } else {
      console.log('No relevant console logs found.');
    }

    // Print diagnostics
    console.log('\n=== Diagnostics ===');
    console.log('Has useDeviceSettings logs:', hasUseDeviceSettingsLog);
    console.log('Has InverterConfigPage logs:', hasInverterConfigPageLog);
    console.log('Has MeterConfigPage logs:', hasMeterConfigPageLog);
    console.log('Has BatteryConfigPage logs:', hasBatteryConfigPageLog);
    console.log('Has old API call logs:', hasOldApiCall);
    console.log('Has hybrid alerts:', hasHybridAlerts);
    console.log('Has refresh button:', hasRefreshButton);
    console.log('Has save button:', hasSaveButton);

    // Check for React errors
    const reactErrors = consoleLogs.filter(log =>
      log.includes('Error') ||
      log.includes('Warning') ||
      log.includes('Failed')
    );
    if (reactErrors.length > 0) {
      console.log('\n=== React Errors/Warnings ===');
      reactErrors.forEach(log => console.log(log));
    }

    // Examine the actual DOM structure
    console.log('\n=== DOM Structure Analysis ===');

    // Check what's actually in the page
    const bodyText = await page.locator('body').textContent();
    console.log('Page contains "Configuration Content":', bodyText?.includes('Configuration Content'));
    console.log('Page contains tab names:', {
      hasGeneral: bodyText?.includes('General'),
      hasBattery: bodyText?.includes('Battery'),
      hasWorkMode: bodyText?.includes('Work Mode'),
      hasAdapter: bodyText?.includes('Adapter'),
    });

    // Check for specific elements
    const tabsCount = await page.locator('[role="tab"], [class*="tab"]').count();
    const inputsCount = await page.locator('input, select, textarea').count();
    const formsCount = await page.locator('form, [class*="form"]').count();

    console.log('DOM elements:', {
      tabs: tabsCount,
      inputs: inputsCount,
      forms: formsCount,
    });

    // Check if motion.div is rendering
    const motionDivs = await page.locator('[class*="motion"], [style*="opacity"]').count();
    console.log('Motion divs found:', motionDivs);

    // Get the HTML structure of the main content area
    const mainContent = await page.locator('[class*="p-6"]').last().innerHTML().catch(() => 'Could not get HTML');
    console.log('Main content area HTML (first 500 chars):', mainContent.slice(0, 500));

    // Take screenshot
    await page.screenshot({
      path: 'tests/e2e-ts/screenshots/settings-page-investigation.png',
      fullPage: true
    });

    // Print conclusion
    console.log('\n=== Conclusion ===');
    if (currentUrl.includes('/settings') && !currentUrl.includes('/devices/')) {
      console.log('❌ WRONG PAGE: Navigated to application settings instead of device settings');
      console.log('Expected URL pattern: /devices/{deviceId}/settings');
      console.log('Actual URL:', currentUrl);
    } else if (hasUseDeviceSettingsLog && (hasInverterConfigPageLog || hasMeterConfigPageLog || hasBatteryConfigPageLog)) {
      console.log('✅ CORRECT: Using DeviceSettingsHybrid with proper component');
    } else if (hasUseDeviceSettingsLog) {
      console.log('⚠️  PARTIAL: Using useDeviceSettings hook but component not initializing');
      console.log('This means DeviceSettingsHybrid is rendering but settings not being passed to child components');
    } else {
      console.log('❌ WRONG: Not using useDeviceSettings hook (old page?)');
    }

    // Verify we're on the right page
    expect(currentUrl).toContain('/devices/');
    expect(currentUrl).toContain('/settings');
  });
});
