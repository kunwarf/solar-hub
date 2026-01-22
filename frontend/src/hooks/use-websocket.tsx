import { useState, useEffect, useCallback, useRef } from 'react';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'failed';

interface UseWebSocketOptions {
  url?: string;
  onMessage?: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  maxRetries?: number;
  enabled?: boolean;
}

interface UseWebSocketReturn {
  status: ConnectionStatus;
  reconnect: () => void;
  lastMessage: any | null;
  retryCount: number;
  nextRetryIn: number | null;
}

// Exponential backoff: 5s, 10s, 20s, 40s, max 60s
const getRetryDelay = (retryCount: number): number => {
  const baseDelay = 5000;
  const delay = baseDelay * Math.pow(2, retryCount);
  return Math.min(delay, 60000);
};

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const {
    url = 'wss://mock-telemetry.local/ws',
    onMessage,
    onConnect,
    onDisconnect,
    maxRetries = 10,
    enabled = true,
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [lastMessage, setLastMessage] = useState<any | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [nextRetryIn, setNextRetryIn] = useState<number | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);
  const mockIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Generate realistic mock telemetry based on time of day
  const generateMockTelemetry = useCallback(() => {
    const now = new Date();
    const hour = now.getHours() + now.getMinutes() / 60;
    
    // Solar power curve: 0 at night, peaks at noon
    let solarPower = 0;
    if (hour >= 6 && hour <= 18) {
      // Bell curve peaking at noon (hour 12)
      const hoursFromNoon = Math.abs(hour - 12);
      const maxPower = 8.5; // kW at peak
      solarPower = maxPower * Math.cos((hoursFromNoon / 6) * (Math.PI / 2));
      // Add some natural variation
      solarPower *= (0.9 + Math.random() * 0.2);
      solarPower = Math.max(0, solarPower);
    }

    // Base consumption with daily patterns
    let consumption = 1.2; // Base load kW
    if (hour >= 7 && hour <= 9) consumption = 2.5; // Morning peak
    if (hour >= 12 && hour <= 14) consumption = 1.8; // Lunch
    if (hour >= 18 && hour <= 22) consumption = 3.5; // Evening peak
    if (hour >= 23 || hour <= 5) consumption = 0.8; // Night low
    // Add variation
    consumption *= (0.85 + Math.random() * 0.3);

    // Battery logic
    const batteryCapacity = 13.5; // kWh
    const currentBatteryLevel = 30 + Math.random() * 50; // 30-80%
    const excessPower = solarPower - consumption;
    
    let batteryPower = 0;
    let isCharging = false;
    
    if (excessPower > 0.5 && currentBatteryLevel < 95) {
      // Charge battery with excess solar
      batteryPower = Math.min(excessPower * 0.8, 5); // Max 5kW charge rate
      isCharging = true;
    } else if (excessPower < -0.3 && currentBatteryLevel > 20) {
      // Discharge battery to cover deficit
      batteryPower = Math.min(-excessPower, 5, (currentBatteryLevel / 100) * batteryCapacity * 0.5);
      isCharging = false;
    }

    // Grid power: import when solar + battery insufficient
    const netPower = solarPower + (isCharging ? -batteryPower : batteryPower) - consumption;
    let gridPower = 0;
    let isGridExporting = false;
    
    if (netPower < -0.1) {
      gridPower = Math.abs(netPower);
      isGridExporting = false;
    } else if (netPower > 0.5) {
      gridPower = netPower;
      isGridExporting = true;
    }

    return {
      timestamp: now.toISOString(),
      solarPower: parseFloat(solarPower.toFixed(2)),
      batteryPower: parseFloat(batteryPower.toFixed(2)),
      batteryLevel: parseFloat(currentBatteryLevel.toFixed(1)),
      isCharging,
      consumption: parseFloat(consumption.toFixed(2)),
      gridPower: parseFloat(gridPower.toFixed(2)),
      isGridExporting,
    };
  }, []);

  // Start mock data simulation
  const startMockSimulation = useCallback(() => {
    if (mockIntervalRef.current) {
      clearInterval(mockIntervalRef.current);
    }

    // Initial data
    const initialData = generateMockTelemetry();
    setLastMessage(initialData);
    onMessage?.(initialData);

    // Update every 2 seconds
    mockIntervalRef.current = setInterval(() => {
      const data = generateMockTelemetry();
      setLastMessage(data);
      onMessage?.(data);
    }, 2000);
  }, [generateMockTelemetry, onMessage]);

  const stopMockSimulation = useCallback(() => {
    if (mockIntervalRef.current) {
      clearInterval(mockIntervalRef.current);
      mockIntervalRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    setStatus('connecting');
    
    // Simulate connection delay
    setTimeout(() => {
      // For now, always succeed with mock simulation
      // In production, this would create actual WebSocket connection
      setStatus('connected');
      setRetryCount(0);
      setNextRetryIn(null);
      onConnect?.();
      startMockSimulation();
    }, 1000 + Math.random() * 500);
  }, [enabled, onConnect, startMockSimulation]);

  const disconnect = useCallback(() => {
    stopMockSimulation();
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
    }
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
    }
    setStatus('failed');
    onDisconnect?.();
  }, [stopMockSimulation, onDisconnect]);

  const scheduleReconnect = useCallback(() => {
    if (retryCount >= maxRetries) {
      setStatus('failed');
      return;
    }

    const delay = getRetryDelay(retryCount);
    setStatus('reconnecting');
    setNextRetryIn(Math.ceil(delay / 1000));

    // Countdown timer
    countdownRef.current = setInterval(() => {
      setNextRetryIn(prev => {
        if (prev === null || prev <= 1) {
          if (countdownRef.current) clearInterval(countdownRef.current);
          return null;
        }
        return prev - 1;
      });
    }, 1000);

    retryTimeoutRef.current = setTimeout(() => {
      setRetryCount(prev => prev + 1);
      connect();
    }, delay);
  }, [retryCount, maxRetries, connect]);

  const reconnect = useCallback(() => {
    stopMockSimulation();
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
    }
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
    }
    setRetryCount(0);
    setNextRetryIn(null);
    connect();
  }, [connect, stopMockSimulation]);

  // Initial connection
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      stopMockSimulation();
      if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    status,
    reconnect,
    lastMessage,
    retryCount,
    nextRetryIn,
  };
};
