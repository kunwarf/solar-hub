/**
 * Field renderers used inside FieldsHomeCard and GroupDetailScreen.
 *
 * SchemaField dispatches on FlatField.type → NumberField / SelectField /
 * ToggleField / TimeField.  FieldRow wraps a single field's label + control
 * with optional register-address chip, destructive badge, and help popover.
 *
 * Ported from D:\Downloads\solar-inverter-settings.html (SchemaField et al.),
 * adapted to TypeScript and the app's existing lucide-react icon set.
 */
import type { FlatField } from "./profiles/types";
import { FieldHelpPopover } from "./primitives";

/* ------------------------------------------------------------------ */
/* Individual controls                                                 */
/* ------------------------------------------------------------------ */

export function NumberField({
  value,
  onChange,
  step = 1,
  suffix,
  disabled,
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number;
  suffix?: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-1">
      <input
        type="number"
        value={value}
        step={step}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-28 text-right rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-2 py-2 text-base font-mono tabular-nums focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50"
      />
      {suffix && <span className="text-[12px] text-zinc-400 w-8">{suffix}</span>}
    </div>
  );
}

export function SelectField({
  value,
  onChange,
  options,
  disabled,
}: {
  value: string | number;
  onChange: (v: string) => void;
  options: string[];
  disabled?: boolean;
}) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-2 py-2 text-base max-w-[12rem] focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

export function ToggleField({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`relative w-9 h-5 rounded-full transition-colors ${
        checked ? "bg-blue-600" : "bg-zinc-300 dark:bg-zinc-700"
      } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

export function TimeField({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <input
      type="time"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-2 py-2 text-base font-mono focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50"
    />
  );
}

/* ------------------------------------------------------------------ */
/* Row wrapper                                                         */
/* ------------------------------------------------------------------ */

export function FieldRow({
  label,
  destructive,
  reg,
  description,
  children,
}: {
  label: string;
  destructive?: boolean;
  reg?: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3 py-3 border-b border-zinc-100 dark:border-zinc-800 last:border-b-0">
      <span className="text-[13.5px] text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5 flex-wrap">
        {label}
        {description && <FieldHelpPopover description={description} />}
        {reg && (
          <span className="font-mono text-[10px] text-zinc-400 dark:text-zinc-500">
            {reg}
          </span>
        )}
        {destructive && (
          <span className="text-[10px] font-semibold uppercase tracking-wide bg-rose-100 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400 rounded px-1.5 py-0.5">
            Destructive
          </span>
        )}
      </span>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Dispatcher                                                          */
/* ------------------------------------------------------------------ */

export function SchemaField({
  field,
  value,
  onChange,
  requestConfirm,
  disabled,
}: {
  field: FlatField;
  value: any;
  onChange: (v: any) => void;
  requestConfirm: (label: string, apply: () => void) => void;
  disabled?: boolean;
}) {
  // Destructive fields go through the confirm modal — matches the memory's
  // established "type serial to confirm" pattern.
  const commit = (v: any) => {
    if (field.destructive) requestConfirm(field.label, () => onChange(v));
    else onChange(v);
  };

  let control: React.ReactNode;
  if (field.type === "number") {
    control = (
      <NumberField
        value={value}
        step={field.step || 1}
        suffix={field.unit}
        onChange={commit}
        disabled={disabled}
      />
    );
  } else if (field.type === "select") {
    control = (
      <SelectField
        value={value}
        options={field.options || []}
        onChange={commit}
        disabled={disabled}
      />
    );
  } else if (field.type === "toggle") {
    control = <ToggleField checked={!!value} onChange={commit} disabled={disabled} />;
  } else if (field.type === "time") {
    control = <TimeField value={value} onChange={commit} disabled={disabled} />;
  }

  return (
    <FieldRow
      label={field.label}
      destructive={field.destructive}
      reg={field.reg}
      description={field.description}
    >
      {control}
    </FieldRow>
  );
}
