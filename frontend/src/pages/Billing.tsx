import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ComposedChart,
  Area,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Zap,
  Calendar,
  Download,
  FileText,
  RefreshCw,
  Settings2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { billingData } from "@/data/mockData";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { useBillingConfig } from "@/hooks/use-billing-config";
import { WhatIfCalculator } from "@/components/billing/WhatIfCalculator";

const BillingPage = () => {
  const navigate = useNavigate();
  const { formatCurrency, getCurrencySymbol } = useBillingConfig();
  const netPositive = billingData.netBalance >= 0;

  const handleRunScheduler = () => {
    toast({
      title: "Running Billing Scheduler",
      description: "Calculating billing data on-demand...",
    });
    // Simulate scheduler running
    setTimeout(() => {
      toast({
        title: "Scheduler Complete",
        description: "Billing data has been updated.",
      });
    }, 2000);
  };

  return (
    <AppLayout>
      <AppHeader 
        title="Billing & Capacity Dashboard" 
        subtitle="Monitor your electricity bills, capacity, and forecasts"
      />
      
      <div className="p-6 space-y-6">
        {/* Top Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-wrap gap-3 justify-end"
        >
          <Button onClick={handleRunScheduler} className="gap-2 bg-green-600 hover:bg-green-700">
            <RefreshCw className="w-4 h-4" />
            Run Scheduler
          </Button>
          <Button onClick={() => navigate("/billing/settings")} className="gap-2">
            <Settings2 className="w-4 h-4" />
            Configure Billing
          </Button>
        </motion.div>

        {/* Current Period Info */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-5"
        >
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
                <Calendar className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Current Billing Period</p>
                <p className="font-medium text-foreground">
                  {billingData.currentPeriod.startDate} - {billingData.currentPeriod.endDate}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                <FileText className="w-4 h-4 mr-2" />
                View Statement
              </Button>
              <Button variant="outline" size="sm">
                <Download className="w-4 h-4 mr-2" />
                Export Data
              </Button>
            </div>
          </div>
        </motion.div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="stat-card"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-solar/20 flex items-center justify-center">
                <Zap className="w-5 h-5 text-solar" />
              </div>
              <span className="text-sm text-muted-foreground">Energy Produced</span>
            </div>
            <p className="font-mono text-2xl font-bold text-solar">
              {billingData.energyProduced.toFixed(1)}
              <span className="text-sm font-normal text-muted-foreground ml-1">kWh</span>
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="stat-card"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-consumption/20 flex items-center justify-center">
                <TrendingDown className="w-5 h-5 text-consumption" />
              </div>
              <span className="text-sm text-muted-foreground">Energy Consumed</span>
            </div>
            <p className="font-mono text-2xl font-bold text-consumption">
              {billingData.energyConsumed.toFixed(1)}
              <span className="text-sm font-normal text-muted-foreground ml-1">kWh</span>
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="stat-card"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-success/20 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-success" />
              </div>
              <span className="text-sm text-muted-foreground">Grid Earnings</span>
            </div>
            <p className="font-mono text-2xl font-bold text-success">
              {formatCurrency(billingData.earnings)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {billingData.energyExported.toFixed(1)} kWh @ {getCurrencySymbol()}{billingData.feedInRate}/kWh
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="stat-card"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-destructive/20 flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-destructive" />
              </div>
              <span className="text-sm text-muted-foreground">Grid Costs</span>
            </div>
            <p className="font-mono text-2xl font-bold text-destructive">
              {formatCurrency(billingData.costs)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {billingData.energyImported.toFixed(1)} kWh @ {getCurrencySymbol()}{billingData.importRate}/kWh
            </p>
          </motion.div>
        </div>

        {/* Net Balance */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className={cn(
            "glass-card p-6 border",
            netPositive ? "border-success/30 bg-success/5" : "border-destructive/30 bg-destructive/5"
          )}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Net Balance This Period</p>
              <p className={cn(
                "font-mono text-4xl font-bold mt-2",
                netPositive ? "text-success" : "text-destructive"
              )}>
                {netPositive ? "+" : "-"}{formatCurrency(Math.abs(billingData.netBalance))}
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                {netPositive
                  ? "You're earning more than you're spending!"
                  : "Your grid usage exceeds your exports."}
              </p>
            </div>
            <div className={cn(
              "w-16 h-16 rounded-full flex items-center justify-center",
              netPositive ? "bg-success/20" : "bg-destructive/20"
            )}>
              {netPositive ? (
                <TrendingUp className="w-8 h-8 text-success" />
              ) : (
                <TrendingDown className="w-8 h-8 text-destructive" />
              )}
            </div>
          </div>
        </motion.div>

        {/* Monthly History Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="glass-card p-6"
        >
          <h3 className="text-lg font-semibold text-foreground mb-6">Monthly Energy History</h3>
          
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={billingData.monthlyHistory} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 13% 20%)" vertical={false} />
                <XAxis
                  dataKey="month"
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
                  tickFormatter={(value) => `${value}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(220 18% 10%)",
                    border: "1px solid hsl(220 13% 20%)",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  labelStyle={{ color: "hsl(210 20% 92%)" }}
                />
                <Legend
                  verticalAlign="top"
                  height={36}
                  wrapperStyle={{ fontSize: "12px" }}
                />
                <Bar
                  dataKey="produced"
                  name="Produced (kWh)"
                  fill="hsl(45 93% 47%)"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="consumed"
                  name="Consumed (kWh)"
                  fill="hsl(280 65% 60%)"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="exported"
                  name="Exported (kWh)"
                  fill="hsl(160 84% 39%)"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Month over Month Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Year over Year Bill Comparison */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
            className="glass-card p-6"
          >
            <h3 className="text-lg font-semibold text-foreground mb-2">Bill Amount: This Year vs Last Year</h3>
            <p className="text-sm text-muted-foreground mb-4">Compare monthly bills year over year</p>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={billingData.monthlyHistory} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis
                    dataKey="month"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${getCurrencySymbol()}${value}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    labelStyle={{ color: "hsl(var(--foreground))" }}
                    formatter={(value: number) => [formatCurrency(value), undefined]}
                  />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: "12px" }} />
                  <Bar dataKey="lastYearBill" name="2023" fill="hsl(var(--muted-foreground))" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="thisYearBill" name="2024" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          {/* Savings Comparison */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
            className="glass-card p-6"
          >
            <h3 className="text-lg font-semibold text-foreground mb-2">Monthly Savings vs Last Year</h3>
            <p className="text-sm text-muted-foreground mb-4">How much you saved compared to last year</p>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart 
                  data={billingData.monthlyHistory.map(m => ({
                    ...m,
                    savings: m.lastYearBill - m.thisYearBill,
                    savingsPercent: Math.round(((m.lastYearBill - m.thisYearBill) / m.lastYearBill) * 100)
                  }))} 
                  margin={{ top: 10, right: 10, left: 10, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis
                    dataKey="month"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${getCurrencySymbol()}${value}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    labelStyle={{ color: "hsl(var(--foreground))" }}
                    formatter={(value: number, name: string) => {
                      if (name === "Savings") return [formatCurrency(value), name];
                      return [`${value}%`, name];
                    }}
                  />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: "12px" }} />
                  <Bar dataKey="savings" name="Savings" fill="hsl(var(--success))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          {/* Import vs Export Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9 }}
            className="glass-card p-6"
          >
            <h3 className="text-lg font-semibold text-foreground mb-6">Grid Import vs Export</h3>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={billingData.monthlyHistory} margin={{ top: 10, right: 10, left: 20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis
                    dataKey="month"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value} kWh`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    labelStyle={{ color: "hsl(var(--foreground))" }}
                    formatter={(value: number) => [`${value} kWh`, undefined]}
                  />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: "12px" }} />
                  <Bar dataKey="exported" name="Exported" fill="hsl(160 84% 39%)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="imported" name="Imported" fill="hsl(var(--consumption))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          {/* Self Sufficiency Trend */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.0 }}
            className="glass-card p-6"
          >
            <h3 className="text-lg font-semibold text-foreground mb-6">Self-Sufficiency Rate</h3>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart 
                  data={billingData.monthlyHistory.map(m => ({
                    ...m,
                    selfSufficiency: Math.round(((m.consumed - m.imported) / m.consumed) * 100)
                  }))} 
                  margin={{ top: 10, right: 10, left: 10, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis
                    dataKey="month"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    domain={[0, 100]}
                    tickFormatter={(value) => `${value}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    labelStyle={{ color: "hsl(var(--foreground))" }}
                    formatter={(value: number) => [`${value}%`, "Self-Sufficiency"]}
                  />
                  <Line
                    type="monotone"
                    dataKey="selfSufficiency"
                    name="Self-Sufficiency"
                    stroke="hsl(var(--solar))"
                    strokeWidth={3}
                    dot={{ fill: "hsl(var(--solar))", strokeWidth: 2, r: 5 }}
                    activeDot={{ r: 7, fill: "hsl(var(--solar))" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        </div>

        {/* What-If Scenario Calculator */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.1 }}
        >
          <WhatIfCalculator />
        </motion.div>

        {/* Rate Information */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.2 }}
          className="glass-card p-6"
        >
          <h3 className="text-lg font-semibold text-foreground mb-4">Current Rates</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-secondary/30">
              <p className="text-sm text-muted-foreground">Grid Import Rate</p>
              <p className="font-mono text-xl font-bold text-foreground">{getCurrencySymbol()}{billingData.importRate}/kWh</p>
            </div>
            <div className="p-4 rounded-lg bg-secondary/30">
              <p className="text-sm text-muted-foreground">Feed-in Tariff (Export)</p>
              <p className="font-mono text-xl font-bold text-foreground">{getCurrencySymbol()}{billingData.feedInRate}/kWh</p>
            </div>
          </div>
        </motion.div>
      </div>
    </AppLayout>
  );
};

export default BillingPage;
