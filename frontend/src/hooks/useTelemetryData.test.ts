/**
 * Unit Tests for useTelemetryData Hook
 */

import { renderHook, waitFor } from '@testing-library/react';
import { useTelemetryData } from './useTelemetryData';
import { devicesService, dashboardService } from '@/api';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// Mock API services
vi.mock('@/api', () => ({
  devicesService: {
    getDeviceMetrics: vi.fn(),
  },
  dashboardService: {
    getPowerFlow: vi.fn(),
    getEnergyChart: vi.fn(),
  },
}));

describe('useTelemetryData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should initialize with loading state', () => {
    const { result } = renderHook(() =>
      useTelemetryData({
        deviceId: 'test-device-1',
        serialNumber: 'SN12345',
      })
    );

    expect(result.current.isLoading).toBe(true);
    expect(result.current.metrics).toBeNull();
    expect(result.current.mpptChannels).toEqual([]);
    expect(result.current.historicalData).toEqual([]);
  });

  it('should fetch and populate telemetry data successfully', async () => {
    const mockMetrics = {
      voltage_v: 580,
      frequency_hz: 50.0,
      efficiency_percent: 97.5,
      temperature_c: 42,
      timestamp: '2024-01-01T12:00:00Z',
    };

    const mockPowerFlow = {
      devices: [
        {
          serial_number: 'SN12345',
          pv_power_w: 7500,
          battery_power_w: 2000,
          load_power_w: 5000,
          grid_power_w: 500,
          battery_soc_pct: 80,
          is_charging: false,
          online: true,
        },
      ],
    };

    vi.mocked(devicesService.getDeviceMetrics).mockResolvedValue(mockMetrics);
    vi.mocked(dashboardService.getPowerFlow).mockResolvedValue(mockPowerFlow as any);
    vi.mocked(dashboardService.getEnergyChart).mockResolvedValue({ data: [] } as any);

    const { result } = renderHook(() =>
      useTelemetryData({
        deviceId: 'test-device-1',
        serialNumber: 'SN12345',
        pollingInterval: 0, // Disable polling for test
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.metrics).toBeDefined();
    expect(result.current.metrics?.dc_voltage_v).toBe(580);
    expect(result.current.metrics?.efficiency_pct).toBe(97.5);
    expect(result.current.usingFallback).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should use fallback data when API fails', async () => {
    vi.mocked(devicesService.getDeviceMetrics).mockRejectedValue(new Error('API Error'));
    vi.mocked(dashboardService.getPowerFlow).mockRejectedValue(new Error('API Error'));
    vi.mocked(dashboardService.getEnergyChart).mockRejectedValue(new Error('API Error'));

    const { result } = renderHook(() =>
      useTelemetryData({
        deviceId: 'test-device-1',
        serialNumber: 'SN12345',
        pollingInterval: 0,
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.usingFallback).toBe(true);
    expect(result.current.error).toBeDefined();
    expect(result.current.metrics).toBeDefined(); // Fallback metrics
    expect(result.current.mpptChannels.length).toBeGreaterThan(0); // Fallback MPPT data
  });

  it('should generate MPPT data when enabled', async () => {
    const mockMetrics = {
      timestamp: '2024-01-01T12:00:00Z',
    };

    vi.mocked(devicesService.getDeviceMetrics).mockResolvedValue(mockMetrics as any);
    vi.mocked(dashboardService.getPowerFlow).mockResolvedValue({
      devices: [{ serial_number: 'SN12345', pv_power_w: 9000 }],
    } as any);
    vi.mocked(dashboardService.getEnergyChart).mockResolvedValue({ data: [] } as any);

    const { result } = renderHook(() =>
      useTelemetryData({
        deviceId: 'test-device-1',
        serialNumber: 'SN12345',
        pollingInterval: 0,
        enableMPPT: true,
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.mpptChannels.length).toBeGreaterThan(0);
    expect(result.current.mpptChannels[0]).toHaveProperty('channel_id');
    expect(result.current.mpptChannels[0]).toHaveProperty('power_w');
    expect(result.current.mpptChannels[0]).toHaveProperty('voltage_v');
  });

  it('should refresh data manually', async () => {
    const mockMetrics = { timestamp: '2024-01-01T12:00:00Z' };

    vi.mocked(devicesService.getDeviceMetrics).mockResolvedValue(mockMetrics as any);
    vi.mocked(dashboardService.getPowerFlow).mockResolvedValue({ devices: [] } as any);
    vi.mocked(dashboardService.getEnergyChart).mockResolvedValue({ data: [] } as any);

    const { result } = renderHook(() =>
      useTelemetryData({
        deviceId: 'test-device-1',
        serialNumber: 'SN12345',
        pollingInterval: 0,
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Clear mocks and set new values
    vi.clearAllMocks();
    vi.mocked(devicesService.getDeviceMetrics).mockResolvedValue({
      ...mockMetrics,
      temperature_c: 50,
    } as any);

    await result.current.refresh();

    await waitFor(() => {
      expect(devicesService.getDeviceMetrics).toHaveBeenCalled();
    });
  });

  it('should cleanup polling on unmount', () => {
    const clearIntervalSpy = vi.spyOn(global, 'clearInterval');

    const { unmount } = renderHook(() =>
      useTelemetryData({
        deviceId: 'test-device-1',
        serialNumber: 'SN12345',
        pollingInterval: 5000,
      })
    );

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
