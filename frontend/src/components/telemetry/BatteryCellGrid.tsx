import { motion } from "framer-motion";
import { Thermometer, Zap, Battery, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
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

interface CellData {
  id: number;
  voltage: number;
  temperature: number;
  soc: number;
  health: number;
  status: "normal" | "warning" | "critical" | "balancing";
}

// Generate mock cell data for a battery pack
const generateCellData = (packId: number, cellCount: number = 16): CellData[] => {
  return Array.from({ length: cellCount }, (_, i) => {
    const baseVoltage = 3.2 + Math.random() * 0.5;
    const baseTemp = 25 + Math.random() * 20;
    const baseSoc = 70 + Math.random() * 25;
    const health = 90 + Math.random() * 10;
    
    // Add some variation for visual interest
    const isWarning = Math.random() > 0.9;
    const isCritical = Math.random() > 0.97;
    const isBalancing = Math.random() > 0.85 && !isWarning && !isCritical;
    
    return {
      id: packId * 100 + i + 1,
      voltage: Number((isWarning ? baseVoltage - 0.3 : baseVoltage).toFixed(3)),
      temperature: Number((isCritical ? baseTemp + 15 : baseTemp).toFixed(1)),
      soc: Number(baseSoc.toFixed(1)),
      health: Number(health.toFixed(1)),
      status: isCritical ? "critical" : isWarning ? "warning" : isBalancing ? "balancing" : "normal",
    };
  });
};

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

const batteryPacks = [
  { id: 1, name: "Battery Pack A", cells: generateCellData(1, 16) },
  { id: 2, name: "Battery Pack B", cells: generateCellData(2, 16) },
];

// Historical battery data
const generateHistoricalData = () => {
  return Array.from({ length: 24 }, (_, i) => {
    const hour = i;
    const sunIntensity = Math.max(0, Math.sin((hour - 6) * Math.PI / 12));
    const baseSOC = 50;
    const charging = sunIntensity > 0.3;
    
    return {
      time: `${hour.toString().padStart(2, "0")}:00`,
      soc: Math.min(95, Math.max(15, baseSOC + (charging ? sunIntensity * 40 : -hour * 2) + Math.random() * 5)),
      voltage: 51.2 + Math.random() * 2,
      current: charging ? 20 + Math.random() * 10 : -(10 + Math.random() * 5),
      temperature: 25 + sunIntensity * 10 + Math.random() * 3,
      power: charging ? 2 + Math.random() : -(1 + Math.random()),
    };
  });
};

const historicalData = generateHistoricalData();

const getStatusColor = (status: CellData["status"]) => {
  switch (status) {
    case "critical":
      return "text-destructive";
    case "warning":
      return "text-warning";
    case "balancing":
      return "text-blue-400";
    default:
      return "text-battery";
  }
};

const getStatusBorderColor = (status: CellData["status"]) => {
  switch (status) {
    case "critical":
      return "#ef4444";
    case "warning":
      return "#f59e0b";
    case "balancing":
      return "#60a5fa";
    default:
      return "#22c55e";
  }
};

const getFillColor = (status: CellData["status"]) => {
  switch (status) {
    case "critical":
      return "#ef4444";
    case "warning":
      return "#f59e0b";
    case "balancing":
      return "#60a5fa";
    default:
      return "#22c55e";
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
              "relative cursor-pointer transition-all hover:scale-110 hover:z-10",
              cell.status === "balancing" && "animate-pulse"
            )}
          >
            <svg
              viewBox="0 0 24 40"
              className="w-full h-10"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {/* Battery terminal (top cap) */}
              <rect
                x="8"
                y="0"
                width="8"
                height="3"
                rx="1"
                fill={borderColor}
                opacity="0.8"
              />
              
              {/* Battery body outline */}
              <rect
                x="2"
                y="4"
                width="20"
                height="34"
                rx="3"
                stroke={borderColor}
                strokeWidth="1.5"
                fill="transparent"
              />
              
              {/* Battery fill level */}
              <motion.rect
                x="4"
                width="16"
                rx="2"
                fill={fillColor}
                opacity="0.7"
                initial={{ y: 36, height: 0 }}
                animate={{ 
                  y: 6 + (30 * (1 - fillPercent / 100)), 
                  height: 30 * (fillPercent / 100) 
                }}
                transition={{ delay: index * 0.015 + 0.1, duration: 0.4, ease: "easeOut" }}
              />
              
              {/* Cell number */}
              <text
                x="12"
                y="24"
                textAnchor="middle"
                dominantBaseline="middle"
                fill="currentColor"
                className="text-[8px] font-mono font-bold fill-foreground"
                style={{ fontSize: '8px' }}
              >
                {index + 1}
              </text>
              
              {/* Status indicator dot */}
              {cell.status !== "normal" && (
                <circle
                  cx="18"
                  cy="8"
                  r="2.5"
                  fill={borderColor}
                  className={cell.status === "critical" ? "animate-ping" : ""}
                />
              )}
            </svg>
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
              <span className={cn("font-mono", getVoltageColor(cell.voltage))}>
                {cell.voltage}V
              </span>
              
              <div className="flex items-center gap-1">
                <Thermometer className={cn("w-3 h-3", getTempColor(cell.temperature))} />
                <span className="text-muted-foreground">Temp:</span>
              </div>
              <span className={cn("font-mono", getTempColor(cell.temperature))}>
                {cell.temperature}°C
              </span>
              
              <div className="flex items-center gap-1">
                <Battery className="w-3 h-3 text-battery" />
                <span className="text-muted-foreground">SOC:</span>
              </div>
              <span className="font-mono text-battery">{cell.soc}%</span>
              
              <span className="text-muted-foreground">Health:</span>
              <span className="font-mono text-foreground">{cell.health}%</span>
              
              <span className="text-muted-foreground">Status:</span>
              <span className={cn(
                "capitalize font-medium",
                cell.status === "critical" && "text-destructive",
                cell.status === "warning" && "text-warning",
                cell.status === "balancing" && "text-blue-400",
                cell.status === "normal" && "text-success"
              )}>
                {cell.status}
              </span>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

const PackStats = ({ cells }: { cells: CellData[] }) => {
  const avgVoltage = cells.reduce((sum, c) => sum + c.voltage, 0) / cells.length;
  const avgTemp = cells.reduce((sum, c) => sum + c.temperature, 0) / cells.length;
  const avgSoc = cells.reduce((sum, c) => sum + c.soc, 0) / cells.length;
  const minVoltage = Math.min(...cells.map(c => c.voltage));
  const maxVoltage = Math.max(...cells.map(c => c.voltage));
  const deltaVoltage = maxVoltage - minVoltage;
  
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 sm:gap-2 mt-2 sm:mt-3">
      <div className="bg-secondary/30 rounded-md px-1.5 sm:px-2 py-1 sm:py-1.5">
        <p className="text-[8px] sm:text-[10px] text-muted-foreground uppercase tracking-wider">Avg V</p>
        <p className="text-xs sm:text-sm font-mono font-bold text-foreground">{avgVoltage.toFixed(3)}V</p>
      </div>
      <div className="bg-secondary/30 rounded-md px-1.5 sm:px-2 py-1 sm:py-1.5">
        <p className="text-[8px] sm:text-[10px] text-muted-foreground uppercase tracking-wider">Delta</p>
        <p className={cn(
          "text-xs sm:text-sm font-mono font-bold",
          deltaVoltage > 0.1 ? "text-warning" : "text-success"
        )}>
          {(deltaVoltage * 1000).toFixed(0)}mV
        </p>
      </div>
      <div className="bg-secondary/30 rounded-md px-1.5 sm:px-2 py-1 sm:py-1.5">
        <p className="text-[8px] sm:text-[10px] text-muted-foreground uppercase tracking-wider">Temp</p>
        <p className={cn(
          "text-xs sm:text-sm font-mono font-bold",
          avgTemp > 40 ? "text-warning" : "text-foreground"
        )}>
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

const BatteryCellGrid = ({ device, telemetry }: BatteryCellGridProps) => {
  // Use real telemetry data when available
  const batteryPowerKw = telemetry?.battery_power_w !== undefined ? telemetry.battery_power_w / 1000 : 2.1;
  const soc = telemetry?.battery_soc_pct !== undefined ? telemetry.battery_soc_pct : 78;
  const isCharging = telemetry?.is_charging ?? batteryPowerKw > 0;

  // Battery pack summary stats using real data
  const packSummary = {
    totalVoltage: 52.4, // Would need extended telemetry for voltage
    totalCurrent: Math.abs(batteryPowerKw) * 1000 / 52.4, // Estimate from power
    totalPower: Math.abs(batteryPowerKw),
    soc: Math.round(soc),
    health: 94, // Would need extended telemetry
    cycles: 342, // Would need extended telemetry
    temperature: 28, // Would need extended telemetry
    status: isCharging ? "charging" as const : "discharging" as const,
  };

  return (
    <div className="space-y-6">
      {/* Battery Pack Summary */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-3 sm:p-5"
      >
        <h3 className="text-base sm:text-lg font-semibold text-foreground mb-3 sm:mb-4">Battery Pack Status</h3>
        
        <div className="grid grid-cols-4 sm:grid-cols-4 lg:grid-cols-8 gap-2 sm:gap-4">
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Zap className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-battery" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Volt</span>
            </div>
            <p className="text-sm sm:text-lg font-mono font-bold text-foreground">{packSummary.totalVoltage}</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Activity className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-success" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Amp</span>
            </div>
            <p className="text-sm sm:text-lg font-mono font-bold text-success">+{packSummary.totalCurrent}</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Zap className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-solar" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Power</span>
            </div>
            <p className="text-sm sm:text-lg font-mono font-bold text-solar">{packSummary.totalPower}kW</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Battery className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-battery" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">SOC</span>
            </div>
            <p className="text-sm sm:text-lg font-mono font-bold text-battery">{packSummary.soc}%</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Activity className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-primary" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Health</span>
            </div>
            <p className="text-sm sm:text-lg font-mono font-bold text-foreground">{packSummary.health}%</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Activity className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-muted-foreground" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Cycles</span>
            </div>
            <p className="text-sm sm:text-lg font-mono font-bold text-foreground">{packSummary.cycles}</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Thermometer className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-warning" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Temp</span>
            </div>
            <p className="text-sm sm:text-lg font-mono font-bold text-foreground">{packSummary.temperature}°</p>
          </div>
          <div className="bg-secondary/30 rounded-lg p-2 sm:p-3">
            <div className="flex items-center gap-0.5 sm:gap-1 mb-0.5 sm:mb-1">
              <Battery className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-success" />
              <span className="text-[9px] sm:text-xs text-muted-foreground">Status</span>
            </div>
            <p className="text-sm sm:text-lg font-mono font-bold text-success capitalize">{packSummary.status}</p>
          </div>
        </div>
      </motion.div>

      {/* Cell Grid */}
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
          {/* Legend - scrollable on mobile */}
          <div className="flex items-center gap-2 sm:gap-3 text-[10px] sm:text-xs overflow-x-auto pb-1">
            <div className="flex items-center gap-1 shrink-0">
              <svg viewBox="0 0 24 40" className="w-2.5 h-4 sm:w-3 sm:h-5" fill="none">
                <rect x="8" y="0" width="8" height="3" rx="1" fill="#22c55e" opacity="0.8" />
                <rect x="2" y="4" width="20" height="34" rx="3" stroke="#22c55e" strokeWidth="1.5" fill="transparent" />
                <rect x="4" y="16" width="16" height="20" rx="2" fill="#22c55e" opacity="0.7" />
              </svg>
              <span className="text-muted-foreground">OK</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <svg viewBox="0 0 24 40" className="w-2.5 h-4 sm:w-3 sm:h-5" fill="none">
                <rect x="8" y="0" width="8" height="3" rx="1" fill="#60a5fa" opacity="0.8" />
                <rect x="2" y="4" width="20" height="34" rx="3" stroke="#60a5fa" strokeWidth="1.5" fill="transparent" />
                <rect x="4" y="16" width="16" height="20" rx="2" fill="#60a5fa" opacity="0.7" />
              </svg>
              <span className="text-muted-foreground">Bal</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <svg viewBox="0 0 24 40" className="w-2.5 h-4 sm:w-3 sm:h-5" fill="none">
                <rect x="8" y="0" width="8" height="3" rx="1" fill="#f59e0b" opacity="0.8" />
                <rect x="2" y="4" width="20" height="34" rx="3" stroke="#f59e0b" strokeWidth="1.5" fill="transparent" />
                <rect x="4" y="26" width="16" height="10" rx="2" fill="#f59e0b" opacity="0.7" />
              </svg>
              <span className="text-muted-foreground">Warn</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <svg viewBox="0 0 24 40" className="w-2.5 h-4 sm:w-3 sm:h-5" fill="none">
                <rect x="8" y="0" width="8" height="3" rx="1" fill="#ef4444" opacity="0.8" />
                <rect x="2" y="4" width="20" height="34" rx="3" stroke="#ef4444" strokeWidth="1.5" fill="transparent" />
                <rect x="4" y="31" width="16" height="5" rx="2" fill="#ef4444" opacity="0.7" />
              </svg>
              <span className="text-muted-foreground">Crit</span>
            </div>
          </div>
        </div>
        
        <div className="space-y-3 sm:space-y-4">
          {batteryPacks.map((pack) => (
            <div key={pack.id} className="border border-border/50 rounded-lg p-2 sm:p-3 bg-secondary/10">
              <div className="flex items-center gap-2 mb-2">
                <Battery className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-battery" />
                <h4 className="font-medium text-xs sm:text-sm text-foreground">{pack.name}</h4>
                <span className="text-[10px] sm:text-xs text-muted-foreground">({pack.cells.length} cells)</span>
              </div>
              
              {/* Cell Grid - responsive columns */}
              <div className="grid grid-cols-8 sm:grid-cols-16 gap-0.5 sm:gap-1">
                {pack.cells.map((cell, index) => (
                  <CellVisual key={cell.id} cell={cell} index={index} />
                ))}
              </div>
              
              {/* Pack Statistics */}
              <PackStats cells={pack.cells} />
            </div>
          ))}
        </div>
      </motion.div>

      {/* Historical Charts */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card p-3 sm:p-5"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 sm:mb-4">
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-foreground">SOC & Power</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">24-hour history</p>
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
            <AreaChart data={historicalData}>
              <defs>
                <linearGradient id="socGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--battery))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--battery))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis 
                dataKey="time" 
                stroke="hsl(var(--muted-foreground))" 
                fontSize={9}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis 
                yAxisId="left"
                stroke="hsl(var(--muted-foreground))" 
                fontSize={9}
                tickLine={false}
                axisLine={false}
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
                width={30}
              />
              <YAxis 
                yAxisId="right"
                orientation="right"
                stroke="hsl(var(--muted-foreground))" 
                fontSize={9}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `${v}kW`}
                width={35}
              />
              <RechartsTooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "11px",
                }}
              />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="soc"
                stroke="hsl(var(--battery))"
                fill="url(#socGradient)"
                strokeWidth={2}
                name="SOC"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="power"
                stroke="hsl(var(--solar))"
                strokeWidth={2}
                dot={false}
                name="Power"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Temperature History */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="glass-card p-3 sm:p-5"
      >
        <div className="mb-3 sm:mb-4">
          <h3 className="text-base sm:text-lg font-semibold text-foreground">Temperature</h3>
          <p className="text-xs sm:text-sm text-muted-foreground">24-hour thermal</p>
        </div>
        
        <div className="h-[120px] sm:h-[150px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={historicalData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis 
                dataKey="time" 
                stroke="hsl(var(--muted-foreground))" 
                fontSize={9}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis 
                stroke="hsl(var(--muted-foreground))" 
                fontSize={9}
                tickLine={false}
                axisLine={false}
                domain={[20, 45]}
                tickFormatter={(v) => `${v}°`}
                width={25}
              />
              <RechartsTooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "11px",
                }}
              />
              <Line
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

export default BatteryCellGrid;
