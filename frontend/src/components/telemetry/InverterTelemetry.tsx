import { motion } from "framer-motion";
import { Sun, Battery, Home, Zap, Activity, Thermometer, Gauge, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
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

interface InverterTelemetryProps {
  device: {
    id: string;
    name: string;
    metrics: { label: string; value: string; unit: string }[];
  };
  telemetry?: DeviceTelemetry | null;
}

// Generate historical data for inverter
const generateHistoricalData = () => {
  return Array.from({ length: 24 }, (_, i) => {
    const hour = i;
    const sunIntensity = Math.max(0, Math.sin((hour - 6) * Math.PI / 12));
    return {
      time: `${hour.toString().padStart(2, "0")}:00`,
      solarPower: parseFloat((sunIntensity * 10 + Math.random() * 0.5).toFixed(1)),
      batteryPower: parseFloat((sunIntensity > 0.5 ? 2 + Math.random() * 0.5 : -1.5 - Math.random() * 0.5).toFixed(1)),
      loadPower: parseFloat((3 + Math.random() * 2 + (hour >= 18 && hour <= 22 ? 2 : 0)).toFixed(1)),
      gridPower: parseFloat((Math.random() * 2 - 1).toFixed(1)),
      efficiency: parseFloat((94 + Math.random() * 4).toFixed(1)),
      temperature: parseFloat((35 + sunIntensity * 15 + Math.random() * 5).toFixed(1)),
    };
  });
};

const historicalData = generateHistoricalData();

const PowerFlowCard = ({ 
  icon: Icon, 
  label, 
  value, 
  unit, 
  color, 
  direction,
  delay 
}: { 
  icon: any; 
  label: string; 
  value: string; 
  unit: string; 
  color: string;
  direction?: "in" | "out" | "bidirectional";
  delay: number;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay }}
    className="bg-secondary/30 rounded-xl p-3 sm:p-4 border border-border/50"
  >
    <div className="flex items-center justify-between mb-2 sm:mb-3">
      <div className={cn("p-1.5 sm:p-2 rounded-lg", color)}>
        <Icon className="w-4 h-4 sm:w-5 sm:h-5" />
      </div>
      {direction && (
        <div className={cn(
          "text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded-full",
          direction === "in" && "bg-success/20 text-success",
          direction === "out" && "bg-warning/20 text-warning",
          direction === "bidirectional" && "bg-blue-500/20 text-blue-400"
        )}>
          {direction === "in" ? "↓ In" : direction === "out" ? "↑ Out" : "↔"}
        </div>
      )}
    </div>
    <p className="text-[10px] sm:text-xs text-muted-foreground uppercase tracking-wider mb-0.5 sm:mb-1">{label}</p>
    <p className="text-lg sm:text-2xl font-mono font-bold text-foreground">
      {value}<span className="text-xs sm:text-sm text-muted-foreground ml-1">{unit}</span>
    </p>
  </motion.div>
);

// Mock solar array data - typically each inverter has multiple MPPT inputs
const solarArrays = [
  {
    id: "mppt-1",
    name: "Array 1 (East Roof)",
    power: 2.85,
    voltage: 385.2,
    current: 7.4,
    status: "optimal" as const,
    panels: 12,
  },
  {
    id: "mppt-2",
    name: "Array 2 (West Roof)",
    power: 3.12,
    voltage: 392.8,
    current: 7.95,
    status: "optimal" as const,
    panels: 14,
  },
  {
    id: "mppt-3",
    name: "Array 3 (South Facing)",
    power: 2.43,
    voltage: 378.5,
    current: 6.42,
    status: "shaded" as const,
    panels: 10,
  },
];

const arrayStatusStyles = {
  optimal: { bg: "bg-success/20", text: "text-success", label: "Optimal" },
  shaded: { bg: "bg-warning/20", text: "text-warning", label: "Partial Shade" },
  offline: { bg: "bg-destructive/20", text: "text-destructive", label: "Offline" },
  low: { bg: "bg-muted/50", text: "text-muted-foreground", label: "Low Output" },
};

