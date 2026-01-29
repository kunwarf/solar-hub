/**
 * Net Metering Hook
 *
 * Provides access to net metering billing data including running bill,
 * daily snapshots, billing months, cycles, and capacity analysis.
 */

import { useState, useEffect, useCallback } from 'react';
import { billingService } from '@/api/services/billing.service';
import type {
  RunningBill,
  DailySnapshot,
  BillingMonth,
  BillingCycle,
  BillingSummary,
  BillingTrendItem,
  CapacityStatus,
  NetMeteringConfig,
} from '@/api/services/billing.service';

interface UseNetMeteringOptions {
  siteId: string;
  autoFetch?: boolean;
}

interface UseNetMeteringReturn {
  // Data
  runningBill: RunningBill | null;
  dailySnapshots: DailySnapshot[];
  billingMonths: BillingMonth[];
  billingCycles: BillingCycle[];
  summary: BillingSummary | null;
  trend: BillingTrendItem[];
  capacityStatus: CapacityStatus | null;
  config: NetMeteringConfig | null;

  // Loading states
  loading: boolean;
  loadingRunningBill: boolean;
  loadingSnapshots: boolean;
  loadingMonths: boolean;
  loadingCycles: boolean;
  loadingSummary: boolean;
  loadingTrend: boolean;
  loadingCapacity: boolean;
  loadingConfig: boolean;

  // Error
  error: string | null;

  // Refetch functions
  refetchRunningBill: () => Promise<void>;
  refetchDailySnapshots: (startDate?: string, endDate?: string) => Promise<void>;
  refetchBillingMonths: (limit?: number) => Promise<void>;
  refetchBillingCycles: (limit?: number) => Promise<void>;
  refetchSummary: () => Promise<void>;
  refetchTrend: (months?: number) => Promise<void>;
  refetchCapacityStatus: () => Promise<void>;
  refetchConfig: () => Promise<void>;
  refetchAll: () => Promise<void>;
}

export function useNetMetering({
  siteId,
  autoFetch = true,
}: UseNetMeteringOptions): UseNetMeteringReturn {
  // Data states
  const [runningBill, setRunningBill] = useState<RunningBill | null>(null);
  const [dailySnapshots, setDailySnapshots] = useState<DailySnapshot[]>([]);
  const [billingMonths, setBillingMonths] = useState<BillingMonth[]>([]);
  const [billingCycles, setBillingCycles] = useState<BillingCycle[]>([]);
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [trend, setTrend] = useState<BillingTrendItem[]>([]);
  const [capacityStatus, setCapacityStatus] = useState<CapacityStatus | null>(null);
  const [config, setConfig] = useState<NetMeteringConfig | null>(null);

  // Loading states
  const [loadingRunningBill, setLoadingRunningBill] = useState(false);
  const [loadingSnapshots, setLoadingSnapshots] = useState(false);
  const [loadingMonths, setLoadingMonths] = useState(false);
  const [loadingCycles, setLoadingCycles] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingTrend, setLoadingTrend] = useState(false);
  const [loadingCapacity, setLoadingCapacity] = useState(false);
  const [loadingConfig, setLoadingConfig] = useState(false);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Fetch functions
  const refetchRunningBill = useCallback(async () => {
    if (!siteId) return;
    setLoadingRunningBill(true);
    try {
      const data = await billingService.getRunningBill(siteId);
      setRunningBill(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch running bill:', err);
      // Don't set error for 404 (no config yet)
    } finally {
      setLoadingRunningBill(false);
    }
  }, [siteId]);

  const refetchDailySnapshots = useCallback(
    async (startDate?: string, endDate?: string) => {
      if (!siteId) return;
      setLoadingSnapshots(true);
      try {
        const data = await billingService.getDailySnapshots(siteId, startDate, endDate, 30);
        setDailySnapshots(data.snapshots);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch daily snapshots:', err);
      } finally {
        setLoadingSnapshots(false);
      }
    },
    [siteId]
  );

  const refetchBillingMonths = useCallback(
    async (limit = 12) => {
      if (!siteId) return;
      setLoadingMonths(true);
      try {
        const data = await billingService.getBillingMonths(siteId, limit);
        setBillingMonths(data.months);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch billing months:', err);
      } finally {
        setLoadingMonths(false);
      }
    },
    [siteId]
  );

  const refetchBillingCycles = useCallback(
    async (limit = 4) => {
      if (!siteId) return;
      setLoadingCycles(true);
      try {
        const data = await billingService.getBillingCycles(siteId, limit);
        setBillingCycles(data.cycles);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch billing cycles:', err);
      } finally {
        setLoadingCycles(false);
      }
    },
    [siteId]
  );

  const refetchSummary = useCallback(async () => {
    if (!siteId) return;
    setLoadingSummary(true);
    try {
      const data = await billingService.getBillingSummary(siteId);
      setSummary(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch billing summary:', err);
    } finally {
      setLoadingSummary(false);
    }
  }, [siteId]);

  const refetchTrend = useCallback(
    async (months = 12) => {
      if (!siteId) return;
      setLoadingTrend(true);
      try {
        const data = await billingService.getBillingTrend(siteId, months);
        setTrend(data.trend);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch billing trend:', err);
      } finally {
        setLoadingTrend(false);
      }
    },
    [siteId]
  );

  const refetchCapacityStatus = useCallback(async () => {
    if (!siteId) return;
    setLoadingCapacity(true);
    try {
      const data = await billingService.getCapacityStatus(siteId);
      setCapacityStatus(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch capacity status:', err);
    } finally {
      setLoadingCapacity(false);
    }
  }, [siteId]);

  const refetchConfig = useCallback(async () => {
    if (!siteId) return;
    setLoadingConfig(true);
    try {
      const data = await billingService.getNetMeteringConfig(siteId);
      setConfig(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch net metering config:', err);
      // Config might not exist yet
    } finally {
      setLoadingConfig(false);
    }
  }, [siteId]);

  const refetchAll = useCallback(async () => {
    await Promise.all([
      refetchConfig(),
      refetchRunningBill(),
      refetchSummary(),
      refetchTrend(12),
    ]);
  }, [refetchConfig, refetchRunningBill, refetchSummary, refetchTrend]);

  // Auto-fetch on mount
  useEffect(() => {
    if (autoFetch && siteId) {
      refetchAll();
    }
  }, [autoFetch, siteId, refetchAll]);

  // Compute overall loading state
  const loading =
    loadingRunningBill ||
    loadingSnapshots ||
    loadingMonths ||
    loadingCycles ||
    loadingSummary ||
    loadingTrend ||
    loadingCapacity ||
    loadingConfig;

  return {
    // Data
    runningBill,
    dailySnapshots,
    billingMonths,
    billingCycles,
    summary,
    trend,
    capacityStatus,
    config,

    // Loading states
    loading,
    loadingRunningBill,
    loadingSnapshots,
    loadingMonths,
    loadingCycles,
    loadingSummary,
    loadingTrend,
    loadingCapacity,
    loadingConfig,

    // Error
    error,

    // Refetch functions
    refetchRunningBill,
    refetchDailySnapshots,
    refetchBillingMonths,
    refetchBillingCycles,
    refetchSummary,
    refetchTrend,
    refetchCapacityStatus,
    refetchConfig,
    refetchAll,
  };
}

export default useNetMetering;
