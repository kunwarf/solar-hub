/**
 * SettingsScreen — top-level router + state orchestrator for the v2
 * settings UI.
 *
 * Manages:
 * - Screen navigation: "home" | "hub" | <sectionId>
 * - draft vs saved (flat, keyed by field key)
 * - Section-scoped Apply/Reset/dirty
 * - Confirm modal state for destructive fields
 * - Fetch coordination (Home mounts fetch union of home-card keys, each
 *   Group Detail mounts fetch its own subset)
 * - Undo toast after successful Apply
 *
 * The three sub-screens are dumb-ish views that receive props and call
 * back up here.  All state lives at this level.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { RefreshCw } from "lucide-react";
import { Button } from "./primitives";
import { ConfirmModal } from "./ConfirmModal";
import { HomeScreen } from "./screens/HomeScreen";
import { SettingsHub } from "./screens/SettingsHub";
import { GroupDetailScreen } from "./screens/GroupDetailScreen";
import { useDeviceSettingsV2 } from "@/hooks/useDeviceSettingsV2";
import { resolveProfile } from "./profiles";
import type { DeviceProfile, Section, ScreenId } from "./profiles/types";

const clone = <T,>(o: T): T => JSON.parse(JSON.stringify(o));
const eq = (a: any, b: any) => JSON.stringify(a) === JSON.stringify(b);

/** Every profile field lives under a section id key on the backend
 *  register map (well, ~effectively — the schema keys are what matter).
 *  This helper returns the union of field keys for the given section. */
function sectionFieldKeys(section: Section): string[] {
  if (section.kind === "schedule") {
    // TOU sections read the toggle + all window fields.  Windows are
    // arrays on saved; we treat each window field as a base name that
    // the backend must implement — Iteration 2 concern for Powdrive.
    // For now, just the toggle field.
    return [section.toggleField.key];
  }
  return section.fields.map((f) => f.key);
}

/** Field keys used on Home (union of all homeCardIds sections' fields,
 *  plus the strategy key which lives on the profile). */
function homeFieldKeys(profile: DeviceProfile, strategyKey: string): string[] {
  const keys = new Set<string>([strategyKey]);
  for (const id of profile.homeCardIds) {
    if (id === "strategy") continue;
    const section = profile.sections[id];
    if (!section) continue;
    sectionFieldKeys(section).forEach((k) => keys.add(k));
  }
  return Array.from(keys);
}

export interface SettingsScreenProps {
  deviceId: string;
  /** The device's serial number — used in the destructive-confirm modal. */
  serial: string;
  /** device.protocol — resolves to a DeviceProfile via the registry. */
  protocol: string;
  /** device.manufacturer + model, shown in the header. */
  deviceName?: string;
  /** If true, all controls disabled + Apply/Reset hidden.  Set by the
   *  parent based on the current user's role. */
  readOnly?: boolean;
  readOnlyReason?: string;
}

/** Which register id is the "energy strategy" for this profile.
 *  Must match the exact register-map id so writes/reads land on the
 *  right register:
 *   - senergy   → hybrid_work_mode  (reg 8448, 5-value enum)
 *   - powdrive  → solar_priority    (Battery First / Load First)
 *   - voltronic → set_output_priority (serial command POPxx) */
function strategyKeyForProfile(profile: DeviceProfile): string {
  switch (profile.id) {
    case "senergy":
      return "hybrid_work_mode";
    case "powdrive":
      return "solar_priority";
    case "voltronic":
      return "set_output_priority";
    default:
      return "hybrid_work_mode";
  }
}

