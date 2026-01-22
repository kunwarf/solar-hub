import { motion } from "framer-motion";
import { 
  Battery, 
  Zap, 
  Power, 
  Moon, 
  Sun, 
  Clock,
  Shield,
  Home
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useState } from "react";

interface QuickAction {
  id: string;
  label: string;
  icon: React.ElementType;
  description: string;
  active?: boolean;
  variant?: "default" | "warning" | "success";
}

const defaultActions: QuickAction[] = [
  { 
    id: "force-charge", 
    label: "Force Charge", 
    icon: Battery, 
    description: "Override to charge battery",
    variant: "default"
  },
  { 
    id: "grid-export", 
    label: "Grid Export", 
    icon: Zap, 
    description: "Enable selling to grid",
    active: true,
    variant: "success"
  },
  { 
    id: "backup-mode", 
    label: "Backup Mode", 
    icon: Shield, 
    description: "Reserve battery for outages",
    variant: "warning"
  },
  { 
    id: "self-consume", 
    label: "Self Consume", 
    icon: Home, 
    description: "Prioritize home usage",
    active: true,
    variant: "success"
  },
];

interface QuickActionsProps {
  className?: string;
}

export function QuickActions({ className }: QuickActionsProps) {
  const [actions, setActions] = useState(defaultActions);

  const toggleAction = (id: string) => {
    setActions(prev => prev.map(action => {
      if (action.id === id) {
        const newActive = !action.active;
        toast.success(`${action.label} ${newActive ? "enabled" : "disabled"}`);
        return { ...action, active: newActive, variant: newActive ? "success" as const : "default" as const };
      }
      return action;
    }));
  };

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
        {actions.map((action, index) => (
          <motion.button
            key={action.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => toggleAction(action.id)}
            className={cn(
              "flex flex-col items-center gap-2 p-3 rounded-lg border transition-all",
              action.active 
                ? "bg-primary/10 border-primary/30 text-primary" 
                : "bg-secondary/50 border-border/50 text-muted-foreground hover:border-border hover:text-foreground"
            )}
          >
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center",
              action.active ? "bg-primary/20" : "bg-muted"
            )}>
              <action.icon className="w-4 h-4" />
            </div>
            <span className="text-xs font-medium text-center leading-tight">{action.label}</span>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}
