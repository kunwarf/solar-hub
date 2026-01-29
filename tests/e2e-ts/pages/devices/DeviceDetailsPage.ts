import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Page object for Device Details/Edit page
 * Displays detailed device information and allows editing
 */
export class DeviceDetailsPage extends BasePage {
  // Page elements
  readonly pageTitle: Locator;
  readonly backButton: Locator;
  readonly editButton: Locator;
  readonly saveButton: Locator;
  readonly cancelButton: Locator;
  readonly deleteButton: Locator;

  // Device information
  readonly deviceNameField: Locator;
  readonly deviceTypeField: Locator;
  readonly serialNumberField: Locator;
  readonly macAddressField: Locator;
  readonly installationDateField: Locator;
  readonly locationField: Locator;
  readonly descriptionField: Locator;

  // Status indicators
  readonly statusIndicator: Locator;
  readonly lastSeenTime: Locator;
  readonly connectionStatus: Locator;

  // Telemetry/Stats
  readonly currentPower: Locator;
  readonly totalEnergy: Locator;
  readonly voltage: Locator;
  readonly current: Locator;
  readonly temperature: Locator;

  // Tabs
  readonly overviewTab: Locator;
  readonly telemetryTab: Locator;
  readonly settingsTab: Locator;
  readonly historyTab: Locator;

  // Actions
  readonly restartButton: Locator;
  readonly calibrateButton: Locator;
  readonly exportDataButton: Locator;

  // Error messages
  readonly errorMessage: Locator;
  readonly successMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Navigation
    this.pageTitle = page.getByRole('heading', { level: 1 });
    this.backButton = page.getByRole('button', { name: /back/i });
    this.editButton = page.getByRole('button', { name: /edit/i });
    this.saveButton = page.getByRole('button', { name: /save/i });
    this.cancelButton = page.getByRole('button', { name: /cancel/i });
    this.deleteButton = page.getByRole('button', { name: /delete/i });

    // Form fields
    this.deviceNameField = page.getByLabel(/device name/i)
      .or(page.getByTestId('device-name'));
    this.deviceTypeField = page.getByLabel(/device type/i)
      .or(page.getByTestId('device-type'));
    this.serialNumberField = page.getByLabel(/serial number/i)
      .or(page.getByTestId('serial-number'));
    this.macAddressField = page.getByLabel(/mac address/i)
      .or(page.getByTestId('mac-address'));
    this.installationDateField = page.getByLabel(/installation date/i);
    this.locationField = page.getByLabel(/location/i);
    this.descriptionField = page.getByLabel(/description/i);

    // Status
    this.statusIndicator = page.getByTestId('device-status')
      .or(page.locator('[class*="status-indicator"]'));
    this.lastSeenTime = page.getByTestId('last-seen');
    this.connectionStatus = page.getByTestId('connection-status');

    // Telemetry
    this.currentPower = page.getByTestId('current-power');
    this.totalEnergy = page.getByTestId('total-energy');
    this.voltage = page.getByTestId('voltage');
    this.current = page.getByTestId('current');
    this.temperature = page.getByTestId('temperature');

    // Tabs
    this.overviewTab = page.getByRole('tab', { name: /overview/i });
    this.telemetryTab = page.getByRole('tab', { name: /telemetry|data/i });
    this.settingsTab = page.getByRole('tab', { name: /settings/i });
    this.historyTab = page.getByRole('tab', { name: /history/i });

    // Actions
    this.restartButton = page.getByRole('button', { name: /restart|reboot/i });
    this.calibrateButton = page.getByRole('button', { name: /calibrate/i });
    this.exportDataButton = page.getByRole('button', { name: /export/i });

