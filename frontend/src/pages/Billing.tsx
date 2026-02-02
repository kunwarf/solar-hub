import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  Loader2,
  Battery,
  Sun,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { useBillingConfig } from "@/hooks/use-billing-config";
import { useNetMetering } from "@/hooks/use-net-metering";
import { WhatIfCalculator } from "@/components/billing/WhatIfCalculator";
import { dashboardService } from "@/api/services/dashboard.service";
import type { AllWidgetsData, EnergyChartResponse } from "@/api/services/dashboard.service";
import { sitesService } from "@/api/services/sites.service";

interface BillingPageData {
  currentPeriod: {
    startDate: string;
    endDate: string;
    daysRemaining: number;
  };
  energyProduced: number;
  energyConsumed: number;
  energyExported: number;
  energyImported: number;
  feedInRate: number;
  importRate: number;
  earnings: number;
  costs: number;
  netBalance: number;
  monthlyHistory: Array<{
    month: string;
    produced: number;
    consumed: number;
    exported: number;
    imported: number;
    earnings: number;
    costs: number;
    netBalance: number;
    lastYearBill: number;
    thisYearBill: number;
  }>;
}

function buildBillingData(
  widgets: AllWidgetsData,
  chartData: EnergyChartResponse
): BillingPageData {
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const daysRemaining = Math.max(0, endOfMonth.getDate() - now.getDate());

  const { billing, stats } = widgets;
  const importRate = billing.import_rate_pkr || 30;
  const exportRate = billing.export_rate_pkr || 15;

  // Energy data from today's stats
  const energyProduced = stats.energy_today_kwh || 0;
  const energyConsumed = energyProduced; // approximate (no separate consumption metric)
  const energyExported = exportRate > 0 ? billing.grid_export_credit / exportRate : 0;
  const energyImported = importRate > 0 ? billing.grid_import_cost / importRate : 0;

  const earnings = billing.grid_export_credit;
  const costs = billing.grid_import_cost;
  const netBalance = earnings - costs;

  // Build monthly history from chart data points
  const monthlyHistory = chartData.data.map((point) => {
    const dt = new Date(point.timestamp);
    const monthName = dt.toLocaleString("en", { month: "short" });
    const produced = point.pv_kwh;
    const imported = point.grid_import_kwh;
    const exported = point.grid_export_kwh;
    const consumed = point.load_kwh;
    const dayEarnings = exported * exportRate;
    const dayCosts = imported * importRate;

    return {
      month: monthName,
      produced: parseFloat(produced.toFixed(1)),
      consumed: parseFloat(consumed.toFixed(1)),
      exported: parseFloat(exported.toFixed(1)),
      imported: parseFloat(imported.toFixed(1)),
      earnings: parseFloat(dayEarnings.toFixed(2)),
      costs: parseFloat(dayCosts.toFixed(2)),
      netBalance: parseFloat((dayEarnings - dayCosts).toFixed(2)),
      lastYearBill: 0, // No historical comparison data yet
      thisYearBill: parseFloat(dayCosts.toFixed(2)),
    };
  });

  return {
    currentPeriod: {
      startDate: startOfMonth.toISOString().split("T")[0],
      endDate: endOfMonth.toISOString().split("T")[0],
      daysRemaining,
    },
    energyProduced,
    energyConsumed,
    energyExported,
    energyImported,
    feedInRate: exportRate,
    importRate,
    earnings,
    costs,
    netBalance,
    monthlyHistory,
  };
}

const BillingPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const urlSiteId = searchParams.get("site_id");
  const [siteId, setSiteId] = useState<string>(urlSiteId || "");
  const [isLoadingSite, setIsLoadingSite] = useState(!urlSiteId);
  const { formatCurrency, getCurrencySymbol, config } = useBillingConfig();
  const [billingData, setBillingData] = useState<BillingPageData | null>(null);
  const [loading, setLoading] = useState(true);

  // Auto-fetch site ID if not provided in URL
  useEffect(() => {
    const fetchSiteId = async () => {
      if (urlSiteId) {
        setSiteId(urlSiteId);
        setIsLoadingSite(false);
        return;
      }

      try {
        const sites = await sitesService.listSites();
        if (sites && sites.length > 0) {
          const firstSiteId = sites[0].id;
          setSiteId(firstSiteId);
          navigate(`/billing?site_id=${firstSiteId}`, { replace: true });
        }
      } catch (error) {
        console.error('Failed to fetch site:', error);
      } finally {
        setIsLoadingSite(false);
      }
    };

    fetchSiteId();
  }, [urlSiteId, navigate]);

  // Net metering data from new API
  const {
    runningBill,
    trend,
    capacityStatus,
    loading: netMeteringLoading,
    refetchAll: refetchNetMetering,
  } = useNetMetering({
    siteId: siteId || "",
    autoFetch: !!siteId && !isLoadingSite,
  });

  const fetchData = useCallback(async () => {
    try {
      const [widgets, chartResponse] = await Promise.all([
        dashboardService.getAllWidgets(),
        dashboardService.getEnergyChart("month"),
      ]);
      setBillingData(buildBillingData(widgets, chartResponse));
    } catch {
      // Keep previous data on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRunScheduler = async () => {
    toast({
      title: "Syncing billing data",
      description: "Refreshing data from telemetry...",
    });
    try {
      await Promise.all([
        dashboardService.getAllWidgets(),
        fetchData(),
        siteId ? refetchNetMetering() : Promise.resolve(),
      ]);
      toast({
        title: "Billing data refreshed",
        description: "Latest telemetry data has been loaded.",
      });
    } catch {
      toast({
        title: "Refresh failed",
        description: "Could not refresh billing data. Please try again.",
        variant: "destructive",
      });
    }
  };

  if (loading || !billingData) {
    return (
      <AppLayout>
        <AppHeader
          title="Billing & Capacity Dashboard"
          subtitle="Monitor your electricity bills, capacity, and forecasts"
        />
        <div className="p-6 flex items-center justify-center min-h-[400px]">
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="w-6 h-6 animate-spin" />
            <span>Loading billing data...</span>
          </div>
        </div>
      </AppLayout>
    );
  }

  const netPositive = billingData.netBalance >= 0;

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
            Refresh Data
          </Button>
          <Button
            onClick={() => navigate(siteId ? `/billing/settings?site_id=${siteId}` : "/billing/settings")}
            className="gap-2"
            disabled={!siteId}
          >
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
            className="stat-card p-5"
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
            className="stat-card p-5"
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
            className="stat-card p-5"
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
            className="stat-card p-5"
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

        {/* Running Bill (from Net Metering API) */}
        {runningBill && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.55 }}
            className="glass-card p-6"
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-foreground">Running Bill (Month-to-Date)</h3>
              <Badge variant={runningBill.surplus_deficit_flag === 'SURPLUS' ? 'default' : 'destructive'}>
                {runningBill.surplus_deficit_flag}
              </Badge>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {/* Progress */}
              <div className="p-4 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground mb-1">Billing Progress</p>
                <p className="font-mono text-xl font-bold text-foreground">
                  {runningBill.progress_percent.toFixed(0)}%
                </p>
                <p className="text-xs text-muted-foreground">
                  Day {runningBill.days_elapsed} of {runningBill.total_days_in_month}
                </p>
              </div>

              {/* Bill to Date */}
              <div className="p-4 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground mb-1">Bill To-Date</p>
                <p className="font-mono text-xl font-bold text-foreground">
                  {formatCurrency(runningBill.bill_final_rs_to_date)}
                </p>
              </div>

              {/* Credit Balance */}
              <div className="p-4 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground mb-1">Credit Balance</p>
                <p className="font-mono text-xl font-bold text-success">
                  {formatCurrency(runningBill.bill_credit_balance_rs_to_date)}
                </p>
              </div>

              {/* Net Position */}
              <div className="p-4 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground mb-1">Net kWh Position</p>
                <p className={cn(
                  "font-mono text-xl font-bold",
                  runningBill.net_kwh_position >= 0 ? "text-success" : "text-destructive"
                )}>
                  {runningBill.net_kwh_position >= 0 ? "+" : ""}{runningBill.net_kwh_position.toFixed(1)} kWh
                </p>
              </div>
            </div>

            {/* Energy Breakdown */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-primary/10">
                <ArrowDownRight className="w-5 h-5 text-consumption" />
                <div>
                  <p className="text-xs text-muted-foreground">Peak Import</p>
                  <p className="font-mono font-medium">{runningBill.import_peak_kwh.toFixed(1)} kWh</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-primary/10">
                <ArrowDownRight className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Off-Peak Import</p>
                  <p className="font-mono font-medium">{runningBill.import_off_kwh.toFixed(1)} kWh</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-success/10">
                <ArrowUpRight className="w-5 h-5 text-success" />
                <div>
                  <p className="text-xs text-muted-foreground">Peak Export</p>
                  <p className="font-mono font-medium">{runningBill.export_peak_kwh.toFixed(1)} kWh</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-success/10">
                <ArrowUpRight className="w-5 h-5 text-success/70" />
                <div>
                  <p className="text-xs text-muted-foreground">Off-Peak Export</p>
                  <p className="font-mono font-medium">{runningBill.export_off_kwh.toFixed(1)} kWh</p>
                </div>
              </div>
            </div>

            {/* Credit Pools */}
            <div className="mt-6 pt-6 border-t border-border">
              <p className="text-sm font-medium text-foreground mb-3">Credit Pools (3-Month Cycle)</p>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/20">
                  <span className="text-sm text-muted-foreground">Off-Peak Credits</span>
                  <span className="font-mono font-medium text-success">
                    {runningBill.credits_off_cycle_kwh_balance.toFixed(1)} kWh
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/20">
                  <span className="text-sm text-muted-foreground">Peak Credits</span>
                  <span className="font-mono font-medium text-success">
                    {runningBill.credits_peak_cycle_kwh_balance.toFixed(1)} kWh
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Capacity Status */}
        {capacityStatus && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className={cn(
              "glass-card p-6 border",
              capacityStatus.status === 'balanced' ? "border-success/30" :
              capacityStatus.status === 'over-capacity' ? "border-primary/30" :
              "border-warning/30"
            )}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-foreground">Capacity Analysis</h3>
              <Badge variant={
                capacityStatus.status === 'balanced' ? 'default' :
                capacityStatus.status === 'over-capacity' ? 'secondary' : 'destructive'
              }>
                {capacityStatus.status.replace('-', ' ').toUpperCase()}
              </Badge>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-secondary/30">
                <div className="flex items-center gap-2 mb-2">
                  <Sun className="w-4 h-4 text-solar" />
                  <p className="text-xs text-muted-foreground">Installed</p>
                </div>
                <p className="font-mono text-xl font-bold text-foreground">
                  {capacityStatus.installed_kw.toFixed(1)} kW
                </p>
              </div>
              <div className="p-4 rounded-lg bg-secondary/30">
                <div className="flex items-center gap-2 mb-2">
                  <Battery className="w-4 h-4 text-primary" />
                  <p className="text-xs text-muted-foreground">Required for Zero Bill</p>
                </div>
                <p className="font-mono text-xl font-bold text-foreground">
                  {capacityStatus.required_kw_for_zero_bill.toFixed(1)} kW
                </p>
              </div>
              <div className="p-4 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground mb-2">Deficit/Surplus</p>
                <p className={cn(
                  "font-mono text-xl font-bold",
                  capacityStatus.deficit_kw <= 0 ? "text-success" : "text-destructive"
                )}>
                  {capacityStatus.deficit_kw <= 0 ? "+" : "-"}{Math.abs(capacityStatus.deficit_kw).toFixed(1)} kW
                </p>
              </div>
              <div className="p-4 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground mb-2">Annual Bill</p>
                <p className="font-mono text-xl font-bold text-foreground">
                  {formatCurrency(capacityStatus.annual_bill_rs)}
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* Billing Trend (from Net Metering API) */}
        {trend.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.65 }}
            className="glass-card p-6"
          >
            <h3 className="text-lg font-semibold text-foreground mb-6">Monthly Bill Trend</h3>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={trend.map(item => ({
                    month: `${item.year}-${String(item.month).padStart(2, '0')}`,
                    bill: item.bill_final_rs,
                    importPeak: item.import_peak_kwh,
                    importOff: item.import_off_kwh,
                    exportPeak: item.export_peak_kwh,
                    exportOff: item.export_off_kwh,
                  }))}
                  margin={{ top: 10, right: 10, left: 20, bottom: 0 }}
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
                      if (name === 'bill') return [formatCurrency(value), 'Bill'];
                      return [`${value.toFixed(1)} kWh`, name];
                    }}
                  />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: "12px" }} />
                  <Bar dataKey="bill" name="Bill (Rs)" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        )}

        {/* Monthly History Chart */}
        {billingData.monthlyHistory.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
            className="glass-card p-6"
          >
            <h3 className="text-lg font-semibold text-foreground mb-6">Energy History</h3>

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
        )}

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Grid Import vs Export */}
          {billingData.monthlyHistory.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
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
          )}

          {/* Self Sufficiency Trend */}
          {billingData.monthlyHistory.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8 }}
              className="glass-card p-6"
            >
              <h3 className="text-lg font-semibold text-foreground mb-6">Self-Sufficiency Rate</h3>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={billingData.monthlyHistory.map(m => ({
                      ...m,
                      selfSufficiency: m.consumed > 0
                        ? Math.round(((m.consumed - m.imported) / m.consumed) * 100)
                        : 0
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
          )}
        </div>

        {/* What-If Scenario Calculator */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.9 }}
        >
          <WhatIfCalculator />
        </motion.div>

        {/* Rate Information */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0 }}
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
