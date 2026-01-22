import { motion } from "framer-motion";
import { Cpu, Gauge, ChevronRight, ChevronDown, Sun, Zap, Home, Grid3X3, ArrowDown, ArrowUp, Layers, Battery, CircuitBoard } from "lucide-react";
import { cn } from "@/lib/utils";
import { Link } from "react-router-dom";
import { useState } from "react";
import {
  homeHierarchy,
  getInverterArrayAggregates,
  getBatteryArrayAggregates,
  getSystemAggregates,
  InverterArray,
  BatteryArray,
  Inverter,
  BatteryBank,
  Meter,
  System,
} from "@/data/mockData";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

const statusColors = {
  online: "status-online",
  offline: "status-offline",
  warning: "status-warning",
};

function DynamicBatteryIcon({ className, soc, isCharging }: { className?: string; soc: number; isCharging?: boolean }) {
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
      className={cn(className, isCharging && "animate-pulse")}
      xmlns="http://www.w3.org/2000/svg"
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

function getArrayStatus(onlineCount: number, warningCount: number, total: number): "online" | "warning" | "offline" {
  if (onlineCount === total) return "online";
  if (onlineCount === 0) return "offline";
  return "warning";
}

// System Card with aggregated data
function SystemCard({ system, index, defaultExpanded = true }: { system: System; index: number; defaultExpanded?: boolean }) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const agg = getSystemAggregates(system);
  const totalDevices = agg.inverterCount + agg.batteryCount;
  const onlineDevices = agg.onlineInverters + agg.onlineBatteries;
  const warningDevices = agg.warningInverters + agg.warningBatteries;
  const status = getArrayStatus(onlineDevices, warningDevices, totalDevices);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 * index }}
      className="rounded-lg border border-border/50 bg-card/50 overflow-hidden"
    >
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <button 
            className="w-full p-4 hover:bg-secondary/30 transition-colors"
            aria-expanded={isExpanded}
            aria-controls={`system-content-${system.id}`}
            aria-label={`${system.name} system with ${system.inverterArrays.length} inverter arrays and ${system.batteryArrays.length} battery arrays. Status: ${status}`}
          >
            {/* System Header */}
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <CircuitBoard className="w-5 h-5 text-primary" aria-hidden="true" />
              </div>
              <div className="flex-1 min-w-0 text-left">
                <p className="text-sm font-semibold text-foreground truncate">{system.name}</p>
                <p className="text-xs text-muted-foreground">
                  {system.inverterArrays.length} Inverter Array{system.inverterArrays.length > 1 ? "s" : ""}
                  {system.batteryArrays.length > 0 && ` • ${system.batteryArrays.length} Battery Array${system.batteryArrays.length > 1 ? "s" : ""}`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground capitalize">{status}</span>
                <div className={cn("w-2.5 h-2.5 rounded-full", statusColors[status])} aria-label={`Status: ${status}`} />
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                )}
              </div>
            </div>

            {/* System Aggregated Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
              <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
                <Sun className="w-4 h-4 text-warning" />
                <div className="min-w-0 text-left">
                  <p className="text-[10px] text-muted-foreground">Solar</p>
                  <p className="font-mono text-sm font-medium text-foreground">
                    {agg.solarPower.toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kW</span>
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
                <Home className="w-4 h-4 text-success" />
                <div className="min-w-0 text-left">
                  <p className="text-[10px] text-muted-foreground">Load</p>
                  <p className="font-mono text-sm font-medium text-foreground">
                    {agg.loadPower.toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kW</span>
                  </p>
                </div>
              </div>
              {agg.batteryCount > 0 ? (
                <>
                  <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
                    <DynamicBatteryIcon className="w-4 h-4 text-cyan-400" soc={agg.avgBatterySoc} />
                    <div className="min-w-0 text-left">
                      <p className="text-[10px] text-muted-foreground">Avg SOC</p>
                      <p className="font-mono text-sm font-medium text-foreground">
                        {agg.avgBatterySoc.toFixed(0)}<span className="text-xs text-muted-foreground ml-0.5">%</span>
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
                    {agg.batteryPower >= 0 ? (
                      <ArrowDown className="w-4 h-4 text-success" />
                    ) : (
                      <ArrowUp className="w-4 h-4 text-warning" />
                    )}
                    <div className="min-w-0 text-left">
                      <p className="text-[10px] text-muted-foreground">
                        {agg.batteryPower >= 0 ? "Charging" : "Discharging"}
                      </p>
                      <p className="font-mono text-sm font-medium text-foreground">
                        {Math.abs(agg.batteryPower).toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kW</span>
                      </p>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
                    <Grid3X3 className="w-4 h-4 text-primary" />
                    <div className="min-w-0 text-left">
                      <p className="text-[10px] text-muted-foreground">Grid</p>
                      <p className="font-mono text-sm font-medium text-foreground">
                        {agg.gridPower.toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kW</span>
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
                    <Battery className="w-4 h-4 text-cyan-400" />
                    <div className="min-w-0 text-left">
                      <p className="text-[10px] text-muted-foreground">Battery</p>
                      <p className="font-mono text-sm font-medium text-foreground">
                        {agg.batteryPower.toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kW</span>
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent id={`system-content-${system.id}`}>
          <div className="px-4 pb-4 space-y-4">
            {/* Inverter Arrays */}
            {system.inverterArrays.map((array) => (
              <InverterArrayCard key={array.id} array={array} />
            ))}

            {/* Battery Arrays */}
            {system.batteryArrays.map((array) => (
              <BatteryArrayCard key={array.id} array={array} />
            ))}

            {/* System-level Meters */}
            {system.meters.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">System Meters</p>
                {system.meters.map((meter) => (
                  <MeterCard key={meter.id} meter={meter} compact />
                ))}
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </motion.div>
  );
}

