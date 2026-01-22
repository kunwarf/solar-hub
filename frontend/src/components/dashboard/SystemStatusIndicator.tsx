import { motion } from "framer-motion";
import { 
  CheckCircle2, 
  AlertTriangle, 
  AlertCircle, 
  Wifi, 
  WifiOff,
  Activity,
  Zap
} from "lucide-react";
import { cn } from "@/lib/utils";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";

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

const mockStatus: SystemStatus = {
  overall: "healthy",
  connection: "online",
  activeAlerts: 2,
  lastSync: "Just now",
  uptime: "99.8%",
  components: [
    { name: "Inverters", status: "healthy" },
    { name: "Batteries", status: "warning", message: "1 battery at low charge" },
    { name: "Meters", status: "healthy" },
    { name: "Network", status: "healthy" },
  ],
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
  const status = mockStatus;
  const config = healthConfig[status.overall];
  const StatusIcon = config.icon;

  if (compact) {
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
