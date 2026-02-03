import { useState, useEffect, useCallback, useRef } from "react";
import { dashboardService } from "@/api/services/dashboard.service";
import type { AllWidgetsData, EnergyChartResponse } from "@/api/services/dashboard.service";

export interface EnergyAggregates {
  solarPower: number;
  batteryPower: number;
  batteryLevel: number;
  consumption: number;
  gridPower: number;
  isGridExporting: boolean;
  dailyProduction: number;
  dailyConsumption: number;
  selfConsumption: number;
  gridExported: number;
  co2Saved: number;
  moneySaved: number;
  monthlyBillAmount: number;
  dailyPrediction: number;
  avgKwPerKwp: number;
  installedCapacity: number;
}

export interface SystemAggregates {
  solarPower: number;
  gridPower: number;
  loadPower: number;
  batteryPower: number;
  avgBatterySoc: number;
  batteryCount: number;
  inverterCount: number;
  onlineInverters: number;
  warningInverters: number;
  onlineBatteries: number;
  warningBatteries: number;
}

interface ChartDataPoint {
  time: string;
  solar: number;
  consumption: number;
  battery: number;
  grid: number;
}

const POLL_INTERVAL_MS = 30_000;

const defaultStats: EnergyAggregates = {
  solarPower: 0,
  batteryPower: 0,
  batteryLevel: 0,
  consumption: 0,
  gridPower: 0,
  isGridExporting: false,
  dailyProduction: 0,
  dailyConsumption: 0,
  selfConsumption: 0,
  gridExported: 0,
  co2Saved: 0,
  moneySaved: 0,
  monthlyBillAmount: 0,
  dailyPrediction: 0,
  avgKwPerKwp: 0,
  installedCapacity: 0,
};

function mapWidgetsToStats(data: AllWidgetsData): EnergyAggregates {
  const { power_flow, stats, billing, environmental } = data;

  const dailyProduction = stats.energy_today_kwh;
  const gridPowerW = power_flow.grid_power_w;

  const dailyConsumption = stats.load_energy_today_kwh;
  const gridExported = stats.grid_export_today_kwh;
  const gridImported = stats.grid_import_today_kwh;

  // Self-consumption: solar energy used directly (not exported)
  const selfConsumedKwh = Math.max(0, dailyProduction - gridExported);
  const selfConsumptionPct = dailyProduction > 0
    ? Math.round((selfConsumedKwh / dailyProduction) * 100)
    : 0;

  // Daily savings: value of self-consumed solar (avoided grid purchase cost)
  const importRate = billing.import_rate_pkr || 30;
  const dailySavings = selfConsumedKwh * importRate;

  // Monthly bill estimate: use grid import cost from billing widget
  // Note: This is a simplified estimate. For accurate bills, use net metering API
  const monthlyBillEstimate = billing.grid_import_cost || 0;

  // Average yield (kWh per kWp of installed capacity)
  const installedCapacityKw = stats.peak_power_kw > 0 ? Math.ceil(stats.peak_power_kw) : 1;
  const avgYield = dailyProduction / installedCapacityKw;

  return {
    solarPower: power_flow.pv_power_w / 1000,
    batteryPower: Math.abs(power_flow.battery_power_w) / 1000,
    batteryLevel: Math.round(power_flow.battery_soc_pct),
    consumption: power_flow.load_power_w / 1000,
    gridPower: Math.abs(gridPowerW) / 1000,
    isGridExporting: gridPowerW < 0,
    dailyProduction,
    dailyConsumption,
    selfConsumption: selfConsumptionPct,
    gridExported,
    co2Saved: stats.co2_saved_kg,
    moneySaved: dailySavings,
    monthlyBillAmount: monthlyBillEstimate,
    dailyPrediction: dailyProduction * 1.05, // slight buffer until prediction service exists
    avgKwPerKwp: avgYield,
    installedCapacity: installedCapacityKw,
  };
}

function mapChartResponse(response: EnergyChartResponse): ChartDataPoint[] {
  return response.data.map((point) => {
    // Extract hour from ISO timestamp for display
    let timeLabel: string;
    try {
      const dt = new Date(point.timestamp);
      timeLabel = `${dt.getHours().toString().padStart(2, "0")}:00`;
    } catch {
      timeLabel = point.timestamp;
    }

    return {
      time: timeLabel,
      solar: parseFloat(point.pv_kwh.toFixed(1)),
      consumption: parseFloat(point.load_kwh.toFixed(1)),
      battery: 0, // battery chart data not in energy-chart endpoint
      grid: parseFloat((point.grid_import_kwh - point.grid_export_kwh).toFixed(1)),
    };
  });
}

/**
 * Custom hook for centralized energy data access.
 *
 * Fetches from the dashboard API and polls every 30 seconds.
 * Falls back to zero values while loading.
 */
export function useEnergyData() {
  const [stats, setStats] = useState<EnergyAggregates>(defaultStats);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [widgetsData, setWidgetsData] = useState<AllWidgetsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [widgets, chartResponse] = await Promise.all([
        dashboardService.getAllWidgets(),
        dashboardService.getEnergyChart("day"),
      ]);

      setStats(mapWidgetsToStats(widgets));
      setChartData(mapChartResponse(chartResponse));
      setWidgetsData(widgets);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch dashboard data";
      setError(message);
      // Keep previous data on error (don't reset to defaults)
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    intervalRef.current = setInterval(fetchData, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchData]);

  return {
    stats,
    chartData,
    widgetsData,
    loading,
    error,
  };
}
