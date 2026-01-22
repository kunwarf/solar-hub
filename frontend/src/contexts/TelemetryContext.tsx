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
import { dashboardService, PowerSnapshot } from '@/api';

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

// Convert API PowerSnapshot to TelemetryData
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
  const fetchTelemetry = useCallback(async () => {
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