export function SettingsScreen({
  deviceId,
  serial,
  protocol,
  deviceName,
  readOnly,
  readOnlyReason,
}: SettingsScreenProps) {
  const profile = resolveProfile(protocol);
  // Always call hooks unconditionally — bail-out UI happens at the bottom
  // via a conditional render.
  const strategyKey = profile ? strategyKeyForProfile(profile) : "work_mode";
  const hook = useDeviceSettingsV2({ deviceId });
  const { settings, fetch, update, refresh, isOffline, lastSyncedAt } = hook;

  // draft is flat, keyed by field key, initialized empty and populated
  // from saved (hook.settings) as data comes in.  When the user hasn't
  // edited a field, we mirror saved into draft on every settings change.
  const [draft, setDraft] = useState<Record<string, any>>({});
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set());

  // Sync draft <- saved for keys the user hasn't touched.
  useEffect(() => {
    setDraft((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const [k, v] of Object.entries(settings)) {
        if (dirtyKeys.has(k)) continue;
        if (!eq(next[k], v)) {
          next[k] = clone(v);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [settings, dirtyKeys]);

  // Fetch home keys on mount.
  const homeKeysRef = useRef<string[]>([]);
  useEffect(() => {
    if (!profile) return;
    homeKeysRef.current = homeFieldKeys(profile, strategyKey);
    fetch(homeKeysRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.id, deviceId]);

  const [screen, setScreen] = useState<ScreenId>("home");
  const [pending, setPending] = useState<
    Record<string, "apply" | "reset" | null>
  >({});
  const [confirming, setConfirming] = useState<{
    label: string;
    apply: () => void;
  } | null>(null);

  const patch = useCallback((keys: Record<string, any>) => {
    setDraft((prev) => ({ ...prev, ...keys }));
    setDirtyKeys((prev) => {
      const next = new Set(prev);
      for (const k of Object.keys(keys)) next.add(k);
      return next;
    });
  }, []);

  /** Compute which keys are dirty for a section (draft differs from saved). */
  const isSectionDirty = useCallback(
    (sectionId: string): boolean => {
      if (sectionId === "strategy") {
        return draft[strategyKey] != null && draft[strategyKey] !== settings[strategyKey];
      }
      const section = profile.sections[sectionId];
      if (!section) return false;
      return sectionFieldKeys(section).some(
        (k) => draft[k] !== undefined && !eq(draft[k], settings[k]),
      );
    },
    [profile, strategyKey, draft, settings],
  );

  /** Diff between draft and saved for the section — the patch to send. */
  const sectionPatch = useCallback(
    (sectionId: string): Record<string, any> => {
      const out: Record<string, any> = {};
      if (sectionId === "strategy") {
        if (draft[strategyKey] !== settings[strategyKey]) {
          out[strategyKey] = draft[strategyKey];
        }
        return out;
      }
      const section = profile.sections[sectionId];
      if (!section) return out;
      for (const key of sectionFieldKeys(section)) {
        if (draft[key] !== undefined && !eq(draft[key], settings[key])) {
          out[key] = draft[key];
        }
      }
      return out;
    },
    [profile, strategyKey, draft, settings],
  );

  const applyCard = useCallback(
    async (sectionId: string) => {
      const patchDict = sectionPatch(sectionId);
      if (Object.keys(patchDict).length === 0) return;

      // Capture the pre-apply values so Undo can restore them.
      const preApply: Record<string, any> = {};
      for (const k of Object.keys(patchDict)) preApply[k] = settings[k];

      setPending((p) => ({ ...p, [sectionId]: "apply" }));
      try {
        await update(patchDict);
        // Clear dirty flags for the applied keys
        setDirtyKeys((prev) => {
          const next = new Set(prev);
          Object.keys(patchDict).forEach((k) => next.delete(k));
          return next;
        });
        // Undo toast — 10s to reverse the write
        toast.success("Applied", {
          description: "Reverting is possible for the next 10 seconds.",
          duration: 10_000,
          action: {
            label: "Undo",
            onClick: async () => {
              try {
                await update(preApply);
                toast.info("Reverted to previous values");
              } catch (e) {
                toast.error(
                  `Undo failed: ${e instanceof Error ? e.message : String(e)}`,
                );
              }
            },
          },
        });
      } catch (e) {
        toast.error(
          `Apply failed: ${e instanceof Error ? e.message : String(e)}`,
        );
      } finally {
        setPending((p) => ({ ...p, [sectionId]: null }));
      }
    },
    [sectionPatch, update, settings],
  );

  const resetCard = useCallback(
    (sectionId: string) => {
      setPending((p) => ({ ...p, [sectionId]: "reset" }));
      // Rewind draft slice back to saved
      setDraft((prev) => {
        const next = { ...prev };
        const keys =
          sectionId === "strategy"
            ? [strategyKey]
            : sectionFieldKeys(profile.sections[sectionId] || ({ kind: "fields", fields: [] } as any));
        for (const k of keys) next[k] = clone(settings[k]);
        return next;
      });
      setDirtyKeys((prev) => {
        const next = new Set(prev);
        const keys =
          sectionId === "strategy"
            ? [strategyKey]
            : sectionFieldKeys(profile.sections[sectionId] || ({ kind: "fields", fields: [] } as any));
        for (const k of keys) next.delete(k);
        return next;
      });
      setTimeout(() => setPending((p) => ({ ...p, [sectionId]: null })), 200);
    },
    [profile, strategyKey, settings],
  );

  const requestConfirm = useCallback(
    (label: string, apply: () => void) => setConfirming({ label, apply }),
    [],
  );

  // Group Detail: fetch on open if needed.
  useEffect(() => {
    if (!profile) return;
    if (screen === "home" || screen === "hub") return;
    const section = profile.sections[screen];
    if (!section) return;
    fetch(sectionFieldKeys(section));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen]);

  const anyHubDirty = useMemo(
    () => (profile ? profile.hubGroupIds.some(isSectionDirty) : false),
    [profile, isSectionDirty],
  );

  if (!profile) {
    return (
      <div className="p-6 text-sm text-zinc-500">
        No settings profile available for protocol <code>{protocol}</code>.
      </div>
    );
  }

  const syncedLabel = lastSyncedAt
    ? new Date(lastSyncedAt).toLocaleTimeString()
    : "Not yet synced";

  const header = (
    <div className="flex items-center gap-1.5 shrink-0">
      <Button variant="outline" onClick={refresh} pending={hook.inFlightKeys.size > 0}>
        {hook.inFlightKeys.size === 0 && <RefreshCw className="w-3.5 h-3.5" />}
        Refresh
      </Button>
    </div>
  );

  return (
    <>
      {screen === "home" && (
        <HomeScreen
          profile={profile}
          strategyKey={strategyKey}
          draft={draft}
          saved={settings}
          patch={patch}
          pending={pending}
          isSectionDirty={isSectionDirty}
          applyCard={applyCard}
          resetCard={resetCard}
          requestConfirm={requestConfirm}
          onOpenHub={() => setScreen("hub")}
          deviceName={deviceName || profile.name}
          serial={serial}
          syncedLabel={syncedLabel}
          isOffline={isOffline}
          headerRight={header}
          readOnly={readOnly}
          readOnlyReason={readOnlyReason}
          anyHubDirty={anyHubDirty}
        />
      )}
      {screen === "hub" && (
        <SettingsHub
          profile={profile}
          isSectionDirty={isSectionDirty}
          onOpenGroup={(id) => setScreen(id)}
          onBack={() => setScreen("home")}
        />
      )}
      {screen !== "home" &&
        screen !== "hub" &&
        profile.sections[screen] && (
          <GroupDetailScreen
            profile={profile}
            sectionId={screen}
            draft={draft}
            saved={settings}
            patch={patch}
            pending={pending[screen] ?? null}
            dirty={isSectionDirty(screen)}
            applyCard={() => applyCard(screen)}
            resetCard={() => resetCard(screen)}
            requestConfirm={requestConfirm}
            onBack={() => setScreen("hub")}
            readOnly={readOnly}
          />
        )}
      {confirming && (
        <ConfirmModal
          fieldLabel={confirming.label}
          serial={serial}
          onCancel={() => setConfirming(null)}
          onConfirm={() => {
            confirming.apply();
            setConfirming(null);
          }}
        />
      )}
    </>
  );
}
