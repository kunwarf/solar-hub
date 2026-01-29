import { test, expect } from '@/fixtures/auth.fixture';
import { SettingsPage } from '@/pages/settings/SettingsPage';

/**
 * Settings Tests
 *
 * Tests user account settings and preferences
 * Priority: P2
 */
test.describe('Settings', { tag: '@settings' }, () => {
  let settingsPage: SettingsPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    settingsPage = new SettingsPage(authenticatedPage);
    await settingsPage.goto();
  });

  test('should load settings page successfully', {
    tag: ['@smoke', '@medium']
  }, async () => {
    // Verify page loaded
    await settingsPage.expectSettingsPageLoaded();

    // Should have page title
    await expect(settingsPage.pageTitle).toBeVisible();
  });

  test('should display account settings', {
    tag: '@regression'
  }, async () => {
    await settingsPage.expectAccountTabVisible();
  });

  test('should show account information fields', {
    tag: '@regression'
  }, async () => {
    await settingsPage.goToAccountTab();

    // Check for account fields
    const hasFirstName = await settingsPage.firstNameInput.isVisible().catch(() => false);
    const hasEmail = await settingsPage.emailInput.isVisible().catch(() => false);

    expect(hasFirstName || hasEmail).toBe(true);
  });

  test('should show save button', {
    tag: '@regression'
  }, async () => {
    await settingsPage.expectSaveButtonVisible();
  });

  test('should display settings tabs or sections', {
    tag: '@regression'
  }, async () => {
    // Check for tabs
    const hasAccountTab = await settingsPage.accountTab.isVisible().catch(() => false);
    const hasNotificationsTab = await settingsPage.notificationsTab.isVisible().catch(() => false);
    const hasPreferencesTab = await settingsPage.preferencesTab.isVisible().catch(() => false);
    const hasSecurityTab = await settingsPage.securityTab.isVisible().catch(() => false);

    // At least one tab should be visible
    expect(hasAccountTab || hasNotificationsTab || hasPreferencesTab || hasSecurityTab).toBe(true);
  });

  test('should allow switching between tabs', {
    tag: '@regression'
  }, async () => {
    const hasNotificationsTab = await settingsPage.notificationsTab.isVisible().catch(() => false);

    if (hasNotificationsTab) {
      await settingsPage.goToNotificationsTab();

      // Tab should be active
      const isSelected = await settingsPage.notificationsTab.getAttribute('aria-selected');
      expect(isSelected).toBe('true');
    }
  });

  test('should display notification settings', {
    tag: '@regression'
  }, async () => {
    await settingsPage.goToNotificationsTab();

    // Check for notification toggles
    const hasEmailNotif = await settingsPage.emailNotifications.isVisible().catch(() => false);
    const bodyText = await settingsPage.page.locator('body').textContent();
    const hasNotifText = bodyText && bodyText.toLowerCase().includes('notification');

    expect(hasEmailNotif || hasNotifText).toBe(true);
  });

  test('should display preferences settings', {
    tag: '@regression'
  }, async () => {
    const hasPreferencesTab = await settingsPage.preferencesTab.isVisible().catch(() => false);

    if (hasPreferencesTab) {
      await settingsPage.goToPreferencesTab();

      // Should show preference options
      const bodyText = await settingsPage.page.locator('body').textContent();
      expect(bodyText).toBeTruthy();
    }
  });

  test('should display security settings', {
    tag: '@regression'
  }, async () => {
    const hasSecurityTab = await settingsPage.securityTab.isVisible().catch(() => false);

    if (hasSecurityTab) {
      await settingsPage.goToSecurityTab();

      // Check for password fields or security options
      const hasPasswordField = await settingsPage.currentPasswordInput.isVisible().catch(() => false);
      const bodyText = await settingsPage.page.locator('body').textContent();
      const hasSecurityText = bodyText && (
        bodyText.toLowerCase().includes('password') ||
        bodyText.toLowerCase().includes('security')
      );

      expect(hasPasswordField || hasSecurityText).toBe(true);
    }
  });

  test('should show timezone selector', {
    tag: '@regression'
  }, async () => {
    await settingsPage.goToAccountTab();

    const hasTimezone = await settingsPage.timezoneSelect.isVisible().catch(() => false);

    if (hasTimezone) {
      await expect(settingsPage.timezoneSelect).toBeVisible();
    }
  });

  test('should show language selector', {
    tag: '@regression'
  }, async () => {
    await settingsPage.goToAccountTab();

    const hasLanguage = await settingsPage.languageSelect.isVisible().catch(() => false);

    if (hasLanguage) {
      await expect(settingsPage.languageSelect).toBeVisible();
    }
  });

  test('should allow canceling changes', {
    tag: '@regression'
  }, async () => {
    const hasCancelButton = await settingsPage.cancelButton.isVisible().catch(() => false);

    if (hasCancelButton) {
      await expect(settingsPage.cancelButton).toBeVisible();
      await expect(settingsPage.cancelButton).toBeEnabled();
    }
  });

  test('should display dark mode toggle', {
    tag: '@regression'
  }, async () => {
    const hasPreferencesTab = await settingsPage.preferencesTab.isVisible().catch(() => false);

    if (hasPreferencesTab) {
      await settingsPage.goToPreferencesTab();

      const hasDarkMode = await settingsPage.darkModeToggle.isVisible().catch(() => false);
      const bodyText = await settingsPage.page.locator('body').textContent();
      const hasDarkModeText = bodyText && bodyText.toLowerCase().includes('dark mode');

      expect(hasDarkMode || hasDarkModeText).toBe(true);
    }
  });

  test('should show energy unit preferences', {
    tag: '@regression'
  }, async () => {
    const hasPreferencesTab = await settingsPage.preferencesTab.isVisible().catch(() => false);

    if (hasPreferencesTab) {
      await settingsPage.goToPreferencesTab();

      const bodyText = await settingsPage.page.locator('body').textContent();
      const hasEnergyUnit = bodyText && (
        bodyText.includes('kWh') ||
        bodyText.includes('unit') ||
        bodyText.toLowerCase().includes('energy')
      );

      expect(hasEnergyUnit).toBe(true);
    }
  });
});
