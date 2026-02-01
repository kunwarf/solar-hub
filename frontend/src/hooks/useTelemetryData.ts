/**
 * useTelemetryData Hook
 *
 * Fetches and manages real-time telemetry data for devices
 * with automatic fallback to mock data when APIs are unavailable
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { devicesService, dashboardService } from '@/api';
import type {
  MPPTChannel,
  ExtendedInverterMetrics,
  HistoricalPowerPoint,
  DeviceMetrics
} from '@/api/types';

interface UseTelemetryDataOptions {
  deviceId: string;
  serialNumber?: string;
  pollingInterval?: number; // ms, default 5000
  enableHistorical?: boolean; // Fetch historical data
  enableMPPT?: boolean; // Fetch MPPT channel data
}

interface TelemetryDataState {
  // Real-time metrics
  metrics: ExtendedInverterMetrics | null;

  // MPPT/Solar array data
  mpptChannels: MPPTChannel[];

  // Historical power data
  historicalData: HistoricalPowerPoint[];

  // Loading states
  isLoading: boolean;
  isPolling: boolean;

  // Error handling
  error: Error | null;

  // Data freshness
  lastUpdated: Date | null;
  usingFallback: boolean;
}

// All mock data generators removed - using real data only

/**
 * Extract MPPT channel data from raw telemetry
 */
function extractMPPTChannels(rawTelemetry: any): MPPTChannel[] {
  if (!rawTelemetry) return [];

  const channels: MPPTChannel[] = [];

  // Check for up to 4 MPPT channels
  for (let i = 1; i <= 4; i++) {
    const voltageKey = `pv${i}_voltage_v`;
    const currentKey = `pv${i}_current_a`;
    const powerKey = `pv${i}_power_w`;

    if (rawTelemetry[voltageKey] !== undefined || rawTelemetry[powerKey] !== undefined) {
      const voltage = rawTelemetry[voltageKey] || 0;
      const current = rawTelemetry[currentKey] || 0;
      const power = rawTelemetry[powerKey] || 0;

      // Determine status based on power output
      let status: 'optimal' | 'shaded' | 'offline' | 'low' = 'offline';
      if (power >= 50) {
        if (voltage > 0 && current > 0) {
          const expectedPower = voltage * current;
          const actualEfficiency = expectedPower > 0 ? (power / expectedPower * 100) : 0;
          if (actualEfficiency > 85) {
            status = 'optimal';
          } else if (actualEfficiency > 60) {
            status = 'shaded';
          } else {
            status = 'low';
          }
        } else {
          status = 'low';
        }
      } else if (power > 0) {
        status = 'low';
      }

      // Calculate efficiency
      let efficiency_pct: number | undefined;
      if (voltage > 0 && current > 0) {
        const expectedPower = voltage * current;
        if (expectedPower > 0) {
          efficiency_pct = Math.round((power / expectedPower) * 100 * 10) / 10;
        }
      }

      channels.push({
        id: i,
        channel_id: i,
        name: `String ${i}`,
        power_w: Math.round(power * 100) / 100,
        voltage_v: Math.round(voltage * 100) / 100,
        current_a: Math.round(current * 100) / 100,
        status,
        panel_count: rawTelemetry[`pv${i}_panel_count`],
        efficiency_pct,
      });
    }
  }

  return channels;
}

/**
 * Extract extended metrics from raw telemetry
 */
function extractExtendedMetrics(rawTelemetry: any, deviceMetrics: DeviceMetrics | null): ExtendedInverterMetrics | null {
  if (!rawTelemetry && !deviceMetrics) return null;

  const raw = rawTelemetry || {};

  return {
    dc_voltage_v: raw.dc_voltage_v || raw.voltage_v || deviceMetrics?.voltage_v || 0,
    ac_voltage_v: raw.ac_voltage_v || raw.grid_voltage_v || 0,
    ac_frequency_hz: raw.frequency_hz || raw.grid_frequency_hz || deviceMetrics?.frequency_hz || 0,
    efficiency_pct: raw.efficiency_pct || raw.efficiency_percent || deviceMetrics?.efficiency_percent || 0,
    temperature_c: raw.temperature_c || raw.inverter_temp_c || deviceMetrics?.temperature_c || 0,
    battery_soc_pct: raw.battery_soc_pct || raw.battery_soc_percent || deviceMetrics?.state_of_charge,
    timestamp: raw.timestamp || deviceMetrics?.timestamp || new Date().toISOString(),
    online: true,
  };
}

