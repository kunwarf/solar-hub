/**
 * Small visual primitives used across the v2 settings screens.
 *
 * Ported from D:\Downloads\solar-inverter-settings.html (TaskCard, Button,
 * Switch, Alert, ScreenHeader, GroupCard), adapted to TypeScript, lucide-react
 * icons, and the app's existing sonner/toast conventions.
 *
 * SafeZoneSlider lives in its own file (SafeZoneSlider.tsx) because of its
 * size and pointer/keyboard event complexity.
 */
import type { ReactNode } from "react";
import { AlertTriangle, ArrowLeft, ChevronRight, Info, RefreshCw } from "lucide-react";

/* ------------------------------------------------------------------ */
/* Card accent utility                                                 */
/* ------------------------------------------------------------------ */

export type Accent = "safe" | "tuned" | "destructive";
const ACCENT_CLASS: Record<Accent, string> = {
  safe: "bg-emerald-500",
  tuned: "bg-amber-500",
  destructive: "bg-rose-500",
};

/* ------------------------------------------------------------------ */
/* Button                                                              */
/* ------------------------------------------------------------------ */

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "destructive" | "outline";
  pending?: boolean;
}

export function Button({
  variant = "primary",
  pending,
  disabled,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-lg text-sm font-medium px-3.5 py-2 min-h-[40px] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 disabled:pointer-events-none";
  const styles: Record<string, string> = {
    primary:
      "bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white focus-visible:outline-blue-600",
    ghost:
      "text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 active:bg-zinc-200 dark:hover:bg-zinc-800 dark:active:bg-zinc-700 focus-visible:outline-zinc-400",
    destructive:
      "bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white focus-visible:outline-rose-600",
    outline:
      "border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 active:bg-zinc-200 dark:hover:bg-zinc-800 dark:active:bg-zinc-700 focus-visible:outline-zinc-400",
  };
  return (
    <button
      className={`${base} ${styles[variant]} ${className}`}
      disabled={disabled || pending}
      {...rest}
    >
      {pending && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Switch                                                              */
/* ------------------------------------------------------------------ */

export function Switch({
  checked,
  onChange,
  label,
  id,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  id?: string;
  disabled?: boolean;
}) {
  return (
    <label
      htmlFor={id}
      className={`flex items-center justify-between gap-3 select-none ${
        disabled ? "opacity-50" : "cursor-pointer"
      }`}
    >
      <span className="text-sm font-medium">{label}</span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        disabled={disabled}
        className={`relative w-10 h-6 rounded-full transition-colors shrink-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
          checked ? "bg-blue-600" : "bg-zinc-300 dark:bg-zinc-700"
        } ${disabled ? "cursor-not-allowed" : ""}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </button>
    </label>
  );
}

/* ------------------------------------------------------------------ */
/* Alert — used for the installer-tier red banner                     */
/* ------------------------------------------------------------------ */

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 px-4 py-3 text-[13px] leading-relaxed mb-4">
      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
      <p>{children}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* ScreenHeader — sticky top bar for Hub and Group Detail             */
/* ------------------------------------------------------------------ */

export function ScreenHeader({
  onBack,
  title,
  subtitle,
  right,
}: {
  onBack: () => void;
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <header
      className="sticky top-0 z-10 backdrop-blur bg-zinc-50/90 dark:bg-zinc-950/90 border-b border-zinc-200 dark:border-zinc-800"
      style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
    >
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3.5 flex items-center gap-3">
        <button
          onClick={onBack}
          aria-label="Back"
          className="w-10 h-10 -ml-2 flex items-center justify-center rounded-lg active:bg-zinc-200 dark:active:bg-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-300 shrink-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-[15px] font-semibold leading-tight truncate">{title}</h1>
          {subtitle && (
            <p className="text-[12px] text-zinc-500 dark:text-zinc-400 truncate">{subtitle}</p>
          )}
        </div>
        {right}
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* TaskCard — home-page card wrapper                                  */
/* ------------------------------------------------------------------ */

export interface TaskCardProps {
  accent?: Accent;
  icon: ReactNode;
  title: string;
  description: string;
  dirty?: boolean;
  pending?: "apply" | "reset" | null;
  onApply?: () => void;
  onReset?: () => void;
  /** Read-only mode disables Apply/Reset — used when the current user
   *  role doesn't allow settings changes. */
  readOnly?: boolean;
  children: ReactNode;
  preview?: string;
}

export function TaskCard({
  accent = "safe",
  icon,
  title,
  description,
  dirty,
  pending,
  onApply,
  onReset,
  readOnly,
  children,
  preview,
}: TaskCardProps) {
  const showFooter = dirty && !readOnly;
  return (
    <div className="rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-sm hover:shadow-md transition-shadow overflow-hidden flex flex-col">
      <div className={`h-1 w-full transition-colors ${ACCENT_CLASS[accent]}`} />
      <div className="p-5 flex flex-col gap-4 flex-1">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 shrink-0 rounded-lg bg-zinc-100 dark:bg-zinc-800 p-2 text-zinc-700 dark:text-zinc-300">
            {icon}
          </div>
          <div>
            <h3 className="text-[16px] font-semibold leading-tight">{title}</h3>
            <p className="text-[13px] text-zinc-500 dark:text-zinc-400 mt-0.5">{description}</p>
          </div>
        </div>
        <div className="flex-1">{children}</div>
        {preview && (
          <p className="text-[13px] italic text-zinc-500 dark:text-zinc-400 border-t border-dashed border-zinc-200 dark:border-zinc-800 pt-3">
            {preview}
          </p>
        )}
      </div>
      <div
        className={`px-5 pb-4 flex items-center gap-2 overflow-hidden transition-all duration-200 ${
          showFooter ? "max-h-16 opacity-100" : "max-h-0 opacity-0 pb-0"
        }`}
      >
        <Button variant="primary" onClick={onApply} pending={pending === "apply"}>
          Apply
        </Button>
        <Button variant="ghost" onClick={onReset} pending={pending === "reset"}>
          Reset
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* GroupCard — used on the All-Settings hub                           */
/* ------------------------------------------------------------------ */

export function GroupCard({
  icon,
  title,
  description,
  countLabel,
  installer,
  dirty,
  onOpen,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  countLabel: string;
  installer?: boolean;
  dirty?: boolean;
  onOpen: () => void;
}) {
  return (
    <button
      onClick={onOpen}
      className="text-left rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-sm hover:shadow-md transition-shadow overflow-hidden flex flex-col focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
    >
      <div className={`h-1 w-full ${installer ? "bg-rose-500" : "bg-blue-500"}`} />
      <div className="p-5 flex items-start gap-3">
        <div
          className={`mt-0.5 shrink-0 rounded-lg p-2 ${
            installer
              ? "bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400"
              : "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
          }`}
        >
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-[15px] font-semibold leading-tight">{title}</h3>
            {dirty && (
              <span
                className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0"
                title="Unsaved changes"
              />
            )}
          </div>
          <p className="text-[12.5px] text-zinc-500 dark:text-zinc-400 mt-0.5">{description}</p>
          <p className="text-[11px] font-mono text-zinc-400 dark:text-zinc-500 mt-2">
            {countLabel}
          </p>
        </div>
        <ChevronRight className="w-4 h-4 text-zinc-300 dark:text-zinc-600 shrink-0 mt-1" />
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* FieldHelpPopover — Info icon that reveals field.description        */
/* ------------------------------------------------------------------ */

export function FieldHelpPopover({ description }: { description?: string }) {
  if (!description) return null;
  return (
    <span className="relative inline-flex items-center group">
      <button
        type="button"
        aria-label="Help"
        className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 rounded"
      >
        <Info className="w-3.5 h-3.5" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-2 z-20 hidden group-hover:block group-focus-within:block w-64 rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-[12px] leading-snug px-3 py-2 shadow-lg"
      >
        {description}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* ReadOnlyBanner — top-of-screen role notice                         */
/* ------------------------------------------------------------------ */

export function ReadOnlyBanner({ reason }: { reason: string }) {
  return (
    <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-300 px-4 py-3 text-[13px] mb-4">
      <span className="font-medium">Read-only.</span> {reason}
    </div>
  );
}