// Inverter Array Card
function InverterArrayCard({ array }: { array: InverterArray }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const agg = getInverterArrayAggregates(array);
  const status = getArrayStatus(agg.onlineCount, agg.warningCount, agg.inverterCount);

  return (
    <div className="rounded-lg border border-border/30 bg-secondary/20 overflow-hidden">
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <button 
            className="w-full p-3 hover:bg-secondary/40 transition-colors"
            aria-expanded={isExpanded}
            aria-controls={`inverter-array-content-${array.id}`}
            aria-label={`${array.name} with ${agg.inverterCount} inverters producing ${agg.solarPower.toFixed(1)} kW. Status: ${status}`}
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center">
                <Layers className="w-4 h-4 text-warning" aria-hidden="true" />
              </div>
              <div className="flex-1 min-w-0 text-left">
                <p className="text-sm font-medium text-foreground truncate">{array.name}</p>
                <p className="text-xs text-muted-foreground">
                  {agg.inverterCount} Inverter{agg.inverterCount > 1 ? "s" : ""} • {agg.solarPower.toFixed(1)} kW
                </p>
              </div>
              <div className="flex items-center gap-2">
                <div className={cn("w-2 h-2 rounded-full", statusColors[status])} aria-label={`Status: ${status}`} />
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                )}
              </div>
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent id={`inverter-array-content-${array.id}`}>
          <div className="px-3 pb-3 space-y-2">
            {array.inverters.map((inv) => (
              <InverterCard key={inv.id} inverter={inv} />
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

// Battery Array Card
function BatteryArrayCard({ array }: { array: BatteryArray }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const agg = getBatteryArrayAggregates(array);
  const status = getArrayStatus(agg.onlineCount, agg.warningCount, agg.batteryCount);

  return (
    <div className="rounded-lg border border-border/30 bg-secondary/20 overflow-hidden">
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <button 
            className="w-full p-3 hover:bg-secondary/40 transition-colors"
            aria-expanded={isExpanded}
            aria-controls={`battery-array-content-${array.id}`}
            aria-label={`${array.name} with ${agg.batteryCount} battery banks at ${agg.avgSoc.toFixed(0)}% average state of charge. Status: ${status}`}
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-cyan-400/10 flex items-center justify-center">
                <DynamicBatteryIcon className="w-4 h-4 text-cyan-400" soc={agg.avgSoc} isCharging={agg.totalPower > 0} aria-hidden="true" />
              </div>
              <div className="flex-1 min-w-0 text-left">
                <p className="text-sm font-medium text-foreground truncate">{array.name}</p>
                <p className="text-xs text-muted-foreground">
                  {agg.batteryCount} Bank{agg.batteryCount > 1 ? "s" : ""} • {agg.avgSoc.toFixed(0)}% SOC
                </p>
              </div>
              <div className="flex items-center gap-2">
                <div className={cn("w-2 h-2 rounded-full", statusColors[status])} aria-label={`Status: ${status}`} />
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                )}
              </div>
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent id={`battery-array-content-${array.id}`}>
          <div className="px-3 pb-3 space-y-2">
            {array.batteries.map((bat) => (
              <BatteryCard key={bat.id} battery={bat} />
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

// Individual Inverter Card
function InverterCard({ inverter }: { inverter: Inverter }) {
  return (
    <Link to={`/telemetry?device=${inverter.id}`}>
      <div className="p-3 rounded-lg bg-background/50 hover:bg-background/80 transition-colors">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
            <Cpu className="w-4 h-4 text-muted-foreground" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{inverter.name}</p>
            <p className="text-xs text-muted-foreground">{inverter.model}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn("w-2 h-2 rounded-full", statusColors[inverter.status])} />
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-1">
          <MetricPill icon={Sun} label="Solar" value={inverter.metrics.solarPower.toFixed(1)} unit="kW" color="text-warning" />
          <MetricPill icon={Grid3X3} label="Grid" value={inverter.metrics.gridPower.toFixed(1)} unit="kW" color="text-primary" />
          <MetricPill icon={Home} label="Load" value={inverter.metrics.loadPower.toFixed(1)} unit="kW" color="text-success" />
          <MetricPill icon={Battery} label="Bat" value={inverter.metrics.batteryPower.toFixed(1)} unit="kW" color="text-cyan-400" />
        </div>
      </div>
    </Link>
  );
}

// Individual Battery Card
function BatteryCard({ battery }: { battery: BatteryBank }) {
  const isCharging = battery.metrics.power >= 0;
  return (
    <Link to={`/telemetry?device=${battery.id}`}>
      <div className="p-3 rounded-lg bg-background/50 hover:bg-background/80 transition-colors">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
            <DynamicBatteryIcon className="w-4 h-4 text-muted-foreground" soc={battery.metrics.soc} isCharging={isCharging} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{battery.name}</p>
            <p className="text-xs text-muted-foreground">{battery.model}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn("w-2 h-2 rounded-full", statusColors[battery.status])} />
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-1">
          <MetricPill 
            icon={() => <DynamicBatteryIcon className="w-3 h-3" soc={battery.metrics.soc} />} 
            label="SOC" 
            value={battery.metrics.soc.toString()} 
            unit="%" 
            color="text-success" 
          />
          <MetricPill 
            icon={isCharging ? ArrowDown : ArrowUp} 
            label={isCharging ? "Chrg" : "Disch"} 
            value={Math.abs(battery.metrics.power).toFixed(1)} 
            unit="kW" 
            color={isCharging ? "text-success" : "text-warning"} 
          />
          <MetricPill icon={Gauge} label="Volt" value={battery.metrics.voltage.toFixed(1)} unit="V" color="text-muted-foreground" />
          <MetricPill icon={Gauge} label="Temp" value={battery.metrics.temperature.toString()} unit="°C" color="text-muted-foreground" />
        </div>
      </div>
    </Link>
  );
}

// Meter Card
function MeterCard({ meter, compact = false }: { meter: Meter; compact?: boolean }) {
  const isExporting = meter.metrics.power < 0;
  const netExport = meter.metrics.exportKwh - meter.metrics.importKwh;
  
  if (compact) {
    return (
      <Link to={`/telemetry?device=${meter.id}`}>
        <div className="p-3 rounded-lg bg-background/50 hover:bg-background/80 transition-colors">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
              <Gauge className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">{meter.name}</p>
              <p className="text-xs text-muted-foreground">{meter.model}</p>
            </div>
            <div className="flex items-center gap-2">
              <div className={cn("w-2 h-2 rounded-full", statusColors[meter.status])} />
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            </div>
          </div>
          <div className="grid grid-cols-4 gap-1">
            <MetricPill 
              icon={isExporting ? ArrowUp : ArrowDown} 
              label={isExporting ? "Export" : "Import"} 
              value={Math.abs(meter.metrics.power).toFixed(1)} 
              unit="kW" 
              color={isExporting ? "text-success" : "text-destructive"} 
            />
            <MetricPill icon={ArrowDown} label="Import" value={meter.metrics.importKwh.toFixed(1)} unit="kWh" color="text-destructive" />
            <MetricPill icon={ArrowUp} label="Export" value={meter.metrics.exportKwh.toFixed(1)} unit="kWh" color="text-success" />
            <MetricPill 
              icon={netExport >= 0 ? ArrowUp : ArrowDown} 
              label="Net" 
              value={Math.abs(netExport).toFixed(1)} 
              unit="kWh" 
              color={netExport >= 0 ? "text-success" : "text-destructive"} 
            />
          </div>
        </div>
      </Link>
    );
  }
  
  return (
    <Link to={`/telemetry?device=${meter.id}`}>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-4 rounded-lg border border-border/50 bg-card/50 hover:bg-secondary/30 transition-colors"
      >
        <div className="flex items-center gap-4 mb-3">
          <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
            <Gauge className="w-5 h-5 text-muted-foreground" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{meter.name}</p>
            <p className="text-xs text-muted-foreground">{meter.model}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground capitalize">{meter.status}</span>
            <div className={cn("w-2.5 h-2.5 rounded-full", statusColors[meter.status])} />
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
            {isExporting ? <ArrowUp className="w-4 h-4 text-success" /> : <ArrowDown className="w-4 h-4 text-destructive" />}
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">{isExporting ? "Exporting" : "Importing"}</p>
              <p className="font-mono text-sm font-medium text-foreground">
                {Math.abs(meter.metrics.power).toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kW</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
            <ArrowDown className="w-4 h-4 text-destructive" />
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">Import</p>
              <p className="font-mono text-sm font-medium text-foreground">
                {meter.metrics.importKwh.toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kWh</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
            <ArrowUp className="w-4 h-4 text-success" />
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">Export</p>
              <p className="font-mono text-sm font-medium text-foreground">
                {meter.metrics.exportKwh.toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kWh</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
            {netExport >= 0 ? <ArrowUp className="w-4 h-4 text-success" /> : <ArrowDown className="w-4 h-4 text-destructive" />}
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">{netExport >= 0 ? "Net Export" : "Net Import"}</p>
              <p className="font-mono text-sm font-medium text-foreground">
                {Math.abs(netExport).toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kWh</span>
              </p>
            </div>
          </div>
        </div>
      </motion.div>
    </Link>
  );
}

// Metric Pill Component
function MetricPill({ 
  icon: Icon, 
  label, 
  value, 
  unit, 
  color 
}: { 
  icon: React.ComponentType<{ className?: string }>; 
  label: string; 
  value: string; 
  unit: string; 
  color: string;
}) {
  return (
    <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
      <Icon className={cn("w-3 h-3 shrink-0", color)} />
      <div className="min-w-0 overflow-hidden">
        <p className="font-mono text-xs font-medium text-foreground truncate">
          {value}<span className="text-[10px] text-muted-foreground">{unit}</span>
        </p>
      </div>
    </div>
  );
}

export function HierarchicalDeviceOverview() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="glass-card p-6"
    >
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Device Hierarchy</h3>
          <p className="text-sm text-muted-foreground">{homeHierarchy.name}</p>
        </div>
        <Link
          to="/devices"
          className="text-sm text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
        >
          View All
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      <div className="space-y-4">
        {/* Home-level Meters */}
        {homeHierarchy.meters.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Home Meters</p>
            {homeHierarchy.meters.map((meter) => (
              <MeterCard key={meter.id} meter={meter} />
            ))}
          </div>
        )}

        {/* Systems */}
        {homeHierarchy.systems.map((system, index) => (
          <SystemCard key={system.id} system={system} index={index} />
        ))}
      </div>
    </motion.div>
  );
}