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
  const initializedRef = useRef(false);

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
      console.log('[useDeviceSettings] Starting query for device:', deviceId);
      const response = await deviceCommandsService.querySettings(deviceId);
      console.log('[useDeviceSettings] Command created:', response.command_id, 'status:', response.status);

      // Poll command status until complete
      console.log('[useDeviceSettings] Polling for command completion...');
      const status = await deviceCommandsService.waitForCommand(
        deviceId,
        response.command_id,
        30000, // 30s timeout
        2000  // 2s poll interval
      );

      console.log('[useDeviceSettings] Command completed with status:', status.status);
      console.log('[useDeviceSettings] Has result?', !!status.result);
      console.log('[useDeviceSettings] Has settings?', !!status.result?.settings);
      if (status.result?.settings) {
        console.log('[useDeviceSettings] Settings keys:', Object.keys(status.result.settings).length);
      }

      if (status.status === 'completed' && status.result?.settings) {
        const deviceSettings = status.result.settings;
        console.log('[useDeviceSettings] SUCCESS! Got settings:', Object.keys(deviceSettings).slice(0, 10));

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
        console.log('[useDeviceSettings] State updated successfully');
      } else if (status.status === 'failed') {
        console.error('[useDeviceSettings] Command failed:', status.error);
        throw new Error(status.error || 'Device query failed');
      } else {
        console.error('[useDeviceSettings] Command timed out or invalid status:', status.status);
        throw new Error('Device query timed out');
      }
    } catch (err) {
      console.error('[useDeviceSettings] CATCH BLOCK - Error occurred:', err);
      console.error('[useDeviceSettings] Error type:', err instanceof Error ? err.constructor.name : typeof err);
      console.error('[useDeviceSettings] Error message:', err instanceof Error ? err.message : String(err));
      setError(err as Error);
      setIsStale(true);
      setIsDeviceOffline(true);

      // Mark cached settings as stale
      markSettingsAsStale(deviceId);

      // FALLBACK: Try loading from database
      console.log('[useDeviceSettings] Attempting database fallback...');
      const fallbackLoaded = await loadFromDatabase();
      if (!fallbackLoaded) {
        console.warn('[useDeviceSettings] No fallback settings available in database');
      } else {
        console.log('[useDeviceSettings] Loaded from database fallback');
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
   * Reset initialization flag when deviceId changes
   */
  useEffect(() => {
    initializedRef.current = false;
  }, [deviceId]);

  /**
   * Initial load and polling setup (HYBRID MODE)
   */
  useEffect(() => {
    isMountedRef.current = true;

    if (!enabled) {
      setIsLoading(false);
      return;
    }

    // Only initialize once per deviceId
    if (initializedRef.current) {
      return;
    }

    initializedRef.current = true;

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId, enabled]);

  /**
   * Handle page visibility changes
   */
  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // Page became visible, query device immediately
        queryDevice();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId, enabled]);

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
