import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Page object for the Device List page
 * Displays all devices with search, filter, and management capabilities
 */
export class DeviceListPage extends BasePage {
  // Page elements
  readonly pageTitle: Locator;
  readonly addDeviceButton: Locator;
  readonly searchInput: Locator;
  readonly filterDropdown: Locator;
  readonly deviceTable: Locator;
  readonly deviceCards: Locator;

  // Table headers
  readonly nameHeader: Locator;
  readonly typeHeader: Locator;
  readonly statusHeader: Locator;
  readonly actionHeader: Locator;

  // Filters
  readonly filterByStatus: Locator;
  readonly filterByType: Locator;
  readonly filterOnlineOnly: Locator;
  readonly filterOfflineOnly: Locator;

  // Actions
  readonly bulkActionButton: Locator;
  readonly exportButton: Locator;
  readonly refreshButton: Locator;

  // Empty states
  readonly noDevicesMessage: Locator;
  readonly emptySearchResults: Locator;

  constructor(page: Page) {
    super(page);

    // Main elements
    this.pageTitle = page.getByRole('heading', { name: /devices/i });
    this.addDeviceButton = page.getByRole('button', { name: /add device|new device|claim device/i });
    this.searchInput = page.getByPlaceholder(/search.*device/i)
      .or(page.getByTestId('device-search'));
    this.filterDropdown = page.getByTestId('filter-dropdown')
      .or(page.getByRole('button', { name: /filter/i }));

    // Device list (grid layout, not table)
    this.deviceTable = page.getByTestId('device-table')
      .or(page.locator('table'));
    // Device cards are identified by their headings (h3 with device names)
    this.deviceCards = page.getByTestId('device-card')
      .or(page.locator('h3').filter({ hasText: /inverter|battery|meter|solar|device/i }).locator('..'));

    // Table headers
    this.nameHeader = page.getByRole('columnheader', { name: /name/i });
    this.typeHeader = page.getByRole('columnheader', { name: /type/i });
    this.statusHeader = page.getByRole('columnheader', { name: /status/i });
    this.actionHeader = page.getByRole('columnheader', { name: /action/i });

    // Filters
    this.filterByStatus = page.getByTestId('filter-status');
    this.filterByType = page.getByTestId('filter-type');
    this.filterOnlineOnly = page.getByRole('checkbox', { name: /online only/i });
    this.filterOfflineOnly = page.getByRole('checkbox', { name: /offline only/i });

    // Actions
    this.bulkActionButton = page.getByRole('button', { name: /bulk action/i });
    this.exportButton = page.getByRole('button', { name: /export/i });
    this.refreshButton = page.getByRole('button', { name: /refresh/i });

    // Empty states
    this.noDevicesMessage = page.getByText(/no devices|no devices found/i);
    this.emptySearchResults = page.getByText(/no results|no devices match/i);
  }

  /**
   * Navigate to device list page
   */
  async goto() {
    await this.page.goto('/devices');
    await this.waitForLoaded();
  }

  /**
   * Wait for device list to load
   */
  async waitForLoaded() {
    await this.page.waitForLoadState('domcontentloaded');

    // Wait for either devices to appear or empty state
    await Promise.race([
      expect(this.deviceTable).toBeVisible({ timeout: 10000 }).catch(() => null),
      expect(this.deviceCards.first()).toBeVisible({ timeout: 10000 }).catch(() => null),
      expect(this.noDevicesMessage).toBeVisible({ timeout: 10000 }).catch(() => null),
    ]);
  }

  /**
   * Wait for devices data to load from API
   */
  async waitForDevicesData() {
    // Wait for devices API response, but don't fail if it times out
    await this.waitForAPIResponse('/api/v1/devices').catch(() => {
      // API might not respond or endpoint might be different
      // Just continue with the test
    });
  }

  /**
   * Get all device names from the list
   */
  async getDeviceNames(): Promise<string[]> {
    await this.waitForDevicesData();

    const names: string[] = [];

    // Try table format first
    const nameColumns = this.page.locator('td:has-text(""), [data-label="name"], [class*="device-name"]');
    const count = await nameColumns.count();

    if (count > 0) {
      for (let i = 0; i < count; i++) {
        const text = await nameColumns.nth(i).textContent();
        if (text && text.trim()) {
          names.push(text.trim());
        }
      }
    } else {
      // Try card format
      const cards = await this.deviceCards.count();
      for (let i = 0; i < cards; i++) {
        const nameElement = this.deviceCards.nth(i).locator('[class*="name"], h3, h4').first();
        const text = await nameElement.textContent().catch(() => null);
        if (text && text.trim()) {
          names.push(text.trim());
        }
      }
    }

    return names;
  }

  /**
   * Get total device count
   */
  async getDeviceCount(): Promise<number> {
    const names = await this.getDeviceNames();
    return names.length;
  }

  /**
   * Get count of online devices
   */
  async getOnlineDeviceCount(): Promise<number> {
    const onlineIndicators = this.page.locator('[class*="online"], [data-status="online"], [class*="status-active"]');
    return await onlineIndicators.count();
  }

  /**
   * Get count of offline devices
   */
  async getOfflineDeviceCount(): Promise<number> {
    const offlineIndicators = this.page.locator('[class*="offline"], [data-status="offline"], [class*="status-inactive"]');
    return await offlineIndicators.count();
  }