export function useTelemetryData(options: UseTelemetryDataOptions): TelemetryDataState & {
  refresh: () => Promise<void>;
} {
  const {
    deviceId,
    serialNumber,
    pollingInterval = 5000,
    enableHistorical = true,
    enableMPPT = true,
  } = options;

  const [state, setState] = useState<TelemetryDataState>({
    metrics: null,
    mpptChannels: [],
    historicalData: [],
    isLoading: true,
    isPolling: false,
    error: null,
    lastUpdated: null,
    usingFallback: false,
  });

  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);

  /**
   * Fetch all telemetry data
   */
  const fetchTelemetryData = useCallback(async () => {
    if (!isMountedRef.current) return;

    setState(prev => ({ ...prev, isPolling: true, error: null }));

    try {
      // Fetch device metrics and power flow data
      const [deviceMetrics, powerFlowData, energyChartData] = await Promise.all([
        devicesService.getDeviceMetrics(deviceId),
        dashboardService.getPowerFlow().catch(() => null),
        enableHistorical
          ? dashboardService.getEnergyChart('day').catch(() => null)
          : Promise.resolve(null),
      ]);

      if (!isMountedRef.current) return;

      // Find current device in power flow data
      const currentDevicePower = powerFlowData?.devices?.find(
        d => d.serial_number === serialNumber
      );

      // Extract raw telemetry data (contains MPPT and extended metrics)
      const rawTelemetry = (currentDevicePower as any)?.raw || (currentDevicePower as any);

      // Extract MPPT channels from raw telemetry
      let mpptData: MPPTChannel[] = [];
      if (enableMPPT && rawTelemetry) {
        mpptData = extractMPPTChannels(rawTelemetry);
      }

      // Extract extended metrics from raw telemetry
      const extendedMetrics = extractExtendedMetrics(rawTelemetry, deviceMetrics);

      // Process historical data from API only
      let historicalPoints: HistoricalPowerPoint[] = [];
      if (enableHistorical && energyChartData?.data) {
        historicalPoints = energyChartData.data.map(point => ({
          timestamp: point.timestamp,
          solar_power_kw: point.pv_kwh,
          battery_power_kw: 0, // Will be added in backend later
          load_power_kw: point.load_kwh,
          grid_power_kw: point.grid_import_kwh - point.grid_export_kwh,
          efficiency_pct: point.efficiency_pct,
          temperature_c: point.temperature_c,
        }));
      }

      setState({
        metrics: extendedMetrics,
        mpptChannels: mpptData,
        historicalData: historicalPoints,
        isLoading: false,
        isPolling: false,
        error: null,
        lastUpdated: new Date(),
        usingFallback: false,
      });

    } catch (error) {
      console.error('[useTelemetryData] Error fetching telemetry:', error);

      if (!isMountedRef.current) return;

      // On error, show empty data with error message
      setState({
        metrics: null,
        mpptChannels: [],
        historicalData: [],
        isLoading: false,
        isPolling: false,
        error: error as Error,
        lastUpdated: null,
        usingFallback: false,
      });
    }
  }, [deviceId, serialNumber, enableHistorical, enableMPPT]);

  /**
   * Manual refresh
   */
  const refresh = useCallback(async () => {
    await fetchTelemetryData();
  }, [fetchTelemetryData]);

  /**
   * Setup polling
   */
  useEffect(() => {
    isMountedRef.current = true;

    // Initial fetch
    fetchTelemetryData();

    // Setup polling
    if (pollingInterval > 0) {
      pollingTimerRef.current = setInterval(fetchTelemetryData, pollingInterval);
    }

    return () => {
      isMountedRef.current = false;
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
      }
    };
  }, [fetchTelemetryData, pollingInterval]);

  return {
    ...state,
    refresh,
  };
}
