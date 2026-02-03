import { memo } from "react";
import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { cn } from "@/lib/utils";

interface DataPoint {
  time: string;
  solar: number;
  consumption: number;
  battery: number;
  grid: number;
}

interface EnergyChartProps {
  data: DataPoint[];
  title: string;
  className?: string;
}

const EnergyChartComponent = ({ data, title, className }: EnergyChartProps) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
    className={cn("glass-card p-6", className)}
    >
      <h3 className="text-lg font-semibold text-foreground mb-6">{title}</h3>
      
      <div className="h-[350px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="solarGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(45 93% 47%)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(45 93% 47%)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="consumptionGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(280 65% 60%)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(280 65% 60%)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="batteryGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(160 84% 39%)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(160 84% 39%)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 13% 20%)" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="hsl(215 14% 55%)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="hsl(215 14% 55%)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `${value} kWh`}
              label={{
                value: "Energy (kWh)",
                angle: -90,
                position: "insideLeft",
                style: { fill: "hsl(215 14% 55%)", fontSize: 12 }
              }}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const total = payload.reduce((sum: number, entry: any) => sum + (entry.value || 0), 0);
                  return (
                    <div className="bg-card border border-border rounded-lg p-3 shadow-lg">
                      <p className="text-sm font-semibold text-foreground mb-2">{label}</p>
                      <div className="space-y-1.5">
                        {payload.map((entry: any, index: number) => (
                          <div key={index} className="flex items-center justify-between gap-4">
                            <div className="flex items-center gap-2">
                              <div 
                                className="w-2.5 h-2.5 rounded-full" 
                                style={{ backgroundColor: entry.color }}
                              />
                              <span className="text-xs text-muted-foreground">{entry.name}</span>
                            </div>
                            <span className="text-xs font-medium text-foreground">
                              {Math.round(entry.value || 0)} kWh
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="border-t border-border mt-2 pt-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">Total</span>
                          <span className="text-xs font-semibold text-foreground">{Math.round(total)} kWh</span>
                        </div>
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              wrapperStyle={{ fontSize: "12px" }}
            />
            <Area
              type="monotone"
              dataKey="solar"
              stroke="hsl(45 93% 47%)"
              strokeWidth={2}
              fill="url(#solarGradient)"
              name="Solar"
            />
            <Area
              type="monotone"
              dataKey="consumption"
              stroke="hsl(280 65% 60%)"
              strokeWidth={2}
              fill="url(#consumptionGradient)"
              name="Consumption"
            />
            <Area
              type="monotone"
              dataKey="battery"
              stroke="hsl(160 84% 39%)"
              strokeWidth={2}
              fill="url(#batteryGradient)"
              name="Battery"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
};

// Memoize to prevent unnecessary re-renders
export const EnergyChart = memo(EnergyChartComponent);
