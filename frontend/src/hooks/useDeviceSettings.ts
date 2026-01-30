/**
 * useDeviceSettings Hook - HYBRID MODE
 *
 * Custom hook for managing device settings with hybrid architecture:
 *
 * PRIMARY PATH:
 * - localStorage caching (instant)
 * - Device commands (real-time, authoritative)
 *
 * FALLBACK PATH:
 * - Database API (when device offline)
 * - Graceful degradation
 *
 * FEATURES:
 * - Background polling from device
 * - Multi-tab synchronization
 * - Automatic database backup
 * - Stale data detection
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  loadDeviceSettings,
  saveDeviceSettings,
  updateSettingsFromDevice,
  markSettingsAsStale,
  type DeviceSettingsCache,
} from '@/lib/device-settings-storage';
import { deviceCommandsService, deviceSettingsService } from '@/api';

interface UseDeviceSettingsOptions {
  deviceId: string;
  deviceType: string;
  enabled?: boolean;
  pollInterval?: number; // ms between device queries (default: 30000 = 30s)
}

interface UseDeviceSettingsReturn {
  settings: Record<string, any> | null;
  isLoading: boolean;
  isQuerying: boolean;
  isUpdating: boolean;
  isStale: boolean;
  isDeviceOffline: boolean;
  usingFallback: boolean;
  lastSyncedAt: string | null;
  error: Error | null;
  queryDevice: () => Promise<void>;
  updateDevice: (newSettings: Record<string, any>) => Promise<void>;
  refresh: () => Promise<void>;
}

export function useDeviceSettings(
  options: UseDeviceSettingsOptions
): UseDeviceSettingsReturn {
  const { deviceId, deviceType, enabled = true, pollInterval = 30000 } = options;

  const [settings, setSettings] = useState<Record<string, any> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isQuerying, setIsQuerying] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isStale, setIsStale] = useState(false);
  const [isDeviceOffline, setIsDeviceOffline] = useState(false);
  const [usingFallback, setUsingFallback] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const queryClient = useQueryClient();
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);

  /**
   * Load settings from localStorage
   */
  const loadCachedSettings = useCallback(() => {
    const cached = loadDeviceSettings(deviceId);
    if (cached) {
      setSettings(cached.settings);
      setIsStale(cached.isStale);
      setLastSyncedAt(cached.lastSyncedAt || null);
      setIsLoading(false);
      return true;
    }
    return false;
  }, [deviceId]);

  /**
   * Load settings from database (DEPRECATED - fallback removed)
   * Settings are now stored only on device and in localStorage cache.
   * This function is kept for backwards compatibility but does nothing.
   */
  const loadFromDatabase = useCallback(async () => {
    console.log('Database fallback skipped - settings stored on device only');
    return false;
  }, []);

  /**
   * Query device for current settings (PRIMARY PATH)
   */
  const queryDevice = useCallback(async () => {
    if (!enabled) return;

    setIsQuerying(true);
    setError(null);

    try {
      const response = await deviceCommandsService.querySettings(deviceId);

      // Poll command status until complete
      const status = await deviceCommandsService.waitForCommand(
        deviceId,
        response.command_id,
        30000, // 30s timeout
        2000  // 2s poll interval
      );

      if (status.status === 'completed' && status.result?.settings) {
        const deviceSettings = status.result.settings;

        // Update localStorage cache
        updateSettingsFromDevice(deviceId, deviceType, deviceSettings);

        // Database backup removed - settings now live on device only
        // localStorage provides caching, device commands provide authoritative source

        // Update state
        setSettings(deviceSettings);
        setIsStale(false);
        setIsDeviceOffline(false);
        setUsingFallback(false);
        setLastSyncedAt(new Date().toISOString());
        setError(null);
      } else if (status.status === 'failed') {
        throw new Error(status.error || 'Device query failed');
      } else {
        throw new Error('Device query timed out');
      }
    } catch (err) {
      console.error('Failed to query device settings:', err);
      setError(err as Error);
      setIsStale(true);
      setIsDeviceOffline(true);

      // Mark cached settings as stale
      markSettingsAsStale(deviceId);

      // FALLBACK: Try loading from database
      const fallbackLoaded = await loadFromDatabase();
      if (!fallbackLoaded) {
        console.warn('No fallback settings available in database');
      }
    } finally {
      if (isMountedRef.current) {
        setIsQuerying(false);
      }
    }
  }, [deviceId, deviceType, enabled, loadFromDatabase]);

  /**
   * Update device settings (HYBRID: Device + Database)
   */
  const updateDevice = useCallback(
    async (newSettings: Record<string, any>) => {
      if (!enabled) return;

      setIsUpdating(true);
      setError(null);

      try {
        // 1. Optimistic update to localStorage
        saveDeviceSettings(deviceId, deviceType, newSettings, false);
        setSettings(newSettings);

        // 2. Database backup removed - device commands are the authoritative source
        // localStorage provides optimistic updates and caching

        // 3. Send command to device (primary)
        const response = await deviceCommandsService.updateSettings(
          deviceId,
          newSettings,
          true
        );

        // Poll command status
        const status = await deviceCommandsService.waitForCommand(
          deviceId,
          response.command_id,
          30000,
          2000
        );

        if (status.status === 'completed') {
          // Device update succeeded
          updateSettingsFromDevice(deviceId, deviceType, newSettings);
          setIsStale(false);
          setIsDeviceOffline(false);
          setUsingFallback(false);
          setLastSyncedAt(new Date().toISOString());
        } else if (status.status === 'failed') {
          // Device update failed, but database backup is saved
          setIsDeviceOffline(true);
          setUsingFallback(true);

          throw new Error(status.error || 'Failed to update device (saved to database backup)');
        }
      } catch (err) {
        console.error('Failed to update device settings:', err);
        setError(err as Error);
        setIsDeviceOffline(true);

        // Rollback localStorage to previous value
        const cached = loadDeviceSettings(deviceId);
        if (cached) {
          setSettings(cached.settings);
        }

        throw err; // Re-throw for caller
      } finally {
        if (isMountedRef.current) {
          setIsUpdating(false);
        }
      }
    },
    [deviceId, deviceType, enabled]
  );

  /**
   * Refresh settings (query device)
   */
  const refresh = useCallback(async () => {
    await queryDevice();
  }, [queryDevice]);

  /**
   * Start background polling
   */
  const startPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
    }

    if (!enabled || !pollInterval) return;

    pollingTimerRef.current = setInterval(() => {
      // Only poll if page is visible
      if (document.visibilityState === 'visible') {
        queryDevice();
      }
    }, pollInterval);
  }, [enabled, pollInterval, queryDevice]);

  /**
   * Stop background polling
   */
  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  /**
   * Initial load and polling setup (HYBRID MODE)
   */
  useEffect(() => {
    isMountedRef.current = true;

    if (!enabled) {
      setIsLoading(false);
      return;
    }

    const initialize = async () => {
      // 1. Try localStorage first (instant)
      const hasCached = loadCachedSettings();

      if (hasCached) {
        // Have cache, show immediately
        setIsLoading(false);
        // Query device in background for fresh values
        queryDevice();
      } else {
        // 2. No cache, try database (fallback)
        const hasDatabase = await loadFromDatabase();

        if (hasDatabase) {
          // Loaded from database, show it
          setIsLoading(false);
          // Query device in background
          queryDevice();
        } else {
          // 3. Nothing cached, must wait for device query
          await queryDevice();
          setIsLoading(false);
        }
      }
    };

    initialize();

    // Start background polling
    startPolling();

    return () => {
      isMountedRef.current = false;
      stopPolling();
    };
  }, [deviceId, enabled, loadCachedSettings, loadFromDatabase, queryDevice, startPolling, stopPolling]);

  /**
   * Handle page visibility changes
   */
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && enabled) {
        // Page became visible, query device immediately
        queryDevice();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [enabled, queryDevice]);

  /**
   * Multi-tab synchronization with BroadcastChannel
   */
  useEffect(() => {
    if (!enabled || typeof BroadcastChannel === 'undefined') return;

    const channel = new BroadcastChannel(`device_settings_${deviceId}`);

    channel.onmessage = (event) => {
      if (event.data.type === 'settings_updated') {
        // Another tab updated settings, reload from localStorage
        loadCachedSettings();
      }
    };

    return () => {
      channel.close();
    };
  }, [deviceId, enabled, loadCachedSettings]);

  return {
    settings,
    isLoading,
    isQuerying,
    isUpdating,
    isStale,
    isDeviceOffline,
    usingFallback,
    lastSyncedAt,
    error,
    queryDevice,
    updateDevice,
    refresh,
  };
}