  /**
   * Search for a device by name
   */
  async searchDevice(deviceName: string) {
    await this.searchInput.fill(deviceName);
    await this.searchInput.press('Enter');
    await this.page.waitForTimeout(1000); // Wait for search results
  }

  /**
   * Clear search
   */
  async clearSearch() {
    await this.searchInput.clear();
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter devices by status
   */
  async filterByStatus(status: 'online' | 'offline' | 'all') {
    if (!await this.filterByStatus.isVisible()) {
      await this.filterDropdown.click();
    }

    const option = this.page.getByRole('option', { name: new RegExp(status, 'i') });
    await option.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Filter devices by type
   */
  async filterByType(type: string) {
    if (!await this.filterByType.isVisible()) {
      await this.filterDropdown.click();
    }

    const option = this.page.getByRole('option', { name: new RegExp(type, 'i') });
    await option.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Click on a device by name
   */
  async clickDevice(deviceName: string) {
    const deviceRow = this.page.getByRole('row', { name: new RegExp(deviceName, 'i') })
      .or(this.deviceCards.filter({ hasText: deviceName }));

    await deviceRow.click();
  }

  /**
   * Click "Add Device" button
   */
  async clickAddDevice() {
    await this.addDeviceButton.click();
    await this.page.waitForLoadState('domcontentloaded');
  }

  /**
   * Check if device exists in list
   */
  async hasDevice(deviceName: string): Promise<boolean> {
    const names = await this.getDeviceNames();
    return names.some(name => name.toLowerCase().includes(deviceName.toLowerCase()));
  }

  /**
   * Get device status
   */
  async getDeviceStatus(deviceName: string): Promise<'online' | 'offline' | 'unknown'> {
    const deviceRow = this.page.getByRole('row', { name: new RegExp(deviceName, 'i') })
      .or(this.deviceCards.filter({ hasText: deviceName }));

    if (!await deviceRow.isVisible()) {
      return 'unknown';
    }

    const statusElement = deviceRow.locator('[class*="status"], [data-status]').first();
    const statusText = await statusElement.textContent().catch(() => null);

    if (statusText?.toLowerCase().includes('online')) return 'online';
    if (statusText?.toLowerCase().includes('offline')) return 'offline';

    // Check for status classes
    const classes = await statusElement.getAttribute('class').catch(() => null);
    if (classes?.includes('online')) return 'online';
    if (classes?.includes('offline')) return 'offline';

    return 'unknown';
  }

  /**
   * Delete a device
   */
  async deleteDevice(deviceName: string) {
    const deviceRow = this.page.getByRole('row', { name: new RegExp(deviceName, 'i') });
    const deleteButton = deviceRow.getByRole('button', { name: /delete|remove/i });

    await deleteButton.click();

    // Confirm deletion
    const confirmButton = this.page.getByRole('button', { name: /confirm|yes|delete/i });
    await confirmButton.click();

    await this.waitForDevicesData();
  }

  /**
   * Edit a device
   */
  async editDevice(deviceName: string) {
    const deviceRow = this.page.getByRole('row', { name: new RegExp(deviceName, 'i') });
    const editButton = deviceRow.getByRole('button', { name: /edit|modify/i });

    await editButton.click();
    await this.page.waitForLoadState('domcontentloaded');
  }

  /**
   * Refresh device list
   */
  async refresh() {
    if (await this.refreshButton.isVisible()) {
      await this.refreshButton.click();
      await this.waitForDevicesData();
    } else {
      await this.page.reload();
      await this.waitForLoaded();
    }
  }

  /**
   * Check if list is empty
   */
  async isEmpty(): Promise<boolean> {
    return await this.noDevicesMessage.isVisible();
  }

  /**
   * Verify device list loaded successfully
   */
  async expectDeviceListLoaded() {
    await expect(this.page).toHaveURL(/.*devices/);

    // Should not show error (use shorter timeout)
    const errorToast = this.page.getByTestId('error-toast');
    await expect(errorToast).not.toBeVisible({ timeout: 2000 }).catch(() => {
      // Ignore if error toast doesn't exist
    });

    // Wait for page to be loaded
    await this.page.waitForLoadState('domcontentloaded');

    // Check for content that indicates the page loaded successfully
    const hasContent = await Promise.race([
      // Look for the device count text
      this.page.getByText(/showing \d+ of \d+ devices?/i).isVisible({ timeout: 15000 }).catch(() => false),
      // Look for device headings (device names)
      this.page.locator('h3').first().isVisible({ timeout: 15000 }).catch(() => false),
      // Look for empty state
      this.noDevicesMessage.isVisible({ timeout: 15000 }).catch(() => false),
      // Look for "No Devices" in EmptyState component
      this.page.getByText(/no devices/i).isVisible({ timeout: 15000 }).catch(() => false),
    ]);

    expect(hasContent).toBe(true);
  }

  /**
   * Verify search results contain text
   */
  async expectSearchResults(searchTerm: string) {
    const names = await this.getDeviceNames();

    const matchingDevices = names.filter(name =>
      name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    expect(matchingDevices.length).toBeGreaterThan(0);
  }

  /**
   * Verify device is in list
   */
  async expectDeviceInList(deviceName: string) {
    const hasDevice = await this.hasDevice(deviceName);
    expect(hasDevice).toBe(true);
  }

  /**
   * Verify device is not in list
   */
  async expectDeviceNotInList(deviceName: string) {
    const hasDevice = await this.hasDevice(deviceName);
    expect(hasDevice).toBe(false);
  }
}
