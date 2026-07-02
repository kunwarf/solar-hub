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

  // Powdrive has 6 fixed hardware slots. Always render all six so
  // operators can see the whole schedule at a glance — inactive slots
  // (charge_mode = "0") are dimmed but still editable, so clicking a
  // mode into "1"/"2"/"3" is the equivalent of "add program".
  const allByRowOrder = draft;
  const activePrograms = draft.filter((p) => p.chargeMode !== "0");

  // End time for each *active* row = the next active program's start
  // time (24 h cycle). Inactive rows show a dash. This encodes the
  // Powdrive rule: each program runs from its start until the next
  // program's start, and disabled slots are skipped entirely.
  const activeSorted = [...activePrograms].sort((a, b) => a.time - b.time);
  const endTimeMap = new Map<number, number | null>();
  activeSorted.forEach((p, idx) => {
    const nxt = activeSorted[(idx + 1) % activeSorted.length];
    endTimeMap.set(p.index, activeSorted.length > 1 ? nxt.time : p.time);
  });
  // Inactive slots have no end time.
  draft.forEach((p) => {
    if (!endTimeMap.has(p.index)) endTimeMap.set(p.index, null);
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

  const enableProgram = (index: number) => {
    // Enabling a previously inactive slot: pick sensible defaults so the
    // sliders don't sit at zero and confuse the operator.
    const target = draft.find((p) => p.index === index);
    if (!target || target.chargeMode !== "0") return;
    let nextStart = 600;
    if (activePrograms.length > 0) {
      const last = activePrograms.reduce((a, b) => (a.time > b.time ? a : b));
      const nextHour = (Math.floor(last.time / 100) + 1) % 24;
      nextStart = nextHour * 100 + (last.time % 100);
    }
    updateProgram(index, {
      chargeMode: "1",
      time: target.time || nextStart,
      powerW: target.powerW || 2000,
      voltageV: target.voltageV || 49,
      capacityPct: target.capacityPct || 80,
    });
  };

  const disableProgram = (index: number) => {
    updateProgram(index, { chargeMode: "0" });
  };

  const duplicateProgram = (source: Program) => {
    const target = draft.find((p) => p.chargeMode === "0" && p.index !== source.index);
    if (!target) return;
    updateProgram(target.index, {
      chargeMode: source.chargeMode,
      time: source.time,
      powerW: source.powerW,
      voltageV: source.voltageV,
      capacityPct: source.capacityPct,
    });
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

      {/* Rows — all 6 hardware slots, always. Inactive ones are dimmed
          but still editable so the operator sees the whole schedule. */}
      <div className="space-y-2">
        {allByRowOrder.map((p) => (
          <TouRow
            key={p.index}
            program={p}
            displayIndex={p.index}
            endTime={endTimeMap.get(p.index) ?? null}
            isActive={p.chargeMode !== "0"}
            onChange={(patch) => updateProgram(p.index, patch)}
            onEnable={() => enableProgram(p.index)}
            onDisable={() => disableProgram(p.index)}
            onDuplicate={() => duplicateProgram(p)}
            canDuplicate={
              draft.some(
                (q) => q.chargeMode === "0" && q.index !== p.index,
              )
            }
          />
        ))}
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
  endTime: number | null;
  isActive: boolean;
  onChange: (patch: Partial<Program>) => void;
  onEnable: () => void;
  onDisable: () => void;
  onDuplicate: () => void;
  canDuplicate: boolean;
}

const TouRow = ({
  program,
  displayIndex,
  endTime,
  isActive,
  onChange,
  onEnable,
  onDisable,
  onDuplicate,
  canDuplicate,
}: RowProps) => {
  const Icon = MODE_META[program.chargeMode]?.icon ?? Zap;
  const modeClass = MODE_META[program.chargeMode]?.className ?? "text-foreground";

  return (
    <div
      className={cn(
        "glass-card p-3 sm:p-3 rounded-lg border border-border/40 transition-opacity",
        // Below lg: single column with labels visible.
        // At lg+: 7-column row with column headers above providing labels.
        "grid grid-cols-1 lg:grid-cols-[44px_100px_100px_1fr_1fr_1fr_64px]",
        "gap-2 sm:gap-3 items-start lg:items-center",
        !isActive && "opacity-60",
      )}
    >
      {/* Number badge — full-width band on mobile so the row is obvious */}
      <div className="flex items-center justify-between lg:justify-center gap-2">
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={cn(
              "h-7 min-w-[28px] flex items-center justify-center font-mono font-semibold text-xs",
              isActive && "border-emerald-500/50 text-emerald-400",
            )}
          >
            {displayIndex.toString().padStart(2, "0")}
          </Badge>
          <span className="text-xs text-muted-foreground lg:hidden">
            Program {displayIndex}
            {!isActive && " · disabled"}
          </span>
        </div>
        {/* On mobile, quick enable/disable toggle at the top of the row */}
        <div className="flex items-center gap-1 lg:hidden">
          {!isActive ? (
            <Button
              size="sm"
              variant="outline"
              onClick={onEnable}
              className="h-7 text-xs gap-1"
            >
              <Plus className="w-3 h-3" />
              Enable
            </Button>
          ) : (
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-destructive hover:text-destructive"
              onClick={onDisable}
              title="Disable"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Start Time */}
      <div className="space-y-1 min-w-0">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Start Time
        </label>
        <Input
          type="time"
          value={hhmmToDisplay(program.time)}
          onChange={(e) => onChange({ time: displayToHhmm(e.target.value) })}
          disabled={!isActive}
          className="h-9 font-mono text-sm w-full"
        />
      </div>

      {/* End Time (derived) */}
      <div className="space-y-1 min-w-0">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          End Time
        </label>
        {endTime !== null ? (
          <Input
            type="time"
            value={hhmmToDisplay(endTime)}
            readOnly
            disabled
            className="h-9 font-mono text-sm cursor-not-allowed opacity-70 w-full"
            title="End time is the next active program's start time"
          />
        ) : (
          <div className="h-9 flex items-center px-2 text-xs text-muted-foreground">
            —
          </div>
        )}
      </div>

      {/* Mode */}
      <div className="space-y-1 min-w-0">
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
          Mode
        </label>
        <Select
          value={program.chargeMode}
          onValueChange={(v) => onChange({ chargeMode: v })}
        >
          <SelectTrigger className="h-9 text-sm">
            <div className="flex items-center gap-2 min-w-0">
              <Icon className={cn("w-3.5 h-3.5 shrink-0", modeClass)} />
              <span className="truncate">
                <SelectValue />
              </span>
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
      <div className="space-y-1 min-w-0">
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
          disabled={!isActive}
        />
      </div>

      {/* Voltage + SOC stacked in one cell */}
      <div className="space-y-1 min-w-0">
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
            disabled={!isActive}
          />
          <NumberWithSlider
            value={program.capacityPct}
            onChange={(n) => onChange({ capacityPct: n })}
            min={0}
            max={100}
            step={1}
            unit="%"
            disabled={!isActive}
          />
        </div>
      </div>

      {/* Actions — desktop only; mobile has enable/disable near the badge */}
      <div className="hidden lg:flex items-center justify-end gap-1">
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={onDuplicate}
          disabled={!canDuplicate || !isActive}
          title="Duplicate to a free slot"
        >
          <Copy className="w-3.5 h-3.5" />
        </Button>
        {isActive ? (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-destructive hover:text-destructive"
            onClick={onDisable}
            title="Disable this program (set to No charge/discharge)"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        ) : (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-emerald-400 hover:text-emerald-400"
            onClick={onEnable}
            title="Enable this program"
          >
            <Plus className="w-3.5 h-3.5" />
          </Button>
        )}
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
  disabled?: boolean;
}

const NumberWithSlider = ({
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  disabled,
}: NumberWithSliderProps) => {
  const clamp = (n: number) => Math.max(min, Math.min(max, n));

  return (
    <div className={cn("space-y-1.5 min-w-0", disabled && "opacity-60")}>
      <div className="flex items-center gap-1.5 min-w-0">
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
          disabled={disabled}
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
        disabled={disabled}
        className="pt-1"
        aria-label={`${unit ?? ""} slider`}
      />
    </div>
  );
};

export default PowdriveTouSchedule;
