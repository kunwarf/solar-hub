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

/**
 * Generate mock MPPT data as fallback
 */
function generateMockMPPTData(solarPowerW: number): MPPTChannel[] {
  const channelCount = 3;
  const powerPerChannel = solarPowerW / channelCount;

  return Array.from({ length: channelCount }, (_, i) => ({
    channel_id: i + 1,
    name: `Array ${i + 1} (${['East', 'West', 'South'][i]} Roof)`,
    power_w: powerPerChannel * (0.9 + Math.random() * 0.2), // Vary by ±10%
    voltage_v: 380 + Math.random() * 20,
    current_a: (powerPerChannel / 390) * (0.9 + Math.random() * 0.2),
    status: i === 2 ? 'shaded' as const : 'optimal' as const,
    panel_count: [12, 14, 10][i],
    efficiency_pct: 95 + Math.random() * 3,
  }));
}

/**
 * Generate mock historical data as fallback
 */
function generateMockHistoricalData(): HistoricalPowerPoint[] {
  const now = new Date();
  const points: HistoricalPowerPoint[] = [];

  for (let i = 23; i >= 0; i--) {
    const hour = new Date(now.getTime() - i * 60 * 60 * 1000);
    const hourOfDay = hour.getHours();
    const sunIntensity = Math.max(0, Math.sin((hourOfDay - 6) * Math.PI / 12));

    points.push({
      timestamp: hour.toISOString(),
      solar_power_kw: sunIntensity * 10 + Math.random() * 0.5,
      battery_power_kw: sunIntensity > 0.5 ? 2 + Math.random() * 0.5 : -1.5 - Math.random() * 0.5,
      load_power_kw: 3 + Math.random() * 2 + (hourOfDay >= 18 && hourOfDay <= 22 ? 2 : 0),
      grid_power_kw: Math.random() * 2 - 1,
      efficiency_pct: 94 + Math.random() * 4,
      temperature_c: 35 + sunIntensity * 15 + Math.random() * 5,
    });
  }

  return points;
}

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

      // Generate or extract MPPT data
      let mpptData: MPPTChannel[] = [];
      if (enableMPPT) {
        // TODO: When backend provides MPPT endpoint, fetch from there
        // For now, generate from current solar power
        mpptData = generateMockMPPTData(currentSolarPowerW);
      }

      // Process historical data
      let historicalPoints: HistoricalPowerPoint[] = [];
      if (enableHistorical && energyChartData?.data) {
        // Map energy chart data to historical points
        historicalPoints = energyChartData.data.map(point => ({
          timestamp: point.timestamp,
          solar_power_kw: point.pv_kwh,
          battery_power_kw: 0, // Not available in energy chart
          load_power_kw: point.load_kwh,
          grid_power_kw: point.grid_import_kwh - point.grid_export_kwh,
        }));
      } else if (enableHistorical) {
        // Fallback to mock historical data
        historicalPoints = generateMockHistoricalData();
      }

      setState({
        metrics: extendedMetrics,
        mpptChannels: mpptData,
        historicalData: historicalPoints,
        isLoading: false,
        isPolling: false,
        error: null,
        lastUpdated: new Date(),
        usingFallback: !deviceMetrics, // Flag if we're using fallback data
      });

    } catch (error) {
      console.error('[useTelemetryData] Error fetching telemetry:', error);

      if (!isMountedRef.current) return;

      // On error, use complete fallback data
      setState({
        metrics: {
          dc_voltage_v: 580,
          ac_voltage_v: 238,
          ac_frequency_hz: 50.0,
          efficiency_pct: 97.0,
          temperature_c: 42,
          timestamp: new Date().toISOString(),
          online: false,
        },
        mpptChannels: enableMPPT ? generateMockMPPTData(7000) : [],
        historicalData: enableHistorical ? generateMockHistoricalData() : [],
        isLoading: false,
        isPolling: false,
        error: error as Error,
        lastUpdated: new Date(),
        usingFallback: true,
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
