/**
 * PowdriveTouSchedule — row-per-program TOU schedule editor.
 *
 * Replaces the generic ``SettingsSection`` rendering for the ``schedule``
 * group. Each Powdrive program (up to 6 hardware slots) is one horizontal
 * row: number badge · start / end time · mode · power / voltage / SOC
 * limits · row actions. End time is derived from the next active program's
 * start time (Powdrive supports a start-time-only schedule; each program
 * runs until the next one begins).
 *
 * Schema keys owned per program `i` (1..6):
 *   prog{i}_time            number  HHMM (e.g. 0600 → 06:00)
 *   prog{i}_charge_mode     enum    "0" no charge/discharge · "1" charge
 *                                   · "2" discharge · "3" grid priority
 *   prog{i}_power_w         number  0..20000 W
 *   prog{i}_voltage_v       number  40..62 V (step 0.1)
 *   prog{i}_capacity_pct    number  0..100 %
 *
 * "Add program" activates the next inactive slot by setting its charge
 * mode to "1" (charge) as a sensible default. "Delete row" sets that
 * slot's charge mode back to "0". No hardware slots are added or
 * destroyed — the schema stays authoritative.
 */
import { useMemo, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  Copy,
  Info,
  Plug,
  Plus,
  RotateCcw,
  Save,
  Trash2,
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
const PROGRAM_SLOT_COUNT = 6;

const MODE_LABELS: Record<string, string> = {
  "0": "No charge/discharge",
  "1": "Charge",
  "2": "Discharge",
  "3": "Grid priority",
};

const MODE_META: Record<string, { icon: React.ElementType; className: string }> = {
  "1": { icon: Zap, className: "text-emerald-400" },
  "2": { icon: ArrowDownRight, className: "text-amber-400" },
  "3": { icon: Plug, className: "text-sky-400" },
  "0": { icon: ArrowUpRight, className: "text-muted-foreground" },
};

interface Program {
  index: number;                // 1..6
  time: number;                 // HHMM
  chargeMode: string;           // "0" | "1" | "2" | "3"
  powerW: number;
  voltageV: number;
  capacityPct: number;
}

interface Props {
  settings: Record<string, any>;
  lastSyncedAt?: string | null;
  onApplyBulk: (changes: Record<string, string | number | boolean>) => Promise<void>;
}

// ─── Time helpers ────────────────────────────────────────────────────────────

function hhmmToDisplay(raw: number | string | undefined): string {
  const n = typeof raw === "string" ? parseInt(raw, 10) : (raw ?? 0);
  const safe = Number.isFinite(n) ? Math.max(0, Math.min(2359, Math.floor(n))) : 0;
  const hours = Math.floor(safe / 100);
  const mins = safe % 100;
  return `${hours.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}`;
}

function displayToHhmm(display: string): number {
  const [h, m] = display.split(":").map((s) => parseInt(s, 10));
  const hh = Number.isFinite(h) ? Math.max(0, Math.min(23, h)) : 0;
  const mm = Number.isFinite(m) ? Math.max(0, Math.min(59, m)) : 0;
  return hh * 100 + mm;
}

function readProgram(settings: Record<string, any>, i: number): Program {
  return {
    index: i,
    time: Number(settings[`prog${i}_time`] ?? 0),
    chargeMode: String(settings[`prog${i}_charge_mode`] ?? "0"),
    powerW: Number(settings[`prog${i}_power_w`] ?? 0),
    voltageV: Number(settings[`prog${i}_voltage_v`] ?? 48),
    capacityPct: Number(settings[`prog${i}_capacity_pct`] ?? 0),
  };
}

function programToChangeSet(p: Program): Record<string, string | number> {
  return {
    [`prog${p.index}_time`]: p.time,
    [`prog${p.index}_charge_mode`]: p.chargeMode,
    [`prog${p.index}_power_w`]: p.powerW,
    [`prog${p.index}_voltage_v`]: p.voltageV,
    [`prog${p.index}_capacity_pct`]: p.capacityPct,
  };
}

function diffProgram(prev: Program, next: Program): Record<string, string | number> {
  const changes: Record<string, string | number> = {};
  if (prev.time !== next.time) changes[`prog${next.index}_time`] = next.time;
  if (prev.chargeMode !== next.chargeMode)
    changes[`prog${next.index}_charge_mode`] = next.chargeMode;
  if (prev.powerW !== next.powerW) changes[`prog${next.index}_power_w`] = next.powerW;
  if (prev.voltageV !== next.voltageV)
    changes[`prog${next.index}_voltage_v`] = next.voltageV;
  if (prev.capacityPct !== next.capacityPct)
    changes[`prog${next.index}_capacity_pct`] = next.capacityPct;
  return changes;
}

// ─── Component ──────────────────────────────────────────────────────────────

export const PowdriveTouSchedule = ({
  settings,
  lastSyncedAt,
  onApplyBulk,
}: Props) => {
  const initial = useMemo(
    () =>
      Array.from({ length: PROGRAM_SLOT_COUNT }, (_, i) => readProgram(settings, i + 1)),
    [settings],
  );

  const [draft, setDraft] = useState<Program[]>(initial);
  const [isSaving, setIsSaving] = useState(false);

  // Active programs are the ones with a non-idle charge mode. Everything
  // else is a "free slot" reachable via "+ Add Program".
  const activePrograms = draft.filter((p) => p.chargeMode !== "0");
  const hasFreeSlot = activePrograms.length < PROGRAM_SLOT_COUNT;

  // End time for each active row = the next active program's start time,
  // rendered right after the start time column. If this is the last
  // active row, its "end" wraps to the first program's start (24 h cycle).
  const activeSorted = [...activePrograms].sort((a, b) => a.time - b.time);
  const endTimeMap = new Map<number, number>();
  activeSorted.forEach((p, idx) => {
    const nxt = activeSorted[(idx + 1) % activeSorted.length];
    endTimeMap.set(p.index, nxt.time);
  });

  const changeSet = useMemo(() => {
    const changes: Record<string, string | number> = {};
    draft.forEach((p, i) => Object.assign(changes, diffProgram(initial[i], p)));
    return changes;
  }, [draft, initial]);
  const dirtyCount = Object.keys(changeSet).length;

  const updateProgram = (index: number, patch: Partial<Program>) => {
    setDraft((prev) =>
      prev.map((p) => (p.index === index ? { ...p, ...patch } : p)),
    );
  };

  const addProgram = () => {
    // First inactive slot becomes a new active row with sensible defaults.
    const target = draft.find((p) => p.chargeMode === "0");
    if (!target) return;
    // Default start time = 1 hour after the latest active program's start,
    // wrapping at 24 h. Falls back to 06:00 if there are no active
    // programs yet.
    let nextStart = 600;
    if (activePrograms.length > 0) {
      const last = activePrograms.reduce((a, b) => (a.time > b.time ? a : b));
      const nextHour = (Math.floor(last.time / 100) + 1) % 24;
      nextStart = nextHour * 100 + (last.time % 100);
    }
    updateProgram(target.index, {
      chargeMode: "1",
      time: nextStart,
      powerW: 2000,
      voltageV: 49,
      capacityPct: 80,
    });
  };

  const removeProgram = (index: number) => {
    updateProgram(index, { chargeMode: "0" });
  };

  const duplicateProgram = (source: Program) => {
    const target = draft.find((p) => p.chargeMode === "0");
    if (!target) return;
    updateProgram(target.index, { ...source, index: target.index });
  };

  const reset = () => {
    setDraft(initial);
  };

  const save = async () => {
    if (dirtyCount === 0) return;
    setIsSaving(true);
    try {
      // Coerce all changed number fields through programToChangeSet's typing
      // so the backend receives the same shape as generic field applies do.
      await onApplyBulk(changeSet as Record<string, string | number | boolean>);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-foreground">
            Time of Use (TOU) Schedule
          </h3>
          <p className="text-xs text-muted-foreground">
            One row per program · start times set the switch-over point ·
            {lastSyncedAt && (
              <>
                {" "}synced{" "}
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

      {/* Column headers (desktop) */}
      <div className="hidden lg:grid grid-cols-[48px_140px_120px_1fr_1fr_1fr_72px] items-center gap-2 px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground">
        <div>Program</div>
        <div>Start Time</div>
        <div>End Time</div>
        <div>Mode</div>
        <div>Power Limit</div>
        <div>Voltage / SOC</div>
        <div className="text-right">Actions</div>
      </div>

      {/* Rows */}
      <div className="space-y-2">
        {activeSorted.length === 0 && (
          <div className="glass-card p-6 text-center text-xs text-muted-foreground border border-border/40">
            No active programs. Add one to build a TOU schedule.
          </div>
        )}
        {activeSorted.map((p, rowIdx) => (
          <TouRow
            key={p.index}
            program={p}
            displayIndex={rowIdx + 1}
            endTime={endTimeMap.get(p.index) ?? p.time}
            onChange={(patch) => updateProgram(p.index, patch)}
            onDelete={() => removeProgram(p.index)}
            onDuplicate={() => duplicateProgram(p)}
            canDuplicate={hasFreeSlot}
          />
        ))}
      </div>

      {/* Add program */}
      <div className="flex justify-center">
        <Button
          variant="outline"
          size="sm"
          onClick={addProgram}
          disabled={!hasFreeSlot}
          className="gap-2 border-dashed"
        >
          <Plus className="w-4 h-4" />
          {hasFreeSlot
            ? "Add Program"
            : `All ${PROGRAM_SLOT_COUNT} program slots in use`}
        </Button>
      </div>

      {/* Tip footer */}
      <div className="glass-card p-3 border border-border/40 flex items-start gap-2">
        <Info className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-muted-foreground leading-relaxed">
          Programs execute in order of their start time each day. Each program
          runs from its start time until the next program's start time; the
          last program wraps around to the first. If no programs are active,
          the inverter uses the default self-consumption mode.
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
          {isSaving ? "Saving…" : `Save Schedule${dirtyCount > 0 ? ` (${dirtyCount})` : ""}`}
        </Button>
      </div>
    </div>
  );
};

// ─── Row ────────────────────────────────────────────────────────────────────

interface RowProps {
  program: Program;
  displayIndex: number;
  endTime: number;
  onChange: (patch: Partial<Program>) => void;
  onDelete: () => void;
  onDuplicate: () => void;
  canDuplicate: boolean;
}

const TouRow = ({
  program,
  displayIndex,
  endTime,
  onChange,
  onDelete,
  onDuplicate,
  canDuplicate,
}: RowProps) => {
  const Icon = MODE_META[program.chargeMode]?.icon ?? Zap;
  const modeClass = MODE_META[program.chargeMode]?.className ?? "text-foreground";

  return (
    <div
      className={cn(
        "glass-card p-3 rounded-lg border border-border/40",
        "grid grid-cols-1 lg:grid-cols-[48px_140px_120px_1fr_1fr_1fr_72px]",
        "gap-3 items-center",
      )}
    >
      {/* Number badge */}
      <div className="flex lg:justify-center">
        <Badge
          variant="outline"
          className="h-8 w-8 flex items-center justify-center font-mono font-semibold"
        >
          {displayIndex.toString().padStart(2, "0")}
        </Badge>
      </div>

      {/* Start Time */}
      <div className="space-y-1">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Start Time
        </label>
        <Input
          type="time"
          value={hhmmToDisplay(program.time)}
          onChange={(e) => onChange({ time: displayToHhmm(e.target.value) })}
          className="h-9 font-mono"
        />
      </div>

      {/* End Time (derived) */}
      <div className="space-y-1">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          End Time
        </label>
        <Input
          type="time"
          value={hhmmToDisplay(endTime)}
          readOnly
          disabled
          className="h-9 font-mono cursor-not-allowed opacity-70"
          title="End time is the next program's start time"
        />
      </div>

      {/* Mode */}
      <div className="space-y-1">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Mode
        </label>
        <Select
          value={program.chargeMode}
          onValueChange={(v) => onChange({ chargeMode: v })}
        >
          <SelectTrigger className="h-9">
            <div className="flex items-center gap-2">
              <Icon className={cn("w-3.5 h-3.5", modeClass)} />
              <SelectValue />
            </div>
          </SelectTrigger>
          <SelectContent>
            {["1", "2", "3", "0"].map((code) => {
              const M = MODE_META[code].icon;
              const cls = MODE_META[code].className;
              return (
                <SelectItem key={code} value={code}>
                  <div className="flex items-center gap-2">
                    <M className={cn("w-3.5 h-3.5", cls)} />
                    <span>{MODE_LABELS[code]}</span>
                  </div>
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
      </div>

      {/* Power Limit */}
      <div className="space-y-1">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Power Limit
        </label>
        <NumberWithSlider
          value={program.powerW}
          onChange={(n) => onChange({ powerW: n })}
          min={0}
          max={20000}
          step={100}
          unit="W"
        />
      </div>

      {/* Voltage + SOC stacked in one cell (matches the sample's "Voltage Limit" +
          "SOC Limit" pair; the schema treats them as independent numbers). */}
      <div className="space-y-1">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Voltage / SOC
        </label>
        <div className="grid grid-cols-2 gap-2">
          <NumberWithSlider
            value={program.voltageV}
            onChange={(n) => onChange({ voltageV: n })}
            min={40}
            max={62}
            step={0.1}
            unit="V"
            decimals={1}
          />
          <NumberWithSlider
            value={program.capacityPct}
            onChange={(n) => onChange({ capacityPct: n })}
            min={0}
            max={100}
            step={1}
            unit="%"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-1">
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={onDuplicate}
          disabled={!canDuplicate}
          title="Duplicate to a free slot"
        >
          <Copy className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-destructive hover:text-destructive"
          onClick={onDelete}
          title="Disable this program (set to No charge/discharge)"
        >
          <Trash2 className="w-3.5 h-3.5" />
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
  decimals?: number;
}

const NumberWithSlider = ({
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  decimals = 0,
}: NumberWithSliderProps) => {
  const clamp = (n: number) => Math.max(min, Math.min(max, n));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
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
          className="h-8 font-mono text-sm px-2"
        />
        {unit && (
          <span className="text-[10px] text-muted-foreground min-w-[16px]">
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
        // Formatting for tick label if needed: value.toFixed(decimals)
        {...(decimals ? {} : {})}
      />
    </div>
  );
};

export default PowdriveTouSchedule;
