/**
 * Device Settings LocalStorage Manager
 *
 * Manages device settings in browser localStorage instead of database.
 * Settings are cached locally and synced with actual device hardware.
 */

const STORAGE_PREFIX = 'device_settings_';
const STORAGE_VERSION = '1.0';
const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export interface DeviceSettingsCache {
  deviceId: string;
  deviceType: string;
  settings: Record<string, any>;
  lastSyncedAt: string;
  lastQueriedAt: string;
  version: string;
  isStale: boolean;
}

/**
 * Save device settings to localStorage
 */
export function saveDeviceSettings(
  deviceId: string,
  deviceType: string,
  settings: Record<string, any>,
  isSynced: boolean = false
): void {
  const cache: DeviceSettingsCache = {
    deviceId,
    deviceType,
    settings,
    lastSyncedAt: isSynced ? new Date().toISOString() : '',
    lastQueriedAt: new Date().toISOString(),
    version: STORAGE_VERSION,
    isStale: !isSynced,
  };

  try {
    const key = `${STORAGE_PREFIX}${deviceId}`;
    localStorage.setItem(key, JSON.stringify(cache));
  } catch (error) {
    console.error('Failed to save device settings to localStorage:', error);

    // If quota exceeded, clear old entries and retry
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      cleanupOldSettings();
      try {
        const key = `${STORAGE_PREFIX}${deviceId}`;
        localStorage.setItem(key, JSON.stringify(cache));
      } catch (retryError) {
        console.error('Failed to save after cleanup:', retryError);
      }
    }
  }
}

/**
 * Load device settings from localStorage
 */
export function loadDeviceSettings(deviceId: string): DeviceSettingsCache | null {
  try {
    const key = `${STORAGE_PREFIX}${deviceId}`;
    const cached = localStorage.getItem(key);

    if (!cached) {
      return null;
    }

    const cache: DeviceSettingsCache = JSON.parse(cached);

    // Check if cache is too old
    if (cache.lastQueriedAt) {
      const age = Date.now() - new Date(cache.lastQueriedAt).getTime();
      if (age > MAX_AGE_MS) {
        // Cache expired, delete it
        localStorage.removeItem(key);
        return null;
      }
    }

    return cache;
  } catch (error) {
    console.error('Failed to load device settings from localStorage:', error);
    return null;
  }
}

/**
 * Mark cached settings as stale (device query failed)
 */
export function markSettingsAsStale(deviceId: string): void {
  const cache = loadDeviceSettings(deviceId);
  if (cache) {
    cache.isStale = true;
    cache.lastQueriedAt = new Date().toISOString();
    const key = `${STORAGE_PREFIX}${deviceId}`;
    localStorage.setItem(key, JSON.stringify(cache));
  }
}

/**
 * Update settings with fresh values from device
 */
export function updateSettingsFromDevice(
  deviceId: string,
  deviceType: string,
  settings: Record<string, any>
): void {
  saveDeviceSettings(deviceId, deviceType, settings, true);
}

/**
 * Delete device settings from localStorage
 */
export function deleteDeviceSettings(deviceId: string): void {
  try {
    const key = `${STORAGE_PREFIX}${deviceId}`;
    localStorage.removeItem(key);
  } catch (error) {
    console.error('Failed to delete device settings:', error);
  }
}

/**
 * Cleanup old device settings entries
 */
export function cleanupOldSettings(): void {
  try {
    const keys = Object.keys(localStorage);
    const settingsKeys = keys.filter(k => k.startsWith(STORAGE_PREFIX));

    const entries: Array<{ key: string; age: number }> = [];

    for (const key of settingsKeys) {
      const cached = localStorage.getItem(key);
      if (cached) {
        try {
          const cache: DeviceSettingsCache = JSON.parse(cached);
          const age = Date.now() - new Date(cache.lastQueriedAt).getTime();
          entries.push({ key, age });
        } catch {
          // Invalid entry, delete it
          localStorage.removeItem(key);
        }
      }
    }

    // Sort by age (oldest first)
    entries.sort((a, b) => b.age - a.age);

    // Remove oldest 25% of entries
    const toRemove = Math.ceil(entries.length * 0.25);
    for (let i = 0; i < toRemove; i++) {
      localStorage.removeItem(entries[i].key);
    }

    console.log(`Cleaned up ${toRemove} old device settings entries`);
  } catch (error) {
    console.error('Failed to cleanup old settings:', error);
  }
}

/**
 * Get all cached device IDs
 */
export function getAllCachedDeviceIds(): string[] {
  try {
    const keys = Object.keys(localStorage);
    const settingsKeys = keys.filter(k => k.startsWith(STORAGE_PREFIX));
    return settingsKeys.map(k => k.replace(STORAGE_PREFIX, ''));
  } catch (error) {
    console.error('Failed to get cached device IDs:', error);
    return [];
  }
}

/**
 * Export all settings to JSON (for backup)
 */
export function exportAllSettings(): Record<string, DeviceSettingsCache> {
  const deviceIds = getAllCachedDeviceIds();
  const exported: Record<string, DeviceSettingsCache> = {};

  for (const deviceId of deviceIds) {
    const cache = loadDeviceSettings(deviceId);
    if (cache) {
      exported[deviceId] = cache;
    }
  }

  return exported;
}

/**
 * Import settings from JSON (for restore)
 */
export function importSettings(data: Record<string, DeviceSettingsCache>): void {
  for (const [deviceId, cache] of Object.entries(data)) {
    saveDeviceSettings(deviceId, cache.deviceType, cache.settings, false);
  }
}

/**
 * Clear all device settings from localStorage
 */
export function clearAllSettings(): void {
  const keys = Object.keys(localStorage);
  const settingsKeys = keys.filter(k => k.startsWith(STORAGE_PREFIX));

  for (const key of settingsKeys) {
    localStorage.removeItem(key);
  }

  console.log(`Cleared ${settingsKeys.length} device settings entries`);
}
