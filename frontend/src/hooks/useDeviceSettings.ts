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
   * Query device for current settings (PRIMARY PATH).
   *
   * We retry once on an "empty-success" response — the backend historically
   * returned ``success: true, settings: {}`` when every Modbus register read
   * failed transiently (RS485 collision, adapter offline mid-command). The
   * backend is being fixed to report those as ``success: false`` (Fix A), but
   * this client-side retry stays as a cushion for older workers still in the
   * fleet and for genuinely marginal links.
   */
  const queryDevice = useCallback(async () => {
    if (!enabled) return;

    setIsQuerying(true);
    setError(null);

    const MAX_ATTEMPTS = 2;
    const RETRY_DELAY_MS = 2000;

    try {
      let deviceSettings: Record<string, any> | null = null;
      let lastError: string | undefined;

      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        console.log(`[useDeviceSettings] Query attempt ${attempt}/${MAX_ATTEMPTS} for device:`, deviceId);
        const response = await deviceCommandsService.querySettings(deviceId);
        console.log('[useDeviceSettings] Command created:', response.command_id, 'status:', response.status);

        console.log('[useDeviceSettings] Polling for command completion...');
        // Settings queries can legitimately take 60+ seconds on a healthy but
        // slow Modbus RTU chain (ESP32 uplink + 80–90 register reads). Give
        // the roundtrip real headroom; the UI shows cached settings from
        // localStorage immediately so this doesn't block the user's view.
        const status = await deviceCommandsService.waitForCommand(
          deviceId,
          response.command_id,
          90000, // 90s timeout (was 30s — too tight for Powdrive Modbus RTU)
          2000,  // 2s poll interval
        );

        console.log('[useDeviceSettings] Command completed with status:', status.status);
        const settings = status.result?.settings;
        const keyCount = settings ? Object.keys(settings).length : 0;
        console.log('[useDeviceSettings] Settings keys:', keyCount);

        if (status.status === 'completed' && settings && keyCount > 0) {
          deviceSettings = settings;
          break;
        }

        if (status.status === 'completed' && keyCount === 0 && attempt < MAX_ATTEMPTS) {
          // Empty-success: probably a transient Modbus failure. Wait briefly
          // and try one more time before giving up.
          console.warn('[useDeviceSettings] success=true but 0 settings — retrying in %dms', RETRY_DELAY_MS);
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
          continue;
        }

        if (status.status === 'failed') {
          console.error('[useDeviceSettings] Command failed:', status.error);
          lastError = status.error || 'Device query failed';
          if (attempt < MAX_ATTEMPTS) {
            await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
            continue;
          }
          throw new Error(lastError);
        }

        if (status.status !== 'completed') {
          console.error('[useDeviceSettings] Command timed out or invalid status:', status.status);
          throw new Error('Device query timed out');
        }

        // Fell through: completed with 0 keys after all retries — accept the
        // empty result so the UI doesn't spin forever, but flag it as stale.
        console.warn('[useDeviceSettings] Accepting empty settings after %d attempts', MAX_ATTEMPTS);
        deviceSettings = settings ?? {};
        break;
      }

      if (deviceSettings === null) {
        throw new Error(lastError || 'Device query failed');
      }

      console.log('[useDeviceSettings] SUCCESS! Got settings:', Object.keys(deviceSettings).slice(0, 10));

      // Update localStorage cache
      updateSettingsFromDevice(deviceId, deviceType, deviceSettings);

      // Database backup removed - settings now live on device only
      // localStorage provides caching, device commands provide authoritative source

      // Update state
      setSettings(deviceSettings);
      setIsStale(Object.keys(deviceSettings).length === 0);
      setIsDeviceOffline(false);
      setUsingFallback(false);
      setLastSyncedAt(new Date().toISOString());
      setError(null);
      console.log('[useDeviceSettings] State updated successfully');
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, pollInterval]);

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

    // Always set up cleanup, even if we return early
    const cleanup = () => {
      isMountedRef.current = false;
      stopPolling();
    };

    if (!enabled) {
      setIsLoading(false);
      return cleanup;
    }

    // Only initialize once per deviceId
    if (initializedRef.current) {
      return cleanup;
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

    return cleanup;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId, enabled]);

  /**
   * Handle page visibility changes
   * DISABLED: Automatic query on visibility change was causing unwanted refreshes
   * User can manually refresh using the "Refresh from Device" button
   */
  // useEffect(() => {
  //   if (!enabled) return;

  //   const handleVisibilityChange = () => {
  //     if (document.visibilityState === 'visible') {
  //       // Page became visible, query device immediately
  //       queryDevice();
  //     }
  //   };

  //   document.addEventListener('visibilitychange', handleVisibilityChange);

  //   return () => {
  //     document.removeEventListener('visibilitychange', handleVisibilityChange);
  //   };
  //   // eslint-disable-next-line react-hooks/exhaustive-deps
  // }, [enabled]);

  /**
   * Multi-tab synchronization with BroadcastChannel
   * DISABLED: Was causing unwanted refreshes when multiple tabs were open
   * User can manually refresh if needed
   */
  // useEffect(() => {
  //   if (!enabled || typeof BroadcastChannel === 'undefined') return;

  //   const channel = new BroadcastChannel(`device_settings_${deviceId}`);

  //   channel.onmessage = (event) => {
  //     if (event.data.type === 'settings_updated') {
  //       // Another tab updated settings, reload from localStorage
  //       loadCachedSettings();
  //     }
  //   };

  //   return () => {
  //     channel.close();
  //   };
  //   // eslint-disable-next-line react-hooks/exhaustive-deps
  // }, [deviceId, enabled]);

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
