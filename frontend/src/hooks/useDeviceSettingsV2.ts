/**
 * useDeviceSettingsV2 — lazy per-key device-settings hook for the v2
 * settings UI (frontend/src/components/settings/v2).
 *
 * Why a new hook instead of extending useDeviceSettings:
 * - Existing hook always queries ALL configurable registers (~50 on
 *   Senergy).  The whole point of v2 is to fetch only what a screen
 *   actually needs.
 * - Existing hook has a lot of legacy behavior (localStorage cache with
 *   staleness, database fallback stubs, background polling, visibility
 *   handlers) that the v2 UI doesn't want.  Simpler to keep them apart.
 *
 * Contract:
 * - `settings`      : accumulating partial dict — grows as fetch(keys)
 *                     resolves.  Keys not yet fetched are absent.
 * - `loadedKeys`    : Set of keys with confirmed data
 * - `inFlightKeys`  : Set of keys currently being fetched (for spinners)
 * - `fetch(keys[])` : Promise-returning.  Filters to keys not already
 *                     loaded and not in flight, then issues ONE
 *                     querySettings command with that subset.  If all
 *                     keys are already loaded, resolves immediately.
 * - `update(patch)` : Sends updateSettings with just the patch keys,
 *                     waits for completion, merges into `settings`.
 * - `refresh()`     : Re-fetch every key currently in loadedKeys.
 */
import { useCallback, useRef, useState } from "react";
import { deviceCommandsService } from "@/api";

export interface UseDeviceSettingsV2Options {
  deviceId: string;
}

export interface UseDeviceSettingsV2Return {
  settings: Record<string, any>;
  loadedKeys: Set<string>;
  inFlightKeys: Set<string>;
  isOffline: boolean;
  isUpdating: boolean;
  lastSyncedAt: string | null;
  error: Error | null;
  /** Fetch the given keys.  Deduplicates against already-loaded and
   *  in-flight sets.  Resolves once the underlying command completes. */
  fetch: (keys: string[], opts?: { forceRefresh?: boolean }) => Promise<void>;
  /** Write the given patch to the device.  Merges into `settings` on
   *  success. Throws on failure so callers can toast. */
  update: (patch: Record<string, any>) => Promise<void>;
  /** Re-fetch every key currently in loadedKeys. */
  refresh: () => Promise<void>;
}

export function useDeviceSettingsV2(
  options: UseDeviceSettingsV2Options,
): UseDeviceSettingsV2Return {
  const { deviceId } = options;

  const [settings, setSettings] = useState<Record<string, any>>({});
  const [loadedKeys, setLoadedKeys] = useState<Set<string>>(new Set());
  const [inFlightKeys, setInFlightKeys] = useState<Set<string>>(new Set());
  const [isOffline, setIsOffline] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);

  // Refs mirror state so the async fetch/update closures observe the
  // latest values without forcing the callbacks to be re-created on
  // every state change.  Without this, `fetch` would re-generate every
  // time settings changes, breaking any useEffect that has fetch in its
  // deps.
  const loadedRef = useRef<Set<string>>(new Set());
  const inFlightRef = useRef<Set<string>>(new Set());

  const fetch = useCallback(
    async (keys: string[], opts?: { forceRefresh?: boolean }) => {
      const forceRefresh = opts?.forceRefresh ?? false;
      const needed = forceRefresh
        ? keys
        : keys.filter((k) => !loadedRef.current.has(k) && !inFlightRef.current.has(k));
      if (needed.length === 0) return;

      // Mark in-flight both in ref and in state
      needed.forEach((k) => inFlightRef.current.add(k));
      setInFlightKeys(new Set(inFlightRef.current));

      try {
        const resp = await deviceCommandsService.querySettings(deviceId, needed);
        // 90s timeout — same as the legacy hook, generous for slow RTU chains
        const status = await deviceCommandsService.waitForCommand(
          deviceId,
          resp.command_id,
          90_000,
          2_000,
        );

        if (status.status === "completed" && status.result?.settings) {
          const returned = status.result.settings as Record<string, any>;
          setSettings((prev) => ({ ...prev, ...returned }));
          Object.keys(returned).forEach((k) => loadedRef.current.add(k));
          setLoadedKeys(new Set(loadedRef.current));
          setLastSyncedAt(new Date().toISOString());
          setIsOffline(false);
          setError(null);
        } else {
          // Failed / timeout / empty result — flag offline but leave
          // cached values alone.  Same reasoning as the legacy hook.
          setIsOffline(true);
          const errMsg =
            status.error || `Device query returned ${status.status} with no data`;
          setError(new Error(errMsg));
        }
      } catch (e) {
        setIsOffline(true);
        setError(e as Error);
      } finally {
        needed.forEach((k) => inFlightRef.current.delete(k));
        setInFlightKeys(new Set(inFlightRef.current));
      }
    },
    [deviceId],
  );

  const update = useCallback(
    async (patch: Record<string, any>) => {
      setIsUpdating(true);
      setError(null);
      try {
        const resp = await deviceCommandsService.updateSettings(deviceId, patch, true);
        const status = await deviceCommandsService.waitForCommand(
          deviceId,
          resp.command_id,
          30_000,
          2_000,
        );
        if (status.status !== "completed") {
          throw new Error(status.error || `Update returned status=${status.status}`);
        }
        setSettings((prev) => ({ ...prev, ...patch }));
        Object.keys(patch).forEach((k) => loadedRef.current.add(k));
        setLoadedKeys(new Set(loadedRef.current));
        setLastSyncedAt(new Date().toISOString());
        setIsOffline(false);
      } catch (e) {
        setError(e as Error);
        // Don't flip isOffline on update failure — a write can fail while
        // reads still work.  Caller will toast; keep the UI usable.
        throw e;
      } finally {
        setIsUpdating(false);
      }
    },
    [deviceId],
  );

  const refresh = useCallback(async () => {
    const all = Array.from(loadedRef.current);
    if (all.length === 0) return;
    await fetch(all, { forceRefresh: true });
  }, [fetch]);

  return {
    settings,
    loadedKeys,
    inFlightKeys,
    isOffline,
    isUpdating,
    lastSyncedAt,
    error,
    fetch,
    update,
    refresh,
  };
}
