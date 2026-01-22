import { useMemo } from "react";
import {
  homeHierarchy,
  getHomeAggregates,
  getSystemAggregates,
  energyStats,
  chartData,
  HomeHierarchy,
} from "@/data/mockData";

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

/**
 * Custom hook for centralized energy data access with memoization.
 * Prevents redundant aggregation calculations across components.
 */
export function useEnergyData() {
  // Memoize home-level aggregates
  const homeAggregates = useMemo(() => getHomeAggregates(homeHierarchy), []);

  // Memoize system aggregates
  const systemAggregates = useMemo(() => {
    return homeHierarchy.systems.reduce((acc, system) => {
      acc[system.id] = getSystemAggregates(system);
      return acc;
    }, {} as Record<string, SystemAggregates>);
  }, []);

  // Memoize energy stats for dashboard
  const stats = useMemo<EnergyAggregates>(() => ({
    solarPower: energyStats.solarPower,
    batteryPower: energyStats.batteryPower,
    batteryLevel: energyStats.batteryLevel,
    consumption: energyStats.consumption,
    gridPower: energyStats.gridPower,
    isGridExporting: energyStats.isGridExporting,
    dailyProduction: energyStats.dailyProduction,
    dailyConsumption: energyStats.dailyConsumption,
    selfConsumption: energyStats.selfConsumption,
    gridExported: energyStats.gridExported,
    co2Saved: energyStats.co2Saved,
    moneySaved: energyStats.moneySaved,
    monthlyBillAmount: energyStats.monthlyBillAmount,
    dailyPrediction: energyStats.dailyPrediction,
    avgKwPerKwp: energyStats.avgKwPerKwp,
    installedCapacity: energyStats.installedCapacity,
  }), []);

  // Memoize chart data
  const memoizedChartData = useMemo(() => chartData, []);

  // Memoize hierarchy
  const hierarchy = useMemo<HomeHierarchy>(() => homeHierarchy, []);

  return {
    stats,
    homeAggregates,
    systemAggregates,
    chartData: memoizedChartData,
    hierarchy,
  };
}
