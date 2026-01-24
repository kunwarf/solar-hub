/**
 * Telemetry Context
 *
 * Provides real-time telemetry data via WebSocket with HTTP polling fallback.
 * Integrates with the backend dashboard service.
 * Only polls when user is authenticated to avoid 401 spam.
 */

import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useCallback,
  useMemo,
  useEffect,
  useRef,
} from 'react';
import { useWebSocket, ConnectionStatus } from '@/hooks/use-websocket';
import { dashboardService, PowerSnapshot, PowerFlowData } from '@/api';
import { useAuth } from '@/hooks/use-auth';

export interface TelemetryData {
  timestamp: string;
  solarPower: number;
  batteryPower: number;
  batteryLevel: number;
  isCharging: boolean;
  consumption: number;
  gridPower: number;
  isGridExporting: boolean;
}

interface TelemetryContextType {
  // Connection state
  connectionStatus: ConnectionStatus;
  reconnect: () => void;
  retryCount: number;
  nextRetryIn: number | null;

  // Telemetry data
  telemetry: TelemetryData | null;
  lastUpdated: Date | null;
  isLive: boolean;

  // Data pulse indicator
  dataReceivedAt: number | null;

  // Manual refresh
  refresh: () => Promise<void>;
}

// Convert API PowerSnapshot to TelemetryData (legacy)
function powerSnapshotToTelemetry(snapshot: PowerSnapshot): TelemetryData {
  return {
    timestamp: snapshot.timestamp,
    solarPower: snapshot.solar_power_kw,
    batteryPower: Math.abs(snapshot.battery_power_kw),
    batteryLevel: snapshot.battery_soc,
    isCharging: snapshot.battery_power_kw < 0, // Negative means charging
    consumption: snapshot.consumption_kw,
    gridPower: Math.abs(snapshot.grid_power_kw),
    isGridExporting: snapshot.is_exporting,
  };
}

// Convert PowerFlowData (from Redis cache) to TelemetryData
// Now uses site-level aggregated data
function powerFlowToTelemetry(data: PowerFlowData): TelemetryData {
  return {
    timestamp: data.timestamp || new Date().toISOString(),
    solarPower: data.pv_power_w / 1000,  // Convert W to kW
    batteryPower: Math.abs(data.battery_power_w) / 1000,
    batteryLevel: data.battery_soc_pct,
    isCharging: data.is_charging,
    consumption: data.load_power_w / 1000,
    gridPower: Math.abs(data.grid_power_w) / 1000,
    isGridExporting: data.grid_power_w < 0,
  };
}

const TelemetryContext = createContext<TelemetryContextType | undefined>(undefined);

interface TelemetryProviderProps {
  children: ReactNode;
  siteId?: string;
  pollingInterval?: number; // Polling interval in ms when WebSocket unavailable
}

