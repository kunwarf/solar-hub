import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface LiveMetricCardProps {
  title: string;
  value: string;
  unit: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "stable";
  min?: string;
  max?: string;
  variant?: "default" | "success" | "warning" | "danger";
  delay?: number;
}

const variantStyles = {
  default: {
    bg: "bg-secondary/30",
    icon: "text-muted-foreground",
    value: "text-foreground",
  },
  success: {
    bg: "bg-success/10",
    icon: "text-success",
    value: "text-success",
  },
  warning: {
    bg: "bg-warning/10",
    icon: "text-warning",
    value: "text-warning",
  },
  danger: {
    bg: "bg-destructive/10",
    icon: "text-destructive",
    value: "text-destructive",
  },
};

export function LiveMetricCard({
  title,
  value,
  unit,
  icon: Icon,
  trend,
  min,
  max,
  variant = "default",
  delay = 0,
}: LiveMetricCardProps) {
  const styles = variantStyles[variant];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay }}
      className={cn("glass-card p-4", styles.bg)}
    >
      <div className="flex items-center gap-3 mb-3">
        <Icon className={cn("w-5 h-5", styles.icon)} />
        <span className="text-sm text-muted-foreground">{title}</span>
        {trend && (
          <div className="ml-auto">
            {trend === "up" && <span className="text-success text-xs">↑</span>}
            {trend === "down" && <span className="text-destructive text-xs">↓</span>}
            {trend === "stable" && <span className="text-muted-foreground text-xs">→</span>}
          </div>
        )}
      </div>

      <div className="mb-2">
        <span className={cn("font-mono text-2xl font-bold", styles.value)}>{value}</span>
        <span className="text-sm text-muted-foreground ml-1">{unit}</span>
      </div>

      {(min || max) && (
        <div className="flex justify-between text-xs text-muted-foreground">
          {min && <span>Min: {min}</span>}
          {max && <span>Max: {max}</span>}
        </div>
      )}

      {/* Live indicator */}
      <div className="flex items-center gap-1.5 mt-3">
        <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse-glow" />
        <span className="text-xs text-muted-foreground">Live</span>
      </div>
    </motion.div>
  );
}
