import { motion } from "framer-motion";
import { Cpu, Gauge, ChevronRight, ChevronDown, Sun, Home, Grid3X3, ArrowDown, ArrowUp, Battery, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Link } from "react-router-dom";
import { useState, useEffect, useCallback, useMemo } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useDevicesForUI, type DeviceForUI } from "@/hooks/useDevices";
import { dashboardService, type DevicePowerData, type StatsData, type DeviceStatsData } from "@/api";

const statusColors: Record<string, string> = {
  online: "status-online",
  offline: "status-offline",
  warning: "status-warning",
  error: "status-offline",
  maintenance: "status-warning",
  unknown: "status-offline",
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

// Individual Inverter Card
function InverterCard({
  device,
  telemetry,
  stats
}: {
  device: DeviceForUI;
  telemetry?: DevicePowerData;
  stats?: DeviceStatsData;
}) {
  const solarPower = telemetry?.pv_power_w !== undefined ? telemetry.pv_power_w / 1000 : 0;
  const gridPower = telemetry?.grid_power_w !== undefined ? telemetry.grid_power_w / 1000 : 0;
  const loadPower = telemetry?.load_power_w !== undefined ? telemetry.load_power_w / 1000 : 0;
  const batteryPower = telemetry?.battery_power_w !== undefined ? telemetry.battery_power_w / 1000 : 0;

  return (
    <Link to={`/telemetry?device=${device.id}`}>
      <div className="p-3 rounded-lg bg-background/50 hover:bg-background/80 transition-colors">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
            <Cpu className="w-4 h-4 text-muted-foreground" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{device.name}</p>
            <p className="text-xs text-muted-foreground">{device.model}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn("w-2 h-2 rounded-full", statusColors[device.status])} />
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-1">
          <MetricPill icon={Sun} label="Solar" value={solarPower.toFixed(1)} unit="kW" color="text-warning" />
          <MetricPill icon={Grid3X3} label="Grid" value={Math.abs(gridPower).toFixed(1)} unit="kW" color="text-primary" />
          <MetricPill icon={Home} label="Load" value={loadPower.toFixed(1)} unit="kW" color="text-success" />
          <MetricPill icon={Battery} label="Bat" value={Math.abs(batteryPower).toFixed(1)} unit="kW" color="text-cyan-400" />
        </div>
        {stats && (
          <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-border/30">
            <div className="text-xs">
              <span className="text-muted-foreground">Today: </span>
              <span className="text-success font-mono">{stats.energy_today_kwh.toFixed(1)} kWh</span>
            </div>
            <div className="text-xs">
              <span className="text-muted-foreground">Peak: </span>
              <span className="text-warning font-mono">{stats.peak_power_kw.toFixed(1)} kW</span>
            </div>
          </div>
        )}
      </div>
    </Link>
  );
}

// Individual Battery Card
function BatteryCard({
  device,
  telemetry
}: {
  device: DeviceForUI;
  telemetry?: DevicePowerData;
}) {
  const soc = telemetry?.battery_soc_pct !== undefined ? telemetry.battery_soc_pct : 0;
  const power = telemetry?.battery_power_w !== undefined ? telemetry.battery_power_w / 1000 : 0;
  const isCharging = telemetry?.is_charging ?? power > 0;

  return (
    <Link to={`/telemetry?device=${device.id}`}>
      <div className="p-3 rounded-lg bg-background/50 hover:bg-background/80 transition-colors">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
            <DynamicBatteryIcon className="w-4 h-4 text-muted-foreground" soc={soc} isCharging={isCharging} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{device.name}</p>
            <p className="text-xs text-muted-foreground">{device.model}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn("w-2 h-2 rounded-full", statusColors[device.status])} />
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-1">
          <MetricPill
            icon={() => <DynamicBatteryIcon className="w-3 h-3" soc={soc} />}
            label="SOC"
            value={soc.toFixed(0)}
            unit="%"
            color="text-success"
          />
          <MetricPill
            icon={isCharging ? ArrowDown : ArrowUp}
            label={isCharging ? "Chrg" : "Disch"}
            value={Math.abs(power).toFixed(1)}
            unit="kW"
            color={isCharging ? "text-success" : "text-warning"}
          />
          <MetricPill icon={Gauge} label="Volt" value="52.4" unit="V" color="text-muted-foreground" />
          <MetricPill icon={Gauge} label="Temp" value="28" unit="°C" color="text-muted-foreground" />
        </div>
      </div>
    </Link>
  );
}

