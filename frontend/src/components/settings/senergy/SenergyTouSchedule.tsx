/**
 * SenergyTouSchedule — row-per-window TOU schedule editor for Senergy.
 *
 * Senergy exposes six independent TOU windows (three for charging, three
 * for discharging), each with its own start time, end time, weekly
 * frequency, power limit, and end SOC. This component renders one
 * ``direction`` at a time (Charge or Discharge) — mount it twice from
 * the settings page to cover both sidebar sections.
 *
 * Schema keys per window ``i`` (1..3):
 *
 *   Charge:    charge_start_time_i, charge_end_time_i,
 *              charge_frequency_i, charge_power_i, charger_end_soc_i
 *   Discharge: discharge_start_time_i, discharge_end_time_i,
 *              discharge_frequency_i, discharge_power_i,
 *              discharge_end_soc_i
 *
 * Time encoding: Senergy stores each start/end time as ``hour * 256 +
 * minute`` (max 23:59 → 6047), NOT Powdrive's ``hour * 100 + minute``
 * HHMM. Encode/decode helpers below.
 *
 * Frequency values: 0 Off · 1 Once · 2 Everyday · 3 Weekdays · 4 Weekends.
 */
import { useMemo, useState } from "react";
import {
  ArrowDownRight,
  Battery,
  CalendarClock,
  Copy,
  Info,
  RotateCcw,
  Save,
  Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const ACCENT = "#10B981";
const WINDOW_SLOT_COUNT = 3;
const SENERGY_TIME_MAX = 23 * 256 + 59; // 6047

const FREQUENCY_LABELS: Record<string, string> = {
  "0": "Off",
  "1": "Once",
  "2": "Everyday",
  "3": "Weekdays",
  "4": "Weekends",
};

type Direction = "charge" | "discharge";

interface Window {
  index: number;               // 1..3
  startTime: number;           // Senergy-encoded: hour * 256 + minute
  endTime: number;
  frequency: string;           // "0" | "1" | "2" | "3" | "4"
  powerW: number;
  endSocPct: number;
}

// ─── Time helpers (Senergy: h * 256 + m) ────────────────────────────────────

function encodeSenergyTime(hh: number, mm: number): number {
  const h = Math.max(0, Math.min(23, hh));
  const m = Math.max(0, Math.min(59, mm));
  return h * 256 + m;
}

function decodeSenergyTime(raw: number): { hh: number; mm: number } {
  const clamped = Math.max(0, Math.min(SENERGY_TIME_MAX, raw));
  return { hh: Math.floor(clamped / 256), mm: clamped % 256 };
}

function senergyRawToDisplay(raw: number | undefined): string {
  const { hh, mm } = decodeSenergyTime(raw ?? 0);
  return `${hh.toString().padStart(2, "0")}:${mm.toString().padStart(2, "0")}`;
}

function displayToSenergyRaw(display: string): number {
  const [h, m] = display.split(":").map((s) => parseInt(s, 10));
  return encodeSenergyTime(
    Number.isFinite(h) ? h : 0,
    Number.isFinite(m) ? m : 0,
  );
}

// ─── Key helpers per direction ──────────────────────────────────────────────

function keys(direction: Direction, i: number) {
  const prefix = direction; // "charge" or "discharge"
  const socKey =
    direction === "charge" ? `charger_end_soc_${i}` : `discharge_end_soc_${i}`;
  return {
    start: `${prefix}_start_time_${i}`,
    end: `${prefix}_end_time_${i}`,
    frequency: `${prefix}_frequency_${i}`,
    power: `${prefix}_power_${i}`,
    endSoc: socKey,
  };
}

function readWindow(
  settings: Record<string, any>,
  direction: Direction,
  i: number,
): Window {
  const k = keys(direction, i);
  return {
    index: i,
    startTime: Number(settings[k.start] ?? 0),
    endTime: Number(settings[k.end] ?? 0),
    frequency: String(settings[k.frequency] ?? "0"),
    powerW: Number(settings[k.power] ?? 0),
    endSocPct: Number(settings[k.endSoc] ?? 0),
  };
}

function diffWindow(
  prev: Window,
  next: Window,
  direction: Direction,
): Record<string, string | number> {
  const k = keys(direction, next.index);
  const changes: Record<string, string | number> = {};
  if (prev.startTime !== next.startTime) changes[k.start] = next.startTime;
  if (prev.endTime !== next.endTime) changes[k.end] = next.endTime;
  if (prev.frequency !== next.frequency) changes[k.frequency] = next.frequency;
  if (prev.powerW !== next.powerW) changes[k.power] = next.powerW;
  if (prev.endSocPct !== next.endSocPct) changes[k.endSoc] = next.endSocPct;
  return changes;
}

// ─── Component ──────────────────────────────────────────────────────────────

interface Props {
  settings: Record<string, any>;
  direction: Direction;
  lastSyncedAt?: string | null;
  onApplyBulk: (changes: Record<string, string | number | boolean>) => Promise<void>;
}

export const SenergyTouSchedule = ({
  settings,
  direction,
  lastSyncedAt,
  onApplyBulk,
}: Props) => {
  const initial = useMemo(
    () =>
      Array.from({ length: WINDOW_SLOT_COUNT }, (_, i) =>
        readWindow(settings, direction, i + 1),
      ),
    [settings, direction],
  );

  const [draft, setDraft] = useState<Window[]>(initial);
  const [isSaving, setIsSaving] = useState(false);

  const changeSet = useMemo(() => {
    const changes: Record<string, string | number> = {};
    draft.forEach((w, i) => Object.assign(changes, diffWindow(initial[i], w, direction)));
    return changes;
  }, [draft, initial, direction]);
  const dirtyCount = Object.keys(changeSet).length;

  const updateWindow = (index: number, patch: Partial<Window>) => {
    setDraft((prev) =>
      prev.map((w) => (w.index === index ? { ...w, ...patch } : w)),
    );
  };

  const duplicateWindow = (source: Window) => {
    const nextIdx = (source.index % WINDOW_SLOT_COUNT) + 1;
    updateWindow(nextIdx, {
      startTime: source.startTime,
      endTime: source.endTime,
      frequency: source.frequency,
      powerW: source.powerW,
      endSocPct: source.endSocPct,
    });
  };

  const reset = () => setDraft(initial);

  const save = async () => {
    if (dirtyCount === 0) return;
    setIsSaving(true);
    try {
      await onApplyBulk(changeSet as Record<string, string | number | boolean>);
    } finally {
      setIsSaving(false);
    }
  };

  const isCharge = direction === "charge";
  const DirIcon = isCharge ? Zap : ArrowDownRight;
  const dirColour = isCharge ? "text-emerald-400" : "text-amber-400";
  const titleLabel = isCharge ? "Charge Windows" : "Discharge Windows";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-start gap-2">
          <DirIcon className={cn("w-4 h-4 mt-0.5", dirColour)} />
          <div>
            <h3 className="text-base font-semibold text-foreground">
              TOU — {titleLabel}
            </h3>
            <p className="text-xs text-muted-foreground">
              Three independent {direction} windows · start / end / frequency /
              power / SOC per row
              {lastSyncedAt && (
                <>
                  {" · "}synced{" "}
                  {new Date(lastSyncedAt).toLocaleTimeString(undefined, {
                    hour: "numeric",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Column headers (desktop) */}
      <div className="hidden lg:grid grid-cols-[44px_110px_110px_140px_1fr_1fr_56px] items-center gap-2 px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground">
        <div>Window</div>
        <div>Start Time</div>
        <div>End Time</div>
        <div>Frequency</div>
        <div>Power</div>
        <div>End SOC</div>
        <div className="text-right">Copy</div>
      </div>

      {/* Rows — all 3 windows, always fully editable */}
      <div className="space-y-2">
        {draft.map((w) => (
          <SenergyTouRow
            key={w.index}
            window={w}
            direction={direction}
            onChange={(patch) => updateWindow(w.index, patch)}
            onDuplicate={() => duplicateWindow(w)}
          />
        ))}
      </div>

      {/* Tip footer */}
      <div className="glass-card p-3 border border-border/40 flex items-start gap-2">
        <Info className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-muted-foreground leading-relaxed">
          Set Frequency to "Off" to disable a window. Times are stored as
          <code className="mx-1 text-[11px]">hour × 256 + minute</code> on the
          inverter — the picker converts automatically.
          {isCharge
            ? " Power is the maximum draw from the grid or PV into the battery during this window; End SOC is the target."
            : " Power is the maximum discharge from the battery to loads or export during this window; End SOC is the floor."}
        </p>
      </div>

      {/* Bottom action bar */}
      <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/40">
        <Button
          variant="outline"
          size="sm"
          onClick={reset}
          disabled={dirtyCount === 0 || isSaving}
          className="gap-2"
        >
          <RotateCcw className="w-4 h-4" />
          Reset
        </Button>
        <Button
          size="sm"
          onClick={save}
          disabled={dirtyCount === 0 || isSaving}
          style={{ backgroundColor: ACCENT }}
          className="gap-2"
        >
          <Save className="w-4 h-4" />
          {isSaving ? "Saving…" : `Save ${titleLabel}${dirtyCount > 0 ? ` (${dirtyCount})` : ""}`}
        </Button>
      </div>
    </div>
  );
};

// ─── Row ────────────────────────────────────────────────────────────────────

interface RowProps {
  window: Window;
  direction: Direction;
  onChange: (patch: Partial<Window>) => void;
  onDuplicate: () => void;
}

const SenergyTouRow = ({ window: w, direction, onChange, onDuplicate }: RowProps) => {
  const powerCap = direction === "charge" ? 20000 : 20000;
  const dirIconClass = direction === "charge" ? "text-emerald-400" : "text-amber-400";

  return (
    <div
      className={cn(
        "glass-card p-3 rounded-lg border border-border/40",
        "grid grid-cols-1 lg:grid-cols-[44px_110px_110px_140px_1fr_1fr_56px]",
        "gap-2 sm:gap-3 items-start lg:items-center",
      )}
    >
      {/* Number badge — mobile-first band */}
      <div className="flex items-center justify-between lg:justify-center gap-2">
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="h-7 min-w-[28px] flex items-center justify-center font-mono font-semibold text-xs"
          >
            {w.index.toString().padStart(2, "0")}
          </Badge>
          <span className="text-xs text-muted-foreground lg:hidden">
            Window {w.index}
          </span>
        </div>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 lg:hidden"
          onClick={onDuplicate}
          title="Copy to the next window"
        >
          <Copy className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Start Time */}
      <div className="space-y-1 min-w-0">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Start Time
        </label>
        <Input
          type="time"
          value={senergyRawToDisplay(w.startTime)}
          onChange={(e) => onChange({ startTime: displayToSenergyRaw(e.target.value) })}
          className="h-9 font-mono text-sm w-full"
        />
      </div>

      {/* End Time */}
      <div className="space-y-1 min-w-0">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          End Time
        </label>
        <Input
          type="time"
          value={senergyRawToDisplay(w.endTime)}
          onChange={(e) => onChange({ endTime: displayToSenergyRaw(e.target.value) })}
          className="h-9 font-mono text-sm w-full"
        />
      </div>

      {/* Frequency */}
      <div className="space-y-1 min-w-0">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Frequency
        </label>
        <Select
          value={w.frequency}
          onValueChange={(v) => onChange({ frequency: v })}
        >
          <SelectTrigger className="h-9 text-sm">
            <div className="flex items-center gap-2 min-w-0">
              <CalendarClock className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">
                <SelectValue />
              </span>
            </div>
          </SelectTrigger>
          <SelectContent>
            {["0", "1", "2", "3", "4"].map((code) => (
              <SelectItem key={code} value={code}>
                {FREQUENCY_LABELS[code]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Power */}
      <div className="space-y-1 min-w-0">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Power
        </label>
        <NumberWithSlider
          value={w.powerW}
          onChange={(n) => onChange({ powerW: n })}
          min={0}
          max={powerCap}
          step={100}
          unit="W"
          icon={<Zap className={cn("w-3.5 h-3.5 shrink-0", dirIconClass)} />}
        />
      </div>

      {/* End SOC */}
      <div className="space-y-1 min-w-0">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          End SOC
        </label>
        <NumberWithSlider
          value={w.endSocPct}
          onChange={(n) => onChange({ endSocPct: n })}
          min={0}
          max={100}
          step={1}
          unit="%"
          icon={<Battery className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />}
        />
      </div>

      {/* Copy — desktop only */}
      <div className="hidden lg:flex items-center justify-end gap-1">
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={onDuplicate}
          title="Copy to the next window"
        >
          <Copy className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
};

// ─── Compact number + slider ────────────────────────────────────────────────

interface NumberWithSliderProps {
  value: number;
  onChange: (n: number) => void;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  icon?: React.ReactNode;
}

const NumberWithSlider = ({
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  icon,
}: NumberWithSliderProps) => {
  const clamp = (n: number) => Math.max(min, Math.min(max, n));

  return (
    <div className="space-y-1.5 min-w-0">
      <div className="flex items-center gap-1.5 min-w-0">
        {icon}
        <Input
          type="number"
          value={value}
          onChange={(e) => {
            const n = parseFloat(e.target.value);
            onChange(Number.isFinite(n) ? clamp(n) : min);
          }}
          min={min}
          max={max}
          step={step}
          className="h-8 font-mono text-xs sm:text-sm px-2 min-w-0"
        />
        {unit && (
          <span className="text-[10px] text-muted-foreground min-w-[16px] shrink-0">
            {unit}
          </span>
        )}
      </div>
      <Slider
        value={[value]}
        onValueChange={(v) => onChange(clamp(v[0]))}
        min={min}
        max={max}
        step={step}
        className="pt-1"
        aria-label={`${unit ?? ""} slider`}
      />
    </div>
  );
};

export default SenergyTouSchedule;