const InverterTelemetry = ({ device, telemetry }: InverterTelemetryProps) => {
  // Use real telemetry data when available, with fallback display values
  const solarPower = telemetry?.pv_power_w !== undefined ? telemetry.pv_power_w / 1000 : 0;
  const gridPower = telemetry?.grid_power_w !== undefined ? telemetry.grid_power_w / 1000 : 0;
  const loadPower = telemetry?.load_power_w !== undefined ? telemetry.load_power_w / 1000 : 0;
  const batteryPower = telemetry?.battery_power_w !== undefined ? telemetry.battery_power_w / 1000 : 0;
  const batterySoc = telemetry?.battery_soc_pct !== undefined ? telemetry.battery_soc_pct : 0;
  const isCharging = telemetry?.is_charging ?? batteryPower > 0;
  const isGridExporting = gridPower < 0;

  // Power flow data from real telemetry
  const powerFlowData = {
    solarPower: solarPower,
    batteryPower: Math.abs(batteryPower),
    batterySoc: batterySoc,
    loadPower: loadPower,
    gridPower: Math.abs(gridPower),
    isGridExporting: isGridExporting,
    isCharging: isCharging,
    // These values would come from extended telemetry if available
    dcVoltage: 580,
    acVoltage: 238,
    frequency: 50.02,
    efficiency: 97.2,
    temperature: 42,
  };

  return (
    <div className="space-y-6">
      {/* Power Flow Overview */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-3 sm:p-5"
      >
        <h3 className="text-base sm:text-lg font-semibold text-foreground mb-3 sm:mb-4">Power Flow</h3>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <PowerFlowCard
            icon={Sun}
            label="Solar Input"
            value={powerFlowData.solarPower.toFixed(1)}
            unit="kW"
            color="bg-solar/20 text-solar"
            direction="in"
            delay={0}
          />
          <PowerFlowCard
            icon={Battery}
            label="Battery"
            value={powerFlowData.batteryPower.toFixed(1)}
            unit="kW"
            color="bg-battery/20 text-battery"
            direction={powerFlowData.isCharging ? "in" : "out"}
            delay={0.1}
          />
          <PowerFlowCard
            icon={Home}
            label="Load"
            value={powerFlowData.loadPower.toFixed(1)}
            unit="kW"
            color="bg-consumption/20 text-consumption"
            direction="out"
            delay={0.2}
          />
          <PowerFlowCard
            icon={Zap}
            label="Grid"
            value={Math.abs(powerFlowData.gridPower).toFixed(1)}
            unit="kW"
            color="bg-grid/20 text-grid"
            direction={powerFlowData.isGridExporting ? "out" : "in"}
            delay={0.3}
          />
        </div>
      </motion.div>

      {/* Solar Array Telemetry */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="glass-card p-3 sm:p-5"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 sm:mb-4">
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-foreground">Solar Arrays</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">MPPT channel monitoring</p>
          </div>
          <div className="text-xs sm:text-sm text-muted-foreground">
            Total: <span className="font-mono font-bold text-solar">{solarArrays.reduce((sum, arr) => sum + arr.power, 0).toFixed(2)} kW</span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {solarArrays.map((array, index) => {
            const statusStyle = arrayStatusStyles[array.status];
            return (
              <motion.div
                key={array.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3 + index * 0.1 }}
                className="bg-secondary/30 rounded-xl p-3 sm:p-4 border border-border/50"
              >
                <div className="flex items-center justify-between mb-2 sm:mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="p-1 sm:p-1.5 rounded-lg bg-solar/20 shrink-0">
                      <Sun className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-solar" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-medium text-xs sm:text-sm text-foreground truncate">{array.name}</h4>
                      <p className="text-[10px] sm:text-xs text-muted-foreground">{array.panels} panels</p>
                    </div>
                  </div>
                  <span className={cn("text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded-full shrink-0", statusStyle.bg, statusStyle.text)}>
                    {statusStyle.label}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-1.5 sm:gap-3">
                  <div className="bg-background/50 rounded-lg p-1.5 sm:p-2.5 text-center">
                    <div className="flex items-center justify-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
                      <TrendingUp className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-solar" />
                      <span className="text-[8px] sm:text-[10px] uppercase text-muted-foreground">Power</span>
                    </div>
                    <p className="text-sm sm:text-lg font-mono font-bold text-solar">{array.power.toFixed(2)}</p>
                    <p className="text-[8px] sm:text-[10px] text-muted-foreground">kW</p>
                  </div>
                  <div className="bg-background/50 rounded-lg p-1.5 sm:p-2.5 text-center">
                    <div className="flex items-center justify-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
                      <Zap className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-primary" />
                      <span className="text-[8px] sm:text-[10px] uppercase text-muted-foreground">Volt</span>
                    </div>
                    <p className="text-sm sm:text-lg font-mono font-bold text-foreground">{array.voltage.toFixed(0)}</p>
                    <p className="text-[8px] sm:text-[10px] text-muted-foreground">V</p>
                  </div>
                  <div className="bg-background/50 rounded-lg p-1.5 sm:p-2.5 text-center">
                    <div className="flex items-center justify-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
                      <Activity className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-battery" />
                      <span className="text-[8px] sm:text-[10px] uppercase text-muted-foreground">Amp</span>
                    </div>
                    <p className="text-sm sm:text-lg font-mono font-bold text-foreground">{array.current.toFixed(1)}</p>
                    <p className="text-[8px] sm:text-[10px] text-muted-foreground">A</p>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* Inverter Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card p-3 sm:p-5"
      >
        <h3 className="text-base sm:text-lg font-semibold text-foreground mb-3 sm:mb-4">Inverter Metrics</h3>
        
        <div className="grid grid-cols-3 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-4">
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-1 sm:gap-2 mb-0.5 sm:mb-1">
              <Zap className="w-3 h-3 sm:w-4 sm:h-4 text-solar" />
              <span className="text-[10px] sm:text-xs text-muted-foreground">DC V</span>
            </div>
            <p className="text-base sm:text-xl font-mono font-bold text-foreground">{powerFlowData.dcVoltage}</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-1 sm:gap-2 mb-0.5 sm:mb-1">
              <Activity className="w-3 h-3 sm:w-4 sm:h-4 text-grid" />
              <span className="text-[10px] sm:text-xs text-muted-foreground">AC V</span>
            </div>
            <p className="text-base sm:text-xl font-mono font-bold text-foreground">{powerFlowData.acVoltage}</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-1 sm:gap-2 mb-0.5 sm:mb-1">
              <Activity className="w-3 h-3 sm:w-4 sm:h-4 text-primary" />
              <span className="text-[10px] sm:text-xs text-muted-foreground">Freq</span>
            </div>
            <p className="text-base sm:text-xl font-mono font-bold text-foreground">{powerFlowData.frequency}</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-1 sm:gap-2 mb-0.5 sm:mb-1">
              <Gauge className="w-3 h-3 sm:w-4 sm:h-4 text-success" />
              <span className="text-[10px] sm:text-xs text-muted-foreground">Eff</span>
            </div>
            <p className="text-base sm:text-xl font-mono font-bold text-success">{powerFlowData.efficiency}%</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-1 sm:gap-2 mb-0.5 sm:mb-1">
              <Battery className="w-3 h-3 sm:w-4 sm:h-4 text-battery" />
              <span className="text-[10px] sm:text-xs text-muted-foreground">SOC</span>
            </div>
            <p className="text-base sm:text-xl font-mono font-bold text-battery">{powerFlowData.batterySoc}%</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-1 sm:gap-2 mb-0.5 sm:mb-1">
              <Thermometer className="w-3 h-3 sm:w-4 sm:h-4 text-warning" />
              <span className="text-[10px] sm:text-xs text-muted-foreground">Temp</span>
            </div>
            <p className={cn(
              "text-base sm:text-xl font-mono font-bold",
              powerFlowData.temperature > 50 ? "text-destructive" : powerFlowData.temperature > 45 ? "text-warning" : "text-foreground"
            )}>{powerFlowData.temperature}°</p>
          </div>
        </div>
      </motion.div>

      {/* Historical Power Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="glass-card p-3 sm:p-5"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 sm:mb-4">
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-foreground">Power History</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">24-hour trend</p>
          </div>
          <div className="flex items-center gap-2 sm:gap-4 text-[10px] sm:text-xs">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-solar" />
              <span className="text-muted-foreground">Solar</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-consumption" />
              <span className="text-muted-foreground">Load</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-battery" />
              <span className="text-muted-foreground">Battery</span>
            </div>
          </div>
        </div>
        
        <div className="h-[180px] sm:h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={historicalData}>
              <defs>
                <linearGradient id="solarGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--solar))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--solar))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="loadGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--consumption))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--consumption))" stopOpacity={0} />
                </linearGradient>
              </defs>
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
              <Area
                type="monotone"
                dataKey="solarPower"
                stroke="hsl(var(--solar))"
                fill="url(#solarGradient)"
                strokeWidth={2}
                name="Solar"
              />
              <Area
                type="monotone"
                dataKey="loadPower"
                stroke="hsl(var(--consumption))"
                fill="url(#loadGradient)"
                strokeWidth={2}
                name="Load"
              />
              <Line
                type="monotone"
                dataKey="batteryPower"
                stroke="hsl(var(--battery))"
                strokeWidth={2}
                dot={false}
                name="Battery"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Efficiency & Temperature History */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass-card p-3 sm:p-5"
      >
        <div className="mb-3 sm:mb-4">
          <h3 className="text-base sm:text-lg font-semibold text-foreground">Efficiency & Temp</h3>
          <p className="text-xs sm:text-sm text-muted-foreground">24-hour performance</p>
        </div>
        
        <div className="h-[150px] sm:h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={historicalData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis 
                dataKey="time" 
                stroke="hsl(var(--muted-foreground))" 
                fontSize={10}
                tickLine={false}
              />
              <YAxis 
                yAxisId="left"
                stroke="hsl(var(--muted-foreground))" 
                fontSize={10}
                tickLine={false}
                axisLine={false}
                domain={[90, 100]}
                tickFormatter={(v) => `${v}%`}
              />
              <YAxis 
                yAxisId="right"
                orientation="right"
                stroke="hsl(var(--muted-foreground))" 
                fontSize={10}
                tickLine={false}
                axisLine={false}
                domain={[20, 60]}
                tickFormatter={(v) => `${v}°C`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="efficiency"
                stroke="hsl(var(--success))"
                strokeWidth={2}
                dot={false}
                name="Efficiency"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="temperature"
                stroke="hsl(var(--warning))"
                strokeWidth={2}
                dot={false}
                name="Temperature"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </motion.div>
    </div>
  );
};

export default InverterTelemetry;
