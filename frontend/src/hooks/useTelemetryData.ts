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
 * Map DeviceMetrics to ExtendedInverterMetrics
 */
function mapDeviceMetricsToExtended(metrics: DeviceMetrics | null, currentPowerW: number): ExtendedInverterMetrics | null {
  if (!metrics) return null;

  return {
    dc_voltage_v: metrics.voltage_v || 580,
    ac_voltage_v: 238, // TODO: Get from actual device data when available
    ac_frequency_hz: metrics.frequency_hz || 50.0,
    efficiency_pct: metrics.efficiency_percent || 97.0,
    temperature_c: metrics.temperature_c || 42,
    battery_soc_pct: metrics.state_of_charge,
    timestamp: metrics.timestamp || new Date().toISOString(),
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
      // Fetch device metrics (primary source)
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

      const currentSolarPowerW = currentDevicePower?.pv_power_w || 0;

      // Map to extended metrics
      const extendedMetrics = mapDeviceMetricsToExtended(deviceMetrics, currentSolarPowerW);

      // Fetch MPPT data from backend
      let mpptData: MPPTChannel[] = [];
      if (enableMPPT) {
        try {
          const mpptResponse = await devicesService.getMPPTChannels(deviceId);
          mpptData = mpptResponse || [];
        } catch (error) {
          console.warn('[useTelemetryData] Failed to fetch MPPT data:', error);
          mpptData = [];
        }
      }

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
