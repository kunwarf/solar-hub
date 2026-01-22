import { motion } from "framer-motion";
import { Leaf, Trees, Car, Home, Share2, Award } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface EnvironmentalData {
  co2Avoided: number; // kg
  treesEquivalent: number;
  carMilesSaved: number;
  homesEquivalent: number;
  cleanEnergyGenerated: number; // kWh lifetime
  currentMonthCO2: number;
}

const mockData: EnvironmentalData = {
  co2Avoided: 2450,
  treesEquivalent: 112,
  carMilesSaved: 5890,
  homesEquivalent: 0.8,
  cleanEnergyGenerated: 4892,
  currentMonthCO2: 185,
};

interface EnvironmentalImpactWidgetProps {
  className?: string;
  compact?: boolean;
}

export function EnvironmentalImpactWidget({ className, compact = false }: EnvironmentalImpactWidgetProps) {
  const data = mockData;

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
              <p className="text-xs text-muted-foreground">Lifetime contribution</p>
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
