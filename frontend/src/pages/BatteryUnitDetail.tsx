/**
 * BatteryUnitDetail
 *
 * Deep-dive analysis page for a single battery module (unit) within a
 * bank. Fetches the ``/battery/bank`` snapshot for the device, picks the
 * requested unit, and renders:
 *
 *   1. Nameplate — model, firmware, board, mfr date, barcode, rated Ah
 *   2. Live snapshot — voltage, current, SOC, temp, power, charge state
 *   3. Health verdict — colored status badge + expanded concerns list
 *   4. Cell voltage strip — one bar per cell, coloured by relative
 *      voltage, with imbalance readout
 *   5. Event counters — non-zero stat counters grouped by severity
 *   6. Peer comparison — this unit's SOC/SOH/cycles/temp against the
 *      bank median so anomalies stand out at a glance
 *
 * Route: /devices/:deviceId/battery/unit/:unitNum
 */
import { useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Battery,
  BatteryCharging,
  BatteryFull,
  BatteryLow,
  AlertTriangle,
  CheckCircle2,
  Activity,
  Thermometer,
  Zap,
  Gauge,
  Info,
  Cpu,
  Loader2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { devicesService } from "@/api/services/devices.service";

// ─── Types (mirror what the backend attaches to each unit) ─────────────────

type HealthStatus = "healthy" | "watch" | "degraded" | "critical";

interface UnitHealth {
  status: HealthStatus;
  concerns: string[];
}

interface UnitNameplate {
  manufacturer?: string;
  model?: string;
  board?: string;
  board_version?: string;
  main_soft_version?: string;
  soft_version?: string;
  boot_version?: string;
  comm_version?: string;
  release_date?: string;
  barcode?: string;
  rated_ah?: number;
  specification?: string;
  cell_count?: number;
  max_charge_a?: number;
  max_discharge_a?: number;
}

interface UnitEvents {
  [key: string]: number;
}

interface PeerSummary {
  socMedian?: number;
  sohMedian?: number;
  cyclesMedian?: number;
  tempMedian?: number;
  unitCount: number;
}

interface Unit {
  unit: number;
  voltage_v?: number;
  current_a?: number;
  soc_pct?: number;
  temp_c?: number;
  soh_pct?: number;
  cycle_count?: number;
  power_w?: number;
  total_ah?: number;
  remaining_ah?: number;
  health?: UnitHealth;
  nameplate?: UnitNameplate;
  events?: UnitEvents;
}

interface CellDatum {
  unit: number;
  cell: number;
  voltage_v?: number;
  temperature?: number;
  soc?: number;
}

interface BatteryBankResponse {
  device_id: string;
  serial_number: string;
  available: boolean;
  bank: Record<string, any>;
  units: Unit[];
  cells: CellDatum[];
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const STATUS_META: Record<
  HealthStatus,
  { label: string; ringClass: string; bgClass: string; textClass: string; dotClass: string; icon: typeof CheckCircle2 }
> = {
  healthy: {
    label: "Healthy",
    ringClass: "ring-success/40",
    bgClass: "bg-success/10",
    textClass: "text-success",
    dotClass: "bg-success",
    icon: CheckCircle2,
  },
  watch: {
    label: "Watch",
    ringClass: "ring-warning/40",
    bgClass: "bg-warning/10",
    textClass: "text-warning",
    dotClass: "bg-warning",
    icon: AlertTriangle,
  },
  degraded: {
    label: "Degraded",
    ringClass: "ring-orange-500/40",
    bgClass: "bg-orange-500/10",
    textClass: "text-orange-500",
    dotClass: "bg-orange-500",
    icon: AlertTriangle,
  },
  critical: {
    label: "Critical",
    ringClass: "ring-destructive/40",
    bgClass: "bg-destructive/10",
    textClass: "text-destructive",
    dotClass: "bg-destructive",
    icon: AlertTriangle,
  },
};

/**
 * Human-readable label for each stat counter key.
 */
const EVENT_LABELS: Record<string, string> = {
  life_warn: "Life warning events",
  life_alarm: "Life alarm events",
  soh_events: "SOH-drop events",
  sc_times: "Short-circuit events",
  bat_uv_times: "Battery under-voltage",
  bat_ov_times: "Battery over-voltage",
  bat_hv_times: "Battery high-voltage",
  bat_lv_times: "Battery low-voltage",
  doc_times: "Discharge over-current",
  doc2_times: "Discharge over-current (severe)",
  coc_times: "Charge over-current",
  coc2_times: "Charge over-current (severe)",
  coca_times: "Charge over-current alarm",
  doca_times: "Discharge over-current alarm",
  reset_count: "BMS resets",
  shut_count: "BMS shutdowns",
};

const EVENT_SEVERITY: Record<string, "critical" | "warning" | "info"> = {
  life_alarm: "critical",
  sc_times: "critical",
  bat_uv_times: "critical",
  life_warn: "warning",
  soh_events: "warning",
  bat_ov_times: "warning",
  doc_times: "warning",
  doc2_times: "warning",
  doca_times: "warning",
  coca_times: "warning",
  coc_times: "warning",
  coc2_times: "warning",
  bat_lv_times: "info",
  bat_hv_times: "info",
  reset_count: "info",
  shut_count: "info",
};

const SEVERITY_META = {
  critical: {
    label: "Critical",
    className: "bg-destructive/10 text-destructive border-destructive/20",
  },
  warning: {
    label: "Warning",
    className: "bg-warning/10 text-warning border-warning/20",
  },
  info: {
    label: "Info",
    className: "bg-secondary/40 text-muted-foreground border-border/50",
  },
} as const;

function median(nums: number[]): number | undefined {
  if (nums.length === 0) return undefined;
  const sorted = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

function formatMaybe(
  value: number | undefined,
  digits = 2,
  unit = "",
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)}${unit}`;
}

// ─── Energy response type ──────────────────────────────────────────────────

interface EnergyEntry {
  charge_kwh: number;
  discharge_kwh: number;
  coverage_pct: number;
}

interface BatteryEnergyResponse {
  device_id: string;
  start_time: string;
  end_time: string;
  timezone: string;
  device: EnergyEntry | null;
  units: Record<string, EnergyEntry>;
  window_minutes?: number;
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function BatteryUnitDetail() {
  const { deviceId, unitNum: unitNumStr } = useParams<{
    deviceId: string;
    unitNum: string;
  }>();
  const navigate = useNavigate();
  const unitNum = Number(unitNumStr);

  const { data, isLoading, error } = useQuery<BatteryBankResponse | null>({
    queryKey: ["battery-bank-detail", deviceId],
    queryFn: () => devicesService.getBatteryBank(deviceId!),
    enabled: !!deviceId,
    refetchInterval: 15_000,
    staleTime: 5_000,
  });

  // Today's charge/discharge kWh — refreshed less aggressively (60 s)
  // because the value moves slowly compared to voltage/current.
  const { data: energy } = useQuery<BatteryEnergyResponse | null>({
    queryKey: ["battery-energy-today", deviceId],
    queryFn: () => devicesService.getBatteryEnergy(deviceId!),
    enabled: !!deviceId,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const unit = useMemo(
    () => data?.units.find((u) => u.unit === unitNum),
    [data, unitNum],
  );

  const unitCells = useMemo(
    () => (data?.cells ?? []).filter((c) => c.unit === unitNum),
    [data, unitNum],
  );

  const peerSummary = useMemo(() => {
    if (!data?.units) return null;
    const others = data.units.filter((u) => u.unit !== unitNum);
    return {
      socMedian: median(
        others.map((u) => u.soc_pct).filter((v): v is number => v != null),
      ),
      sohMedian: median(
        others.map((u) => u.soh_pct).filter((v): v is number => v != null),
      ),
      cyclesMedian: median(
        others
          .map((u) => u.cycle_count)
          .filter((v): v is number => v != null),
      ),
      tempMedian: median(
        others.map((u) => u.temp_c).filter((v): v is number => v != null),
      ),
      unitCount: data.units.length,
    };
  }, [data, unitNum]);

  const cellStats = useMemo(() => {
    const mv = unitCells
      .map((c) => (c.voltage_v ?? 0) * 1000)
      .filter((v) => v > 0);
    if (mv.length === 0) return null;
    const max = Math.max(...mv);
    const min = Math.min(...mv);
    const avg = mv.reduce((a, b) => a + b, 0) / mv.length;
    return {
      max,
      min,
      avg,
      range: max - min,
      count: mv.length,
    };
  }, [unitCells]);

  // Loading / error states
  if (isLoading) {
    return (
      <AppLayout>
        <AppHeader title="Battery Unit" subtitle="Loading module details…" />
        <div className="container mx-auto p-3 sm:p-6 flex items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </AppLayout>
    );
  }

  if (error || !data || !unit) {
    return (
      <AppLayout>
        <AppHeader
          title="Battery Unit"
          subtitle="Module not found for this device"
        />
        <div className="container mx-auto p-3 sm:p-6 space-y-4">
          <Button
            variant="ghost"
            onClick={() => navigate(`/devices/${deviceId}`)}
            className="gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Device
          </Button>
          <div className="glass-card p-6 rounded-xl border border-border/40">
            <p className="text-sm text-muted-foreground">
              Couldn't load unit {unitNumStr} for device {deviceId}. The
              module may be offline or its telemetry hasn't been received
              yet.
            </p>
          </div>
        </div>
      </AppLayout>
    );
  }

  const status: HealthStatus = unit.health?.status ?? "healthy";
  const statusMeta = STATUS_META[status];
  const StatusIcon = statusMeta.icon;

  const nameplate = unit.nameplate ?? {};
  const events = unit.events ?? {};
  const eventEntries = Object.entries(events).filter(([, v]) => v > 0);

  return (
    <AppLayout>
      <AppHeader
        title={`Battery Unit ${unit.unit}`}
        subtitle={
          nameplate.model
            ? `${nameplate.manufacturer ?? ""} ${nameplate.model}`.trim()
            : "Module detail analysis"
        }
      />

      <div className="container mx-auto p-3 sm:p-6 space-y-4 sm:space-y-6">
        {/* Back navigation */}
        <Button
          variant="ghost"
          onClick={() => navigate(`/devices/${deviceId}`)}
          className="gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Device
        </Button>

        {/* ─── Header card: identity + health verdict ────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            "glass-card rounded-xl p-4 sm:p-6 border ring-1 transition-all",
            statusMeta.ringClass,
          )}
        >
          <div className="flex flex-col lg:flex-row items-start gap-4 lg:gap-6">
            {/* Icon + title */}
            <div className="flex items-center gap-3 sm:gap-4">
              <div
                className={cn(
                  "w-14 h-14 sm:w-16 sm:h-16 rounded-xl flex items-center justify-center",
                  statusMeta.bgClass,
                )}
              >
                <Battery
                  className={cn("w-8 h-8 sm:w-10 sm:h-10", statusMeta.textClass)}
                />
              </div>
              <div>
                <h2 className="text-xl sm:text-2xl font-semibold text-foreground">
                  Unit {unit.unit}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {nameplate.model ?? "Battery module"}
                  {nameplate.barcode && (
                    <span className="ml-2 font-mono text-xs">
                      · {nameplate.barcode}
                    </span>
                  )}
                </p>
              </div>
            </div>

            {/* Status badge + summary */}
            <div className="lg:ml-auto flex items-start gap-3 sm:gap-4">
              <div
                className={cn(
                  "px-4 py-2 rounded-lg border inline-flex items-center gap-2",
                  statusMeta.bgClass,
                  statusMeta.textClass,
                  "border-current/20",
                )}
              >
                <StatusIcon className="w-5 h-5" />
                <div>
                  <p className="text-xs uppercase tracking-wider opacity-80">
                    Health
                  </p>
                  <p className="text-base sm:text-lg font-semibold leading-tight">
                    {statusMeta.label}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* ─── Live snapshot grid ─────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3">
          <StatCard
            icon={Zap}
            iconColor="text-battery"
            label="Voltage"
            value={formatMaybe(unit.voltage_v, 2, " V")}
          />
          <StatCard
            icon={unit.current_a != null && unit.current_a >= 0 ? BatteryCharging : BatteryLow}
            iconColor={unit.current_a != null && unit.current_a >= 0 ? "text-success" : "text-warning"}
            label="Current"
            value={formatMaybe(unit.current_a, 2, " A")}
            hint={
              unit.current_a != null
                ? unit.current_a >= 0
                  ? "Charging"
                  : "Discharging"
                : undefined
            }
          />
          <StatCard
            icon={Gauge}
            iconColor="text-solar"
            label="SOC"
            value={unit.soc_pct != null ? `${unit.soc_pct}%` : "—"}
          />
          <StatCard
            icon={Thermometer}
            iconColor={
              unit.temp_c != null && unit.temp_c > 42
                ? "text-destructive"
                : "text-muted-foreground"
            }
            label="Temperature"
            value={formatMaybe(unit.temp_c, 1, " °C")}
          />
          <StatCard
            icon={Activity}
            iconColor="text-solar"
            label="Power"
            value={
              unit.power_w != null
                ? Math.abs(unit.power_w) >= 1000
                  ? `${(unit.power_w / 1000).toFixed(2)} kW`
                  : `${unit.power_w.toFixed(0)} W`
                : "—"
            }
          />
          <StatCard
            icon={BatteryFull}
            iconColor="text-battery"
            label="Capacity"
            value={
              unit.remaining_ah != null && unit.total_ah != null
                ? `${unit.remaining_ah.toFixed(1)} / ${unit.total_ah.toFixed(0)} Ah`
                : unit.total_ah != null
                ? `${unit.total_ah.toFixed(0)} Ah`
                : "—"
            }
          />
        </div>

        {/* ─── Health verdict + concerns ─────────────────────────────── */}
        {unit.health && (
          <motion.section
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="glass-card rounded-xl p-4 sm:p-6 border border-border/40 space-y-4"
          >
            <div className="flex items-center gap-2">
              <span
                className={cn("w-2.5 h-2.5 rounded-full", statusMeta.dotClass)}
              />
              <h3 className="text-base sm:text-lg font-semibold text-foreground">
                Health assessment
              </h3>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
              <MetricCell
                label="SOH"
                value={
                  unit.soh_pct != null ? `${unit.soh_pct.toFixed(0)}%` : "—"
                }
                hint={
                  peerSummary?.sohMedian != null
                    ? `peer median ${peerSummary.sohMedian.toFixed(0)}%`
                    : undefined
                }
                accentClass={
                  unit.soh_pct == null
                    ? undefined
                    : unit.soh_pct === 0 || unit.soh_pct < 50
                    ? "text-destructive"
                    : unit.soh_pct < 80
                    ? "text-warning"
                    : "text-success"
                }
              />
              <MetricCell
                label="Cycles"
                value={
                  unit.cycle_count != null ? String(unit.cycle_count) : "—"
                }
                hint={
                  peerSummary?.cyclesMedian != null
                    ? `peer median ${peerSummary.cyclesMedian.toFixed(0)}`
                    : undefined
                }
              />
              <MetricCell
                label="Cell imbalance"
                value={
                  cellStats
                    ? `${cellStats.range.toFixed(0)} mV`
                    : "—"
                }
                accentClass={
                  cellStats
                    ? cellStats.range > 150
                      ? "text-destructive"
                      : cellStats.range > 50
                      ? "text-warning"
                      : "text-success"
                    : undefined
                }
              />
              <MetricCell
                label="Cells"
                value={
                  cellStats
                    ? `${cellStats.count}${
                        nameplate.cell_count
                          ? ` / ${nameplate.cell_count}`
                          : ""
                      }`
                    : "—"
                }
              />
              <MetricCell
                label="Temp Δ vs peers"
                value={
                  unit.temp_c != null && peerSummary?.tempMedian != null
                    ? `${(unit.temp_c - peerSummary.tempMedian).toFixed(1)} °C`
                    : "—"
                }
                accentClass={
                  unit.temp_c != null && peerSummary?.tempMedian != null
                    ? Math.abs(unit.temp_c - peerSummary.tempMedian) > 5
                      ? "text-warning"
                      : undefined
                    : undefined
                }
              />
            </div>

            {unit.health.concerns.length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-success">
                <CheckCircle2 className="w-4 h-4" />
                No issues detected — module operating within normal parameters.
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-foreground mb-2">
                  Concerns detected
                </p>
                <ul className="space-y-1.5">
                  {unit.health.concerns.map((c, i) => (
                    <li
                      key={i}
                      className={cn(
                        "flex items-start gap-2 text-sm rounded-md px-3 py-2 border",
                        statusMeta.bgClass,
                        "border-current/20",
                        statusMeta.textClass,
                      )}
                    >
                      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                      <span className="text-foreground/90">{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </motion.section>
        )}

        {/* ─── Today's energy (kWh) ───────────────────────────────────── */}
        {energy && (energy.units[String(unit.unit)] || energy.device) && (
          <motion.section
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="glass-card rounded-xl p-4 sm:p-6 border border-border/40 space-y-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Activity className="w-4 h-4 text-solar" />
              <h3 className="text-base sm:text-lg font-semibold text-foreground">
                Energy today
              </h3>
              <span className="ml-auto text-xs text-muted-foreground">
                {energy.timezone
                  ? `Local day (${energy.timezone})`
                  : "Today"}
              </span>
            </div>
            <EnergyCardGroup
              unitEntry={energy.units[String(unit.unit)]}
              bankEntry={energy.device}
              unitLabel={`Unit ${unit.unit}`}
            />
          </motion.section>
        )}

        {/* ─── Cell voltage strip ─────────────────────────────────────── */}
        {unitCells.length > 0 && cellStats && (
          <motion.section
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card rounded-xl p-4 sm:p-6 border border-border/40 space-y-4"
          >
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-battery" />
              <h3 className="text-base sm:text-lg font-semibold text-foreground">
                Cell voltages
              </h3>
              <span className="ml-auto text-xs text-muted-foreground">
                min <span className="font-mono">{cellStats.min}</span> · avg{" "}
                <span className="font-mono">{cellStats.avg.toFixed(0)}</span> ·
                max <span className="font-mono">{cellStats.max}</span> · Δ{" "}
                <span className="font-mono">{cellStats.range}</span> mV
              </span>
            </div>
            <CellVoltageChart cells={unitCells} avgMv={cellStats.avg} />
          </motion.section>
        )}

        {/* ─── Event counters ─────────────────────────────────────────── */}
        {eventEntries.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card rounded-xl p-4 sm:p-6 border border-border/40 space-y-4"
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-warning" />
              <h3 className="text-base sm:text-lg font-semibold text-foreground">
                Event counters
              </h3>
              <span className="ml-auto text-xs text-muted-foreground">
                Lifetime events since manufacture · zero counters hidden
              </span>
            </div>
            <EventCountersTable events={events} />
          </motion.section>
        )}

        {/* ─── Peer comparison ────────────────────────────────────────── */}
        {peerSummary && peerSummary.unitCount > 1 && (
          <motion.section
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card rounded-xl p-4 sm:p-6 border border-border/40 space-y-4"
          >
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-primary" />
              <h3 className="text-base sm:text-lg font-semibold text-foreground">
                Comparison with peer modules
              </h3>
              <span className="ml-auto text-xs text-muted-foreground">
                {peerSummary.unitCount - 1} peer module(s) in bank
              </span>
            </div>
            <PeerComparisonTable unit={unit} peer={peerSummary} />
          </motion.section>
        )}

        {/* ─── Nameplate ──────────────────────────────────────────────── */}
        {Object.keys(nameplate).length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="glass-card rounded-xl p-4 sm:p-6 border border-border/40 space-y-4"
          >
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-muted-foreground" />
              <h3 className="text-base sm:text-lg font-semibold text-foreground">
                Nameplate
              </h3>
            </div>
            <NameplateGrid nameplate={nameplate} />
          </motion.section>
        )}
      </div>
    </AppLayout>
  );
}

// ─── Presentational subcomponents ─────────────────────────────────────────

function StatCard({
  icon: Icon,
  iconColor,
  label,
  value,
  hint,
}: {
  icon: typeof Zap;
  iconColor: string;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="glass-card p-3 rounded-lg border border-border/40 space-y-1.5">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className={cn("w-3.5 h-3.5", iconColor)} />
        <span className="truncate">{label}</span>
      </div>
      <p className="text-lg sm:text-xl font-mono font-semibold text-foreground truncate">
        {value}
      </p>
      {hint && (
        <p className="text-[10px] text-muted-foreground truncate">{hint}</p>
      )}
    </div>
  );
}

function EnergyCardGroup({
  unitEntry,
  bankEntry,
  unitLabel,
}: {
  unitEntry?: EnergyEntry;
  bankEntry?: EnergyEntry | null;
  unitLabel: string;
}) {
  const rows: Array<{ label: string; entry?: EnergyEntry; muted?: boolean }> = [];
  if (unitEntry) rows.push({ label: unitLabel, entry: unitEntry });
  if (bankEntry) rows.push({ label: "Whole bank", entry: bankEntry, muted: true });

  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.label} className="space-y-1.5">
          <div className="flex items-center gap-2">
            <p
              className={cn(
                "text-xs font-medium",
                r.muted ? "text-muted-foreground" : "text-foreground",
              )}
            >
              {r.label}
            </p>
            {r.entry && r.entry.coverage_pct < 90 && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-warning/10 text-warning border border-warning/20">
                <AlertTriangle className="w-2.5 h-2.5" />
                Partial ({r.entry.coverage_pct.toFixed(0)}% coverage)
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            <EnergyTile
              icon={BatteryCharging}
              iconColor="text-success"
              label="Charged in"
              value={r.entry ? r.entry.charge_kwh : undefined}
            />
            <EnergyTile
              icon={BatteryLow}
              iconColor="text-warning"
              label="Discharged out"
              value={r.entry ? r.entry.discharge_kwh : undefined}
            />
            <EnergyTile
              icon={Activity}
              iconColor="text-primary"
              label="Net"
              value={
                r.entry ? r.entry.charge_kwh - r.entry.discharge_kwh : undefined
              }
              signed
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function EnergyTile({
  icon: Icon,
  iconColor,
  label,
  value,
  signed = false,
}: {
  icon: typeof BatteryCharging;
  iconColor: string;
  label: string;
  value?: number;
  signed?: boolean;
}) {
  const text =
    value == null
      ? "—"
      : `${signed && value > 0 ? "+" : ""}${value.toFixed(2)} kWh`;
  const colourClass =
    signed && value != null
      ? value > 0
        ? "text-success"
        : value < 0
        ? "text-warning"
        : "text-foreground"
      : "text-foreground";
  return (
    <div className="rounded-md border border-border/40 bg-secondary/20 px-3 py-2">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className={cn("w-3.5 h-3.5", iconColor)} />
        <span className="truncate">{label}</span>
      </div>
      <p className={cn("text-lg sm:text-xl font-mono font-semibold", colourClass)}>
        {text}
      </p>
    </div>
  );
}

function MetricCell({
  label,
  value,
  hint,
  accentClass,
}: {
  label: string;
  value: string;
  hint?: string;
  accentClass?: string;
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-secondary/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "text-base sm:text-lg font-mono font-semibold",
          accentClass ?? "text-foreground",
        )}
      >
        {value}
      </p>
      {hint && (
        <p className="text-[10px] text-muted-foreground mt-0.5 truncate">
          {hint}
        </p>
      )}
    </div>
  );
}

function CellVoltageChart({
  cells,
  avgMv,
}: {
  cells: CellDatum[];
  avgMv: number;
}) {
  const chartData = cells
    .slice()
    .sort((a, b) => a.cell - b.cell)
    .map((c) => ({
      cell: c.cell,
      mv: Math.round((c.voltage_v ?? 0) * 1000),
    }));
  const min = Math.min(...chartData.map((d) => d.mv));
  const max = Math.max(...chartData.map((d) => d.mv));
  const yMin = Math.floor((min - 20) / 10) * 10;
  const yMax = Math.ceil((max + 20) / 10) * 10;

  const colorFor = (mv: number): string => {
    // Colour cells by deviation from module average.
    const delta = Math.abs(mv - avgMv);
    if (delta > 100) return "hsl(var(--destructive))";
    if (delta > 50) return "hsl(var(--warning))";
    return "hsl(var(--battery))";
  };

  return (
    <div className="w-full h-48 sm:h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.4)" />
          <XAxis
            dataKey="cell"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            axisLine={{ stroke: "hsl(var(--border))" }}
          />
          <YAxis
            domain={[yMin, yMax]}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickFormatter={(v) => `${v}`}
            width={48}
          />
          <RechartsTooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(v: number) => [`${v} mV`, "voltage"]}
            labelFormatter={(label) => `Cell ${label}`}
          />
          <ReferenceLine
            y={avgMv}
            stroke="hsl(var(--muted-foreground))"
            strokeDasharray="4 4"
            label={{
              value: "avg",
              fill: "hsl(var(--muted-foreground))",
              fontSize: 10,
              position: "insideTopRight",
            }}
          />
          <Bar dataKey="mv" radius={[3, 3, 0, 0]}>
            {chartData.map((d) => (
              <Cell key={d.cell} fill={colorFor(d.mv)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function EventCountersTable({ events }: { events: UnitEvents }) {
  const rows = Object.entries(events)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({
      key: k,
      label: EVENT_LABELS[k] ?? k,
      value: v,
      severity: EVENT_SEVERITY[k] ?? "info",
    }))
    .sort((a, b) => {
      // Critical first, then warning, then info; within group by count.
      const order = { critical: 0, warning: 1, info: 2 };
      return (
        order[a.severity] - order[b.severity] || b.value - a.value
      );
    });

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
      {rows.map((row) => (
        <div
          key={row.key}
          className={cn(
            "flex items-center justify-between rounded-md border px-3 py-2",
            SEVERITY_META[row.severity].className,
          )}
        >
          <div className="min-w-0">
            <p className="text-xs font-medium truncate text-foreground/90">
              {row.label}
            </p>
            <p className="text-[10px] uppercase tracking-wider opacity-70">
              {SEVERITY_META[row.severity].label}
            </p>
          </div>
          <span className="font-mono text-sm font-semibold shrink-0 ml-2">
            {row.value.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

function PeerComparisonTable({
  unit,
  peer,
}: {
  unit: Unit;
  peer: PeerSummary;
}) {
  const rows = [
    { label: "SOC", value: unit.soc_pct, median: peer.socMedian, unit: "%" },
    { label: "SOH", value: unit.soh_pct, median: peer.sohMedian, unit: "%" },
    { label: "Cycles", value: unit.cycle_count, median: peer.cyclesMedian, unit: "" },
    { label: "Temperature", value: unit.temp_c, median: peer.tempMedian, unit: " °C" },
  ];

  return (
    <div className="overflow-x-auto -mx-2 sm:mx-0">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border/40">
            <th className="text-left px-2 sm:px-3 py-2">Metric</th>
            <th className="text-right px-2 sm:px-3 py-2">This unit</th>
            <th className="text-right px-2 sm:px-3 py-2">Peer median</th>
            <th className="text-right px-2 sm:px-3 py-2">Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const delta =
              row.value != null && row.median != null
                ? row.value - row.median
                : null;
            const deltaClass =
              delta == null
                ? "text-muted-foreground"
                : Math.abs(delta) < 1
                ? "text-muted-foreground"
                : row.label === "Temperature"
                ? delta > 0
                  ? "text-warning"
                  : "text-primary"
                : row.label === "Cycles"
                ? delta > 0
                  ? "text-warning"
                  : "text-success"
                : delta < 0
                ? "text-warning"
                : "text-success";
            return (
              <tr
                key={row.label}
                className="border-b border-border/20 last:border-b-0"
              >
                <td className="px-2 sm:px-3 py-2 text-foreground">
                  {row.label}
                </td>
                <td className="px-2 sm:px-3 py-2 text-right font-mono">
                  {formatMaybe(row.value, row.unit === "" ? 0 : 1, row.unit)}
                </td>
                <td className="px-2 sm:px-3 py-2 text-right font-mono text-muted-foreground">
                  {formatMaybe(row.median, row.unit === "" ? 0 : 1, row.unit)}
                </td>
                <td
                  className={cn(
                    "px-2 sm:px-3 py-2 text-right font-mono",
                    deltaClass,
                  )}
                >
                  {delta == null
                    ? "—"
                    : `${delta > 0 ? "+" : ""}${delta.toFixed(
                        row.unit === "" ? 0 : 1,
                      )}${row.unit}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function NameplateGrid({ nameplate }: { nameplate: UnitNameplate }) {
  const rows: Array<{ label: string; value?: string | number }> = [
    { label: "Manufacturer", value: nameplate.manufacturer },
    { label: "Model", value: nameplate.model },
    { label: "Specification", value: nameplate.specification },
    {
      label: "Rated capacity",
      value:
        nameplate.rated_ah != null
          ? `${nameplate.rated_ah} Ah`
          : undefined,
    },
    { label: "Cell count", value: nameplate.cell_count },
    {
      label: "Max charge",
      value:
        nameplate.max_charge_a != null
          ? `${nameplate.max_charge_a} A`
          : undefined,
    },
    {
      label: "Max discharge",
      value:
        nameplate.max_discharge_a != null
          ? `${Math.abs(nameplate.max_discharge_a)} A`
          : undefined,
    },
    { label: "Board version", value: nameplate.board_version },
    { label: "Board", value: nameplate.board },
    { label: "Main soft version", value: nameplate.main_soft_version },
    { label: "Soft version", value: nameplate.soft_version },
    { label: "Boot version", value: nameplate.boot_version },
    { label: "Comm version", value: nameplate.comm_version },
    { label: "Release date", value: nameplate.release_date },
    { label: "Barcode", value: nameplate.barcode },
  ].filter((r) => r.value !== undefined && r.value !== "");

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
      {rows.map((row) => (
        <div
          key={row.label}
          className="rounded-md border border-border/40 bg-secondary/20 px-3 py-2"
        >
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {row.label}
          </p>
          <p className="text-sm font-mono text-foreground break-all">
            {row.value}
          </p>
        </div>
      ))}
    </div>
  );
}
