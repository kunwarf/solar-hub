import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Wifi,
  WifiOff,
  Activity,
  Zap,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { dashboardService, type DeviceStatusData } from "@/api/services/dashboard.service";

type SystemHealth = "healthy" | "warning" | "critical" | "offline";

interface SystemStatus {
  overall: SystemHealth;
  connection: "online" | "offline" | "unstable";
  activeAlerts: number;
  lastSync: string;
  uptime: string;
  components: {
    name: string;
    status: SystemHealth;
    message?: string;
  }[];
}

function mapDeviceStatusToSystemStatus(data: DeviceStatusData): SystemStatus {
  const { devices_online, devices_total, total_faults, total_warnings, devices } = data;

  // Determine overall health
  let overall: SystemHealth;
  if (devices_total === 0 || devices_online === 0) {
    overall = "offline";
  } else if (total_faults > 0) {
    overall = "critical";
  } else if (total_warnings > 0) {
    overall = "warning";
  } else {
    overall = "healthy";
  }

  // Determine connection status
  const connection = devices_online > 0 ? "online" as const : "offline" as const;

  // Calculate uptime percentage
  const uptimePct = devices_total > 0
    ? ((devices_online / devices_total) * 100).toFixed(1)
    : "0.0";

  // Format last sync from latest device last_seen
  const lastSeenTimestamps = devices
    .map(d => d.last_seen)
    .filter((ts): ts is number => ts !== null);
  let lastSync = "Unknown";
  if (lastSeenTimestamps.length > 0) {
    const latest = Math.max(...lastSeenTimestamps);
    const secondsAgo = Math.floor((Date.now() / 1000) - latest);
    if (secondsAgo < 60) lastSync = "Just now";
    else if (secondsAgo < 3600) lastSync = `${Math.floor(secondsAgo / 60)}m ago`;
    else if (secondsAgo < 86400) lastSync = `${Math.floor(secondsAgo / 3600)}h ago`;
    else lastSync = `${Math.floor(secondsAgo / 86400)}d ago`;
  }

  // Build component status from device types
  const devicesByType: Record<string, { total: number; faults: number; warnings: number; online: number }> = {};
  for (const device of devices) {
    // Categorize by working_mode or status
    const category = device.working_mode || "device";
    if (!devicesByType[category]) {
      devicesByType[category] = { total: 0, faults: 0, warnings: 0, online: 0 };
    }
    devicesByType[category].total++;
    if (device.online) devicesByType[category].online++;
    devicesByType[category].faults += device.faults.length;
    devicesByType[category].warnings += device.warnings.length;
  }

  // Build components list - always show standard groups
  const components: SystemStatus["components"] = [];

  // If we have specific device type info, use it; otherwise derive from aggregate
  if (Object.keys(devicesByType).length > 0) {
    for (const [typeName, info] of Object.entries(devicesByType)) {
      let status: SystemHealth;
      let message: string | undefined;
      if (info.online === 0 && info.total > 0) {
        status = "offline";
        message = `${info.total} offline`;
      } else if (info.faults > 0) {
        status = "critical";
        message = `${info.faults} fault(s)`;
      } else if (info.warnings > 0) {
        status = "warning";
        message = `${info.warnings} warning(s)`;
      } else {
        status = "healthy";
      }
      const label = typeName.charAt(0).toUpperCase() + typeName.slice(1);
      components.push({ name: label, status, message });
    }
  } else {
    // Fallback: show a single "Devices" component
    components.push({
      name: "Devices",
      status: overall,
      message: `${devices_online}/${devices_total} online`,
    });
  }

  // Add network component based on grid_connected
  components.push({
    name: "Network",
    status: data.grid_connected ? "healthy" : "warning",
    message: data.grid_connected ? undefined : "Grid disconnected",
  });

  return {
    overall,
    connection,
    activeAlerts: total_faults + total_warnings,
    lastSync,
    uptime: `${uptimePct}%`,
    components,
  };
}

const fallbackStatus: SystemStatus = {
  overall: "offline",
  connection: "offline",
  activeAlerts: 0,
  lastSync: "Unknown",
  uptime: "0%",
  components: [],
};

