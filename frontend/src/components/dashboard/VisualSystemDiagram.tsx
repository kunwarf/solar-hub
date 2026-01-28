import { motion } from "framer-motion";
import { Sun, Home, Grid3X3, Cpu, Gauge, ArrowRight, Thermometer, Zap, Activity, ArrowDown, ArrowUp, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Link } from "react-router-dom";
import {
  getSystemAggregates,
  type System,
  type Inverter,
  type BatteryBank,
  type Meter,
} from "@/data/mockData";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { useSystemHierarchy } from "@/hooks/useSystemHierarchy";

const statusColors = {
  online: "bg-success",
  offline: "bg-destructive",
  warning: "bg-warning",
};

const statusBorderColors = {
  online: "border-success/50",
  offline: "border-destructive/50",
  warning: "border-warning/50",
};

function DynamicBatteryIcon({ className, soc, isCharging, size = 24 }: { className?: string; soc: number; isCharging?: boolean; size?: number }) {
  const fillHeight = Math.max(0, Math.min(100, soc));
  const getFillColor = () => {
    if (soc >= 60) return "hsl(var(--success))";
    if (soc >= 30) return "hsl(var(--warning))";
    return "hsl(var(--destructive))";
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      width={size}
      height={size}
      className={cn(className, isCharging && "animate-pulse")}
    >
      <rect x="10" y="2" width="4" height="2" rx="0.5" fill="currentColor" opacity="0.6" />
      <rect x="6" y="4" width="12" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <rect
        x="7.5"
        y={4 + 16 * (1 - fillHeight / 100) + 1}
        width="9"
        height={16 * (fillHeight / 100)}
        rx="1"
        fill={getFillColor()}
      />
      {isCharging && (
        <path
          d="M13 8L10 13H12L11 16L14 11H12L13 8Z"
          fill="hsl(var(--background))"
          stroke="hsl(var(--background))"
          strokeWidth="0.5"
        />
      )}
    </svg>
  );
}