// Meter Card
function MeterCard({
  device,
  telemetry
}: {
  device: DeviceForUI;
  telemetry?: DevicePowerData;
}) {
  const gridPower = telemetry?.grid_power_w !== undefined ? telemetry.grid_power_w / 1000 : 0;
  const isExporting = gridPower < 0;

  // Mock cumulative values (would come from stats API in production)
  const importKwh = 2.5;
  const exportKwh = 8.2;
  const netBalance = exportKwh - importKwh;

  return (
    <Link to={`/telemetry?device=${device.id}`}>
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
            <p className="text-sm font-medium text-foreground truncate">{device.name}</p>
            <p className="text-xs text-muted-foreground">{device.model}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground capitalize">{device.status}</span>
            <div className={cn("w-2.5 h-2.5 rounded-full", statusColors[device.status])} />
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
            {isExporting ? <ArrowUp className="w-4 h-4 text-success" /> : <ArrowDown className="w-4 h-4 text-destructive" />}
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">{isExporting ? "Exporting" : "Importing"}</p>
              <p className="font-mono text-sm font-medium text-foreground">
                {Math.abs(gridPower).toFixed(2)}<span className="text-xs text-muted-foreground ml-0.5">kW</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
            <ArrowDown className="w-4 h-4 text-destructive" />
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">Import</p>
              <p className="font-mono text-sm font-medium text-foreground">
                {importKwh.toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kWh</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
            <ArrowUp className="w-4 h-4 text-success" />
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">Export</p>
              <p className="font-mono text-sm font-medium text-foreground">
                {exportKwh.toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kWh</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-md bg-background/50">
            {netBalance >= 0 ? <ArrowUp className="w-4 h-4 text-success" /> : <ArrowDown className="w-4 h-4 text-destructive" />}
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">{netBalance >= 0 ? "Net Export" : "Net Import"}</p>
              <p className="font-mono text-sm font-medium text-foreground">
                +{Math.abs(netBalance).toFixed(1)}<span className="text-xs text-muted-foreground ml-0.5">kWh</span>
              </p>
            </div>
          </div>
        </div>
      </motion.div>
    </Link>
  );
}

// Device Group Card (Inverters or Batteries)
function DeviceGroupCard({
  title,
  subtitle,
  icon: Icon,
  iconColor,
  devices,
  telemetryMap,
  statsMap,
  type,
  aggregatedMetrics,
}: {
  title: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  devices: DeviceForUI[];
  telemetryMap: Map<string, DevicePowerData>;
  statsMap: Map<string, DeviceStatsData>;
  type: "inverter" | "battery";
  aggregatedMetrics: {
    totalPower: number;
    avgSoc?: number;
    isCharging?: boolean;
    todayEnergy?: number;
    peakPower?: number;
  };
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const onlineCount = devices.filter(d => d.status === "online").length;
  const status: string = onlineCount === devices.length ? "online" : onlineCount === 0 ? "offline" : "warning";

  return (
    <div className="rounded-lg border border-border/30 bg-secondary/20 overflow-hidden">
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <button className="w-full p-3 hover:bg-secondary/40 transition-colors">
            <div className="flex items-center gap-3">
              <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", iconColor)}>
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0 text-left">
                <p className="text-sm font-medium text-foreground truncate">{title}</p>
                <p className="text-xs text-muted-foreground">{subtitle}</p>
              </div>
              <div className="flex items-center gap-2">
                <div className={cn("w-2 h-2 rounded-full", statusColors[status])} />
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </div>
            </div>

            {/* Aggregated metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
              {type === "inverter" ? (
                <>
                  <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
                    <Sun className="w-3 h-3 text-warning" />
                    <span className="font-mono text-xs">{aggregatedMetrics.totalPower.toFixed(1)} kW</span>
                  </div>
                  <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
                    <span className="text-[10px] text-muted-foreground">Today:</span>
                    <span className="font-mono text-xs text-success">{(aggregatedMetrics.todayEnergy || 0).toFixed(1)} kWh</span>
                  </div>
                  <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
                    <span className="text-[10px] text-muted-foreground">Peak:</span>
                    <span className="font-mono text-xs text-warning">{(aggregatedMetrics.peakPower || 0).toFixed(1)} kW</span>
                  </div>
                  <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
                    <span className="text-[10px] text-muted-foreground">Avg Load:</span>
                    <span className="font-mono text-xs">{((aggregatedMetrics.todayEnergy || 0) / 8).toFixed(1)} kW</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
                    <DynamicBatteryIcon className="w-3 h-3 text-cyan-400" soc={aggregatedMetrics.avgSoc || 0} isCharging={aggregatedMetrics.isCharging} />
                    <span className="font-mono text-xs">{(aggregatedMetrics.avgSoc || 0).toFixed(0)}%</span>
                  </div>
                  <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
                    {aggregatedMetrics.isCharging ? (
                      <ArrowDown className="w-3 h-3 text-success" />
                    ) : (
                      <ArrowUp className="w-3 h-3 text-warning" />
                    )}
                    <span className="font-mono text-xs">{Math.abs(aggregatedMetrics.totalPower).toFixed(1)} kW</span>
                  </div>
                  <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
                    <span className="text-[10px] text-muted-foreground">Charged:</span>
                    <span className="font-mono text-xs text-success">18.6 kWh</span>
                  </div>
                  <div className="flex items-center gap-1 p-1.5 rounded bg-background/50">
                    <span className="text-[10px] text-muted-foreground">Discharged:</span>
                    <span className="font-mono text-xs text-warning">14.8 kWh</span>
                  </div>
                </>
              )}
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="px-3 pb-3 space-y-2">
            {devices.map((device) => {
              const telemetry = telemetryMap.get(device.serialNumber);
              const stats = statsMap.get(device.serialNumber);

              if (type === "inverter") {
                return <InverterCard key={device.id} device={device} telemetry={telemetry} stats={stats} />;
              }
              return <BatteryCard key={device.id} device={device} telemetry={telemetry} />;
            })}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

export function HierarchicalDeviceOverview() {
  // Fetch real devices from API
  const { devices, isLoading: devicesLoading } = useDevicesForUI({
    autoRefresh: true,
    refreshInterval: 30000,
  });

  // Fetch real-time telemetry
  const [telemetryMap, setTelemetryMap] = useState<Map<string, DevicePowerData>>(new Map());
  const [statsMap, setStatsMap] = useState<Map<string, DeviceStatsData>>(new Map());
  const [isLoading, setIsLoading] = useState(true);

  const fetchTelemetry = useCallback(async () => {
    try {
      const [powerFlow, stats] = await Promise.all([
        dashboardService.getPowerFlow(),
        dashboardService.getStats(),
      ]);

      if (powerFlow.devices && powerFlow.devices.length > 0) {
        const newTelemetryMap = new Map<string, DevicePowerData>();
        for (const device of powerFlow.devices) {
          newTelemetryMap.set(device.serial_number, device);
        }
        setTelemetryMap(newTelemetryMap);
      }

      if (stats.devices && stats.devices.length > 0) {
        const newStatsMap = new Map<string, DeviceStatsData>();
        for (const device of stats.devices) {
          newStatsMap.set(device.serial_number, device);
        }
        setStatsMap(newStatsMap);
      }
    } catch (err) {
      console.warn('Failed to fetch telemetry:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 5000);
    return () => clearInterval(interval);
  }, [fetchTelemetry]);

  // Group devices by type
  const { inverters, batteries, meters } = useMemo(() => {
    const inverters: DeviceForUI[] = [];
    const batteries: DeviceForUI[] = [];
    const meters: DeviceForUI[] = [];

    for (const device of devices) {
      if (device.type === "inverter") {
        inverters.push(device);
      } else if (device.type === "battery") {
        batteries.push(device);
      } else if (device.type === "meter") {
        meters.push(device);
      }
    }

    return { inverters, batteries, meters };
  }, [devices]);

  // Calculate aggregated metrics for inverters
  const inverterMetrics = useMemo(() => {
    let totalPower = 0;
    let todayEnergy = 0;
    let peakPower = 0;

    for (const device of inverters) {
      const telemetry = telemetryMap.get(device.serialNumber);
      const stats = statsMap.get(device.serialNumber);

      if (telemetry) {
        totalPower += telemetry.pv_power_w / 1000;
      }
      if (stats) {
        todayEnergy += stats.energy_today_kwh;
        peakPower = Math.max(peakPower, stats.peak_power_kw);
      }
    }

    return { totalPower, todayEnergy, peakPower };
  }, [inverters, telemetryMap, statsMap]);

  // Calculate aggregated metrics for batteries
  const batteryMetrics = useMemo(() => {
    let totalPower = 0;
    let totalSoc = 0;
    let chargingCount = 0;

    for (const device of batteries) {
      const telemetry = telemetryMap.get(device.serialNumber);

      if (telemetry) {
        totalPower += telemetry.battery_power_w / 1000;
        totalSoc += telemetry.battery_soc_pct;
        if (telemetry.is_charging) chargingCount++;
      }
    }

    const avgSoc = batteries.length > 0 ? totalSoc / batteries.length : 0;
    const isCharging = chargingCount > batteries.length / 2;

    return { totalPower, avgSoc, isCharging };
  }, [batteries, telemetryMap]);

  if (devicesLoading || isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6"
      >
        <div className="flex items-center justify-center gap-2 py-8">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <span className="text-muted-foreground">Loading devices...</span>
        </div>
      </motion.div>
    );
  }

  if (devices.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6"
      >
        <div className="text-center py-8">
          <p className="text-muted-foreground">No devices found</p>
          <Link to="/devices/manage" className="text-sm text-primary hover:underline mt-2 inline-block">
            Add your first device
          </Link>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="glass-card p-6"
    >
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground">System Overview</h3>
          <p className="text-sm text-muted-foreground">Home Solar System</p>
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
        {/* Meters Section */}
        {meters.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Home Meters</p>
            {meters.map((meter) => (
              <MeterCard
                key={meter.id}
                device={meter}
                telemetry={telemetryMap.get(meter.serialNumber)}
              />
            ))}
          </div>
        )}

        {/* Inverters Section */}
        {inverters.length > 0 && (
          <DeviceGroupCard
            title="Inverter"
            subtitle={`${inverters.length} inverter${inverters.length > 1 ? "s" : ""} • ${inverterMetrics.totalPower.toFixed(1)} kW`}
            icon={Sun}
            iconColor="bg-warning/10 text-warning"
            devices={inverters}
            telemetryMap={telemetryMap}
            statsMap={statsMap}
            type="inverter"
            aggregatedMetrics={inverterMetrics}
          />
        )}

        {/* Batteries Section */}
        {batteries.length > 0 && (
          <DeviceGroupCard
            title="Battery"
            subtitle={`${batteryMetrics.avgSoc.toFixed(0)}% • ${Math.abs(batteryMetrics.totalPower).toFixed(1)} kW`}
            icon={() => <DynamicBatteryIcon className="w-4 h-4 text-cyan-400" soc={batteryMetrics.avgSoc} isCharging={batteryMetrics.isCharging} />}
            iconColor="bg-cyan-400/10"
            devices={batteries}
            telemetryMap={telemetryMap}
            statsMap={statsMap}
            type="battery"
            aggregatedMetrics={batteryMetrics}
          />
        )}
      </div>
    </motion.div>
  );
}