const healthConfig = {
  healthy: {
    icon: CheckCircle2,
    color: "text-success",
    bgColor: "bg-success/20",
    borderColor: "border-success/30",
    label: "All Systems Operational",
    pulse: false,
  },
  warning: {
    icon: AlertTriangle,
    color: "text-warning",
    bgColor: "bg-warning/20",
    borderColor: "border-warning/30",
    label: "Attention Required",
    pulse: true,
  },
  critical: {
    icon: AlertCircle,
    color: "text-destructive",
    bgColor: "bg-destructive/20",
    borderColor: "border-destructive/30",
    label: "Critical Issues",
    pulse: true,
  },
  offline: {
    icon: WifiOff,
    color: "text-muted-foreground",
    bgColor: "bg-muted",
    borderColor: "border-border",
    label: "System Offline",
    pulse: false,
  },
};

interface SystemStatusIndicatorProps {
  className?: string;
  compact?: boolean;
}

export function SystemStatusIndicator({ className, compact = false }: SystemStatusIndicatorProps) {
  const [status, setStatus] = useState<SystemStatus>(fallbackStatus);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await dashboardService.getDeviceStatus();
      setStatus(mapDeviceStatusToSystemStatus(data));
    } catch {
      // Keep current status on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30_000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const config = healthConfig[status.overall];
  const StatusIcon = config.icon;

  if (compact) {
    if (loading) {
      return (
        <div className={cn("flex items-center gap-2 px-3 py-1.5 rounded-full border bg-muted border-border", className)}>
          <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Loading</span>
        </div>
      );
    }

    return (
      <HoverCard openDelay={200}>
        <HoverCardTrigger asChild>
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-full border cursor-pointer transition-colors",
              config.bgColor,
              config.borderColor,
              className
            )}
          >
            <div className={cn("relative", config.pulse && "animate-pulse")}>
              <StatusIcon className={cn("w-4 h-4", config.color)} />
            </div>
            <span className={cn("text-xs font-medium", config.color)}>
              {status.overall === "healthy" ? "Healthy" : status.overall}
            </span>
            {status.activeAlerts > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-[10px] font-bold bg-warning/20 text-warning rounded-full">
                {status.activeAlerts}
              </span>
            )}
          </motion.div>
        </HoverCardTrigger>
        <HoverCardContent className="w-72 p-0" align="end">
          <SystemStatusCard status={status} />
        </HoverCardContent>
      </HoverCard>
    );
  }

  if (loading) {
    return (
      <div className={cn("glass-card p-4 flex items-center justify-center", className)}>
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-card p-4", className)}
    >
      <SystemStatusCard status={status} />
    </motion.div>
  );
}

function SystemStatusCard({ status }: { status: SystemStatus }) {
  const config = healthConfig[status.overall];
  const StatusIcon = config.icon;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className={cn("flex items-center gap-3 p-3 rounded-lg", config.bgColor)}>
        <div className={cn("p-2 rounded-lg", config.bgColor)}>
          <StatusIcon className={cn("w-5 h-5", config.color, config.pulse && "animate-pulse")} />
        </div>
        <div>
          <p className={cn("font-semibold text-sm", config.color)}>{config.label}</p>
          <p className="text-xs text-muted-foreground">Last sync: {status.lastSync}</p>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-2 px-3">
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 mb-1">
            {status.connection === "online" ? (
              <Wifi className="w-3 h-3 text-success" />
            ) : (
              <WifiOff className="w-3 h-3 text-destructive" />
            )}
          </div>
          <span className="text-[10px] text-muted-foreground">Connection</span>
        </div>
        <div className="text-center">
          <span className="text-sm font-bold text-foreground">{status.uptime}</span>
          <p className="text-[10px] text-muted-foreground">Uptime</p>
        </div>
        <div className="text-center">
          <span className={cn(
            "text-sm font-bold",
            status.activeAlerts > 0 ? "text-warning" : "text-success"
          )}>
            {status.activeAlerts}
          </span>
          <p className="text-[10px] text-muted-foreground">Alerts</p>
        </div>
      </div>

      {/* Component Status */}
      <div className="px-3 pb-3 space-y-1.5">
        {status.components.map((component) => {
          const compConfig = healthConfig[component.status];
          const CompIcon = compConfig.icon;
          return (
            <div key={component.name} className="flex items-center justify-between py-1">
              <span className="text-xs text-muted-foreground">{component.name}</span>
              <div className="flex items-center gap-1.5">
                <CompIcon className={cn("w-3 h-3", compConfig.color)} />
                <span className={cn("text-[10px] font-medium capitalize", compConfig.color)}>
                  {component.status}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
