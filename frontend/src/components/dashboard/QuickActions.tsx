import { motion } from "framer-motion";
import {
  Battery,
  Zap,
  Power,
  Moon,
  Sun,
  Clock,
  Shield,
  Home,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useState, useCallback } from "react";
import { devicesService } from "@/api/services/devices.service";

interface QuickAction {
  id: string;
  label: string;
  icon: React.ElementType;
  description: string;
  active?: boolean;
  variant?: "default" | "warning" | "success";
  commandType: string;
  commandParams?: Record<string, unknown>;
}

const defaultActions: QuickAction[] = [
  {
    id: "force-charge",
    label: "Force Charge",
    icon: Battery,
    description: "Override to charge battery",
    variant: "default",
    commandType: "set_battery_mode",
    commandParams: { mode: "force_charge" },
  },
  {
    id: "grid-export",
    label: "Grid Export",
    icon: Zap,
    description: "Enable selling to grid",
    active: true,
    variant: "success",
    commandType: "enable_export",
  },
  {
    id: "backup-mode",
    label: "Backup Mode",
    icon: Shield,
    description: "Reserve battery for outages",
    variant: "warning",
    commandType: "set_battery_mode",
    commandParams: { mode: "backup" },
  },
  {
    id: "self-consume",
    label: "Self Consume",
    icon: Home,
    description: "Prioritize home usage",
    active: true,
    variant: "success",
    commandType: "set_battery_mode",
    commandParams: { mode: "self_consume" },
  },
];

interface QuickActionsProps {
  className?: string;
  deviceId?: string;
}

export function QuickActions({ className, deviceId }: QuickActionsProps) {
  const [actions, setActions] = useState(defaultActions);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const toggleAction = useCallback(async (id: string) => {
    const action = actions.find(a => a.id === id);
    if (!action || loadingAction) return;

    const newActive = !action.active;

    // If no device ID, fall back to local-only toggle
    if (!deviceId) {
      setActions(prev => prev.map(a => {
        if (a.id === id) {
          toast.success(`${a.label} ${newActive ? "enabled" : "disabled"}`);
          return { ...a, active: newActive, variant: newActive ? "success" as const : "default" as const };
        }
        return a;
      }));
      return;
    }

    // Send command to backend
    setLoadingAction(id);

    // Determine command type - toggle enable/disable for grid export
    let commandType = action.commandType;
    if (action.id === "grid-export") {
      commandType = newActive ? "enable_export" : "disable_export";
    }

    const result = await devicesService.sendCommand(deviceId, {
      command_type: commandType,
      parameters: action.commandParams,
    });

    if (result.success) {
      setActions(prev => prev.map(a => {
        if (a.id === id) {
          return { ...a, active: newActive, variant: newActive ? "success" as const : "default" as const };
        }
        return a;
      }));
      toast.success(`${action.label} ${newActive ? "enabled" : "disabled"}`);
    } else {
      toast.error(`Failed to ${newActive ? "enable" : "disable"} ${action.label}: ${result.error || "Unknown error"}`);
    }

    setLoadingAction(null);
  }, [actions, deviceId, loadingAction]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-card p-4", className)}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground">Quick Actions</h3>
        <Power className="w-4 h-4 text-muted-foreground" />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {actions.map((action, index) => {
          const isLoading = loadingAction === action.id;
          return (
            <motion.button
              key={action.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.05 }}
              onClick={() => toggleAction(action.id)}
              disabled={isLoading || (loadingAction !== null && loadingAction !== action.id)}
              className={cn(
                "flex flex-col items-center gap-2 p-3 rounded-lg border transition-all",
                isLoading && "opacity-70 cursor-wait",
                action.active
                  ? "bg-primary/10 border-primary/30 text-primary"
                  : "bg-secondary/50 border-border/50 text-muted-foreground hover:border-border hover:text-foreground",
                (loadingAction !== null && loadingAction !== action.id) && "opacity-50"
              )}
            >
              <div className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center",
                action.active ? "bg-primary/20" : "bg-muted"
              )}>
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <action.icon className="w-4 h-4" />
                )}
              </div>
              <span className="text-xs font-medium text-center leading-tight">{action.label}</span>
            </motion.button>
          );
        })}
      </div>
    </motion.div>
  );
}