// Device node component with HoverCard for detailed metrics
function DeviceNode({ 
  device, 
  type, 
  index,
  total 
}: { 
  device: Inverter | BatteryBank | Meter; 
  type: "inverter" | "battery" | "meter";
  index: number;
  total: number;
}) {
  const getIcon = () => {
    if (type === "inverter") return <Cpu className="w-4 h-4" />;
    if (type === "battery") {
      const bat = device as BatteryBank;
      return <DynamicBatteryIcon soc={bat.metrics.soc} isCharging={bat.metrics.power >= 0} size={16} />;
    }
    return <Gauge className="w-4 h-4" />;
  };

  const getValue = () => {
    if (type === "inverter") {
      const inv = device as Inverter;
      return `${inv.metrics.solarPower.toFixed(1)} kW`;
    }
    if (type === "battery") {
      const bat = device as BatteryBank;
      return `${bat.metrics.soc}%`;
    }
    const meter = device as Meter;
    return `${Math.abs(meter.metrics.power).toFixed(1)} kW`;
  };

  const getColor = () => {
    if (type === "inverter") return "bg-warning/20 border-warning/40 text-warning";
    if (type === "battery") return "bg-cyan-400/20 border-cyan-400/40 text-cyan-400";
    return "bg-primary/20 border-primary/40 text-primary";
  };

  const renderHoverContent = () => {
    if (type === "inverter") {
      const inv = device as Inverter;
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-border">
            <Cpu className="w-4 h-4 text-warning" />
            <div>
              <p className="font-semibold text-sm">{inv.name}</p>
              <p className="text-xs text-muted-foreground">{inv.model}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-1.5">
              <Sun className="w-3 h-3 text-warning" />
              <span className="text-muted-foreground">Solar</span>
              <span className="ml-auto font-mono font-medium">{inv.metrics.solarPower.toFixed(1)} kW</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Grid3X3 className="w-3 h-3 text-primary" />
              <span className="text-muted-foreground">Grid</span>
              <span className="ml-auto font-mono font-medium">{inv.metrics.gridPower.toFixed(1)} kW</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Activity className="w-3 h-3 text-success" />
              <span className="text-muted-foreground">Load</span>
              <span className="ml-auto font-mono font-medium">{inv.metrics.loadPower.toFixed(1)} kW</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-cyan-400" />
              <span className="text-muted-foreground">Battery</span>
              <span className="ml-auto font-mono font-medium">{inv.metrics.batteryPower.toFixed(1)} kW</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-muted-foreground" />
              <span className="text-muted-foreground">DC Volt</span>
              <span className="ml-auto font-mono font-medium">{inv.metrics.dcVoltage} V</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Thermometer className="w-3 h-3 text-orange-400" />
              <span className="text-muted-foreground">Temp</span>
              <span className="ml-auto font-mono font-medium">{inv.metrics.temperature}°C</span>
            </div>
          </div>
          <div className="pt-2 border-t border-border">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Efficiency</span>
              <span className="font-mono font-medium text-success">{inv.metrics.efficiency.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      );
    }

    if (type === "battery") {
      const bat = device as BatteryBank;
      const isCharging = bat.metrics.power >= 0;
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-border">
            <DynamicBatteryIcon soc={bat.metrics.soc} isCharging={isCharging} size={18} className="text-cyan-400" />
            <div>
              <p className="font-semibold text-sm">{bat.name}</p>
              <p className="text-xs text-muted-foreground">{bat.model}</p>
            </div>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">State of Charge</span>
              <div className="flex items-center gap-1">
                <div className="w-16 h-2 bg-secondary rounded-full overflow-hidden">
                  <div 
                    className={cn("h-full rounded-full", bat.metrics.soc >= 60 ? "bg-success" : bat.metrics.soc >= 30 ? "bg-warning" : "bg-destructive")}
                    style={{ width: `${bat.metrics.soc}%` }}
                  />
                </div>
                <span className="font-mono font-medium w-8 text-right">{bat.metrics.soc}%</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                {isCharging ? <ArrowDown className="w-3 h-3 text-success" /> : <ArrowUp className="w-3 h-3 text-orange-400" />}
                <span className="text-muted-foreground">{isCharging ? "Charging" : "Discharging"}</span>
              </div>
              <span className="font-mono font-medium">{Math.abs(bat.metrics.power).toFixed(1)} kW</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Zap className="w-3 h-3 text-muted-foreground" />
                <span className="text-muted-foreground">Voltage</span>
              </div>
              <span className="font-mono font-medium">{bat.metrics.voltage.toFixed(1)} V</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Thermometer className="w-3 h-3 text-orange-400" />
                <span className="text-muted-foreground">Temperature</span>
              </div>
              <span className="font-mono font-medium">{bat.metrics.temperature}°C</span>
            </div>
          </div>
        </div>
      );
    }

    // Meter type
    const meter = device as Meter;
    const isExporting = meter.metrics.power < 0;
    const netImportExport = meter.metrics.exportKwh - meter.metrics.importKwh;
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <Gauge className="w-4 h-4 text-primary" />
          <div>
            <p className="font-semibold text-sm">{meter.name}</p>
            <p className="text-xs text-muted-foreground">{meter.model}</p>
          </div>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {isExporting ? <ArrowUp className="w-3 h-3 text-success" /> : <ArrowDown className="w-3 h-3 text-orange-400" />}
              <span className="text-muted-foreground">Current Power</span>
            </div>
            <span className={cn("font-mono font-medium", isExporting ? "text-success" : "text-orange-400")}>
              {isExporting ? "-" : "+"}{Math.abs(meter.metrics.power).toFixed(2)} kW
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Import Today</span>
            <span className="font-mono font-medium">{meter.metrics.importKwh.toFixed(2)} kWh</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Export Today</span>
            <span className="font-mono font-medium">{meter.metrics.exportKwh.toFixed(2)} kWh</span>
          </div>
          <div className="flex items-center justify-between pt-1 border-t border-border/50">
            <span className="text-muted-foreground">Net Import/Export</span>
            <span className={cn("font-mono font-medium", netImportExport >= 0 ? "text-success" : "text-orange-400")}>
              {netImportExport >= 0 ? "+" : ""}{netImportExport.toFixed(2)} kWh
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Frequency</span>
            <span className="font-mono font-medium">{meter.metrics.frequency.toFixed(2)} Hz</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Power Factor</span>
            <span className="font-mono font-medium">{meter.metrics.powerFactor.toFixed(2)}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <HoverCard openDelay={100} closeDelay={100}>
      <HoverCardTrigger asChild>
        <Link to={`/telemetry?device=${device.id}`}>
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1 + index * 0.05, type: "spring", stiffness: 300 }}
            className={cn(
              "relative w-12 h-12 sm:w-14 sm:h-14 rounded-xl border-2 flex flex-col items-center justify-center cursor-pointer",
              "hover:scale-110 transition-transform",
              getColor()
            )}
          >
            {getIcon()}
            <span className="text-[9px] sm:text-[10px] font-mono font-medium mt-0.5">{getValue()}</span>
            <div className={cn(
              "absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full border border-background",
              statusColors[device.status]
            )} />
          </motion.div>
        </Link>
      </HoverCardTrigger>
      <HoverCardContent side="top" className="w-64 p-3">
        {renderHoverContent()}
      </HoverCardContent>
    </HoverCard>
  );
}

