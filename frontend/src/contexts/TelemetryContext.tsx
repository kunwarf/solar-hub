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
  pollingInterval = 10000,
}: TelemetryProviderProps) => {
  const { isAuthenticated } = useAuth();
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [dataReceivedAt, setDataReceivedAt] = useState<number | null>(null);
  const [authError, setAuthError] = useState(false);
  const [hasRealData, setHasRealData] = useState(false); // Track if we have real API data
  const fetchCountRef = useRef(0);
  const initialFetchDoneRef = useRef(false);

  // Handle WebSocket messages - only use if we don't have real API data yet
  // The current WebSocket implementation uses mock data, so we prefer HTTP API
  const handleMessage = useCallback((data: TelemetryData) => {
    // Only use WebSocket data if we don't have real data from the API yet
    // Once we have real API data, ignore the mock WebSocket data
    if (!hasRealData) {
      setTelemetry(data);
      setLastUpdated(new Date());
      setDataReceivedAt(Date.now());
    }
    // Keep polling enabled - the HTTP API provides real device data
  }, [hasRealData]);

  // WebSocket connection - disabled for now since it only provides mock data
  // Enable this when a real WebSocket implementation exists
  const { status, reconnect, retryCount, nextRetryIn } = useWebSocket({
    onMessage: handleMessage,
    enabled: false, // Disabled: current implementation is mock-only
  });

  // Fetch telemetry via HTTP (primary data source)
  // Uses new widget API (reads from Redis cache where System B writes real device data)
  const fetchTelemetry = useCallback(async () => {
    // Don't fetch if not authenticated or if we've had auth errors
    if (!isAuthenticated || authError) {
      console.log('[Telemetry] Skipping fetch: not authenticated or auth error');
      return;
    }

    console.log('[Telemetry] Fetching power flow from API...');

    try {
      // Use widget API which reads from Redis cache (populated by System B)
      // This is the primary source of real device telemetry
      const powerFlow = await dashboardService.getPowerFlow(siteId);
      console.log('[Telemetry] Received power flow:', powerFlow);

      if (powerFlow.online) {
        const telemetryData = powerFlowToTelemetry(powerFlow);
        setTelemetry(telemetryData);
        setLastUpdated(new Date());
        setDataReceivedAt(Date.now());
        setHasRealData(true); // Mark that we have real API data
        setAuthError(false);
        fetchCountRef.current = 0;
        console.log('[Telemetry] Updated with real data:', telemetryData);
        return;
      } else {
        console.log('[Telemetry] Power flow returned online=false, devices may be offline');
        // Even if offline, still use the API response (shows 0 values)
        const telemetryData = powerFlowToTelemetry(powerFlow);
        setTelemetry(telemetryData);
        setLastUpdated(new Date());
        setDataReceivedAt(Date.now());
        setHasRealData(true);
        setAuthError(false);
        fetchCountRef.current = 0;
        return;
      }
    } catch (error: any) {
      // Check for 401 Unauthorized - token refresh might be in progress
      if (error?.response?.status === 401 || error?.status === 401 || error?.error === 'UNAUTHORIZED') {
        // Don't immediately stop polling - the token refresh logic in apiClient will handle this
        // Only stop if we get repeated 401s
        console.warn('[Telemetry] Authentication error (token may be refreshing)');
        fetchCountRef.current += 1;
        if (fetchCountRef.current > 3) {
          console.warn('[Telemetry] Multiple auth errors, stopping polling');
          setAuthError(true);
        }
        return;
      }
      console.warn('[Telemetry] Failed to fetch power flow:', error);
    }

    // Fallback to legacy API only if widget API completely fails
    try {
      console.log('[Telemetry] Trying legacy API fallback...');
      const snapshot = await dashboardService.getCurrentPower(siteId);
      const telemetryData = powerSnapshotToTelemetry(snapshot);
      setTelemetry(telemetryData);
      setLastUpdated(new Date());
      setDataReceivedAt(Date.now());
      setAuthError(false);
      fetchCountRef.current = 0;
    } catch (error: any) {
      // Check for 401 Unauthorized - token refresh might be in progress
      if (error?.response?.status === 401 || error?.status === 401 || error?.error === 'UNAUTHORIZED') {
        console.warn('[Telemetry] Authentication error on legacy API (token may be refreshing)');
        fetchCountRef.current += 1;
        if (fetchCountRef.current > 3) {
          console.warn('[Telemetry] Multiple auth errors, stopping polling');
          setAuthError(true);
        }
        return;
      }
      console.warn('[Telemetry] Failed to fetch from legacy API:', error);
      // Increment fetch count and stop if too many failures
      fetchCountRef.current += 1;
      if (fetchCountRef.current > 5) {
        console.warn('[Telemetry] Too many fetch failures, pausing telemetry');
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
  // Also trigger immediate fetch when user logs in
  useEffect(() => {
    if (isAuthenticated) {
      setAuthError(false);
      fetchCountRef.current = 0;
      // Reset initial fetch flag so polling effect will fetch immediately
      initialFetchDoneRef.current = false;
    }
  }, [isAuthenticated]);

  // HTTP polling is the primary data source
  // Polls the dashboard widget API which reads real device data from Redis
  useEffect(() => {
    if (!isAuthenticated || authError) {
      console.log('[Telemetry] Polling disabled: not authenticated or auth error');
      return;
    }

    console.log('[Telemetry] Starting HTTP polling (interval:', pollingInterval, 'ms)');

    // Initial fetch immediately when authenticated
    if (!initialFetchDoneRef.current) {
      initialFetchDoneRef.current = true;
      fetchTelemetry();
    }

    // Set up polling interval for continuous updates
    const interval = setInterval(fetchTelemetry, pollingInterval);
    return () => {
      console.log('[Telemetry] Stopping HTTP polling');
      clearInterval(interval);
    };
  }, [fetchTelemetry, pollingInterval, isAuthenticated, authError]);

  // Reset initial fetch flag when auth state changes
  useEffect(() => {
    if (!isAuthenticated) {
      initialFetchDoneRef.current = false;
      setHasRealData(false);
    }
  }, [isAuthenticated]);

  // Consider live if we have real data from the API (not mock WebSocket data)
  const isLive = hasRealData && telemetry !== null;

  const value = useMemo(
    () => ({
      connectionStatus: hasRealData ? 'connected' : (isAuthenticated ? 'connecting' : 'failed'),
      reconnect,
      retryCount,
      nextRetryIn,
      telemetry,
      lastUpdated,
      isLive,
      dataReceivedAt,
      refresh,
    }),
    [hasRealData, isAuthenticated, reconnect, retryCount, nextRetryIn, telemetry, lastUpdated, isLive, dataReceivedAt, refresh]
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
