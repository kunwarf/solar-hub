import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Thermometer, Zap, Battery, Activity, AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import CellHealthPanel, { CellHealthReport } from "./CellHealthPanel";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import { devicesService } from "@/api/services/devices.service";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CellData {
  id: number;
  voltage: number;
  temperature: number;
  soc: number;
  health: number;
  status: "normal" | "warning" | "critical" | "balancing";
}

interface UnitData {
  unit: number;
  voltage_v?: number;
  current_a?: number;
  soc_pct?: number;
  temp_c?: number;
  soh_pct?: number;
  cycle_count?: number;
  power_w?: number;
  basic_status?: string;
  has_alarm?: boolean;
  has_fault?: boolean;
}

interface RawCellData {
  unit: number;
  cell: number;
  voltage_v?: number;
  current_a?: number;
  temperature?: number;
  soc?: number;
  basic_st?: string;
  volt_st?: string;
  curr_st?: string;
  temp_st?: string;
}

interface BankData {
  soc_pct?: number;
  voltage_v?: number;
  current_a?: number;
  charging?: boolean;
  power_w?: number;
  temp_c?: number;
  soh_pct?: number;
  cycle_count?: number;
  units_count?: number;
  has_alarm?: boolean;
  alarms?: string[];
}

interface BatteryBankResponse {
  device_id: string;
  serial_number: string;
  available: boolean;
  timestamp?: string;
  bank: BankData;
  units: UnitData[];
  cells: RawCellData[];
  cell_health?: CellHealthReport | null;
}

interface DeviceTelemetry {
  serial_number: string;
  pv_power_w: number;
  grid_power_w: number;
  load_power_w: number;
  battery_power_w: number;
  battery_soc_pct: number;
  is_charging: boolean;
  online: boolean;
}