// Flow line between sections
function FlowLine({ active }: { active?: boolean }) {
  return (
    <div className="flex items-center justify-center w-4 sm:w-8 h-full shrink-0">
      <motion.div
        className={cn(
          "h-0.5 w-full",
          active ? "bg-gradient-to-r from-warning via-success to-primary" : "bg-border"
        )}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ delay: 0.3, duration: 0.5 }}
      />
      {active && (
        <motion.div
          className="absolute rounded-full bg-white/80 w-1.5 h-1.5 sm:w-2 sm:h-2"
          animate={{ x: ["-100%", "100%"] }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        />
      )}
    </div>
  );
}

// Section containing devices of one type - with extra stats (horizontal layout)
function DeviceSection({ 
  title, 
  icon: Icon, 
  devices, 
  type, 
  aggregate,
  extraStats,
  color 
}: { 
  title: string;
  icon: React.ElementType;
  devices: (Inverter | BatteryBank | Meter)[];
  type: "inverter" | "battery" | "meter";
  aggregate: string;
  extraStats?: { label: string; value: string; highlight?: boolean }[];
  color: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-xl border bg-card/30 p-3",
        color
      )}
    >
      {/* Horizontal layout: Left (header + devices) | Right (stats) */}
      <div className="flex items-stretch gap-3">
        {/* Left side: Header and device nodes */}
        <div className="flex flex-col min-w-0">
          {/* Header with icon and title */}
          <div className="flex items-center gap-2 mb-2">
            <div className={cn("w-7 h-7 rounded-lg flex items-center justify-center shrink-0", color.replace("border-", "bg-").replace("/30", "/20"))}>
              <Icon className="w-3.5 h-3.5" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground leading-tight">{title}</p>
              <p className="text-[11px] text-muted-foreground font-mono">{aggregate}</p>
            </div>
          </div>
          
          {/* Device nodes */}
          {devices.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {devices.map((device, i) => (
                <DeviceNode key={device.id} device={device} type={type} index={i} total={devices.length} />
              ))}
            </div>
          )}
        </div>

        {/* Right side: Stats - vertical layout with divider */}
        {extraStats && extraStats.length > 0 && (
          <div className="flex items-center gap-3 ml-auto">
            <div className="w-px h-full bg-border/40 self-stretch" />
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {extraStats.map((stat, i) => (
                <div key={i} className="flex items-center gap-1.5 whitespace-nowrap">
                  <span className="text-[10px] text-muted-foreground">{stat.label}:</span>
                  <span className={cn(
                    "text-[11px] font-mono font-bold",
                    stat.highlight ? "text-success" : "text-foreground"
                  )}>{stat.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// Grid section with meters only
function GridSection({ 
  meters,
  gridPower,
  totalImport,
  totalExport
}: { 
  meters: Meter[];
  gridPower: number;
  totalImport: number;
  totalExport: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border bg-card/30 p-4 flex flex-col min-h-[140px] border-primary/30"
    >
      {/* Grid header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-primary/20">
          <Grid3X3 className="w-5 h-5 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">Grid</p>
          <p className="text-xs text-muted-foreground font-mono">{Math.abs(gridPower).toFixed(1)} kW</p>
        </div>
      </div>
      
      {/* Grid meter tiles */}
      <div className="flex flex-wrap gap-2 mb-3">
        {meters.map((meter, i) => (
          <DeviceNode key={meter.id} device={meter} type="meter" index={i} total={meters.length} />
        ))}
      </div>

      {/* Extra stats row - pushed to bottom */}
      <div className="flex items-center gap-x-4 gap-y-1 pt-2 mt-auto border-t border-border/30 flex-wrap">
        <div className="flex items-center gap-1.5 whitespace-nowrap">
          <span className="text-[11px] text-muted-foreground">Import:</span>
          <span className="text-[11px] font-mono font-semibold text-foreground whitespace-nowrap">{totalImport.toFixed(1)} kWh</span>
        </div>
        <div className="flex items-center gap-1.5 whitespace-nowrap">
          <span className="text-[11px] text-muted-foreground">Export:</span>
          <span className="text-[11px] font-mono font-semibold text-success whitespace-nowrap">{totalExport.toFixed(1)} kWh</span>
        </div>
      </div>
    </motion.div>
  );
}

// System visual block - compact horizontal layout
function SystemVisualBlock({ system, index }: { system: System; index: number }) {
  const agg = getSystemAggregates(system);
  const allInverters = system.inverterArrays.flatMap(arr => arr.inverters);
  const allBatteries = system.batteryArrays.flatMap(arr => arr.batteries);
  
  const hasFlow = agg.solarPower > 0 || agg.batteryPower !== 0;
  const hasBatteries = allBatteries.length > 0;
  const hasMeters = system.meters.length > 0;

  // Calculate daily stats (mock - in real app would come from data)
  const dailyGeneration = (agg.solarPower * 4.2).toFixed(1); // Mock daily estimate
  const peakGeneration = (agg.solarPower * 1.2).toFixed(1); // Mock peak
  
  // Load stats
  const totalLoad = agg.loadPower.toFixed(1);
  const dailyConsumption = (agg.loadPower * 5.2).toFixed(1); // Mock daily
  
  // Battery stats
  const batteryCharging = agg.batteryPower >= 0;
  const batteryTodayCharge = (Math.abs(agg.batteryPower) * 3.5).toFixed(1); // Mock
  const batteryTodayDischarge = (Math.abs(agg.batteryPower) * 2.8).toFixed(1); // Mock
  
  // Grid stats from meters
  const totalImport = system.meters.reduce((sum, m) => sum + m.metrics.importKwh, 0);
  const totalExport = system.meters.reduce((sum, m) => sum + m.metrics.exportKwh, 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="rounded-xl border border-border/50 bg-card/50 p-3"
    >
      {/* System Header - compact */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <Home className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{system.name}</h3>
            <p className="text-[10px] text-muted-foreground">
              {allInverters.length} inverters • {allBatteries.length} batteries • {system.meters.length} meters
            </p>
          </div>
        </div>
        <Link 
          to={`/devices?system=${system.id}`}
          className="text-xs text-primary hover:underline flex items-center gap-1"
        >
          Details <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      {/* Visual Flow Diagram - compact side-by-side layout */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 items-start">
        {/* Inverters Section */}
        {allInverters.length > 0 && (
          <DeviceSection
            title="Inverter"
            icon={Cpu}
            devices={allInverters}
            type="inverter"
            aggregate={`${agg.solarPower.toFixed(1)} kW`}
            extraStats={[
              { label: "Today", value: `${dailyGeneration} kWh`, highlight: true },
              { label: "Peak", value: `${peakGeneration} kW` },
              { label: "Peak Load", value: `${(agg.loadPower * 1.3).toFixed(1)} kW` },
              { label: "Avg Load", value: `${(agg.loadPower * 0.85).toFixed(1)} kW` },
            ]}
            color="border-warning/30 text-warning"
          />
        )}

        {/* Battery Section */}
        {hasBatteries && (
          <DeviceSection
            title="Battery"
            icon={() => <DynamicBatteryIcon soc={agg.avgBatterySoc} size={16} className="text-cyan-400" />}
            devices={allBatteries}
            type="battery"
            aggregate={`${agg.avgBatterySoc.toFixed(0)}% • ${Math.abs(agg.batteryPower).toFixed(1)} kW`}
            extraStats={[
              { label: "Charged", value: `${batteryTodayCharge} kWh`, highlight: batteryCharging },
              { label: "Discharged", value: `${batteryTodayDischarge} kWh` },
              { label: "Max Charge", value: `${(Math.abs(agg.batteryPower) * 1.5).toFixed(1)} kW` },
              { label: "Max Discharge", value: `${(Math.abs(agg.batteryPower) * 1.2).toFixed(1)} kW` },
            ]}
            color="border-cyan-400/30 text-cyan-400"
          />
        )}
      </div>
    </motion.div>
  );
}

export function VisualSystemDiagram() {
  const { hierarchy, loading, error } = useSystemHierarchy();

  if (loading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card p-4 flex items-center justify-center min-h-[200px]">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading system data...</span>
        </div>
      </div>
    );
  }

  if (error && !hierarchy) {
    return (
      <div className="rounded-xl border border-border/50 bg-card p-4 text-center min-h-[200px] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Unable to load system data. Retrying...</p>
      </div>
    );
  }

  const data = hierarchy;

  if (!data || (data.systems.length === 0 && data.meters.length === 0)) {
    return (
      <div className="rounded-xl border border-border/50 bg-card p-4 text-center min-h-[200px] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">No devices registered yet. Add devices to see your system overview.</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="rounded-xl border border-border/50 bg-card p-4"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">System Overview</h2>
          <p className="text-xs text-muted-foreground">{data.name}</p>
        </div>
        <Link
          to="/devices"
          className="text-xs text-primary hover:underline flex items-center gap-1"
        >
          View All <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      {/* Home-level meters - compact inline view */}
      {data.meters.length > 0 && (
        <div className="mb-3 p-3 rounded-xl border border-border/30 bg-secondary/20">
          <div className="flex items-center gap-2 mb-2">
            <Gauge className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-foreground">Home Meters</span>
          </div>
          <div className="grid gap-2">
            {data.meters.map((meter, i) => {
              const isExporting = meter.metrics.power < 0;
              const netImportExport = meter.metrics.exportKwh - meter.metrics.importKwh;
              return (
                <Link key={meter.id} to={`/telemetry?device=${meter.id}`}>
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 + i * 0.05 }}
                    className="flex items-center gap-3 p-2 rounded-lg border border-primary/20 bg-primary/5 hover:bg-primary/10 transition-colors cursor-pointer"
                  >
                    {/* Meter name & status */}
                    <div className="flex items-center gap-2 min-w-[120px]">
                      <div className="relative w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center shrink-0">
                        <Gauge className="w-4 h-4 text-primary" />
                        <div className={cn(
                          "absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full border border-background",
                          statusColors[meter.status]
                        )} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{meter.name}</p>
                        <p className="text-[10px] text-muted-foreground truncate">{meter.model}</p>
                      </div>
                    </div>

                    {/* Current Power */}
                    <div className="flex items-center gap-1 min-w-[80px]">
                      {isExporting ? <ArrowUp className="w-3 h-3 text-success" /> : <ArrowDown className="w-3 h-3 text-orange-400" />}
                      <div>
                        <p className={cn("text-xs font-mono font-semibold", isExporting ? "text-success" : "text-orange-400")}>
                          {Math.abs(meter.metrics.power).toFixed(2)} kW
                        </p>
                        <p className="text-[9px] text-muted-foreground">{isExporting ? "Exporting" : "Importing"}</p>
                      </div>
                    </div>

                    {/* Import */}
                    <div className="min-w-[70px] hidden sm:block">
                      <p className="text-xs font-mono font-medium text-foreground">{meter.metrics.importKwh.toFixed(1)} kWh</p>
                      <p className="text-[9px] text-muted-foreground">Import</p>
                    </div>

                    {/* Export */}
                    <div className="min-w-[70px] hidden sm:block">
                      <p className="text-xs font-mono font-medium text-foreground">{meter.metrics.exportKwh.toFixed(1)} kWh</p>
                      <p className="text-[9px] text-muted-foreground">Export</p>
                    </div>

                    {/* Net */}
                    <div className="min-w-[80px] hidden md:block">
                      <p className={cn("text-xs font-mono font-semibold", netImportExport >= 0 ? "text-success" : "text-orange-400")}>
                        {netImportExport >= 0 ? "+" : ""}{netImportExport.toFixed(1)} kWh
                      </p>
                      <p className="text-[9px] text-muted-foreground">Net Balance</p>
                    </div>

                    {/* Frequency */}
                    <div className="min-w-[60px] hidden lg:block">
                      <p className="text-xs font-mono font-medium text-foreground">{meter.metrics.frequency.toFixed(2)} Hz</p>
                      <p className="text-[9px] text-muted-foreground">Freq</p>
                    </div>

                    {/* Power Factor */}
                    <div className="min-w-[40px] hidden lg:block">
                      <p className="text-xs font-mono font-medium text-foreground">{meter.metrics.powerFactor.toFixed(2)}</p>
                      <p className="text-[9px] text-muted-foreground">PF</p>
                    </div>

                    <ArrowRight className="w-3 h-3 text-muted-foreground ml-auto shrink-0" />
                  </motion.div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Systems */}
      <div className="space-y-3">
        {data.systems.map((system, index) => (
          <SystemVisualBlock key={system.id} system={system} index={index} />
        ))}
      </div>
    </motion.div>
  );
}
