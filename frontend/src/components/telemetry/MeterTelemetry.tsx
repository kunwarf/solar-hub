/**
 * ⚠️ WARNING: MOCK DATA COMPONENT ⚠️
 *
 * This component uses 100% HARDCODED/GENERATED MOCK DATA:
 * - Phase data (Voltage, Current, Power, PF) is completely fabricated
 * - Historical data is generated using sine wave formulas
 * - Today's cumulative stats are hardcoded values
 *
 * TODO: Replace with real meter API integration
 * - Connect to actual meter telemetry endpoints
 * - Use real-time phase measurements
 * - Fetch historical import/export data from System B
 */

import { motion } from "framer-motion";
import { Zap, ArrowUpRight, ArrowDownLeft, Activity, Gauge, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

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

interface MeterTelemetryProps {
  device: {
    id: string;
    name: string;
    metrics: { label: string; value: string; unit: string }[];
  };
  telemetry?: DeviceTelemetry | null;
}

// Phase data
const phaseData = [
  {
    phase: "L1",
    voltage: 238.2,
    current: 12.4,
    power: 2.85,
    powerFactor: 0.97,
    direction: "import" as const,
    frequency: 50.01,
  },
  {
    phase: "L2",
    voltage: 236.8,
    current: 8.6,
    power: 1.92,
    powerFactor: 0.95,
    direction: "export" as const,
    frequency: 50.02,
  },
  {
    phase: "L3",
    voltage: 239.1,
    current: 10.2,
    power: 2.31,
    powerFactor: 0.96,
    direction: "import" as const,
    frequency: 50.01,
  },
];

// Historical import/export data
const generateHistoricalData = () => {
  return Array.from({ length: 24 }, (_, i) => {
    const hour = i;
    const sunIntensity = Math.max(0, Math.sin((hour - 6) * Math.PI / 12));
    const baseConsumption = 3 + (hour >= 18 && hour <= 22 ? 3 : 0) + (hour >= 7 && hour <= 9 ? 1.5 : 0);
    const solarProduction = sunIntensity * 12;
    const netPower = baseConsumption - solarProduction;
    
    return {
      time: `${hour.toString().padStart(2, "0")}:00`,
      import: Math.max(0, netPower + Math.random() * 0.5),
      export: Math.max(0, -netPower + Math.random() * 0.5),
      consumption: baseConsumption + Math.random() * 0.5,
    };
  });
};

const historicalData = generateHistoricalData();

// Cumulative data for today
const todayStats = {
  totalImport: 12.4,
  totalExport: 8.6,
  peakImport: 4.2,
  peakExport: 6.8,
  netEnergy: -3.8, // negative = net export
};

const PhaseCard = ({ data, index }: { data: typeof phaseData[0]; index: number }) => (
  <motion.div
    initial={{ opacity: 0, x: -20 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ delay: index * 0.1 }}
    className="bg-secondary/30 rounded-xl p-3 sm:p-4 border border-border/50"
  >
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <div className={cn(
          "w-10 h-10 rounded-lg flex items-center justify-center font-bold text-lg",
          index === 0 && "bg-red-500/20 text-red-400",
          index === 1 && "bg-yellow-500/20 text-yellow-400",
          index === 2 && "bg-blue-500/20 text-blue-400"
        )}>
          {data.phase}
        </div>
        <span className="text-sm text-muted-foreground">Phase {index + 1}</span>
      </div>
      <div className={cn(
        "flex items-center gap-1 text-xs px-2 py-1 rounded-full",
        data.direction === "import" 
          ? "bg-warning/20 text-warning" 
          : "bg-success/20 text-success"
      )}>
        {data.direction === "import" 
          ? <ArrowDownLeft className="w-3 h-3" /> 
          : <ArrowUpRight className="w-3 h-3" />
        }
        {data.direction === "import" ? "Import" : "Export"}
      </div>
    </div>
    
    <div className="grid grid-cols-2 gap-2 sm:gap-3">
      <div>
        <p className="text-[10px] sm:text-xs text-muted-foreground mb-0.5">Voltage</p>
        <p className="text-base sm:text-lg font-mono font-bold text-foreground">{data.voltage}V</p>
      </div>
      <div>
        <p className="text-[10px] sm:text-xs text-muted-foreground mb-0.5">Current</p>
        <p className="text-base sm:text-lg font-mono font-bold text-foreground">{data.current}A</p>
      </div>
      <div>
        <p className="text-[10px] sm:text-xs text-muted-foreground mb-0.5">Power</p>
        <p className={cn(
          "text-base sm:text-lg font-mono font-bold",
          data.direction === "export" ? "text-success" : "text-warning"
        )}>{data.power}kW</p>
      </div>
      <div>
        <p className="text-[10px] sm:text-xs text-muted-foreground mb-0.5">PF</p>
        <p className={cn(
          "text-base sm:text-lg font-mono font-bold",
          data.powerFactor >= 0.95 ? "text-success" : data.powerFactor >= 0.9 ? "text-warning" : "text-destructive"
        )}>{data.powerFactor}</p>
      </div>
    </div>
    
    {/* Power bar visualization */}
    <div className="mt-3 pt-3 border-t border-border/30">
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
        <span>Power Load</span>
        <span>{((data.power / 5) * 100).toFixed(0)}%</span>
      </div>
      <div className="h-2 bg-secondary rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${(data.power / 5) * 100}%` }}
          transition={{ delay: index * 0.1 + 0.3, duration: 0.5 }}
          className={cn(
            "h-full rounded-full",
            data.direction === "export" ? "bg-success" : "bg-warning"
          )}
        />
      </div>
    </div>
  </motion.div>
);

const MeterTelemetry = ({ device, telemetry }: MeterTelemetryProps) => {
  // Use real grid power when available
  const gridPowerKw = telemetry?.grid_power_w !== undefined ? telemetry.grid_power_w / 1000 : 0;
  const isExporting = gridPowerKw < 0;

  // Update today stats with real data
  const updatedTodayStats = {
    ...todayStats,
    // Current power flow from real telemetry
    currentPower: Math.abs(gridPowerKw),
    isExporting: isExporting,
  };

  const totalPower = phaseData.reduce((sum, p) => sum + (p.direction === "import" ? p.power : -p.power), 0);
  const avgPowerFactor = phaseData.reduce((sum, p) => sum + p.powerFactor, 0) / phaseData.length;
  const avgVoltage = phaseData.reduce((sum, p) => sum + p.voltage, 0) / phaseData.length;

  // Override total power with real telemetry if available
  const displayTotalPower = telemetry?.grid_power_w !== undefined ? gridPowerKw : totalPower;
  
  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Summary Stats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-3 sm:p-5"
      >
        <h3 className="text-base sm:text-lg font-semibold text-foreground mb-3 sm:mb-4">Today's Summary</h3>
        
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-4">
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3 text-center">
            <div className="flex items-center justify-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <ArrowDownLeft className="w-3 h-3 sm:w-4 sm:h-4 text-warning" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Import</span>
            </div>
            <p className="text-lg sm:text-2xl font-mono font-bold text-warning">{todayStats.totalImport}</p>
            <p className="text-[9px] sm:text-xs text-muted-foreground">kWh</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3 text-center">
            <div className="flex items-center justify-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <ArrowUpRight className="w-3 h-3 sm:w-4 sm:h-4 text-success" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Export</span>
            </div>
            <p className="text-lg sm:text-2xl font-mono font-bold text-success">{todayStats.totalExport}</p>
            <p className="text-[9px] sm:text-xs text-muted-foreground">kWh</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3 text-center">
            <div className="flex items-center justify-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Activity className="w-3 h-3 sm:w-4 sm:h-4 text-primary" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Net</span>
            </div>
            <p className={cn(
              "text-lg sm:text-2xl font-mono font-bold",
              todayStats.netEnergy < 0 ? "text-success" : "text-warning"
            )}>
              {todayStats.netEnergy > 0 ? "+" : ""}{todayStats.netEnergy}
            </p>
            <p className="text-[9px] sm:text-xs text-muted-foreground">kWh</p>
          </div>
          <div className="hidden sm:block bg-secondary/30 rounded-lg p-2 sm:p-3 text-center">
            <div className="flex items-center justify-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <TrendingDown className="w-3 h-3 sm:w-4 sm:h-4 text-warning" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Peak In</span>
            </div>
            <p className="text-lg sm:text-2xl font-mono font-bold text-foreground">{todayStats.peakImport}</p>
            <p className="text-[9px] sm:text-xs text-muted-foreground">kW</p>
          </div>
          <div className="hidden sm:block bg-secondary/30 rounded-lg p-2 sm:p-3 text-center">
            <div className="flex items-center justify-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <TrendingUp className="w-3 h-3 sm:w-4 sm:h-4 text-success" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Peak Out</span>
            </div>
            <p className="text-lg sm:text-2xl font-mono font-bold text-foreground">{todayStats.peakExport}</p>
            <p className="text-[9px] sm:text-xs text-muted-foreground">kW</p>
          </div>
        </div>
      </motion.div>

      {/* Phase Data */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card p-3 sm:p-5"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 sm:mb-4">
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-foreground">Three-Phase</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">Real-time measurements</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] sm:text-xs text-muted-foreground">Total Power</p>
            <p className={cn(
              "text-base sm:text-xl font-mono font-bold",
              displayTotalPower > 0 ? "text-warning" : "text-success"
            )}>
              {displayTotalPower > 0 ? "+" : ""}{displayTotalPower.toFixed(2)} kW
            </p>
          </div>
        </div>
        
        <div className="grid sm:grid-cols-3 gap-3 sm:gap-4">
          {phaseData.map((phase, index) => (
            <PhaseCard key={phase.phase} data={phase} index={index} />
          ))}
        </div>
        
        {/* Grid Stats */}
        <div className="grid grid-cols-3 gap-2 sm:gap-4 mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-border/30">
          <div className="text-center">
            <p className="text-[10px] sm:text-xs text-muted-foreground mb-0.5 sm:mb-1">Avg V</p>
            <p className="text-sm sm:text-lg font-mono font-bold text-foreground">{avgVoltage.toFixed(1)}V</p>
          </div>
          <div className="text-center">
            <p className="text-[10px] sm:text-xs text-muted-foreground mb-0.5 sm:mb-1">Freq</p>
            <p className="text-sm sm:text-lg font-mono font-bold text-foreground">50.01Hz</p>
          </div>
          <div className="text-center">
            <p className="text-[10px] sm:text-xs text-muted-foreground mb-0.5 sm:mb-1">Avg PF</p>
            <p className={cn(
              "text-sm sm:text-lg font-mono font-bold",
              avgPowerFactor >= 0.95 ? "text-success" : "text-warning"
            )}>{avgPowerFactor.toFixed(2)}</p>
          </div>
        </div>
      </motion.div>

      {/* Import/Export History */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card p-3 sm:p-5"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 sm:mb-4">
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-foreground">Import/Export</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">24-hour flow</p>
          </div>
          <div className="flex items-center gap-2 sm:gap-4 text-[10px] sm:text-xs">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 sm:w-3 sm:h-3 rounded bg-warning" />
              <span className="text-muted-foreground">Import</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 sm:w-3 sm:h-3 rounded bg-success" />
              <span className="text-muted-foreground">Export</span>
            </div>
          </div>
        </div>
        
        <div className="h-[180px] sm:h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={historicalData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis 
                dataKey="time" 
                stroke="hsl(var(--muted-foreground))" 
                fontSize={10}
                tickLine={false}
              />
              <YAxis 
                stroke="hsl(var(--muted-foreground))" 
                fontSize={10}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `${v}kW`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Bar dataKey="import" fill="hsl(var(--warning))" name="Import" radius={[2, 2, 0, 0]} />
              <Bar dataKey="export" fill="hsl(var(--success))" name="Export" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </motion.div>
    </div>
  );
};

export default MeterTelemetry;