interface BatteryCellGridProps {
  device?: {
    id: string;
    name: string;
  };
  telemetry?: DeviceTelemetry | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Map a raw cell from the backend to the CellData shape the UI expects.
 * Status is derived from voltage/temperature thresholds and status strings.
 */
function mapRawCell(raw: RawCellData, unitIndex: number, unitData?: UnitData): CellData {
  const voltage = raw.voltage_v ?? 0;
  // Pylontech only provides temperature and SOC at unit level, not per-cell
  const temp = raw.temperature ?? unitData?.temp_c ?? 0;
  const soc = raw.soc ?? unitData?.soc_pct ?? 0;

  const statusStr = (raw.basic_st ?? raw.volt_st ?? "Normal").toLowerCase();
  let status: CellData["status"] = "normal";
  if (statusStr.includes("fault") || statusStr.includes("error") || voltage < 2.9 || temp > 50) {
    status = "critical";
  } else if (statusStr.includes("warn") || voltage < 3.1 || temp > 42) {
    status = "warning";
  } else if (statusStr.includes("balance") || statusStr.includes("bal")) {
    status = "balancing";
  }

  return {
    id: raw.unit * 100 + raw.cell,
    voltage,
    temperature: temp,
    soc,
    health: 100,
    status,
  };
}

const getStatusColor = (status: CellData["status"]) => {
  switch (status) {
    case "critical":  return "text-destructive";
    case "warning":   return "text-warning";
    case "balancing": return "text-blue-400";
    default:          return "text-battery";
  }
};

const getStatusBorderColor = (status: CellData["status"]) => {
  switch (status) {
    case "critical":  return "#ef4444";
    case "warning":   return "#f59e0b";
    case "balancing": return "#60a5fa";
    default:          return "#22c55e";
  }
};

const getFillColor = (status: CellData["status"]) => {
  switch (status) {
    case "critical":  return "#ef4444";
    case "warning":   return "#f59e0b";
    case "balancing": return "#60a5fa";
    default:          return "#22c55e";
  }
};

const getVoltageColor = (voltage: number) => {
  if (voltage < 3.0) return "text-destructive";
  if (voltage < 3.2) return "text-warning";
  return "text-battery";
};

const getTempColor = (temp: number) => {
  if (temp > 45) return "text-destructive";
  if (temp > 38) return "text-warning";
  return "text-muted-foreground";
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const CellVisual = ({ cell, index }: { cell: CellData; index: number }) => {
  const fillPercent = cell.soc;
  const borderColor = getStatusBorderColor(cell.status);
  const fillColor = getFillColor(cell.status);

  return (
    <TooltipProvider>
      <Tooltip delayDuration={100}>
        <TooltipTrigger asChild>
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.015, duration: 0.2 }}
            className={cn(
              "relative cursor-pointer transition-all hover:scale-110 hover:z-10 flex flex-col items-center",
              cell.status === "balancing" && "animate-pulse"
            )}
          >
            <svg viewBox="0 0 24 40" className="w-full h-10" fill="none">
              <rect x="8" y="0" width="8" height="3" rx="1" fill={borderColor} opacity="0.8" />
              <rect x="2" y="4" width="20" height="34" rx="3" stroke={borderColor} strokeWidth="1.5" fill="transparent" />
              <motion.rect
                x="4" width="16" rx="2" fill={fillColor} opacity="0.7"
                initial={{ y: 36, height: 0 }}
                animate={{ y: 6 + (30 * (1 - fillPercent / 100)), height: 30 * (fillPercent / 100) }}
                transition={{ delay: index * 0.015 + 0.1, duration: 0.4, ease: "easeOut" }}
              />
              <text x="12" y="24" textAnchor="middle" dominantBaseline="middle"
                fill="currentColor" className="fill-foreground" style={{ fontSize: '8px' }}>
                {index + 1}
              </text>
              {cell.status !== "normal" && (
                <circle cx="18" cy="8" r="2.5" fill={borderColor}
                  className={cell.status === "critical" ? "animate-ping" : ""} />
              )}
            </svg>
            <span className={cn("text-[6px] sm:text-[7px] font-mono leading-none mt-0.5", getVoltageColor(cell.voltage))}>
              {cell.voltage > 0 ? `${cell.voltage.toFixed(2)}V` : "--"}
            </span>
          </motion.div>
        </TooltipTrigger>
        <TooltipContent side="top" className="bg-card border-border p-3">
          <div className="space-y-2">
            <p className="font-semibold text-foreground">Cell #{index + 1}</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <div className="flex items-center gap-1">
                <Zap className={cn("w-3 h-3", getVoltageColor(cell.voltage))} />
                <span className="text-muted-foreground">Voltage:</span>
              </div>
              <span className={cn("font-mono", getVoltageColor(cell.voltage))}>{cell.voltage}V</span>
              <div className="flex items-center gap-1">
                <Thermometer className={cn("w-3 h-3", getTempColor(cell.temperature))} />
                <span className="text-muted-foreground">Unit Temp:</span>
              </div>
              <span className={cn("font-mono", getTempColor(cell.temperature))}>
                {cell.temperature > 0 ? `${cell.temperature}°C` : "—"}
              </span>
              <div className="flex items-center gap-1">
                <Battery className="w-3 h-3 text-battery" />
                <span className="text-muted-foreground">Unit SOC:</span>
              </div>
              <span className="font-mono text-battery">{cell.soc}%</span>
              <span className="text-muted-foreground">Status:</span>
              <span className={cn(
                "capitalize font-medium",
                cell.status === "critical" && "text-destructive",
                cell.status === "warning" && "text-warning",
                cell.status === "balancing" && "text-blue-400",
                cell.status === "normal" && "text-success"
              )}>{cell.status}</span>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

const PackStats = ({ cells }: { cells: CellData[] }) => {
  if (!cells.length) return null;
  const avgVoltage = cells.reduce((s, c) => s + c.voltage, 0) / cells.length;
  const avgTemp = cells.reduce((s, c) => s + c.temperature, 0) / cells.length;
  const avgSoc = cells.reduce((s, c) => s + c.soc, 0) / cells.length;
  const minV = Math.min(...cells.map(c => c.voltage));
  const maxV = Math.max(...cells.map(c => c.voltage));
  const deltaV = maxV - minV;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 sm:gap-2 mt-2 sm:mt-3">
      <div className="bg-secondary/30 rounded-md px-1.5 sm:px-2 py-1 sm:py-1.5">
        <p className="text-[8px] sm:text-[10px] text-muted-foreground uppercase tracking-wider">Avg V</p>
        <p className="text-xs sm:text-sm font-mono font-bold text-foreground">{avgVoltage.toFixed(3)}V</p>
      </div>
      <div className="bg-secondary/30 rounded-md px-1.5 sm:px-2 py-1 sm:py-1.5">
        <p className="text-[8px] sm:text-[10px] text-muted-foreground uppercase tracking-wider">Delta</p>
        <p className={cn("text-xs sm:text-sm font-mono font-bold", deltaV > 0.1 ? "text-warning" : "text-success")}>
          {(deltaV * 1000).toFixed(0)}mV
        </p>
      </div>
      <div className="bg-secondary/30 rounded-md px-1.5 sm:px-2 py-1 sm:py-1.5">
        <p className="text-[8px] sm:text-[10px] text-muted-foreground uppercase tracking-wider">Temp</p>
        <p className={cn("text-xs sm:text-sm font-mono font-bold", avgTemp > 40 ? "text-warning" : "text-foreground")}>
          {avgTemp.toFixed(1)}°C
        </p>
      </div>
      <div className="bg-secondary/30 rounded-md px-1.5 sm:px-2 py-1 sm:py-1.5">
        <p className="text-[8px] sm:text-[10px] text-muted-foreground uppercase tracking-wider">SOC</p>
        <p className="text-xs sm:text-sm font-mono font-bold text-battery">{avgSoc.toFixed(1)}%</p>
      </div>
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────

const BatteryCellGrid = ({ device, telemetry }: BatteryCellGridProps) => {
  // ── SOC history for chart (accumulate last 24 points) ──────────────────────
  const [socHistory, setSocHistory] = useState<
    { time: string; soc: number; power: number; temperature: number }[]
  >([]);

  // ── Fetch battery bank data ────────────────────────────────────────────────
  const { data: bankResponse } = useQuery<BatteryBankResponse | null>({
    queryKey: ["battery-bank", device?.id],
    queryFn: () => (device?.id ? devicesService.getBatteryBank(device.id) : null),
    enabled: !!device?.id,
    refetchInterval: 30_000,
  });

  // ── Accumulate history when telemetry updates ──────────────────────────────
  useEffect(() => {
    if (!telemetry) return;
    const now = new Date();
    const label = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`;
    setSocHistory(prev => {
      const next = [
        ...prev,
        {
          time: label,
          soc: telemetry.battery_soc_pct ?? 0,
          power: (telemetry.battery_power_w ?? 0) / 1000,
          temperature: bankResponse?.bank?.temp_c ?? 0,
        },
      ].slice(-24);
      return next;
    });
  }, [telemetry, bankResponse]);

  // ── Derive display values ──────────────────────────────────────────────────
  const bank = bankResponse?.bank ?? {};
  const units = bankResponse?.units ?? [];
  const rawCells = bankResponse?.cells ?? [];

  const soc = bank.soc_pct ?? telemetry?.battery_soc_pct ?? 0;
  const voltage = bank.voltage_v ?? 0;
  const current = bank.current_a ?? 0;
  const powerKw = ((bank.power_w ?? telemetry?.battery_power_w ?? 0) / 1000);
  const isCharging = bank.charging ?? telemetry?.is_charging ?? powerKw > 0;
  const temp = bank.temp_c ?? 0;
  const soh = bank.soh_pct ?? 0;
  const cycles = bank.cycle_count ?? 0;
  const hasAlarm = bank.has_alarm ?? false;
  const alarms = bank.alarms ?? [];

  // Group cells by unit for the cell grid
  const cellsByUnit = units.map(u => {
    const cells = rawCells
      .filter(c => c.unit === u.unit)
      .map((c, i) => mapRawCell(c, i, u));
    return { unit: u, cells };
  });

  // Fallback: if no units at all, show a minimal view
  const hasBankDetail = bankResponse?.available && units.length > 0;

  return (
    <div className="space-y-6">
      {/* Alarm banner */}
      {hasAlarm && alarms.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-3 border border-destructive/40 bg-destructive/5"
        >
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="w-4 h-4 text-destructive" />
            <span className="font-semibold text-destructive text-sm">Battery Alarms</span>
          </div>
          <ul className="text-xs text-destructive/80 space-y-0.5 ml-6">
            {alarms.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </motion.div>
      )}

      {/* Candidate cells for inspection (snapshot detector) */}
      <CellHealthPanel report={bankResponse?.cell_health ?? null} />

      {/* Battery Pack Summary */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-3 sm:p-5"
      >
        <h3 className="text-base sm:text-lg font-semibold text-foreground mb-3 sm:mb-4">Battery Pack Status</h3>
        <div className="grid grid-cols-4 sm:grid-cols-4 lg:grid-cols-8 gap-2 sm:gap-4">
          {[
            { label: "Volt",   icon: <Zap className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-battery" />,       value: voltage ? `${voltage.toFixed(1)}V` : "—",         color: "" },
            { label: "Amp",    icon: <Activity className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-success" />,   value: current ? `${isCharging ? "+" : ""}${current.toFixed(1)}A` : "—", color: "text-success" },
            { label: "Power",  icon: <Zap className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-solar" />,          value: `${Math.abs(powerKw).toFixed(2)}kW`,              color: "text-solar" },
            { label: "SOC",    icon: <Battery className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-battery" />,   value: `${Math.round(soc)}%`,                             color: "text-battery" },
            { label: "Health", icon: <Activity className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-primary" />,  value: soh ? `${soh.toFixed(1)}%` : "—",                 color: "" },
            { label: "Cycles", icon: <Activity className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-muted-foreground" />, value: cycles ? `${cycles}` : "—",               color: "" },
            { label: "Temp",   icon: <Thermometer className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-warning" />, value: temp ? `${temp.toFixed(1)}°` : "—",            color: "" },
            { label: "Status", icon: <Battery className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-success" />,   value: isCharging ? "Charging" : "Discharging",         color: "text-success capitalize" },
          ].map(({ label, icon, value, color }) => (
            <div key={label} className="bg-secondary/30 rounded-lg p-2 sm:p-3">
              <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
                {icon}
                <span className="text-[9px] sm:text-xs text-muted-foreground">{label}</span>
              </div>
              <p className={cn("text-sm sm:text-lg font-mono font-bold text-foreground", color)}>{value}</p>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Cell Grid — only shown when Pylontech bank data is available */}
      {hasBankDetail && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-3 sm:p-5"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 sm:mb-4">
            <div>
              <h3 className="text-base sm:text-lg font-semibold text-foreground">Cell Monitor</h3>
              <p className="text-xs sm:text-sm text-muted-foreground">Individual cell status</p>
            </div>
            <div className="flex items-center gap-2 sm:gap-3 text-[10px] sm:text-xs overflow-x-auto pb-1">
              {[
                { color: "#22c55e", label: "OK" },
                { color: "#60a5fa", label: "Bal" },
                { color: "#f59e0b", label: "Warn" },
                { color: "#ef4444", label: "Crit" },
              ].map(({ color, label }) => (
                <div key={label} className="flex items-center gap-1 shrink-0">
                  <svg viewBox="0 0 24 40" className="w-2.5 h-4 sm:w-3 sm:h-5" fill="none">
                    <rect x="8" y="0" width="8" height="3" rx="1" fill={color} opacity="0.8" />
                    <rect x="2" y="4" width="20" height="34" rx="3" stroke={color} strokeWidth="1.5" fill="transparent" />
                    <rect x="4" y="16" width="16" height="20" rx="2" fill={color} opacity="0.7" />
                  </svg>
                  <span className="text-muted-foreground">{label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-3 sm:space-y-4">
            {cellsByUnit.map(({ unit: u, cells }) => (
              <div key={u.unit} className="border border-border/50 rounded-lg p-2 sm:p-3 bg-secondary/10">
                {/* Unit header row */}
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <Battery className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-battery shrink-0" />
                  <h4 className="font-medium text-xs sm:text-sm text-foreground">Unit {u.unit}</h4>
                  {cells.length > 0 && (
                    <span className="text-[10px] sm:text-xs text-muted-foreground">({cells.length} cells)</span>
                  )}
                  {u.has_alarm && (
                    <AlertTriangle className="w-3 h-3 text-destructive" />
                  )}

                  {/* Right-side unit stats */}
                  <div className="ml-auto flex items-center gap-1.5 flex-wrap justify-end">
                    {/* Charge / Discharge badge */}
                    {u.current_a != null && (
                      <span className={cn(
                        "inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] sm:text-[10px] font-semibold",
                        u.current_a >= 0
                          ? "bg-success/10 text-success border border-success/20"
                          : "bg-warning/10 text-warning border border-warning/20"
                      )}>
                        {u.current_a >= 0
                          ? <TrendingUp className="w-2.5 h-2.5" />
                          : <TrendingDown className="w-2.5 h-2.5" />
                        }
                        {u.current_a >= 0 ? "Charging" : "Discharging"}
                      </span>
                    )}
                    {/* Unit pack voltage */}
                    {u.voltage_v != null && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] sm:text-[10px] font-mono font-semibold bg-secondary/50 text-foreground border border-border/50">
                        <Zap className="w-2.5 h-2.5 text-battery" />
                        {u.voltage_v.toFixed(2)}V
                      </span>
                    )}
                    {/* Unit power */}
                    {u.power_w != null && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] sm:text-[10px] font-mono font-semibold bg-secondary/50 text-solar border border-border/50">
                        <Activity className="w-2.5 h-2.5" />
                        {Math.abs(u.power_w) >= 1000
                          ? `${(Math.abs(u.power_w) / 1000).toFixed(2)}kW`
                          : `${Math.abs(u.power_w).toFixed(0)}W`}
                      </span>
                    )}
                    {/* SOC / SOH / cycles */}
                    {u.soc_pct != null && (
                      <span className="text-[9px] sm:text-[10px] text-battery font-medium">SOC {u.soc_pct}%</span>
                    )}
                    {u.soh_pct != null && (
                      <span className="text-[9px] sm:text-[10px] text-muted-foreground">SOH {u.soh_pct.toFixed(0)}%</span>
                    )}
                    {u.cycle_count != null && (
                      <span className="text-[9px] sm:text-[10px] text-muted-foreground">{u.cycle_count} cyc</span>
                    )}
                  </div>
                </div>

                {cells.length > 0 ? (
                  <>
                    <div className="grid grid-cols-8 sm:grid-cols-16 gap-0.5 sm:gap-1">
                      {cells.map((cell, idx) => (
                        <CellVisual key={cell.id} cell={cell} index={idx} />
                      ))}
                    </div>
                    <PackStats cells={cells} />
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground">No cell data available for this unit</p>
                )}
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* SOC & Power history */}
      {socHistory.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card p-3 sm:p-5"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 sm:mb-4">
            <div>
              <h3 className="text-base sm:text-lg font-semibold text-foreground">SOC & Power</h3>
              <p className="text-xs sm:text-sm text-muted-foreground">Live history (last {socHistory.length} readings)</p>
            </div>
            <div className="flex items-center gap-2 sm:gap-4 text-[10px] sm:text-xs">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-battery" />
                <span className="text-muted-foreground">SOC</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-solar" />
                <span className="text-muted-foreground">Power</span>
              </div>
            </div>
          </div>
          <div className="h-[150px] sm:h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={socHistory}>
                <defs>
                  <linearGradient id="socGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--battery))" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(var(--battery))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={9} tickLine={false} interval="preserveStartEnd" />
                <YAxis yAxisId="left" stroke="hsl(var(--muted-foreground))" fontSize={9} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={v => `${v}%`} width={30} />
                <YAxis yAxisId="right" orientation="right" stroke="hsl(var(--muted-foreground))" fontSize={9} tickLine={false} axisLine={false} tickFormatter={v => `${v}kW`} width={35} />
                <RechartsTooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "11px" }} />
                <Area yAxisId="left" type="monotone" dataKey="soc" stroke="hsl(var(--battery))" fill="url(#socGradient)" strokeWidth={2} name="SOC" />
                <Line yAxisId="right" type="monotone" dataKey="power" stroke="hsl(var(--solar))" strokeWidth={2} dot={false} name="Power" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      )}

      {/* Temperature history */}
      {socHistory.length > 0 && temp > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card p-3 sm:p-5"
        >
          <div className="mb-3 sm:mb-4">
            <h3 className="text-base sm:text-lg font-semibold text-foreground">Temperature</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">Live thermal history</p>
          </div>
          <div className="h-[120px] sm:h-[150px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={socHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={9} tickLine={false} interval="preserveStartEnd" />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={9} tickLine={false} axisLine={false} tickFormatter={v => `${v}°`} width={25} />
                <RechartsTooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "11px" }} />
                <Line type="monotone" dataKey="temperature" stroke="hsl(var(--warning))" strokeWidth={2} dot={false} name="Temperature" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default BatteryCellGrid;
