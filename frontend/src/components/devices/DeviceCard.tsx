import { motion } from "framer-motion";
import { Cpu, Gauge, Settings, Activity, Sun, Home, Grid3X3, ArrowDown, ArrowUp, Unlink, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

interface DeviceTelemetry {
  pv_power_w?: number;
  grid_power_w?: number;
  load_power_w?: number;
  battery_power_w?: number;
  battery_soc_pct?: number;
  is_charging?: boolean;
  raw?: Record<string, any>;
}

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
  telemetry?: DeviceTelemetry;  // Real-time telemetry from power-flow API
  onConfigure?: () => void;
  onViewTelemetry?: () => void;
  onUnclaim?: () => void;
  onRemove?: () => void;
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

// Get telemetry metrics based on device type and real telemetry data
const getDeviceMetrics = (type: "inverter" | "battery" | "meter", telemetry?: DeviceTelemetry) => {
  if (type === "inverter") {
    // Use real telemetry when available, convert W to kW
    const solarKw = telemetry?.pv_power_w !== undefined ? (telemetry.pv_power_w / 1000).toFixed(1) : "--";
    const gridKw = telemetry?.grid_power_w !== undefined ? (Math.abs(telemetry.grid_power_w) / 1000).toFixed(1) : "--";
    const loadKw = telemetry?.load_power_w !== undefined ? (telemetry.load_power_w / 1000).toFixed(1) : "--";
    const batteryKw = telemetry?.battery_power_w !== undefined ? (Math.abs(telemetry.battery_power_w) / 1000).toFixed(1) : "--";
    const isExporting = telemetry?.grid_power_w !== undefined && telemetry.grid_power_w < 0;
    const isCharging = telemetry?.is_charging ?? (telemetry?.battery_power_w !== undefined && telemetry.battery_power_w > 0);

    return [
      { label: "Solar", value: solarKw, unit: "kW", icon: Sun, color: "text-warning" },
      { label: isExporting ? "Export" : "Grid", value: gridKw, unit: "kW", icon: Grid3X3, color: isExporting ? "text-success" : "text-primary" },
      { label: "Load", value: loadKw, unit: "kW", icon: Home, color: "text-success" },
      { label: isCharging ? "Charging" : "Discharging", value: batteryKw, unit: "kW", iconType: "battery-dynamic", color: isCharging ? "text-cyan-400" : "text-orange-400" },
    ];
  }
  if (type === "battery") {
    const soc = telemetry?.battery_soc_pct !== undefined ? telemetry.battery_soc_pct.toFixed(0) : "--";
    const powerKw = telemetry?.battery_power_w !== undefined ? (Math.abs(telemetry.battery_power_w) / 1000).toFixed(1) : "--";
    const isCharging = telemetry?.is_charging ?? (telemetry?.battery_power_w !== undefined && telemetry.battery_power_w > 0);
    const socNum = telemetry?.battery_soc_pct ?? 50;
    const voltageV = telemetry?.raw?.battery_voltage_v;
    const tempC = telemetry?.raw?.battery_temp_c;

    return [
      { label: "SOC", value: soc, unit: "%", iconType: "battery-dynamic", color: socNum >= 60 ? "text-success" : socNum >= 30 ? "text-warning" : "text-destructive", soc: socNum },
      { label: isCharging ? "Charging" : "Discharging", value: powerKw, unit: "kW", icon: isCharging ? ArrowDown : ArrowUp, color: isCharging ? "text-success" : "text-warning" },
      { label: "Voltage", value: voltageV != null ? Number(voltageV).toFixed(1) : "--", unit: "V", icon: Gauge, color: "text-muted-foreground" },
      { label: "Temp", value: tempC != null ? Number(tempC).toFixed(1) : "--", unit: "°C", icon: Gauge, color: "text-muted-foreground" },
    ];
  }
  if (type === "meter") {
    const gridW = telemetry?.grid_power_w ?? 0;
    const gridKw = Math.abs(gridW) / 1000;
    const isExport = gridW < 0;

    return [
      { label: "Power", value: gridKw.toFixed(1), unit: "kW", icon: isExport ? ArrowUp : ArrowDown, color: isExport ? "text-success" : "text-destructive" },
      { label: "Import", value: "--", unit: "kWh", icon: ArrowDown, color: "text-destructive" },
      { label: "Export", value: "--", unit: "kWh", icon: ArrowUp, color: "text-success" },
      { label: isExport ? "Exporting" : "Importing", value: gridKw.toFixed(1), unit: "kW", icon: isExport ? ArrowUp : ArrowDown, color: isExport ? "text-success" : "text-destructive" },
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
  telemetry,
  onConfigure,
  onViewTelemetry,
  onUnclaim,
  onRemove,
  delay = 0,
}: DeviceCardProps) {
  const colors = typeColors[type];
  const statusConfig = statusLabels[status];
  const telemetryMetrics = getDeviceMetrics(type, telemetry);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className={cn(
        "glass-card-hover p-3 sm:p-5 border",
        colors.bg,
        colors.border
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 sm:gap-4 mb-3 sm:mb-4">
        <div className={cn("w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center shrink-0", colors.bg)}>
          <DeviceIcon type={type} className={cn("w-5 h-5 sm:w-6 sm:h-6", colors.icon)} soc={telemetry?.battery_soc_pct ?? 78} />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm sm:text-base text-foreground truncate">{name}</h3>
          <p className="text-[10px] sm:text-xs text-muted-foreground capitalize">{type}</p>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          <span className="text-[10px] sm:text-xs text-muted-foreground capitalize hidden xs:inline">{status}</span>
          <div className={cn("w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-full", statusColors[status])} />
        </div>
      </div>

      {/* Telemetry Metrics Grid - matching dashboard style */}
      <div className="grid grid-cols-2 gap-1.5 sm:gap-2 mb-3 sm:mb-4">
        {telemetryMetrics.map((metric, idx) => {
          // Use explicit soc from metric if available, otherwise parse from value or default
          const soc = (metric as any).soc ?? (metric.label === "SOC" && metric.value !== "--" ? parseFloat(metric.value) : 78);
          return (
            <div
              key={idx}
              className="flex items-center gap-1.5 sm:gap-2 p-1.5 sm:p-2 rounded-md bg-background/50"
            >
              {metric.iconType === "battery-dynamic" ? (
                <DynamicBatteryIcon className={cn("w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0", metric.color)} soc={soc} />
              ) : metric.icon ? (
                <metric.icon className={cn("w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0", metric.color)} />
              ) : null}
              <div className="min-w-0">
                <p className="text-[9px] sm:text-[10px] text-muted-foreground truncate">{metric.label}</p>
                <p className="font-mono text-xs sm:text-sm font-medium text-foreground">
                  {metric.value}
                  <span className="text-[10px] sm:text-xs text-muted-foreground ml-0.5">{metric.unit}</span>
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Model & Serial */}
      <div className="mb-3 sm:mb-4 p-1.5 sm:p-2 rounded-lg bg-muted/50">
        <div className="flex justify-between text-[10px] sm:text-xs">
          <span className="text-muted-foreground">Model</span>
          <span className="text-foreground font-medium truncate ml-2">{model}</span>
        </div>
        <div className="flex justify-between text-[10px] sm:text-xs mt-0.5 sm:mt-1">
          <span className="text-muted-foreground">Serial</span>
          <span className="font-mono text-foreground truncate ml-2">{serialNumber}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-1.5 sm:gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1 h-8 sm:h-9 text-xs sm:text-sm px-2 sm:px-3"
          onClick={onViewTelemetry}
        >
          <Activity className="w-3.5 h-3.5 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
          <span className="hidden xs:inline">Telemetry</span>
          <span className="xs:hidden">Data</span>
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="flex-1 h-8 sm:h-9 text-xs sm:text-sm px-2 sm:px-3"
          onClick={onConfigure}
        >
          <Settings className="w-3.5 h-3.5 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
          <span className="hidden xs:inline">Configure</span>
          <span className="xs:hidden">Setup</span>
        </Button>

        {onUnclaim && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 sm:h-9 px-2 sm:px-3">
                <Unlink className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Unclaim {name}?</AlertDialogTitle>
                <AlertDialogDescription>
                  This removes the device from this site and releases it back to the available pool. It can be claimed again on any site.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={onUnclaim}>Unclaim</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}

        {onRemove && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm" className="h-8 sm:h-9 px-2 sm:px-3">
                <Trash2 className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Remove {name}?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently removes the device from your system. This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={onRemove} className="bg-destructive text-destructive-foreground">
                  Remove
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>
    </motion.div>
  );
}