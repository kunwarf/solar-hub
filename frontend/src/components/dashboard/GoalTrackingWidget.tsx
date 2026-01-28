import { useMemo } from "react";
import { motion } from "framer-motion";
import { Target, TrendingUp, Zap, Leaf, DollarSign, Edit2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import type { AllWidgetsData } from "@/api/services/dashboard.service";

interface Goal {
  id: string;
  type: "savings" | "generation" | "self-sufficiency" | "environmental";
  title: string;
  target: number;
  current: number;
  unit: string;
  period: string;
}

const goalIcons = {
  savings: DollarSign,
  generation: Zap,
  "self-sufficiency": TrendingUp,
  environmental: Leaf,
};

const goalColors = {
  savings: "text-warning",
  generation: "text-solar",
  "self-sufficiency": "text-primary",
  environmental: "text-success",
};

function buildGoals(data?: AllWidgetsData | null): Goal[] {
  const savings = data?.billing?.estimated_savings_month || 0;
  const energyMonth = data?.stats?.energy_month_kwh || 0;
  const energyToday = data?.stats?.energy_today_kwh || 0;
  const loadW = data?.power_flow?.load_power_w || 0;
  const pvW = data?.power_flow?.pv_power_w || 0;
  const selfConsumption = loadW > 0 ? Math.round(Math.min((pvW / loadW) * 100, 100)) : 0;
  const co2 = data?.environmental?.co2_avoided_kg || 0;

  return [
    {
      id: "1",
      type: "savings",
      title: "Monthly Savings Goal",
      target: 5000,
      current: Math.round(savings),
      unit: "Rs.",
      period: "this month",
    },
    {
      id: "2",
      type: "generation",
      title: "Generation Target",
      target: 500,
      current: Math.round(energyMonth || energyToday),
      unit: "kWh",
      period: "this month",
    },
    {
      id: "3",
      type: "self-sufficiency",
      title: "Self-Sufficiency",
      target: 80,
      current: selfConsumption,
      unit: "%",
      period: "current",
    },
    {
      id: "4",
      type: "environmental",
      title: "CO2 Reduction",
      target: 50,
      current: Math.round(co2),
      unit: "kg",
      period: "today",
    },
  ];
}

interface GoalTrackingWidgetProps {
  className?: string;
  widgetsData?: AllWidgetsData | null;
}

export function GoalTrackingWidget({ className, widgetsData }: GoalTrackingWidgetProps) {
  const goals = useMemo(() => buildGoals(widgetsData), [widgetsData]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-card p-4", className)}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Goal Tracking</h3>
        </div>
        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-muted-foreground">
          <Edit2 className="w-3 h-3 mr-1" />
          Edit Goals
        </Button>
      </div>

      <div className="space-y-4">
        {goals.map((goal, index) => {
          const Icon = goalIcons[goal.type];
          const color = goalColors[goal.type];
          const progress = Math.min((goal.current / goal.target) * 100, 100);
          const isComplete = progress >= 100;

          return (
            <motion.div
              key={goal.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon className={cn("w-4 h-4", color)} />
                  <span className="text-sm font-medium text-foreground">{goal.title}</span>
                </div>
                <span className="text-xs text-muted-foreground">{goal.period}</span>
              </div>
              
              <div className="flex items-center gap-3">
                <Progress 
                  value={progress} 
                  className={cn(
                    "h-2 flex-1",
                    isComplete && "bg-success/20"
                  )}
                />
                <div className="text-right min-w-[80px]">
                  <span className={cn(
                    "text-sm font-bold",
                    isComplete ? "text-success" : "text-foreground"
                  )}>
                    {goal.unit === "Rs." ? `${goal.unit} ${goal.current.toLocaleString()}` : `${goal.current}${goal.unit}`}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {" / "}
                    {goal.unit === "Rs." ? `${goal.target.toLocaleString()}` : `${goal.target}${goal.unit}`}
                  </span>
                </div>
              </div>
              
              {isComplete && (
                <p className="text-xs text-success flex items-center gap-1">
                  ✓ Goal achieved!
                </p>
              )}
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
