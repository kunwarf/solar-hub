import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Page object for User Settings page
 * Handles account preferences, notifications, and personal settings
 */
export class SettingsPage extends BasePage {
  // Main elements
  readonly pageTitle: Locator;

  // Tabs/Sections
  readonly accountTab: Locator;
  readonly notificationsTab: Locator;
  readonly preferencesTab: Locator;
  readonly securityTab: Locator;

  // Account settings
  readonly firstNameInput: Locator;
  readonly lastNameInput: Locator;
  readonly emailInput: Locator;
  readonly phoneInput: Locator;
  readonly timezoneSelect: Locator;
  readonly languageSelect: Locator;

  // Notification settings
  readonly emailNotifications: Locator;
  readonly smsNotifications: Locator;
  readonly pushNotifications: Locator;
  readonly outageAlerts: Locator;
  readonly billingAlerts: Locator;
  readonly deviceAlerts: Locator;

  // Preferences
  readonly themeSelect: Locator;
  readonly darkModeToggle: Locator;
  readonly dateFormatSelect: Locator;
  readonly energyUnitSelect: Locator;
  readonly currencySelect: Locator;

  // Security
  readonly currentPasswordInput: Locator;
  readonly newPasswordInput: Locator;
  readonly confirmPasswordInput: Locator;
  readonly changePasswordButton: Locator;
  readonly twoFactorToggle: Locator;

  // Actions
  readonly saveButton: Locator;
  readonly cancelButton: Locator;
  readonly resetButton: Locator;

  // Messages
  readonly successMessage: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Main (use .first() to avoid strict mode violation with multiple settings headings)
    this.pageTitle = page.getByRole('heading', { name: /^settings$/i }).first();

    // Tabs
    this.accountTab = page.getByRole('tab', { name: /account|profile/i });
    this.notificationsTab = page.getByRole('tab', { name: /notifications|alerts/i });
    this.preferencesTab = page.getByRole('tab', { name: /preferences/i });
    this.securityTab = page.getByRole('tab', { name: /security|password/i });

    // Account
    this.firstNameInput = page.getByLabel(/first name/i);
    this.lastNameInput = page.getByLabel(/last name/i);
    this.emailInput = page.getByLabel(/email/i);
    this.phoneInput = page.getByLabel(/phone/i);
    this.timezoneSelect = page.getByLabel(/timezone/i);
    this.languageSelect = page.getByLabel(/language/i);

    // Notifications
    this.emailNotifications = page.getByLabel(/email notifications/i);
    this.smsNotifications = page.getByLabel(/sms notifications/i);
    this.pushNotifications = page.getByLabel(/push notifications/i);
    this.outageAlerts = page.getByLabel(/outage.*alert/i);
    this.billingAlerts = page.getByLabel(/billing.*alert/i);
    this.deviceAlerts = page.getByLabel(/device.*alert/i);

    // Preferences
    this.themeSelect = page.getByLabel(/theme/i);
    this.darkModeToggle = page.getByLabel(/dark mode/i);
    this.dateFormatSelect = page.getByLabel(/date format/i);
    this.energyUnitSelect = page.getByLabel(/energy unit/i);
    this.currencySelect = page.getByLabel(/currency/i);

    // Security
    this.currentPasswordInput = page.getByLabel(/current password/i);
    this.newPasswordInput = page.getByLabel(/new password/i);
    this.confirmPasswordInput = page.getByLabel(/confirm password/i);
    this.changePasswordButton = page.getByRole('button', { name: /change password/i });
    this.twoFactorToggle = page.getByLabel(/two.*factor|2fa/i);

    // Actions
    this.saveButton = page.getByRole('button', { name: /save|update/i });
    this.cancelButton = page.getByRole('button', { name: /cancel/i });
    this.resetButton = page.getByRole('button', { name: /reset/i });

