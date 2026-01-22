import { motion } from "framer-motion";
import { LucideIcon, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface StatCardProps {
  title: string;
  value: string;
  unit: string;
  icon: LucideIcon;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  variant?: "solar" | "battery" | "consumption" | "grid" | "environment" | "financial" | "prediction" | "savings" | "eco" | "production" | "default" | "backup";
  delay?: number;
  tooltip?: string;
  compact?: boolean;
}

const variantStyles = {
  solar: {
    iconBg: "bg-yellow-500/20",
    iconColor: "text-yellow-400",
    valueColor: "text-yellow-400",
    glow: "energy-glow-solar",
  },
  battery: {
    iconBg: "bg-purple-500/20",
    iconColor: "text-purple-400",
    valueColor: "text-purple-400",
    glow: "energy-glow-primary",
  },
  consumption: {
    iconBg: "bg-fuchsia-500/20",
    iconColor: "text-fuchsia-400",
    valueColor: "text-fuchsia-400",
    glow: "",
  },
  grid: {
    iconBg: "bg-blue-500/20",
    iconColor: "text-blue-400",
    valueColor: "text-blue-400",
    glow: "energy-glow-accent",
  },
  environment: {
    iconBg: "bg-emerald-500/20",
    iconColor: "text-emerald-400",
    valueColor: "text-emerald-400",
    glow: "",
  },
  financial: {
    iconBg: "bg-amber-500/20",
    iconColor: "text-amber-400",
    valueColor: "text-amber-400",
    glow: "",
  },
  prediction: {
    iconBg: "bg-blue-600/20",
    iconColor: "text-blue-400",
    valueColor: "text-blue-400",
    glow: "",
  },
  savings: {
    iconBg: "bg-amber-600/20",
    iconColor: "text-amber-500",
    valueColor: "text-amber-500",
    glow: "",
  },
  eco: {
    iconBg: "bg-emerald-600/20",
    iconColor: "text-emerald-400",
    valueColor: "text-emerald-400",
    glow: "",
  },
  production: {
    iconBg: "bg-yellow-600/20",
    iconColor: "text-yellow-500",
    valueColor: "text-yellow-500",
    glow: "",
  },
  backup: {
    iconBg: "bg-purple-600/20",
    iconColor: "text-purple-400",
    valueColor: "text-purple-400",
    glow: "",
  },
  default: {
    iconBg: "bg-cyan-500/20",
    iconColor: "text-cyan-400",
    valueColor: "text-cyan-400",
    glow: "",
  },
};

export function StatCard({
  title,
  value,
  unit,
  icon: Icon,
  trend,
  variant = "default",
  delay = 0,
  tooltip,
  compact = false,
}: StatCardProps) {
  const styles = variantStyles[variant];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className={cn("stat-card relative", styles.glow, compact && "p-3")}
    >
      <div className={cn("flex items-start justify-between", compact ? "mb-2" : "mb-4")}>
        <div className={cn(
          "rounded-xl flex items-center justify-center",
          styles.iconBg,
          compact ? "w-9 h-9" : "w-12 h-12"
        )}>
          <Icon className={cn(styles.iconColor, compact ? "w-4 h-4" : "w-6 h-6")} />
        </div>
        <div className="flex items-center gap-1.5">
          {trend && (
            <div
              className={cn(
                "text-xs font-medium px-2 py-1 rounded-full",
                trend.isPositive ? "bg-success/20 text-success" : "bg-destructive/20 text-destructive"
              )}
            >
              {trend.isPositive ? "+" : ""}{trend.value}%
            </div>
          )}
          {tooltip && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <HelpCircle className="w-3.5 h-3.5 text-muted-foreground/50 hover:text-muted-foreground cursor-help" />
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[200px]">
                  <p className="text-xs">{tooltip}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>

      <div className="space-y-1">
        <p className={cn("data-label", compact && "text-[10px]")}>{title}</p>
        <div className="flex items-baseline gap-1">
          <span className={cn("data-value", styles.valueColor, compact ? "text-xl" : "text-3xl")}>{value}</span>
          <span className={cn("text-muted-foreground", compact ? "text-xs" : "text-sm")}>{unit}</span>
        </div>
      </div>
    </motion.div>
  );
}
