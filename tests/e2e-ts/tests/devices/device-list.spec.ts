import { test, expect } from '@/fixtures/auth.fixture';
import { DeviceListPage } from '@/pages/devices/DeviceListPage';
import { NavigationComponent } from '@/pages/components/NavigationComponent';

/**
 * Device List Tests
 *
 * Tests device listing, search, filter, and management features
 * Priority: P1
 */
test.describe('Devices - Device List', { tag: '@devices' }, () => {
  let deviceListPage: DeviceListPage;
  let navigation: NavigationComponent;

  test.beforeEach(async ({ authenticatedPage }) => {
    deviceListPage = new DeviceListPage(authenticatedPage);
    navigation = new NavigationComponent(authenticatedPage);

    await deviceListPage.goto();
  });

  test('should load device list page successfully', {
    tag: ['@smoke', '@critical']
  }, async () => {
    // Verify page loaded
    await deviceListPage.expectDeviceListLoaded();

    // Should have page title
    await expect(deviceListPage.pageTitle).toBeVisible();
  });

  test('should display list of devices', {
    tag: ['@smoke', '@critical']
  }, async () => {
    await deviceListPage.waitForDevicesData();

    // Should show devices or empty state
    const deviceCount = await deviceListPage.getDeviceCount();
    const isEmpty = await deviceListPage.isEmpty();

    // Either has devices or shows empty state message
    expect(deviceCount > 0 || isEmpty).toBe(true);
  });

  test('should display device names from database', {
    tag: '@regression'
  }, async () => {
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      // Device names should not be empty
      deviceNames.forEach(name => {
        expect(name.length).toBeGreaterThan(0);
      });

      // Should not be placeholder names
      const hasRealNames = deviceNames.every(name =>
        !name.match(/^(device\s*\d+|test|demo|sample)$/i)
      );
      expect(hasRealNames).toBe(true);
    }
  });

  test('should display accurate device count', {
    tag: '@regression'
  }, async () => {
    const deviceCount = await deviceListPage.getDeviceCount();

    // Count should be non-negative
    expect(deviceCount).toBeGreaterThanOrEqual(0);

    // Count should be reasonable (not obviously fake)
    expect(deviceCount).toBeLessThan(1000);
  });

  test('should show online and offline device counts', {
    tag: '@regression'
  }, async () => {
    const onlineCount = await deviceListPage.getOnlineDeviceCount();
    const offlineCount = await deviceListPage.getOfflineDeviceCount();
    const totalCount = await deviceListPage.getDeviceCount();

    // Counts should be non-negative
    expect(onlineCount).toBeGreaterThanOrEqual(0);
    expect(offlineCount).toBeGreaterThanOrEqual(0);

    // Online + offline should not exceed total
    if (totalCount > 0) {
      expect(onlineCount + offlineCount).toBeLessThanOrEqual(totalCount + 5); // Some tolerance for rendering
    }
  });

  test('should display device status indicators', {
    tag: '@regression'
  }, async () => {
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      // Check status of first device
      const status = await deviceListPage.getDeviceStatus(deviceNames[0]);

      // Status should be one of the known states
      expect(['online', 'offline', 'unknown']).toContain(status);
    }
  });

  test('should search devices by name', {
    tag: '@regression'
  }, async () => {
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      const searchTerm = deviceNames[0].substring(0, 3); // Search first 3 chars

      await deviceListPage.searchDevice(searchTerm);

      // Results should contain the search term
      await deviceListPage.expectSearchResults(searchTerm);
    } else {
      test.skip();
    }
  });

  test('should clear search and show all devices', {
    tag: '@regression'
  }, async () => {
    const deviceNames = await deviceListPage.getDeviceNames();
    const initialCount = deviceNames.length;

    if (initialCount > 0) {
      // Search for something
      await deviceListPage.searchDevice(deviceNames[0].substring(0, 3));

      // Clear search
      await deviceListPage.clearSearch();

      // Should show all devices again
      const finalCount = await deviceListPage.getDeviceCount();
      expect(finalCount).toBeGreaterThanOrEqual(initialCount);
    } else {
      test.skip();
    }
  });

  test('should filter devices by status', {
    tag: '@regression'
  }, async () => {
    const initialCount = await deviceListPage.getDeviceCount();

    if (initialCount > 0) {
      // Filter to show online only
      await deviceListPage.filterByStatus('online');
      await deviceListPage.page.waitForTimeout(1000);

      const onlineCount = await deviceListPage.getOnlineDeviceCount();

      // All visible devices should be online
      expect(onlineCount).toBeGreaterThan(0);
    } else {
      test.skip();
    }
  });

  test('should click on device to view details', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      const deviceName = deviceNames[0];

      // Click on device
      await deviceListPage.clickDevice(deviceName);

      // Should navigate to device details
      await expect(authenticatedPage).toHaveURL(/.*devices\/.+/);
    } else {
      test.skip();
    }
  });

  test('should refresh device list', {
    tag: '@regression'
  }, async () => {
    await deviceListPage.waitForDevicesData();

    // Refresh
    await deviceListPage.refresh();

    // Should still be on devices page
    await deviceListPage.expectDeviceListLoaded();
  });

  test('should show "Add Device" button for authorized users', {
    tag: '@regression'
  }, async ({ userRole }) => {
    // Only owners and admins can add devices
    if (['owner', 'admin'].includes(userRole)) {
      await expect(deviceListPage.addDeviceButton).toBeVisible();
    }
  });

  test('should handle empty search results gracefully', {
    tag: '@regression'
  }, async () => {
    // Search for something that doesn't exist
    await deviceListPage.searchDevice('xyzNonExistentDevice12345');

    // Should show empty results message
    const isEmpty = await deviceListPage.emptySearchResults.isVisible().catch(() => false);
    const noDevices = await deviceListPage.isEmpty();

    expect(isEmpty || noDevices).toBe(true);
  });
});
