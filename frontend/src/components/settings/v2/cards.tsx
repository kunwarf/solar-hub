/**
 * Card body renderers — the three "kind"s of section content that go
 * inside a TaskCard: strategy radio, slider group, flat field list, and
 * TOU schedule windows.
 *
 * Ported from D:\Downloads\solar-inverter-settings.html, adapted to
 * TypeScript and lucide-react.  Cross-field validation output is rendered
 * inline under the offending slider (or at the section top when the
 * warning has no specific key).
 */
import type { ReactNode } from "react";
import type { Section, SliderField, StrategyOption, WindowField, ScheduleWindow } from "./profiles/types";
import { SafeZoneSlider } from "./SafeZoneSlider";
import { SchemaField, NumberField, TimeField } from "./fields";
import { Switch, TaskCard, type Accent } from "./primitives";
import type { CrossFieldWarning } from "./validation";

/* ------------------------------------------------------------------ */
/* Strategy radio                                                      */
/* ------------------------------------------------------------------ */

export function StrategyRadioGroup({
  options,
  value,
  onChange,
  disabled,
}: {
  options: StrategyOption[];
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <div role="radiogroup" aria-label="Energy strategy" className="flex flex-col gap-1.5">
      {options.map((opt) => {
        const selected = value === opt.id;
        const OptIcon = opt.icon;
        return (
          <label
            key={opt.id}
            className={`flex items-start gap-3 rounded-xl px-3 py-2.5 border transition-colors ${
              disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
            } ${
              selected
                ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                : "border-transparent hover:bg-zinc-50 dark:hover:bg-zinc-800/60"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              className="sr-only"
              checked={selected}
              disabled={disabled}
              onChange={() => onChange(opt.id)}
            />
            <span
              className={`mt-0.5 w-4 h-4 rounded-full border-2 shrink-0 flex items-center justify-center ${
                selected ? "border-blue-600" : "border-zinc-300 dark:border-zinc-600"
              }`}
            >
              {selected && <span className="w-2 h-2 rounded-full bg-blue-600" />}
            </span>
            <OptIcon className="w-4 h-4 mt-0.5 text-zinc-500 dark:text-zinc-400 shrink-0" />
            <span>
              <span className="text-sm font-medium block leading-tight">{opt.label}</span>
              <span className="text-[12.5px] text-zinc-500 dark:text-zinc-400">{opt.blurb}</span>
            </span>
          </label>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Inline warning line                                                 */
/* ------------------------------------------------------------------ */

function WarningLine({ text }: { text: string }) {
  return (
    <p className="text-[12px] text-amber-600 dark:text-amber-400 -mt-2">
      ⚠ {text}
    </p>
  );
}

/* ------------------------------------------------------------------ */
/* Slider card                                                         */
/* ------------------------------------------------------------------ */

export interface DynamicSliderCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  section: Extract<Section, { kind: "slider" }>;
  values: Record<string, any>;
  onPatch: (key: string, value: any) => void;
  accent: Accent;
  dirty: boolean;
  pending?: "apply" | "reset" | null;
  onApply: () => void;
  onReset: () => void;
  warnings?: CrossFieldWarning[];
  readOnly?: boolean;
}

export function DynamicSliderCard({
  icon,
  title,
  description,
  section,
  values,
  onPatch,
  accent,
  dirty,
  pending,
  onApply,
  onReset,
  warnings = [],
  readOnly,
}: DynamicSliderCardProps) {
  const toggleField = section.fields.find((f) => f.type === "toggle") as SliderField | undefined;
  const sliderFields = section.fields.filter((f) => f.type !== "toggle");
  const preview = section.preview ? section.preview(values) : undefined;
  const warningsByKey = new Map<string | null, string[]>();
  warnings.forEach((w) => {
    const arr = warningsByKey.get(w.key) ?? [];
    arr.push(w.message);
    warningsByKey.set(w.key, arr);
  });

  return (
    <TaskCard
      icon={icon}
      title={title}
      description={description}
      accent={accent}
      dirty={dirty}
      pending={pending}
      onApply={onApply}
      onReset={onReset}
      readOnly={readOnly}
      preview={preview}
    >
      <div className="flex flex-col gap-4">
        {toggleField && (
          <Switch
            id={title.replace(/\s+/g, "-").toLowerCase()}
            label={toggleField.label}
            checked={!!values[toggleField.key]}
            onChange={(v) => onPatch(toggleField.key, v)}
            disabled={readOnly}
          />
        )}
        {warningsByKey.get(null)?.map((w, i) => <WarningLine key={"top" + i} text={w} />)}
        <div className="flex flex-col gap-5">
          {sliderFields.map((f) => {
            const shown = !toggleField || !!values[toggleField.key] || f.alwaysVisible;
            if (!shown) return null;
            const min = f.minFrom
              ? (values[f.minFrom.key] ?? f.min ?? 0) + (f.minFrom.offset || 0)
              : f.min ?? 0;
            const max = f.max ?? 100;
            const val = Math.min(Math.max(values[f.key] ?? min, min), max);
            const fieldWarnings = warningsByKey.get(f.key) ?? [];
            return (
              <div key={f.key}>
                <SafeZoneSlider
                  label={f.label}
                  value={val}
                  min={min}
                  max={max}
                  step={f.step || 1}
                  zones={f.zones}
                  unit={f.unit || ""}
                  formatValue={f.formatValue}
                  disabled={readOnly}
                  onChange={(v) => {
                    onPatch(f.key, v);
                    // Cascade: any field that has minFrom pointing at this one
                    // may now be below its new min; nudge it up.
                    section.fields.forEach((other) => {
                      if (other.minFrom && other.minFrom.key === f.key) {
                        const newMin = v + (other.minFrom.offset || 0);
                        if ((values[other.key] ?? 0) < newMin) {
                          onPatch(other.key, Math.min(other.max ?? 100, newMin));
                        }
                      }
                    });
                  }}
                />
                {fieldWarnings.map((w, i) => <WarningLine key={f.key + i} text={w} />)}
              </div>
            );
          })}
        </div>
      </div>
    </TaskCard>
  );
}

/* ------------------------------------------------------------------ */
/* Fields card — flat list of SchemaField rows                        */
/* ------------------------------------------------------------------ */

export function FieldsHomeCard({
  icon,
  title,
  description,
  section,
  values,
  patch,
  accent,
  dirty,
  pending,
  onApply,
  onReset,
  requestConfirm,
  readOnly,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  section: Extract<Section, { kind: "fields" }>;
  values: Record<string, any>;
  patch: (key: string, value: any) => void;
  accent: Accent;
  dirty: boolean;
  pending?: "apply" | "reset" | null;
  onApply: () => void;
  onReset: () => void;
  requestConfirm: (label: string, apply: () => void) => void;
  readOnly?: boolean;
}) {
  const preview = section.preview ? section.preview(values) : undefined;
  const isVisible = (f: any) =>
    !f.showIf || values[f.showIf.key] === f.showIf.equals;
  return (
    <TaskCard
      icon={icon}
      title={title}
      description={description}
      accent={accent}
      dirty={dirty}
      pending={pending}
      onApply={onApply}
      onReset={onReset}
      readOnly={readOnly}
      preview={preview}
    >
      <div className="flex flex-col -my-1">
        {section.fields.filter(isVisible).map((f) => (
          <SchemaField
            key={f.key}
            field={f}
            value={values[f.key]}
            onChange={(v) => patch(f.key, v)}
            requestConfirm={requestConfirm}
            disabled={readOnly}
          />
        ))}
      </div>
    </TaskCard>
  );
}

/* ------------------------------------------------------------------ */
/* Schedule windows                                                    */
/* ------------------------------------------------------------------ */

export function ScheduleWindows({
  windowFields,
  windows,
  patchPath,
  readOnly,
}: {
  windowFields: WindowField[];
  windows: ScheduleWindow[];
  patchPath: (subpath: (string | number)[], v: any) => void;
  readOnly?: boolean;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
      {windows.map((w, i) => {
        const next = windows[(i + 1) % windows.length];
        return (
          <div
            key={i}
            className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-3 flex flex-col gap-2.5"
          >
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-semibold text-zinc-600 dark:text-zinc-300">
                Window {i + 1}
              </span>
              <span
                className="text-[11px] font-mono text-zinc-400"
                title="Runs until the next window starts"
              >
                until {String(next.time)}
              </span>
            </div>
            {windowFields
              .filter((f) => f.type !== "checkbox")
              .map((f) => (
                <label key={f.key} className="flex flex-col gap-1">
                  <span className="text-[11px] text-zinc-500 dark:text-zinc-400 flex items-center gap-1">
                    {f.label}
                    {f.reg && (
                      <span className="font-mono text-[9.5px] text-zinc-400">{f.reg}</span>
                    )}
                  </span>
                  {f.type === "time" ? (
                    <TimeField
                      value={w[f.key] as string}
                      onChange={(v) => patchPath(["windows", i, f.key], v)}
                      disabled={readOnly}
                    />
                  ) : (
                    <NumberField
                      value={w[f.key] as number}
                      step={f.step || 1}
                      suffix={f.unit}
                      onChange={(v) => patchPath(["windows", i, f.key], v)}
                      disabled={readOnly}
                    />
                  )}
                </label>
              ))}
            {windowFields.some((f) => f.type === "checkbox") && (
              <div className="flex items-center gap-4 pt-1 flex-wrap">
                {windowFields
                  .filter((f) => f.type === "checkbox")
                  .map((f) => (
                    <label
                      key={f.key}
                      className={`flex items-center gap-1.5 text-[12px] text-zinc-600 dark:text-zinc-300 ${
                        readOnly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={!!w[f.key]}
                        disabled={readOnly}
                        onChange={(e) => patchPath(["windows", i, f.key], e.target.checked)}
                        className="w-4 h-4 rounded border-zinc-300 dark:border-zinc-600 text-blue-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
                      />
                      {f.label}
                    </label>
                  ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ScheduleWindowsCard({
  icon,
  title,
  description,
  section,
  values,
  patchPath,
  accent,
  dirty,
  pending,
  onApply,
  onReset,
  readOnly,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  section: Extract<Section, { kind: "schedule" }>;
  values: { touEnabled: boolean; windows: ScheduleWindow[] };
  patchPath: (subpath: (string | number)[], v: any) => void;
  accent: Accent;
  dirty: boolean;
  pending?: "apply" | "reset" | null;
  onApply: () => void;
  onReset: () => void;
  readOnly?: boolean;
}) {
  const preview = section.preview ? section.preview(values) : undefined;
  return (
    <TaskCard
      icon={icon}
      title={title}
      description={description}
      accent={accent}
      dirty={dirty}
      pending={pending}
      onApply={onApply}
      onReset={onReset}
      readOnly={readOnly}
      preview={preview}
    >
      <div className="flex flex-col gap-4">
        <Switch
          id="tou-enabled"
          label={section.toggleField.label}
          checked={values.touEnabled}
          onChange={(v) => patchPath(["touEnabled"], v)}
          disabled={readOnly}
        />
        {values.touEnabled && (
          <ScheduleWindows
            windowFields={section.windowFields}
            windows={values.windows}
            patchPath={patchPath}
            readOnly={readOnly}
          />
        )}
      </div>
    </TaskCard>
  );
}
