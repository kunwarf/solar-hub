import { motion } from "framer-motion";
import { Receipt, Leaf, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useBillingConfig } from "@/hooks/use-billing-config";
import { useNavigate } from "react-router-dom";

interface BillingSummaryProps {
  currentMonthEstimate: number;
  lastMonthBill: number;
  exportCredits: number;
  exportedKwh: number;
  totalSavings: number;
  importRate: number;
  exportRate: number;
  peakHoursStart: string;
  peakHoursEnd: string;
  className?: string;
}

export function BillingSummary({
  currentMonthEstimate,
  lastMonthBill,
  exportCredits,
  exportedKwh,
  totalSavings,
  importRate,
  exportRate,
  peakHoursStart,
  peakHoursEnd,
  className,
}: BillingSummaryProps) {
  const { getCurrencySymbol } = useBillingConfig();
  const navigate = useNavigate();
  const currencySymbol = getCurrencySymbol();

  // Calculate percentage change vs last month
  const percentChange = lastMonthBill > 0 
    ? Math.round(((currentMonthEstimate - lastMonthBill) / lastMonthBill) * 100) 
    : 0;
  const isPositiveChange = percentChange <= 0;

  // Export progress (assume max 1000 kWh for visualization)
  const exportProgress = Math.min((exportedKwh / 1000) * 100, 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className={className}
    >
      <Card className="h-full border-border/50 bg-card/80 backdrop-blur-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-semibold">Billing Summary</CardTitle>
            <div className="p-2 rounded-lg bg-muted">
              <Receipt className="h-5 w-5 text-primary" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Current Month Estimate */}
          <div className="p-4 rounded-xl bg-muted/50 border border-border/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-muted-foreground">Current Month</span>
              <span className={`text-xs font-medium flex items-center gap-1 ${
                isPositiveChange ? 'text-success' : 'text-destructive'
              }`}>
                <span className="text-lg">↘</span>
                {isPositiveChange ? '' : '+'}{percentChange}% vs last month
              </span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-foreground">
                {currencySymbol}{currentMonthEstimate.toFixed(2)}
              </span>
              <span className="text-muted-foreground text-sm">estimated</span>
            </div>
          </div>

          {/* Export Credits */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Export Credits</span>
              <span className="text-sm font-semibold text-success">
                +{currencySymbol}{exportCredits.toFixed(2)}
              </span>
            </div>
            <Progress value={exportProgress} className="h-2 bg-muted" />
            <span className="text-xs text-muted-foreground mt-1 block">
              {exportedKwh} kWh exported this month
            </span>
          </div>

          {/* Total Savings Card */}
          <div className="p-4 rounded-xl bg-success/10 border border-success/20">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-full bg-success/20">
                <Leaf className="h-5 w-5 text-success" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Savings</p>
                <p className="text-xs text-muted-foreground">Since installation</p>
              </div>
            </div>
            <p className="text-2xl font-bold text-success mt-2">
              {currencySymbol}{totalSavings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>

          {/* Rate Info */}
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Import Rate</span>
              <span className="font-medium">{currencySymbol}{importRate.toFixed(2)}/kWh</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Export Rate</span>
              <span className="font-medium">{currencySymbol}{exportRate.toFixed(2)}/kWh</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Peak Hours</span>
              <span className="font-medium">{peakHoursStart} - {peakHoursEnd}</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              className="flex-1"
              onClick={() => navigate('/billing')}
            >
              Billing
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
            <Button 
              variant="outline" 
              className="flex-1"
              onClick={() => navigate('/savings')}
            >
              ROI
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
