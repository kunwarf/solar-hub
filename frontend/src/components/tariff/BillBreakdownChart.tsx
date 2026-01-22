import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { BarChart3 } from 'lucide-react';
import { BillBreakdown } from '@/data/pakistanTariffs';

interface BillBreakdownChartProps {
  bill: BillBreakdown;
  className?: string;
}

const BILL_COMPONENTS = [
  { key: 'energyCharges', label: 'Energy Charges', color: 'hsl(var(--primary))' },
  { key: 'fixedCharges', label: 'Fixed Charges', color: 'hsl(217, 91%, 60%)' },
  { key: 'fuelPriceAdjustment', label: 'FPA', color: 'hsl(45, 93%, 47%)' },
  { key: 'quarterlyTariffAdjustment', label: 'QTA', color: 'hsl(280, 65%, 60%)' },
  { key: 'electricityDuty', label: 'Elec. Duty', color: 'hsl(340, 75%, 55%)' },
  { key: 'gst', label: 'GST', color: 'hsl(15, 80%, 55%)' },
  { key: 'tvFee', label: 'TV Fee', color: 'hsl(180, 60%, 45%)' },
] as const;

const chartConfig = {
  energyCharges: { label: 'Energy Charges', color: 'hsl(var(--primary))' },
  fixedCharges: { label: 'Fixed Charges', color: 'hsl(217, 91%, 60%)' },
  fuelPriceAdjustment: { label: 'Fuel Price Adjustment', color: 'hsl(45, 93%, 47%)' },
  quarterlyTariffAdjustment: { label: 'Quarterly Adjustment', color: 'hsl(280, 65%, 60%)' },
  electricityDuty: { label: 'Electricity Duty', color: 'hsl(340, 75%, 55%)' },
  gst: { label: 'GST', color: 'hsl(15, 80%, 55%)' },
  tvFee: { label: 'TV Fee', color: 'hsl(180, 60%, 45%)' },
};

export function BillBreakdownChart({ bill, className }: BillBreakdownChartProps) {
  const chartData = useMemo(() => {
    // Create stacked bar data
    const data = [{
      name: 'Bill Breakdown',
      energyCharges: bill.energyCharges,
      fixedCharges: bill.fixedCharges,
      fuelPriceAdjustment: bill.fuelPriceAdjustment,
      quarterlyTariffAdjustment: bill.quarterlyTariffAdjustment,
      electricityDuty: bill.electricityDuty,
      gst: bill.gst,
      tvFee: bill.tvFee,
    }];
    return data;
  }, [bill]);

  // Individual bar data for horizontal visualization
  const horizontalData = useMemo(() => {
    return BILL_COMPONENTS
      .filter(comp => {
        const val = bill[comp.key as keyof BillBreakdown];
        return typeof val === 'number' && val > 0;
      })
      .map(comp => ({
        name: comp.label,
        value: bill[comp.key as keyof BillBreakdown] as number,
        fill: comp.color,
      }));
  }, [bill]);

  const formatCurrency = (value: number) => {
    return `Rs. ${value.toLocaleString('en-PK', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  };

  // Calculate percentages for the legend
  const totalBeforeCredits = bill.energyCharges + bill.fixedCharges + bill.fuelPriceAdjustment + 
    bill.quarterlyTariffAdjustment + bill.electricityDuty + bill.gst + bill.tvFee;

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <BarChart3 className="h-5 w-5 text-primary" />
          Bill Components Breakdown
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 10, right: 30, left: 0, bottom: 10 }}
              barSize={40}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
              <XAxis 
                type="number" 
                tickFormatter={formatCurrency}
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                axisLine={{ stroke: 'hsl(var(--border))' }}
              />
              <YAxis 
                type="category" 
                dataKey="name" 
                hide 
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const data = payload[0].payload;
                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-xl">
                      <p className="font-semibold mb-2">Bill Components</p>
                      <div className="space-y-1.5 text-sm">
                        {BILL_COMPONENTS.map(comp => {
                          const value = data[comp.key];
                          if (value <= 0) return null;
                          const percentage = ((value / totalBeforeCredits) * 100).toFixed(1);
                          return (
                            <div key={comp.key} className="flex items-center justify-between gap-4">
                              <div className="flex items-center gap-2">
                                <div 
                                  className="h-3 w-3 rounded-sm" 
                                  style={{ backgroundColor: comp.color }}
                                />
                                <span className="text-muted-foreground">{comp.label}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-medium">Rs. {value.toLocaleString()}</span>
                                <span className="text-xs text-muted-foreground">({percentage}%)</span>
                              </div>
                            </div>
                          );
                        })}
                        <div className="border-t pt-1.5 mt-1.5 flex justify-between font-semibold">
                          <span>Total</span>
                          <span className="font-mono">Rs. {totalBeforeCredits.toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                  );
                }}
              />
              {BILL_COMPONENTS.map(comp => (
                <Bar 
                  key={comp.key}
                  dataKey={comp.key} 
                  stackId="bill" 
                  fill={comp.color}
                  radius={comp.key === 'energyCharges' ? [4, 0, 0, 4] : comp.key === 'tvFee' ? [0, 4, 4, 0] : 0}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-3 justify-center">
          {BILL_COMPONENTS.map(comp => {
            const value = bill[comp.key as keyof BillBreakdown] as number;
            if (value <= 0) return null;
            return (
              <div key={comp.key} className="flex items-center gap-1.5 text-xs">
                <div 
                  className="h-2.5 w-2.5 rounded-sm shrink-0" 
                  style={{ backgroundColor: comp.color }}
                />
                <span className="text-muted-foreground">{comp.label}</span>
              </div>
            );
          })}
        </div>

        {/* Export Credits (if any) */}
        {bill.exportCredits > 0 && (
          <div className="mt-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
            <div className="flex items-center justify-between">
              <span className="text-sm text-green-600 dark:text-green-400">Export Credits Deduction</span>
              <span className="font-mono font-semibold text-green-600 dark:text-green-400">
                -Rs. {bill.exportCredits.toLocaleString()}
              </span>
            </div>
          </div>
        )}

        {/* Net Amount */}
        <div className="mt-4 p-4 rounded-lg bg-primary/5 border border-primary/20">
          <div className="flex items-center justify-between">
            <span className="font-medium">Net Payable Amount</span>
            <span className="text-xl font-bold font-mono text-primary">
              Rs. {bill.totalAmount.toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
