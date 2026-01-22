/**
 * useDevices Hook
 *
 * Provides device data from the API with loading and error states.
 * Falls back to mock data when API is unavailable.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { devicesService } from '@/api';
import type { Device, DeviceType, DeviceStatus, PaginationParams } from '@/api/types';

interface DeviceFilters {
  device_type?: DeviceType;
  status?: DeviceStatus;
  site_id?: string;
  search?: string;
}

interface UseDevicesOptions {
  filters?: DeviceFilters;
  pagination?: PaginationParams;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseDevicesReturn {
  devices: Device[];
  total: number;
  page: number;
  pages: number;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setFilters: (filters: DeviceFilters) => void;
  setPage: (page: number) => void;
}

export function useDevices(options: UseDevicesOptions = {}): UseDevicesReturn {
  const {
    filters: initialFilters = {},
    pagination: initialPagination = { page: 1, page_size: 20 },
    autoRefresh = false,
    refreshInterval = 30000,
  } = options;

  const [devices, setDevices] = useState<Device[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPageState] = useState(initialPagination.page || 1);
  const [pages, setPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<DeviceFilters>(initialFilters);

  const fetchDevices = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await devicesService.listDevices(filters, {
        page,
        page_size: initialPagination.page_size || 20,
      });

      setDevices(response.items);
      setTotal(response.total);
      setPages(response.pages);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch devices';
      setError(message);
      console.error('useDevices error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [filters, page, initialPagination.page_size]);

  // Initial fetch
  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchDevices, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchDevices]);

  const setFilters = useCallback((newFilters: DeviceFilters) => {
    setFiltersState(newFilters);
    setPageState(1); // Reset to first page when filters change
  }, []);

  const setPage = useCallback((newPage: number) => {
    setPageState(newPage);
  }, []);

  return {
    devices,
    total,
    page,
    pages,
    isLoading,
    error,
    refresh: fetchDevices,
    setFilters,
    setPage,
  };
}

/**
 * Hook to get a single device by ID
 */
export function useDevice(deviceId: string | null) {
  const [device, setDevice] = useState<Device | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDevice = useCallback(async () => {
    if (!deviceId) {
      setDevice(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await devicesService.getDevice(deviceId);
      setDevice(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch device';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [deviceId]);

  useEffect(() => {
    fetchDevice();
  }, [fetchDevice]);

  return { device, isLoading, error, refresh: fetchDevice };
}

/**
 * Hook for device commands
 */
export function useDeviceCommand() {
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeCommand = useCallback(
    async (deviceId: string, commandType: string, params: Record<string, unknown> = {}) => {
      setIsExecuting(true);
      setError(null);

      try {
        const result = await devicesService.sendCommand(deviceId, {
          command_type: commandType,
          params,
        });

        if (!result.success) {
          throw new Error(result.error || 'Command failed');
        }

        return result.result;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Command failed';
        setError(message);
        throw err;
      } finally {
        setIsExecuting(false);
      }
    },
    []
  );

  return { executeCommand, isExecuting, error };
}

/**
 * Convert API Device format to the format expected by UI components
 */
export function formatDeviceForUI(device: Device) {
  const metrics: Array<{ label: string; value: string; unit: string }> = [];

  if (device.latest_metrics) {
    const m = device.latest_metrics;

    if (device.device_type === 'inverter') {
      if (m.power_output_w !== undefined) {
        metrics.push({ label: 'Power Output', value: (m.power_output_w / 1000).toFixed(1), unit: 'kW' });
      }
      if (m.efficiency_percent !== undefined) {
        metrics.push({ label: 'Efficiency', value: m.efficiency_percent.toFixed(1), unit: '%' });
      }
      if (m.voltage_v !== undefined) {
        metrics.push({ label: 'Voltage', value: m.voltage_v.toString(), unit: 'V' });
      }
      if (m.temperature_c !== undefined) {
        metrics.push({ label: 'Temperature', value: m.temperature_c.toString(), unit: '°C' });
      }
    } else if (device.device_type === 'battery') {
      if (m.state_of_charge !== undefined) {
        metrics.push({ label: 'State of Charge', value: m.state_of_charge.toString(), unit: '%' });
      }
      if (m.power_output_w !== undefined) {
        const power = m.power_output_w / 1000;
        metrics.push({
          label: power >= 0 ? 'Charge Rate' : 'Discharge Rate',
          value: Math.abs(power).toFixed(1),
          unit: 'kW',
        });
      }
      if (m.temperature_c !== undefined) {
        metrics.push({ label: 'Temperature', value: m.temperature_c.toString(), unit: '°C' });
      }
    } else if (device.device_type === 'meter') {
      if (m.power_import_w !== undefined || m.power_export_w !== undefined) {
        const importW = m.power_import_w || 0;
        const exportW = m.power_export_w || 0;
        const net = importW - exportW;
        metrics.push({
          label: net >= 0 ? 'Importing' : 'Exporting',
          value: (Math.abs(net) / 1000).toFixed(1),
          unit: 'kW',
        });
      }
      if (m.frequency_hz !== undefined) {
        metrics.push({ label: 'Frequency', value: m.frequency_hz.toFixed(2), unit: 'Hz' });
      }
    }
  }

  // Determine primary value based on device type
  let value = '0';
  let unit = '';

  if (device.device_type === 'inverter' && device.latest_metrics?.power_output_w !== undefined) {
    value = (device.latest_metrics.power_output_w / 1000).toFixed(1);
    unit = 'kW';
  } else if (device.device_type === 'battery' && device.latest_metrics?.state_of_charge !== undefined) {
    value = device.latest_metrics.state_of_charge.toString();
    unit = '%';
  } else if (device.device_type === 'meter') {
    const m = device.latest_metrics;
    if (m) {
      const importW = m.power_import_w || 0;
      const exportW = m.power_export_w || 0;
      value = (Math.abs(importW - exportW) / 1000).toFixed(1);
      unit = 'kW';
    }
  }

  return {
    id: device.id,
    name: device.name,
    type: device.device_type,
    status: device.status,
    model: device.model,
    serialNumber: device.serial_number,
    value,
    unit,
    metrics,
  };
}

/**
 * Hook that provides devices in the UI-compatible format
 */
export function useDevicesForUI(options: UseDevicesOptions = {}) {
  const { devices, ...rest } = useDevices(options);

  const formattedDevices = useMemo(() => devices.map(formatDeviceForUI), [devices]);

  return {
    devices: formattedDevices,
    ...rest,
  };
}
