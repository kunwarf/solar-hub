/**
 * Telemetry Context
 *
 * Provides real-time telemetry data via WebSocket with HTTP polling fallback.
 * Integrates with the backend dashboard service.
 */

import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useCallback,
  useMemo,
  useEffect,
} from 'react';
import { useWebSocket, ConnectionStatus } from '@/hooks/use-websocket';
import { dashboardService, PowerSnapshot, PowerFlowData } from '@/api';

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
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [dataReceivedAt, setDataReceivedAt] = useState<number | null>(null);
  const [usePolling, setUsePolling] = useState(false);

  // Handle WebSocket messages
  const handleMessage = useCallback((data: TelemetryData) => {
    setTelemetry(data);
    setLastUpdated(new Date());
    setDataReceivedAt(Date.now());
    setUsePolling(false); // WebSocket is working
  }, []);

  // WebSocket connection
  const { status, reconnect, retryCount, nextRetryIn } = useWebSocket({
    onMessage: handleMessage,
    enabled: true,
  });

  // Fetch telemetry via HTTP (polling fallback)
  // Uses new widget API (reads from Redis cache) with fallback to legacy API
  const fetchTelemetry = useCallback(async () => {
    try {
      // Try new widget API first (reads from Redis cache)
      // Uses site-level aggregated data from all devices
      const powerFlow = await dashboardService.getPowerFlow(siteId);
      if (powerFlow.online) {
        const telemetryData = powerFlowToTelemetry(powerFlow);
        setTelemetry(telemetryData);
        setLastUpdated(new Date());
        setDataReceivedAt(Date.now());
        return;
      }
    } catch (error) {
      console.warn('Failed to fetch from widget API, trying legacy:', error);
    }

    // Fallback to legacy API
    try {
      const snapshot = await dashboardService.getCurrentPower(siteId);
      const telemetryData = powerSnapshotToTelemetry(snapshot);
      setTelemetry(telemetryData);
      setLastUpdated(new Date());
      setDataReceivedAt(Date.now());
    } catch (error) {
      console.warn('Failed to fetch telemetry:', error);
    }
  }, [siteId]);

  // Manual refresh
  const refresh = useCallback(async () => {
    await fetchTelemetry();
  }, [fetchTelemetry]);

  // Switch to polling if WebSocket fails after several retries
  useEffect(() => {
    if (status === 'error' && retryCount >= 3) {
      setUsePolling(true);
    }
  }, [status, retryCount]);

  // Polling fallback
  useEffect(() => {
    if (usePolling || status === 'error') {
      // Initial fetch
      fetchTelemetry();

      // Set up polling interval
      const interval = setInterval(fetchTelemetry, pollingInterval);
      return () => clearInterval(interval);
    }
  }, [usePolling, status, fetchTelemetry, pollingInterval]);

  // Initial telemetry fetch (even if WebSocket is connecting)
  useEffect(() => {
    if (!telemetry) {
      fetchTelemetry();
    }
  }, [fetchTelemetry, telemetry]);

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
