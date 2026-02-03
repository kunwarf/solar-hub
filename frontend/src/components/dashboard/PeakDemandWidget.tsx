import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Gauge, TrendingUp, Clock, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import dashboardService from "@/api/services/dashboard.service";
import type { PeakDemandData } from "@/api/services/dashboard.service";

interface PeakDemandWidgetProps {
  className?: string;
}

export function PeakDemandWidget({ className }: PeakDemandWidgetProps) {
  const [data, setData] = useState<PeakDemandData | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const result = await dashboardService.getPeakDemand();
      setData(result);
    } catch {
      // Keep existing data on error
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 300000); // 5 minutes
    return () => clearInterval(interval);
  }, [fetchData]);

  const peak = data?.peak_demand_kw ?? 0;
  const avg = data?.average_demand_kw ?? 0;
  const current = data?.current_demand_kw ?? 0;
  const peakHour = data?.peak_hour || "--:--";
  const profile = data?.hourly_profile ?? [];

  // Calculate bar heights for sparkline
  const maxDemand = Math.max(...profile.map(p => p.demand_kw), 1);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-card p-4", className)}
    >
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center">
          <Gauge className="w-4 h-4 text-warning" />
        </div>
        <h3 className="text-sm font-semibold text-foreground">Peak Demand</h3>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="text-center p-2 rounded-lg bg-secondary/50">
          <div className="flex items-center justify-center gap-1 mb-1">
            <Zap className="w-3 h-3 text-warning" />
          </div>
          <p className="text-lg font-bold text-foreground">{peak.toFixed(1)}</p>
          <p className="text-[10px] text-muted-foreground">Peak kW</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-secondary/50">
          <div className="flex items-center justify-center gap-1 mb-1">
            <TrendingUp className="w-3 h-3 text-primary" />
          </div>
          <p className="text-lg font-bold text-foreground">{avg.toFixed(1)}</p>
          <p className="text-[10px] text-muted-foreground">Avg kW</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-secondary/50">
          <div className="flex items-center justify-center gap-1 mb-1">
            <Clock className="w-3 h-3 text-info" />
          </div>
          <p className="text-lg font-bold text-foreground">{peakHour}</p>
          <p className="text-[10px] text-muted-foreground">Peak Hour</p>
        </div>
      </div>

      {/* Hourly demand sparkline */}
      {profile.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">Today's Demand Profile</p>
            <p className="text-[10px] text-muted-foreground">Max: {maxDemand.toFixed(1)} kW</p>
          </div>
          <div className="space-y-1">
            <div className="flex items-end gap-[2px] h-16">
              {profile.map((point, i) => {
                const height = maxDemand > 0 ? (point.demand_kw / maxDemand) * 100 : 0;
                const isPeak = point.hour === peakHour;
                return (
                  <div
                    key={i}
                    className={cn(
                      "flex-1 rounded-t-sm min-w-[3px] transition-colors",
                      isPeak ? "bg-warning" : "bg-primary/40"
                    )}
                    style={{ height: `${Math.max(height, 4)}%` }}
                    title={`${point.hour}: ${point.demand_kw.toFixed(1)} kW`}
                  />
                );
              })}
            </div>
            {/* Time axis labels */}
            <div className="flex items-center justify-between text-[9px] text-muted-foreground/60">
              <span>00:00</span>
              <span>06:00</span>
              <span>12:00</span>
              <span>18:00</span>
              <span>24:00</span>
            </div>
          </div>
        </div>
      )}

      {/* Current demand footer */}
      <div className="mt-3 pt-2 border-t border-border/50 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Current demand</span>
        <span className="text-sm font-bold text-foreground">{current.toFixed(1)} kW</span>
      </div>
    </motion.div>
  );
}