export const TelemetryProvider = ({
  children,
  siteId,
  pollingInterval = 5000,
}: TelemetryProviderProps) => {
  const { isAuthenticated } = useAuth();
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [dataReceivedAt, setDataReceivedAt] = useState<number | null>(null);
  const [usePolling, setUsePolling] = useState(false);
  const [authError, setAuthError] = useState(false);
  const fetchCountRef = useRef(0);

  // Handle WebSocket messages
  const handleMessage = useCallback((data: TelemetryData) => {
    setTelemetry(data);
    setLastUpdated(new Date());
    setDataReceivedAt(Date.now());
    setUsePolling(false); // WebSocket is working
    setAuthError(false);
  }, []);

  // WebSocket connection - only enable when authenticated
  const { status, reconnect, retryCount, nextRetryIn } = useWebSocket({
    onMessage: handleMessage,
    enabled: isAuthenticated && !authError,
  });

  // Fetch telemetry via HTTP (polling fallback)
  // Uses new widget API (reads from Redis cache) with fallback to legacy API
  const fetchTelemetry = useCallback(async () => {
    // Don't fetch if not authenticated or if we've had auth errors
    if (!isAuthenticated || authError) {
      return;
    }

    try {
      // Try new widget API first (reads from Redis cache)
      // Uses site-level aggregated data from all devices
      const powerFlow = await dashboardService.getPowerFlow(siteId);
      if (powerFlow.online) {
        const telemetryData = powerFlowToTelemetry(powerFlow);
        setTelemetry(telemetryData);
        setLastUpdated(new Date());
        setDataReceivedAt(Date.now());
        setAuthError(false);
        fetchCountRef.current = 0;
        return;
      }
    } catch (error: any) {
      // Check for 401 Unauthorized - stop polling
      if (error?.response?.status === 401 || error?.status === 401) {
        console.warn('Authentication error, stopping telemetry polling');
        setAuthError(true);
        return;
      }
      console.warn('Failed to fetch from widget API, trying legacy:', error);
    }

    // Fallback to legacy API
    try {
      const snapshot = await dashboardService.getCurrentPower(siteId);
      const telemetryData = powerSnapshotToTelemetry(snapshot);
      setTelemetry(telemetryData);
      setLastUpdated(new Date());
      setDataReceivedAt(Date.now());
      setAuthError(false);
      fetchCountRef.current = 0;
    } catch (error: any) {
      // Check for 401 Unauthorized - stop polling
      if (error?.response?.status === 401 || error?.status === 401) {
        console.warn('Authentication error, stopping telemetry polling');
        setAuthError(true);
        return;
      }
      console.warn('Failed to fetch telemetry:', error);
      // Increment fetch count and stop if too many failures
      fetchCountRef.current += 1;
      if (fetchCountRef.current > 5) {
        console.warn('Too many fetch failures, pausing telemetry');
        setAuthError(true);
      }
    }
  }, [siteId, isAuthenticated, authError]);

  // Manual refresh
  const refresh = useCallback(async () => {
    setAuthError(false); // Reset auth error on manual refresh
    fetchCountRef.current = 0;
    await fetchTelemetry();
  }, [fetchTelemetry]);

  // Reset auth error when authentication state changes
  useEffect(() => {
    if (isAuthenticated) {
      setAuthError(false);
      fetchCountRef.current = 0;
    }
  }, [isAuthenticated]);

  // Switch to polling if WebSocket fails after several retries
  useEffect(() => {
    if (status === 'error' && retryCount >= 3 && isAuthenticated && !authError) {
      setUsePolling(true);
    }
  }, [status, retryCount, isAuthenticated, authError]);

  // Polling fallback - only when authenticated and no auth errors
  useEffect(() => {
    if (!isAuthenticated || authError) {
      return;
    }

    if (usePolling || status === 'error') {
      // Initial fetch
      fetchTelemetry();

      // Set up polling interval
      const interval = setInterval(fetchTelemetry, pollingInterval);
      return () => clearInterval(interval);
    }
  }, [usePolling, status, fetchTelemetry, pollingInterval, isAuthenticated, authError]);

  // Initial telemetry fetch (only when authenticated)
  useEffect(() => {
    if (!telemetry && isAuthenticated && !authError) {
      fetchTelemetry();
    }
  }, [fetchTelemetry, telemetry, isAuthenticated, authError]);

  const isLive = (status === 'connected' || usePolling) && telemetry !== null;

  const value = useMemo(
    () => ({
      connectionStatus: usePolling ? 'connected' : status, // Show connected if polling works
      reconnect,
      retryCount,
      nextRetryIn,
      telemetry,
      lastUpdated,
      isLive,
      dataReceivedAt,
      refresh,
    }),
    [status, usePolling, reconnect, retryCount, nextRetryIn, telemetry, lastUpdated, isLive, dataReceivedAt, refresh]
  );

  return (
    <TelemetryContext.Provider value={value}>{children}</TelemetryContext.Provider>
  );
};

export const useTelemetry = () => {
  const context = useContext(TelemetryContext);
  if (!context) {
    throw new Error('useTelemetry must be used within a TelemetryProvider');
  }
  return context;
};

// Helper hook to detect data pulse (for "Live" indicator animation)
export const useDataPulse = (duration: number = 1000) => {
  const { dataReceivedAt } = useTelemetry();
  const [isPulsing, setIsPulsing] = React.useState(false);

  React.useEffect(() => {
    if (dataReceivedAt) {
      setIsPulsing(true);
      const timer = setTimeout(() => setIsPulsing(false), duration);
      return () => clearTimeout(timer);
    }
  }, [dataReceivedAt, duration]);

  return isPulsing;
};
