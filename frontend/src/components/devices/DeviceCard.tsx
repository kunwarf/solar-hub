import { motion } from "framer-motion";
import { Cpu, Gauge, Settings, Activity, Sun, Home, Grid3X3, ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface DeviceCardProps {
  id: string;
  name: string;
  type: "inverter" | "battery" | "meter";
  status: "online" | "offline" | "warning";
  model: string;
  serialNumber: string;
  metrics: {
    label: string;
    value: string;
    unit: string;
  }[];
  onConfigure?: () => void;
  onViewTelemetry?: () => void;
  delay?: number;
}

const typeColors = {
  inverter: {
    bg: "bg-solar/10",
    border: "border-solar/30",
    icon: "text-solar",
    accent: "text-solar",
  },
  battery: {
    bg: "bg-battery/10",
    border: "border-battery/30",
    icon: "text-battery",
    accent: "text-battery",
  },
  meter: {
    bg: "bg-grid/10",
    border: "border-grid/30",
    icon: "text-grid",
    accent: "text-grid",
  },
};

const statusColors = {
  online: "status-online",
  offline: "status-offline",
  warning: "status-warning",
};

const statusLabels = {
  online: { text: "Online", color: "bg-success/20 text-success" },
  offline: { text: "Offline", color: "bg-destructive/20 text-destructive" },
  warning: { text: "Warning", color: "bg-warning/20 text-warning" },
};

// Dynamic battery icon component
function DynamicBatteryIcon({ className, soc }: { className?: string; soc: number }) {
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
      className={className}
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
    </svg>
  );
}

// Device icon component based on type
function DeviceIcon({ type, className, soc = 78 }: { type: "inverter" | "battery" | "meter"; className?: string; soc?: number }) {
  if (type === "battery") {
    return <DynamicBatteryIcon className={className} soc={soc} />;
  }
  if (type === "inverter") {
    return <Cpu className={className} />;
  }
  return <Gauge className={className} />;
}

// Get telemetry metrics based on device type (matching dashboard)
const getDeviceMetrics = (type: "inverter" | "battery" | "meter") => {
  if (type === "inverter") {
    return [
      { label: "Solar", value: "4.2", unit: "kW", icon: Sun, color: "text-warning" },
      { label: "Grid", value: "0.8", unit: "kW", icon: Grid3X3, color: "text-primary" },
      { label: "Load", value: "2.1", unit: "kW", icon: Home, color: "text-success" },
      { label: "Battery", value: "1.3", unit: "kW", iconType: "battery-dynamic", color: "text-cyan-400" },
    ];
  }
  if (type === "battery") {
    const isCharging = true;
    return [
      { label: "SOC", value: "78", unit: "%", iconType: "battery-dynamic", color: "text-success" },
      { label: isCharging ? "Charging" : "Discharging", value: "1.3", unit: "kW", icon: isCharging ? ArrowDown : ArrowUp, color: isCharging ? "text-success" : "text-warning" },
      { label: "Voltage", value: "52.4", unit: "V", icon: Gauge, color: "text-muted-foreground" },
      { label: "Temp", value: "28", unit: "°C", icon: Gauge, color: "text-muted-foreground" },
    ];
  }
  if (type === "meter") {
    const currentPower = 0.3;
    const netExport = 5.7;
    const isExport = netExport > 0;
    return [
      { label: "Power", value: Math.abs(currentPower).toFixed(1), unit: "kW", icon: currentPower >= 0 ? ArrowDown : ArrowUp, color: currentPower >= 0 ? "text-destructive" : "text-success" },
      { label: "Import", value: "2.5", unit: "kWh", icon: ArrowDown, color: "text-destructive" },
      { label: "Export", value: "8.2", unit: "kWh", icon: ArrowUp, color: "text-success" },
      { label: isExport ? "Net Export" : "Net Import", value: Math.abs(netExport).toFixed(1), unit: "kWh", icon: isExport ? ArrowUp : ArrowDown, color: isExport ? "text-success" : "text-destructive" },
    ];
  }
  return [];
};

export function DeviceCard({
  id,
  name,
  type,
  status,
  model,
  serialNumber,
  onConfigure,
  onViewTelemetry,
  delay = 0,
}: DeviceCardProps) {
  const colors = typeColors[type];
  const statusConfig = statusLabels[status];
  const telemetryMetrics = getDeviceMetrics(type);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className={cn(
        "glass-card-hover p-5 border",
        colors.bg,
        colors.border
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-4 mb-4">
        <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", colors.bg)}>
          <DeviceIcon type={type} className={cn("w-6 h-6", colors.icon)} soc={78} />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-foreground truncate">{name}</h3>
          <p className="text-xs text-muted-foreground capitalize">{type}</p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground capitalize">{status}</span>
          <div className={cn("w-2.5 h-2.5 rounded-full", statusColors[status])} />
        </div>
      </div>

      {/* Telemetry Metrics Grid - matching dashboard style */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        {telemetryMetrics.map((metric, idx) => {
          const soc = metric.label === "SOC" ? parseFloat(metric.value) : 78;
          return (
            <div
              key={idx}
              className="flex items-center gap-2 p-2 rounded-md bg-background/50"
            >
              {metric.iconType === "battery-dynamic" ? (
                <DynamicBatteryIcon className={cn("w-4 h-4", metric.color)} soc={soc} />
              ) : metric.icon ? (
                <metric.icon className={cn("w-4 h-4", metric.color)} />
              ) : null}
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

      {/* Model & Serial */}
      <div className="mb-4 p-2 rounded-lg bg-muted/50">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Model</span>
          <span className="text-foreground font-medium">{model}</span>
        </div>
        <div className="flex justify-between text-xs mt-1">
          <span className="text-muted-foreground">Serial</span>
          <span className="font-mono text-foreground">{serialNumber}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          onClick={onViewTelemetry}
        >
          <Activity className="w-4 h-4 mr-2" />
          Telemetry
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          onClick={onConfigure}
        >
          <Settings className="w-4 h-4 mr-2" />
          Configure
        </Button>
      </div>
    </motion.div>
  );
}