import { motion } from "framer-motion";
import { Cpu, Gauge, ChevronRight, Sun, Zap, Home, Grid3X3, ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { Link } from "react-router-dom";

interface DeviceMetric {
  label: string;
  value: string;
  unit: string;
  icon: React.ComponentType<{ className?: string }> | "battery-dynamic";
  color: string;
}

interface Device {
  id: string;
  name: string;
  type: "inverter" | "battery" | "meter";
  status: "online" | "offline" | "warning";
  value: string;
  unit: string;
}

interface DeviceOverviewProps {
  devices: Device[];
}

const deviceIcons = {
  inverter: Cpu,
  battery: ({ className, soc = 78 }: { className?: string; soc?: number }) => (
    <DynamicBatteryIcon className={className} soc={soc} />
  ),
  meter: Gauge,
};

const statusColors = {
  online: "status-online",
  offline: "status-offline",
  warning: "status-warning",
};

// Dynamic battery icon component with charging indicator
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
      {/* Battery terminal */}
      <rect x="10" y="2" width="4" height="2" rx="0.5" fill="currentColor" opacity="0.6" />
      {/* Battery body outline */}
      <rect x="6" y="4" width="12" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none" />
      {/* Battery fill based on SOC */}
      <rect
        x="7.5"
        y={4 + 16 * (1 - fillHeight / 100) + 1}
        width="9"
        height={16 * (fillHeight / 100)}
        rx="1"
        fill={getFillColor()}
      />
      {/* Charging bolt icon */}
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

// Mock battery status - in real app this would come from device data
const getBatteryStatus = () => {
  const power = 1.3; // kW - positive = charging, negative = discharging
  return {
    isCharging: power > 0,
    power: Math.abs(power),
  };
};

// Mock meter data - in real app this would come from device data
const getMeterNetData = () => {
  const importKwh = 2.5;
  const exportKwh = 8.2;
  const net = exportKwh - importKwh;
  return {
    value: Math.abs(net).toFixed(1),
    isExport: net > 0,
  };
};

// Generate telemetry metrics based on device type
const getDeviceMetrics = (device: Device): DeviceMetric[] => {
  if (device.type === "inverter") {
    return [
      { label: "Solar", value: "4.2", unit: "kW", icon: Sun, color: "text-warning" },
      { label: "Grid", value: "0.8", unit: "kW", icon: Grid3X3, color: "text-primary" },
      { label: "Load", value: "2.1", unit: "kW", icon: Home, color: "text-success" },
      { label: "Battery", value: "1.3", unit: "kW", icon: "battery-dynamic", color: "text-cyan-400" },
    ];
  }
  if (device.type === "battery") {
    const batteryStatus = getBatteryStatus();
    return [
      { label: "SOC", value: "78", unit: "%", icon: "battery-dynamic", color: "text-success" },
      { label: batteryStatus.isCharging ? "Charging" : "Discharging", value: batteryStatus.power.toFixed(1), unit: "kW", icon: batteryStatus.isCharging ? ArrowDown : ArrowUp, color: batteryStatus.isCharging ? "text-success" : "text-warning" },
      { label: "Voltage", value: "52.4", unit: "V", icon: Gauge, color: "text-muted-foreground" },
      { label: "Temp", value: "28", unit: "°C", icon: Gauge, color: "text-muted-foreground" },
    ];
  }
  if (device.type === "meter") {
    const netData = getMeterNetData();
    const currentPower = 0.3; // kW - positive = importing, negative = exporting
    return [
      { label: "Power", value: Math.abs(currentPower).toFixed(1), unit: "kW", icon: currentPower >= 0 ? ArrowDown : ArrowUp, color: currentPower >= 0 ? "text-destructive" : "text-success" },
      { label: "Import", value: "2.5", unit: "kWh", icon: ArrowDown, color: "text-destructive" },
      { label: "Export", value: "8.2", unit: "kWh", icon: ArrowUp, color: "text-success" },
      { label: netData.isExport ? "Net Export" : "Net Import", value: netData.value, unit: "kWh", icon: netData.isExport ? ArrowUp : ArrowDown, color: netData.isExport ? "text-success" : "text-destructive" },
    ];
  }
  return [];
};

export function DeviceOverview({ devices }: DeviceOverviewProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="glass-card p-6"
    >
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-foreground">Device Status</h3>
        <Link
          to="/devices"
          className="text-sm text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
        >
          View All
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      <div className="space-y-4">
        {devices.map((device, index) => {
          const Icon = deviceIcons[device.type];
          const metrics = getDeviceMetrics(device);
          
          return (
            <Link to={`/telemetry?device=${device.id}`} key={device.id}>
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 * index }}
                className="p-4 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer group"
              >
                {/* Device Header */}
                <div className="flex items-center gap-4 mb-3">
                  <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                    <Icon className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate group-hover:text-primary transition-colors">{device.name}</p>
                    <p className="text-xs text-muted-foreground capitalize">{device.type}</p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground capitalize">{device.status}</span>
                    <div className={cn("w-2.5 h-2.5 rounded-full", statusColors[device.status])} />
                    <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>
                </div>

                {/* Telemetry Metrics Grid */}
                {metrics.length > 0 && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {metrics.map((metric, idx) => {
                      const soc = metric.label === "SOC" ? parseFloat(metric.value) : 78;
                      return (
                        <div
                          key={idx}
                          className="flex items-center gap-2 p-2 rounded-md bg-background/50"
                        >
                          {metric.icon === "battery-dynamic" ? (
                            <DynamicBatteryIcon className={cn("w-4 h-4", metric.color)} soc={soc} />
                          ) : (
                            <metric.icon className={cn("w-4 h-4", metric.color)} />
                          )}
                          <div className="min-w-0">
                            <p className="text-[10px] text-muted-foreground truncate">{metric.label}</p>
                            <p className="font-mono text-sm font-medium text-foreground">
                              {metric.value}
                              <span className="text-xs text-muted-foreground ml-0.5">{metric.unit}</span>
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </motion.div>
            </Link>
          );
        })}
      </div>
    </motion.div>
  );
}
