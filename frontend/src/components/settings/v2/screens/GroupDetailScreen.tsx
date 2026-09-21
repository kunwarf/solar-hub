/**
 * GroupDetailScreen — one settings group's fields, mounted on demand.
 *
 * When mounted, SettingsScreen triggers fetch(group.field keys) so the
 * data arrives just-in-time.  Fields render as flat SchemaField rows.
 * Installer-tier sections show a red Alert banner at the top.  Cross-
 * field warnings render above the field list as summary lines.
 */
import type { DeviceProfile } from "../profiles/types";
import { Alert, Button, ScreenHeader } from "../primitives";
import { SchemaField } from "../fields";
import { checkSection } from "../validation";

function countLabel(section: any): string {
  if (section.kind === "schedule") {
    return `${section.windowCount} window${section.windowCount === 1 ? "" : "s"}`;
  }
  return `${section.fields.length} setting${section.fields.length === 1 ? "" : "s"}`;
}

export function GroupDetailScreen({
  profile,
  sectionId,
  draft,
  saved,
  patch,
  pending,
  dirty,
  applyCard,
  resetCard,
  requestConfirm,
  onBack,
  readOnly,
}: {
  profile: DeviceProfile;
  sectionId: string;
  draft: Record<string, any>;
  saved: Record<string, any>;
  patch: (patch: Record<string, any>) => void;
  pending: "apply" | "reset" | null;
  dirty: boolean;
  applyCard: () => void;
  resetCard: () => void;
  requestConfirm: (label: string, apply: () => void) => void;
  onBack: () => void;
  readOnly?: boolean;
}) {
  const section = profile.sections[sectionId];
  if (!section) return null;

  const isInstaller = section.tier === "installer";
  const isVisible = (f: any) =>
    !f.showIf || draft[f.showIf.key] === f.showIf.equals;

  const sectionValues =
    section.kind === "schedule"
      ? { [section.toggleField.key]: draft[section.toggleField.key] }
      : Object.fromEntries(section.fields.map((f) => [f.key, draft[f.key]]));
  const warnings = checkSection(sectionId, sectionValues);

  return (
    <div className="min-h-screen pb-16">
      <ScreenHeader onBack={onBack} title={section.title} subtitle={countLabel(section)} />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-4">
        {isInstaller && (
          <Alert>
            These settings are configured by your installer to match local grid
            regulations. Changing them may cause the inverter to disconnect from the
            grid or violate local rules. Only edit if you know what you're doing.
          </Alert>
        )}

        {warnings.length > 0 && (
          <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-300 px-4 py-3 text-[13px] space-y-1">
            {warnings.map((w, i) => (
              <p key={i}>⚠ {w.message}</p>
            ))}
          </div>
        )}

        {section.kind === "schedule" ? (
          <div className="rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 px-5">
            <SchemaField
              field={section.toggleField}
              value={draft[section.toggleField.key]}
              onChange={(v) => patch({ [section.toggleField.key]: v })}
              requestConfirm={requestConfirm}
              disabled={readOnly}
            />
          </div>
        ) : (
          <div className="rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 px-5">
            {section.fields.filter(isVisible).map((f) => (
              <SchemaField
                key={f.key}
                field={f}
                value={draft[f.key]}
                onChange={(v) => patch({ [f.key]: v })}
                requestConfirm={requestConfirm}
                disabled={readOnly}
              />
            ))}
          </div>
        )}

        {!readOnly && (
          <div
            className={`flex items-center gap-2 overflow-hidden transition-all duration-200 ${
              dirty ? "max-h-16 opacity-100" : "max-h-0 opacity-0"
            }`}
          >
            <Button
              variant={isInstaller ? "destructive" : "primary"}
              onClick={applyCard}
              pending={pending === "apply"}
              disabled={warnings.length > 0}
            >
              Apply
            </Button>
            <Button variant="ghost" onClick={resetCard} pending={pending === "reset"}>
              Reset
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