    // Messages
    this.errorMessage = page.getByTestId('error-message')
      .or(page.getByRole('alert'));
    this.successMessage = page.getByTestId('success-message');
  }

  /**
   * Navigate to device details page
   */
  async goto(deviceId: string) {
    await this.page.goto(`/devices/${deviceId}`);
    await this.waitForLoaded();
  }

  /**
   * Wait for device details to load
   */
  async waitForLoaded() {
    await this.page.waitForLoadState('domcontentloaded');
    await this.waitForAPIResponse('/api/v1/devices/');
  }

  /**
   * Get device name
   */
  async getDeviceName(): Promise<string> {
    const name = await this.deviceNameField.inputValue().catch(() => null);
    if (name) return name;

    // If not in edit mode, get from display
    return await this.pageTitle.textContent().then(t => t?.trim() || '');
  }

  /**
   * Get device type
   */
  async getDeviceType(): Promise<string> {
    return await this.deviceTypeField.textContent().then(t => t?.trim() || '');
  }

  /**
   * Get device status
   */
  async getStatus(): Promise<'online' | 'offline' | 'unknown'> {
    const statusText = await this.statusIndicator.textContent().catch(() => '');

    if (statusText?.toLowerCase().includes('online')) return 'online';
    if (statusText?.toLowerCase().includes('offline')) return 'offline';

    return 'unknown';
  }

  /**
   * Get current power reading
   */
  async getCurrentPower(): Promise<number | null> {
    const powerText = await this.currentPower.textContent().catch(() => null);
    if (!powerText) return null;

    const match = powerText.match(/(\d+\.?\d*)/);
    return match ? parseFloat(match[1]) : null;
  }

  /**
   * Enter edit mode
   */
  async startEditing() {
    if (await this.editButton.isVisible()) {
      await this.editButton.click();
      await expect(this.saveButton).toBeVisible();
    }
  }

  /**
   * Update device name
   */
  async updateDeviceName(newName: string) {
    await this.startEditing();
    await this.deviceNameField.clear();
    await this.deviceNameField.fill(newName);
  }

  /**
   * Update device description
   */
  async updateDescription(description: string) {
    await this.startEditing();
    await this.descriptionField.clear();
    await this.descriptionField.fill(description);
  }

  /**
   * Save changes
   */
  async saveChanges() {
    await this.saveButton.click();

    // Wait for save to complete
    await this.waitForAPIResponse('/api/v1/devices/');

    // Wait for success message or edit button to reappear
    await Promise.race([
      expect(this.successMessage).toBeVisible({ timeout: 5000 }).catch(() => null),
      expect(this.editButton).toBeVisible({ timeout: 5000 }).catch(() => null),
    ]);
  }

  /**
   * Cancel editing
   */
  async cancelEditing() {
    await this.cancelButton.click();
    await expect(this.editButton).toBeVisible();
  }

  /**
   * Delete device
   */
  async deleteDevice() {
    await this.deleteButton.click();

    // Confirm deletion in dialog
    const confirmButton = this.page.getByRole('button', { name: /confirm|yes|delete/i });
    await confirmButton.click();

    // Should redirect to device list
    await expect(this.page).toHaveURL(/.*devices(?!\/)/);
  }

  /**
   * Switch to telemetry tab
   */
  async goToTelemetryTab() {
    await this.telemetryTab.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Switch to settings tab
   */
  async goToSettingsTab() {
    await this.settingsTab.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Switch to history tab
   */
  async goToHistoryTab() {
    await this.historyTab.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Restart device
   */
  async restartDevice() {
    await this.restartButton.click();

    // Confirm restart
    const confirmButton = this.page.getByRole('button', { name: /confirm|yes|restart/i });
    if (await confirmButton.isVisible()) {
      await confirmButton.click();
    }

    await this.page.waitForTimeout(1000);
  }

  /**
   * Export device data
   */
  async exportData() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportDataButton.click();
    return await downloadPromise;
  }

  /**
   * Go back to device list
   */
  async goBack() {
    await this.backButton.click();
    await expect(this.page).toHaveURL(/.*devices(?!\/)/);
  }

  /**
   * Verify device details loaded successfully
   */
  async expectDeviceDetailsLoaded() {
    await expect(this.page).toHaveURL(/.*devices\/.+/);

    // Should not show error
    await expect(this.errorMessage).not.toBeVisible();

    // Should show device name
    const deviceName = await this.getDeviceName();
    expect(deviceName.length).toBeGreaterThan(0);
  }

  /**
   * Verify device is online
   */
  async expectDeviceOnline() {
    const status = await this.getStatus();
    expect(status).toBe('online');
  }

  /**
   * Verify device name matches
   */
  async expectDeviceName(expectedName: string) {
    const actualName = await this.getDeviceName();
    expect(actualName.toLowerCase()).toContain(expectedName.toLowerCase());
  }

  /**
   * Verify changes were saved
   */
  async expectChangesSaved() {
    await expect(this.successMessage.or(this.editButton)).toBeVisible();
  }
}
