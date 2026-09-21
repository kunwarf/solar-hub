/**
 * HomeScreen — 4 task cards + "All settings" tile + footer.
 *
 * The heavy lifting lives in SettingsScreen (state/orchestration).  This
 * component is a mostly-dumb view that reads draft/saved from props and
 * renders each homeCardId to its section renderer.
 */
import { createElement } from "react";
import { ChevronRight, Sliders as SlidersIcon, Cpu } from "lucide-react";
import type { DeviceProfile } from "../profiles/types";
import { TaskCard, ReadOnlyBanner, type Accent } from "../primitives";
import { StrategyRadioGroup, DynamicSliderCard, FieldsHomeCard, ScheduleWindowsCard } from "../cards";
import { checkSection, hasBlockingWarnings } from "../validation";

export interface HomeScreenProps {
  profile: DeviceProfile;
  strategyKey: string;
  draft: Record<string, any>;
  saved: Record<string, any>;
  patch: (patch: Record<string, any>) => void;
  pending: Record<string, "apply" | "reset" | null>;
  isSectionDirty: (sectionId: string) => boolean;
  applyCard: (sectionId: string) => void;
  resetCard: (sectionId: string) => void;
  requestConfirm: (label: string, apply: () => void) => void;
  onOpenHub: () => void;
  deviceName: string;
  serial: string;
  syncedLabel: string;
  isOffline: boolean;
  headerRight?: React.ReactNode;
  readOnly?: boolean;
  readOnlyReason?: string;
  anyHubDirty: boolean;
}

/** Extract a section's field values from the flat draft dict. */
function pickSectionValues(fieldKeys: string[], draft: Record<string, any>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const k of fieldKeys) out[k] = draft[k];
  return out;
}

export function HomeScreen({
  profile,
  strategyKey,
  draft,
  saved,
  patch,
  pending,
  isSectionDirty,
  applyCard,
  resetCard,
  requestConfirm,
  onOpenHub,
  deviceName,
  serial,
  syncedLabel,
  isOffline,
  headerRight,
  readOnly,
  readOnlyReason,
  anyHubDirty,
}: HomeScreenProps) {
  const strategyPreview = profile.strategyPreview[draft[strategyKey]] || "";

  return (
    <div className="min-h-screen pb-16">
      <header
        className="sticky top-0 z-10 backdrop-blur bg-zinc-50/85 dark:bg-zinc-950/85 border-b border-zinc-200 dark:border-zinc-800"
        style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
      >
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between gap-3">
          <div className="min-w-0 flex items-center gap-2.5">
            <div className="flex shrink-0 rounded-lg bg-zinc-100 dark:bg-zinc-800 p-1.5 text-zinc-500 dark:text-zinc-400">
              <Cpu className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <h1 className="text-[15px] font-semibold leading-tight truncate">
                  {deviceName}
                </h1>
              </div>
              <p className="text-[12px] font-mono text-zinc-500 dark:text-zinc-400 truncate">
                {serial}
              </p>
            </div>
          </div>

          <div
            className={`hidden sm:flex items-center gap-1.5 text-[12.5px] px-3 py-1 rounded-full shrink-0 ${
              isOffline
                ? "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900"
                : "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isOffline ? "bg-amber-500" : "bg-emerald-500"
              }`}
            />
            {isOffline ? "Offline — cached" : `Synced ${syncedLabel}`}
          </div>

          {headerRight}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-5">
        {readOnly && (
          <ReadOnlyBanner
            reason={readOnlyReason || "Your role doesn't allow editing settings."}
          />
        )}
        {profile.sourceNote && (
          <p className="text-[12px] text-zinc-400 dark:text-zinc-500 -mb-1">
            {profile.sourceNote}
          </p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
          {profile.homeCardIds.map((id) => {
            const span = (profile.spanCardIds || []).includes(id);
            const wrap = (el: React.ReactNode) =>
              span ? (
                <div key={id} className="md:col-span-2">
                  {el}
                </div>
              ) : (
                el
              );

            // Strategy card is synthetic (not in profile.sections)
            if (id === "strategy") {
              const dirty = isSectionDirty("strategy");
              const accent: Accent = dirty ? "tuned" : "safe";
              return wrap(
                <TaskCard
                  key={span ? undefined : "strategy"}
                  icon={createElement(SlidersIcon, { className: "w-5 h-5" })}
                  title="Energy strategy"
                  description="How your inverter balances solar, battery, and grid"
                  accent={accent}
                  dirty={dirty}
                  pending={pending.strategy ?? null}
                  onApply={() => applyCard("strategy")}
                  onReset={() => resetCard("strategy")}
                  readOnly={readOnly}
                  preview={strategyPreview}
                >
                  <StrategyRadioGroup
                    options={profile.strategies}
                    value={draft[strategyKey] ?? profile.defaults.strategy}
                    onChange={(v) => patch({ [strategyKey]: v })}
                    disabled={readOnly}
                  />
                </TaskCard>,
              );
            }

            const section = profile.sections[id];
            if (!section) return null;

            const fieldKeys =
              section.kind === "schedule"
                ? [section.toggleField.key]
                : section.fields.map((f) => f.key);
            const values = pickSectionValues(fieldKeys, draft);
            const dirty = isSectionDirty(id);
            const warnings = checkSection(id, values);
            const blocked = hasBlockingWarnings(id, values);
            const accent: Accent = blocked ? "destructive" : dirty ? "tuned" : "safe";
            const commonProps = {
              icon: section.icon,
              title: section.title,
              description: section.description,
              accent,
              dirty,
              pending: pending[id] ?? null,
              onApply: () => {
                if (!blocked) applyCard(id);
              },
              onReset: () => resetCard(id),
              readOnly,
            };

            if (section.kind === "slider") {
              return wrap(
                <DynamicSliderCard
                  key={span ? undefined : id}
                  {...commonProps}
                  section={section}
                  values={values}
                  onPatch={(k, v) => patch({ [k]: v })}
                  warnings={warnings}
                />,
              );
            }
            if (section.kind === "schedule") {
              // Schedule handling on Home is not in scope for Iteration 1
              // (Senergy has no TOU section in the profile).
              return null;
            }
            return wrap(
              <FieldsHomeCard
                key={span ? undefined : id}
                {...commonProps}
                section={section}
                values={values}
                patch={(k, v) => patch({ [k]: v })}
                requestConfirm={requestConfirm}
              />,
            );
          })}
        </div>

        {profile.hubGroupIds.length > 0 && (
          <button
            onClick={onOpenHub}
            className="flex items-center justify-between gap-3 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-sm hover:shadow-md transition-shadow px-5 py-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-zinc-100 dark:bg-zinc-800 p-2 text-zinc-700 dark:text-zinc-300">
                <SlidersIcon className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-[14.5px] font-semibold leading-tight">All settings</p>
                  {anyHubDirty && (
                    <span
                      className="w-1.5 h-1.5 rounded-full bg-amber-500"
                      title="Unsaved changes in an advanced section"
                    />
                  )}
                </div>
                <p className="text-[12.5px] text-zinc-500 dark:text-zinc-400 mt-0.5">
                  Battery details, thresholds, protection, and installer settings live here
                  {anyHubDirty && (
                    <span className="text-amber-600 dark:text-amber-400">
                      {" "}
                      · unsaved changes
                    </span>
                  )}
                </p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-zinc-300 dark:text-zinc-600 shrink-0" />
          </button>
        )}
      </main>
    </div>
  );
}
