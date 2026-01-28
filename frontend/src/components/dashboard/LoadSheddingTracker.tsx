import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Zap,
  ZapOff,
  Clock,
  AlertTriangle,
  Battery,
  Calendar,
  ArrowRight
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import dashboardService from "@/api/services/dashboard.service";
import type { LoadSheddingData } from "@/api/services/dashboard.service";

interface LoadSheddingSchedule {
  stage: number;
  active: boolean;
  currentWindow: {
    start: string;
    end: string;
    duration: number;
  } | null;
  nextWindow: {
    start: string;
    end: string;
    date: string;
  } | null;
  batteryReserve: number;
  estimatedCoverage: number;
}

function mapApiToSchedule(data: LoadSheddingData): LoadSheddingSchedule {
  return {
    stage: data.stage,
    active: data.active,
    currentWindow: data.current_window ? {
      start: data.current_window.start,
      end: data.current_window.end,
      duration: data.current_window.duration ?? 0,
    } : null,
    nextWindow: data.next_window ? {
      start: data.next_window.start,
      end: data.next_window.end,
      date: data.next_window.date ?? "",
    } : null,
    batteryReserve: data.battery_reserve,
    estimatedCoverage: data.estimated_coverage,
  };
}

const defaultSchedule: LoadSheddingSchedule = {
  stage: 0,
  active: false,
  currentWindow: null,
  nextWindow: null,
  batteryReserve: 0,
  estimatedCoverage: 0,
};

interface LoadSheddingTrackerProps {
  className?: string;
}

export function LoadSheddingTracker({ className }: LoadSheddingTrackerProps) {
  const [schedule, setSchedule] = useState<LoadSheddingSchedule>(defaultSchedule);
  const navigate = useNavigate();

  const fetchData = useCallback(async () => {
    try {
      const data = await dashboardService.getLoadShedding();
      setSchedule(mapApiToSchedule(data));
    } catch {
      // Keep existing data on error
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // 10 seconds
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-card overflow-hidden", className)}
    >
      {/* Status Header */}
      <div className={cn(
        "px-4 py-3 flex items-center justify-between",
        schedule.active 
          ? "bg-destructive/10 border-b border-destructive/20" 
          : "bg-success/10 border-b border-success/20"
      )}>
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-10 h-10 rounded-lg flex items-center justify-center",
            schedule.active ? "bg-destructive/20" : "bg-success/20"
          )}>
            {schedule.active ? (
              <ZapOff className="w-5 h-5 text-destructive animate-pulse" />
            ) : (
              <Zap className="w-5 h-5 text-success" />
            )}
          </div>
          <div>
            <p className={cn(
              "font-semibold",
              schedule.active ? "text-destructive" : "text-success"
            )}>
              {schedule.active ? `Stage ${schedule.stage} Active` : "No Load Shedding"}
            </p>
            <p className="text-xs text-muted-foreground">
              {schedule.active 
                ? `${schedule.currentWindow?.duration} min remaining`
                : "Grid power available"
              }
            </p>
          </div>
        </div>

        {schedule.stage > 0 && (
          <div className="text-right">
            <span className={cn(
              "text-2xl font-bold",
              schedule.active ? "text-destructive" : "text-warning"
            )}>
              {schedule.stage}
            </span>
            <p className="text-[10px] text-muted-foreground">Stage</p>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Active Window Progress */}
        {schedule.active && schedule.currentWindow && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Current Window</span>
              <span className="font-mono text-foreground">
                {schedule.currentWindow.start} - {schedule.currentWindow.end}
              </span>
            </div>
            <Progress 
              value={30} 
              className="h-2 bg-destructive/20"
            />
          </div>
        )}

        {/* Next Scheduled Window */}
        {schedule.nextWindow && !schedule.active && (
          <div className="flex items-center gap-3 p-3 rounded-lg bg-warning/10 border border-warning/20">
            <Calendar className="w-5 h-5 text-warning" />
            <div className="flex-1">
              <p className="text-sm font-medium text-foreground">Next Scheduled</p>
              <p className="text-xs text-muted-foreground">
                {schedule.nextWindow.date} • {schedule.nextWindow.start} - {schedule.nextWindow.end}
              </p>
            </div>
            <AlertTriangle className="w-4 h-4 text-warning" />
          </div>
        )}

        {/* Battery Reserve */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <Battery className="w-4 h-4 text-battery" />
              <span className="text-xs text-muted-foreground">Reserve</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-bold text-foreground">{schedule.batteryReserve}</span>
              <span className="text-sm text-muted-foreground">%</span>
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">Reserved for outages</p>
          </div>

          <div className="p-3 rounded-lg bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-info" />
              <span className="text-xs text-muted-foreground">Coverage</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-bold text-foreground">{schedule.estimatedCoverage}</span>
              <span className="text-sm text-muted-foreground">hrs</span>
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">Backup available</p>
          </div>
        </div>

        {/* View Outages Button */}
        <Button 
          variant="outline" 
          className="w-full"
          onClick={() => navigate('/outages')}
        >
          View Outage History
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
}
