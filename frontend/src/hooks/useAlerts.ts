/**
 * Alerts Hooks
 *
 * Custom React hooks for managing alerts data and operations.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  alertsService,
  type UIAlert,
  type AlertFilters,
} from '@/api/services/alerts.service';
import type {
  Alert as ApiAlert,
  AlertRule,
  AlertsSummary,
  PaginationParams,
} from '@/api/types';

export interface UseAlertsOptions {
  filters?: AlertFilters;
  pagination?: PaginationParams;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export interface UseAlertsReturn {
  alerts: UIAlert[];
  total: number;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  acknowledgeAlert: (alertId: string) => Promise<void>;
  resolveAlert: (alertId: string) => Promise<void>;
}

/**
 * Hook for fetching and managing alerts (UI format)
 */
export function useAlerts(options: UseAlertsOptions = {}): UseAlertsReturn {
  const {
    filters,
    pagination,
    autoRefresh = false,
    refreshInterval = 30000,
  } = options;

  const [alerts, setAlerts] = useState<UIAlert[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchAlerts = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await alertsService.getAlertsForUI(filters, pagination);
      if (mountedRef.current) {
        setAlerts(response.alerts);
        setTotal(response.total);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch alerts');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [filters, pagination]);

  const acknowledgeAlert = useCallback(async (alertId: string) => {
    try {
      await alertsService.acknowledgeAlert(alertId);
      // Update local state
      setAlerts(prev =>
        prev.map(alert =>
          alert.id === alertId ? { ...alert, acknowledged: true } : alert
        )
      );
    } catch (err) {
      throw err;
    }
  }, []);

  const resolveAlert = useCallback(async (alertId: string) => {
    try {
      await alertsService.resolveAlert(alertId);
      // Update local state
      setAlerts(prev =>
        prev.map(alert =>
          alert.id === alertId
            ? { ...alert, severity: 'resolved' as const, acknowledged: true }
            : alert
        )
      );
    } catch (err) {
      throw err;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchAlerts();

    let intervalId: NodeJS.Timeout | undefined;
    if (autoRefresh && refreshInterval > 0) {
      intervalId = setInterval(fetchAlerts, refreshInterval);
    }

    return () => {
      mountedRef.current = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [fetchAlerts, autoRefresh, refreshInterval]);

  return {
    alerts,
    total,
    isLoading,
    error,
    refresh: fetchAlerts,
    acknowledgeAlert,
    resolveAlert,
  };
}

export interface UseAlertsSummaryReturn {
  summary: AlertsSummary | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Hook for fetching alerts summary
 */
export function useAlertsSummary(
  autoRefresh = false,
  refreshInterval = 30000
): UseAlertsSummaryReturn {
  const [summary, setSummary] = useState<AlertsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchSummary = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await alertsService.getAlertsSummary();
      if (mountedRef.current) {
        setSummary(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch alerts summary');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchSummary();

    let intervalId: NodeJS.Timeout | undefined;
    if (autoRefresh && refreshInterval > 0) {
      intervalId = setInterval(fetchSummary, refreshInterval);
    }

    return () => {
      mountedRef.current = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [fetchSummary, autoRefresh, refreshInterval]);

  return {
    summary,
    isLoading,
    error,
    refresh: fetchSummary,
  };
}

export interface UseAlertRulesReturn {
  rules: AlertRule[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  toggleRule: (ruleId: string) => Promise<void>;
  createRule: (rule: Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>) => Promise<AlertRule>;
  updateRule: (
    ruleId: string,
    updates: Partial<Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>>
  ) => Promise<AlertRule>;
  deleteRule: (ruleId: string) => Promise<void>;
}

/**
 * Hook for managing alert rules
 */
export function useAlertRules(): UseAlertRulesReturn {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchRules = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await alertsService.getAlertRules();
      if (mountedRef.current) {
        setRules(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch alert rules');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  const toggleRule = useCallback(async (ruleId: string) => {
    try {
      const updatedRule = await alertsService.toggleAlertRule(ruleId);
      setRules(prev =>
        prev.map(rule => (rule.id === ruleId ? updatedRule : rule))
      );
    } catch (err) {
      throw err;
    }
  }, []);

  const createRule = useCallback(
    async (rule: Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>) => {
      const newRule = await alertsService.createAlertRule(rule);
      setRules(prev => [...prev, newRule]);
      return newRule;
    },
    []
  );

  const updateRule = useCallback(
    async (
      ruleId: string,
      updates: Partial<Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>>
    ) => {
      const updatedRule = await alertsService.updateAlertRule(ruleId, updates);
      setRules(prev =>
        prev.map(rule => (rule.id === ruleId ? updatedRule : rule))
      );
      return updatedRule;
    },
    []
  );

  const deleteRule = useCallback(async (ruleId: string) => {
    await alertsService.deleteAlertRule(ruleId);
    setRules(prev => prev.filter(rule => rule.id !== ruleId));
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchRules();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchRules]);

  return {
    rules,
    isLoading,
    error,
    refresh: fetchRules,
    toggleRule,
    createRule,
    updateRule,
    deleteRule,
  };
}

/**
 * Hook for a single alert's operations
 */
export function useAlertActions() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const acknowledge = useCallback(async (alertId: string) => {
    setIsProcessing(true);
    setError(null);
    try {
      await alertsService.acknowledgeAlert(alertId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to acknowledge alert');
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const resolve = useCallback(async (alertId: string) => {
    setIsProcessing(true);
    setError(null);
    try {
      await alertsService.resolveAlert(alertId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve alert');
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  return {
    acknowledge,
    resolve,
    isProcessing,
    error,
  };
}
