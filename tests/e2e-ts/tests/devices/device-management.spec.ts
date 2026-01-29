import { test, expect } from '@/fixtures/auth.fixture';
import { DeviceListPage } from '@/pages/devices/DeviceListPage';
import { DeviceDetailsPage } from '@/pages/devices/DeviceDetailsPage';

/**
 * Device Management Tests
 *
 * Tests device CRUD operations and management features
 * Priority: P1
 *
 * Note: Some tests may be skipped if user doesn't have permissions
 */
test.describe('Devices - Device Management', { tag: '@devices' }, () => {
  let deviceListPage: DeviceListPage;
  let deviceDetailsPage: DeviceDetailsPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    deviceListPage = new DeviceListPage(authenticatedPage);
    deviceDetailsPage = new DeviceDetailsPage(authenticatedPage);
  });

  test('should view device details', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      const deviceName = deviceNames[0];

      // Click device to view details
      await deviceListPage.clickDevice(deviceName);

      // Wait for details page to load
      await deviceDetailsPage.waitForLoaded();

      // Verify details loaded
      await deviceDetailsPage.expectDeviceDetailsLoaded();

      // Device name should match
      await deviceDetailsPage.expectDeviceName(deviceName);
    } else {
      test.skip();
    }
  });

  test('should display device status in details page', {
    tag: '@regression'
  }, async () => {
    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      await deviceListPage.clickDevice(deviceNames[0]);
      await deviceDetailsPage.waitForLoaded();

      // Get device status
      const status = await deviceDetailsPage.getStatus();

      // Status should be valid
      expect(['online', 'offline', 'unknown']).toContain(status);
    } else {
      test.skip();
    }
  });

  test('should display device telemetry data', {
    tag: '@regression'
  }, async () => {
    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      await deviceListPage.clickDevice(deviceNames[0]);
      await deviceDetailsPage.waitForLoaded();

      // Check for telemetry data
      const power = await deviceDetailsPage.getCurrentPower();

      // Power should be a number or null (if device offline)
      if (power !== null) {
        expect(power).toBeGreaterThanOrEqual(0);
        expect(power).toBeLessThan(1000000); // Reasonable limit
      }
    } else {
      test.skip();
    }
  });

  test('should edit device name (owner/admin only)', {
    tag: '@regression'
  }, async ({ authenticatedPage, userRole }) => {
    // Skip if not owner or admin
    test.skip(!['owner', 'admin'].includes(userRole), 'Requires owner or admin role');

    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      await deviceListPage.clickDevice(deviceNames[0]);
      await deviceDetailsPage.waitForLoaded();

      const originalName = await deviceDetailsPage.getDeviceName();
      const newName = `${originalName}_EDITED`;

      // Update device name
      await deviceDetailsPage.updateDeviceName(newName);
      await deviceDetailsPage.saveChanges();

      // Verify save succeeded
      await deviceDetailsPage.expectChangesSaved();

      // Revert name back
      await deviceDetailsPage.startEditing();
      await deviceDetailsPage.updateDeviceName(originalName);
      await deviceDetailsPage.saveChanges();
    } else {
      test.skip();
    }
  });

  test('should cancel device editing without saving', {
    tag: '@regression'
  }, async ({ userRole }) => {
    test.skip(!['owner', 'admin'].includes(userRole), 'Requires owner or admin role');

    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      await deviceListPage.clickDevice(deviceNames[0]);
      await deviceDetailsPage.waitForLoaded();

      const originalName = await deviceDetailsPage.getDeviceName();

      // Start editing
      await deviceDetailsPage.updateDeviceName('TEMP_NAME');

      // Cancel without saving
      await deviceDetailsPage.cancelEditing();

      // Name should remain unchanged
      const currentName = await deviceDetailsPage.getDeviceName();
      expect(currentName).toBe(originalName);
    } else {
      test.skip();
    }
  });

  test('should navigate back to device list from details', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      await deviceListPage.clickDevice(deviceNames[0]);
      await deviceDetailsPage.waitForLoaded();

      // Go back to list
      await deviceDetailsPage.goBack();

      // Should be on device list
      await expect(authenticatedPage).toHaveURL(/.*devices(?!\/)/);
    } else {
      test.skip();
    }
  });

  test('should display device type', {
    tag: '@regression'
  }, async () => {
    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      await deviceListPage.clickDevice(deviceNames[0]);
      await deviceDetailsPage.waitForLoaded();

      const deviceType = await deviceDetailsPage.getDeviceType();

      // Device type should not be empty
      expect(deviceType.length).toBeGreaterThan(0);
    } else {
      test.skip();
    }
  });

  test('should show edit button for authorized users', {
    tag: '@regression'
  }, async ({ userRole }) => {
    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      await deviceListPage.clickDevice(deviceNames[0]);
      await deviceDetailsPage.waitForLoaded();

      if (['owner', 'admin'].includes(userRole)) {
        // Edit button should be visible
        await expect(deviceDetailsPage.editButton).toBeVisible();
      }
    } else {
      test.skip();
    }
  });

  test('should switch between device detail tabs', {
    tag: '@regression'
  }, async () => {
    await deviceListPage.goto();
    const deviceNames = await deviceListPage.getDeviceNames();

    if (deviceNames.length > 0) {
      await deviceListPage.clickDevice(deviceNames[0]);
      await deviceDetailsPage.waitForLoaded();

      // Check if tabs exist
      const hasTelemetryTab = await deviceDetailsPage.telemetryTab.isVisible().catch(() => false);

      if (hasTelemetryTab) {
        // Switch to telemetry tab
        await deviceDetailsPage.goToTelemetryTab();

        // Tab should be active
        await expect(deviceDetailsPage.telemetryTab).toHaveAttribute('aria-selected', 'true');
      }
    } else {
      test.skip();
    }
  });

  test('should handle missing devices gracefully', {
    tag: '@regression'
  }, async ({ authenticatedPage }) => {
    // Try to access non-existent device
    await authenticatedPage.goto('/devices/non-existent-device-id-12345');

    // Should show error or redirect
    const hasError = await deviceDetailsPage.errorMessage.isVisible({ timeout: 5000 }).catch(() => false);
    const redirectedToList = authenticatedPage.url().endsWith('/devices');

    expect(hasError || redirectedToList).toBe(true);
  });
});