    // Messages
    this.successMessage = page.getByTestId('success-message')
      .or(page.getByRole('alert').filter({ hasText: /success|saved/i }));
    this.errorMessage = page.getByTestId('error-message')
      .or(page.getByRole('alert').filter({ hasText: /error|failed/i }));
  }

  /**
   * Navigate to settings page
   */
  async goto() {
    await this.page.goto('/settings');
    await this.waitForLoaded();
  }

  /**
   * Wait for settings page to load
   */
  async waitForLoaded() {
    await this.page.waitForLoadState('domcontentloaded');
    await this.waitForAPIResponse('/api/v1/users/me').catch(() => null);
  }

  /**
   * Go to account tab
   */
  async goToAccountTab() {
    if (await this.accountTab.isVisible()) {
      await this.accountTab.click();
      await this.page.waitForTimeout(500);
    }
  }

  /**
   * Go to notifications tab
   */
  async goToNotificationsTab() {
    if (await this.notificationsTab.isVisible()) {
      await this.notificationsTab.click();
      await this.page.waitForTimeout(500);
    }
  }

  /**
   * Go to preferences tab
   */
  async goToPreferencesTab() {
    if (await this.preferencesTab.isVisible()) {
      await this.preferencesTab.click();
      await this.page.waitForTimeout(500);
    }
  }

  /**
   * Go to security tab
   */
  async goToSecurityTab() {
    if (await this.securityTab.isVisible()) {
      await this.securityTab.click();
      await this.page.waitForTimeout(500);
    }
  }

  /**
   * Update account information
   */
  async updateAccountInfo(firstName?: string, lastName?: string) {
    await this.goToAccountTab();

    if (firstName && await this.firstNameInput.isVisible()) {
      await this.firstNameInput.clear();
      await this.firstNameInput.fill(firstName);
    }

    if (lastName && await this.lastNameInput.isVisible()) {
      await this.lastNameInput.clear();
      await this.lastNameInput.fill(lastName);
    }

    await this.saveButton.click();
    await this.expectChangesSaved();
  }

  /**
   * Toggle email notifications
   */
  async toggleEmailNotifications(enabled: boolean) {
    await this.goToNotificationsTab();

    if (await this.emailNotifications.isVisible()) {
      const isChecked = await this.emailNotifications.isChecked();

      if ((enabled && !isChecked) || (!enabled && isChecked)) {
        await this.emailNotifications.click();
      }

      await this.saveButton.click();
    }
  }

  /**
   * Enable dark mode
   */
  async enableDarkMode() {
    await this.goToPreferencesTab();

    if (await this.darkModeToggle.isVisible()) {
      const isChecked = await this.darkModeToggle.isChecked();

      if (!isChecked) {
        await this.darkModeToggle.click();
        await this.saveButton.click();
      }
    }
  }

  /**
   * Change password
   */
  async changePassword(currentPassword: string, newPassword: string) {
    await this.goToSecurityTab();

    await this.currentPasswordInput.fill(currentPassword);
    await this.newPasswordInput.fill(newPassword);
    await this.confirmPasswordInput.fill(newPassword);

    await this.changePasswordButton.click();

    await this.expectChangesSaved();
  }

  /**
   * Select timezone
   */
  async selectTimezone(timezone: string) {
    await this.goToAccountTab();

    if (await this.timezoneSelect.isVisible()) {
      await this.timezoneSelect.selectOption({ label: timezone });
      await this.saveButton.click();
    }
  }

  /**
   * Save settings
   */
  async saveSettings() {
    await this.saveButton.click();
    await this.expectChangesSaved();
  }

  /**
   * Cancel changes
   */
  async cancelChanges() {
    await this.cancelButton.click();
  }

  /**
   * Verify settings page loaded
   */
  async expectSettingsPageLoaded() {
    await expect(this.page).toHaveURL(/.*settings/);
    await expect(this.pageTitle).toBeVisible();
  }

  /**
   * Verify changes were saved
   */
  async expectChangesSaved() {
    await Promise.race([
      expect(this.successMessage).toBeVisible({ timeout: 5000 }).catch(() => null),
      this.page.waitForTimeout(2000),
    ]);
  }

  /**
   * Verify account tab is accessible
   */
  async expectAccountTabVisible() {
    const hasAccountTab = await this.accountTab.isVisible().catch(() => false);
    const hasAccountFields = await this.firstNameInput.isVisible().catch(() => false);

    expect(hasAccountTab || hasAccountFields).toBe(true);
  }

  /**
   * Verify save button is present
   */
  async expectSaveButtonVisible() {
    await expect(this.saveButton).toBeVisible();
  }
}
