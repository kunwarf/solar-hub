import { motion } from "framer-motion";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend
} from "recharts";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Calendar, TrendingUp, TrendingDown } from "lucide-react";

interface ComparisonData {
  label: string;
  current: number;
  previous: number;
}

const weeklyData: ComparisonData[] = [
  { label: "Mon", current: 28, previous: 24 },
  { label: "Tue", current: 32, previous: 29 },
  { label: "Wed", current: 25, previous: 31 },
  { label: "Thu", current: 35, previous: 27 },
  { label: "Fri", current: 30, previous: 28 },
  { label: "Sat", current: 38, previous: 33 },
  { label: "Sun", current: 42, previous: 35 },
];

const monthlyData: ComparisonData[] = [
  { label: "Week 1", current: 180, previous: 165 },
  { label: "Week 2", current: 195, previous: 178 },
  { label: "Week 3", current: 210, previous: 190 },
  { label: "Week 4", current: 225, previous: 205 },
];

interface ComparisonChartProps {
  className?: string;
  title?: string;
}

export function ComparisonChart({ className, title = "Production Comparison" }: ComparisonChartProps) {
  const [period, setPeriod] = useState<"week" | "month">("week");
  
  const data = period === "week" ? weeklyData : monthlyData;
  const currentTotal = data.reduce((sum, d) => sum + d.current, 0);
  const previousTotal = data.reduce((sum, d) => sum + d.previous, 0);
  const percentChange = ((currentTotal - previousTotal) / previousTotal) * 100;
  const isPositive = percentChange >= 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-card p-4", className)}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Calendar className="w-5 h-5 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant={period === "week" ? "default" : "ghost"}
            size="sm"
            onClick={() => setPeriod("week")}
            className="h-7 text-xs"
          >
            Week
          </Button>
          <Button
            variant={period === "month" ? "default" : "ghost"}
            size="sm"
            onClick={() => setPeriod("month")}
            className="h-7 text-xs"
          >
            Month
          </Button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-4 p-3 rounded-lg bg-secondary/50">
        <div>
          <p className="text-xs text-muted-foreground mb-1">This {period}</p>
          <p className="text-lg font-bold text-primary">{currentTotal} kWh</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">Last {period}</p>
          <p className="text-lg font-bold text-muted-foreground">{previousTotal} kWh</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">Change</p>
          <div className={cn(
            "flex items-center gap-1 text-lg font-bold",
            isPositive ? "text-success" : "text-destructive"
          )}>
            {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            {Math.abs(percentChange).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={4}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis 
              dataKey="label" 
              axisLine={false}
              tickLine={false}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            />
            <YAxis 
              axisLine={false}
              tickLine={false}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
              width={35}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              labelStyle={{ color: "hsl(var(--foreground))" }}
            />
            <Legend 
              wrapperStyle={{ fontSize: "11px" }}
              iconType="circle"
              iconSize={8}
            />
            <Bar 
              dataKey="current" 
              name={`This ${period}`}
              fill="hsl(var(--primary))" 
              radius={[4, 4, 0, 0]}
            />
            <Bar 
              dataKey="previous" 
              name={`Last ${period}`}
              fill="hsl(var(--muted-foreground))" 
              radius={[4, 4, 0, 0]}
              opacity={0.5}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
