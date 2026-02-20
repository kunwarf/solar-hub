import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Leaf, Trees, Car, Home, Share2, Award } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import dashboardService from "@/api/services/dashboard.service";
import type { EnvironmentalData as ApiEnvironmentalData, StatsData } from "@/api/services/dashboard.service";

interface EnvironmentalMetrics {
  co2Avoided: number; // kg
  treesEquivalent: number;
  carMilesSaved: number;
  homesEquivalent: number;
  cleanEnergyGenerated: number; // kWh
  currentMonthCO2: number;
}

function mapApiToMetrics(env: ApiEnvironmentalData, stats?: StatsData | null): EnvironmentalMetrics {
  const co2 = env.co2_avoided_kg || 0;
  const energyKwh = stats?.energy_today_kwh || 0;
  const energyMonthKwh = stats?.energy_month_kwh || 0;
  return {
    co2Avoided: Math.round(co2),
    treesEquivalent: Math.round(env.trees_equivalent || 0),
    // 1 kg CO2 ≈ 2.4 miles of driving avoided
    carMilesSaved: Math.round(co2 * 2.4),
    // Average US household uses ~900 kWh/month
    homesEquivalent: energyMonthKwh > 0 ? parseFloat((energyMonthKwh / 900).toFixed(1)) : 0,
    cleanEnergyGenerated: Math.round(energyMonthKwh || energyKwh),
    currentMonthCO2: Math.round(co2),
  };
}

interface EnvironmentalImpactWidgetProps {
  className?: string;
  compact?: boolean;
  environmentalData?: ApiEnvironmentalData | null;
  statsData?: StatsData | null;
}

export function EnvironmentalImpactWidget({ className, compact = false, environmentalData, statsData }: EnvironmentalImpactWidgetProps) {
  const [fetchedEnv, setFetchedEnv] = useState<ApiEnvironmentalData | null>(null);
  const [fetchedStats, setFetchedStats] = useState<StatsData | null>(null);

  const fetchData = useCallback(async () => {
    if (environmentalData) return; // Skip if data provided via props
    try {
      const [env, st] = await Promise.all([
        dashboardService.getEnvironmental(),
        dashboardService.getStats(),
      ]);
      setFetchedEnv(env);
      setFetchedStats(st);
    } catch {
      // Keep existing data on error
    }
  }, [environmentalData]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const envSource = environmentalData || fetchedEnv;
  const statsSource = statsData || fetchedStats;

  const data: EnvironmentalMetrics = envSource
    ? mapApiToMetrics(envSource, statsSource)
    : { co2Avoided: 0, treesEquivalent: 0, carMilesSaved: 0, homesEquivalent: 0, cleanEnergyGenerated: 0, currentMonthCO2: 0 };

  const handleShare = () => {
    toast.success("Environmental impact certificate generated!");
  };

  const impactMetrics = [
    {
      icon: Leaf,
      value: data.co2Avoided.toLocaleString(),
      unit: "kg",
      label: "CO₂ Avoided",
      color: "text-success",
      bgColor: "bg-success/10",
    },
    {
      icon: Trees,
      value: data.treesEquivalent,
      unit: "",
      label: "Trees Equivalent",
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
    {
      icon: Car,
      value: data.carMilesSaved.toLocaleString(),
      unit: "mi",
      label: "Car Miles Saved",
      color: "text-info",
      bgColor: "bg-info/10",
    },
    {
      icon: Home,
      value: data.homesEquivalent.toFixed(1),
      unit: "",
      label: "Homes Powered",
      color: "text-warning",
      bgColor: "bg-warning/10",
    },
  ];

  if (compact) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn("glass-card p-4", className)}
      >
        <div className="flex items-center gap-2 mb-3">
          <Leaf className="w-5 h-5 text-success" />
          <h3 className="text-sm font-semibold text-foreground">Environmental Impact</h3>
        </div>
        
        <div className="grid grid-cols-2 gap-3">
          {impactMetrics.slice(0, 2).map((metric, index) => (
            <div key={index} className="flex items-center gap-2">
              <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", metric.bgColor)}>
                <metric.icon className={cn("w-4 h-4", metric.color)} />
              </div>
              <div>
                <p className="text-sm font-bold text-foreground">
                  {metric.value}{metric.unit && <span className="text-xs"> {metric.unit}</span>}
                </p>
                <p className="text-[10px] text-muted-foreground">{metric.label}</p>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-card overflow-hidden", className)}
    >
      {/* Header with gradient */}
      <div className="bg-gradient-to-r from-success/20 to-primary/20 p-4 border-b border-border/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-success/20 flex items-center justify-center">
              <Leaf className="w-5 h-5 text-success" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Environmental Impact</h3>
              <p className="text-xs text-muted-foreground">This month's contribution</p>
            </div>
          </div>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleShare}
            className="gap-1 text-xs"
          >
            <Share2 className="w-3 h-3" />
            Share
          </Button>
        </div>
      </div>

      {/* Main Stats */}
      <div className="p-4">
        {/* Hero Stat */}
        <div className="text-center mb-4 p-4 rounded-xl bg-success/10 border border-success/20">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Award className="w-5 h-5 text-success" />
            <span className="text-xs text-success font-medium">Clean Energy Champion</span>
          </div>
          <p className="text-3xl font-bold text-success mb-1">
            {data.cleanEnergyGenerated.toLocaleString()} kWh
          </p>
          <p className="text-sm text-muted-foreground">Clean energy generated</p>
        </div>

        {/* Impact Grid */}
        <div className="grid grid-cols-2 gap-3">
          {impactMetrics.map((metric, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.1 }}
              className="p-3 rounded-lg bg-secondary/50 text-center"
            >
              <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center mx-auto mb-2", metric.bgColor)}>
                <metric.icon className={cn("w-4 h-4", metric.color)} />
              </div>
              <p className="text-lg font-bold text-foreground">
                {metric.value}
                {metric.unit && <span className="text-xs text-muted-foreground"> {metric.unit}</span>}
              </p>
              <p className="text-[10px] text-muted-foreground">{metric.label}</p>
            </motion.div>
          ))}
        </div>

        {/* This Month */}
        <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between">
          <span className="text-sm text-muted-foreground">This month's CO₂ avoided</span>
          <span className="text-sm font-bold text-success">{data.currentMonthCO2} kg</span>
        </div>
      </div>
    </motion.div>
  );
}
