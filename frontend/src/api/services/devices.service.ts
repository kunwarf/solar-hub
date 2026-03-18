/**
 * Devices Service
 *
 * Handles all device-related API calls including CRUD operations and commands.
 */

import apiClient from '../client';
import axios from 'axios';
import { API_ENDPOINTS, SYSTEM_B_CONFIG, SYSTEM_B_ENDPOINTS } from '../config';
import type {
  Device,
  DeviceType,
  DeviceStatus,
  DeviceMetrics,
  DeviceCommand,
  PaginatedResponse,
  PaginationParams,
  OrphanDevice,
  ClaimDeviceRequest,
  ClaimDeviceResponse,
  DeviceLookupResult,
} from '../types';

interface DeviceFilters {
  device_type?: DeviceType;
  status?: DeviceStatus;
  site_id?: string;
  search?: string;
}

class DevicesService {
  /**
   * List devices with pagination and filters
   */
  async listDevices(
    filters?: DeviceFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<Device>> {
    const response = await apiClient.get<PaginatedResponse<Device>>(
      API_ENDPOINTS.devices.list,
      { params: { ...filters, ...pagination } }
    );
    return response.data;
  }

  /**
   * Get single device by ID
   */
  async getDevice(deviceId: string): Promise<Device> {
    const response = await apiClient.get<Device>(
      API_ENDPOINTS.devices.byId(deviceId)
    );
    return response.data;
  }

  /**
   * Create new device
   */
  async createDevice(
    data: Partial<Device>
  ): Promise<{ success: boolean; device?: Device; error?: string }> {
    try {
      const response = await apiClient.post<Device>(
        API_ENDPOINTS.devices.create,
        data
      );
      return { success: true, device: response.data };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to create device' };
    }
  }

  /**
   * Update device
   */
  async updateDevice(
    deviceId: string,
    data: Partial<Device>
  ): Promise<{ success: boolean; device?: Device; error?: string }> {
    try {
      const response = await apiClient.put<Device>(
        API_ENDPOINTS.devices.byId(deviceId),
        data
      );
      return { success: true, device: response.data };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to update device' };
    }
  }

  /**
   * Delete device
   */
  async deleteDevice(
    deviceId: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      await apiClient.delete(API_ENDPOINTS.devices.byId(deviceId));
      return { success: true };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to delete device' };
    }
  }

  /**
   * Send command to device
   */
  async sendCommand(
    deviceId: string,
    command: DeviceCommand
  ): Promise<{ success: boolean; result?: unknown; error?: string }> {
    try {
      const response = await apiClient.post(
        API_ENDPOINTS.devices.command(deviceId),
        command
      );
      return { success: true, result: response.data };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to send command' };
    }
  }

  /**
   * Update device status
   */
  async updateStatus(
    deviceId: string,
    status: DeviceStatus
  ): Promise<{ success: boolean; error?: string }> {
    try {
      await apiClient.put(API_ENDPOINTS.devices.status(deviceId), { status });
      return { success: true };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to update status' };
    }
  }

  /**
   * Get device metrics/snapshot
   */
  async getDeviceMetrics(deviceId: string): Promise<DeviceMetrics | null> {
    try {
      const response = await apiClient.get<DeviceMetrics>(
        `/devices/${deviceId}/metrics`
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch device metrics:', error);
      return null;
    }
  }

  /**
   * Get MPPT channel data for inverter
   */
  async getMPPTChannels(deviceId: string): Promise<any> {
    try {
      const response = await apiClient.get(`/devices/${deviceId}/mppt-channels`);
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch MPPT channels:', error);
      throw error;
    }
  }

  /**
   * Get extended device telemetry (detailed metrics)
   */
  async getExtendedTelemetry(deviceId: string): Promise<any> {
    try {
      const response = await apiClient.get(`/devices/${deviceId}/telemetry/extended`);
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch extended telemetry:', error);
      throw error;
    }
  }

  /**
   * Get real-time telemetry snapshot for a device
   */
  async getRealtimeTelemetry(deviceId: string): Promise<any> {
    try {
      const response = await apiClient.get(`/devices/${deviceId}/telemetry/realtime`);
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch realtime telemetry:', error);
      throw error;
    }
  }

  /**
   * Get battery bank detail (Pylontech/Pytes) — per-unit and per-cell data
   */
  async getBatteryBank(deviceId: string): Promise<any> {
    try {
      const response = await apiClient.get(API_ENDPOINTS.devices.batteryBank(deviceId));
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch battery bank data:', error);
      return null;
    }
  }

  // ============================================================================
  // Device Claiming Methods (via System A auth endpoints)
  // ============================================================================

  /**
   * Look up a device by serial number
   * First checks available devices from System A, which proxies to System B
   */
  async getDeviceBySerial(serialNumber: string): Promise<DeviceLookupResult> {
    try {
      // Get all available (orphan) devices via System A
      const devices = await this.getOrphanDevices();
      const device = devices.find(
        (d) => d.serial_number.toLowerCase() === serialNumber.toLowerCase()
      );

      if (device) {
        return {
          found: true,
          device: device,
        };
      }

      // Device not in orphan list - try direct lookup via System B as fallback
      try {
        const response = await axios.get<OrphanDevice>(
          `${SYSTEM_B_CONFIG.baseUrl}${SYSTEM_B_ENDPOINTS.devices.bySerial(serialNumber)}`
        );
        return {
          found: true,
          device: response.data,
        };
      } catch {
        return {
          found: false,
          error: 'Device not found. Please ensure your device is powered on and connected.',
        };
      }
    } catch (error: unknown) {
      const axiosError = error as { response?: { status?: number; data?: { detail?: string } } };
      return {
        found: false,
        error: axiosError.response?.data?.detail || 'Failed to look up device',
      };
    }
  }

  /**
   * Claim an orphan device for a user via System A auth endpoint
   * Uses serial number instead of device ID
   */
  async claimDevice(
    _deviceId: string,
    request: ClaimDeviceRequest
  ): Promise<ClaimDeviceResponse> {
    try {
      const response = await axios.put<ClaimDeviceResponse>(
        `${SYSTEM_B_CONFIG.baseUrl}${SYSTEM_B_ENDPOINTS.devices.claim(_deviceId)}`,
        request
      );
      return response.data;
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      return {
        success: false,
        message: axiosError.response?.data?.detail || 'Failed to claim device',
      };
    }
  }

  /**
   * Claim device by serial number via System A (preferred method)
   */
  async claimDeviceBySerial(
    serialNumber: string,
    siteId: string
  ): Promise<ClaimDeviceResponse> {
    try {
      const response = await apiClient.post<OrphanDevice>(
        API_ENDPOINTS.auth.claimDevice(serialNumber),
        null,
        { params: { site_id: siteId } }
      );
      return {
        success: true,
        message: 'Device claimed successfully',
        device: response.data,
      };
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      return {
        success: false,
        message: axiosError.response?.data?.detail || 'Failed to claim device',
      };
    }
  }

  /**
   * Unclaim a device via System A — removes it from the site and releases it in System B.
   * The device becomes an orphan and can be claimed again.
   */
  async unclaimDevice(deviceId: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post<{ success: boolean; message: string }>(
      API_ENDPOINTS.devices.unclaim(deviceId)
    );
    return response.data;
  }

  /**
   * Release a claimed device (make it orphan again)
   */
  async releaseDevice(deviceId: string): Promise<ClaimDeviceResponse> {
    try {
      const response = await axios.put<ClaimDeviceResponse>(
        `${SYSTEM_B_CONFIG.baseUrl}${SYSTEM_B_ENDPOINTS.devices.release(deviceId)}`
      );
      return response.data;
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      return {
        success: false,
        message: axiosError.response?.data?.detail || 'Failed to release device',
      };
    }
  }

  /**
   * Get all orphan devices via System A auth endpoint
   */
  async getOrphanDevices(): Promise<OrphanDevice[]> {
    try {
      const response = await apiClient.get<OrphanDevice[]>(
        API_ENDPOINTS.auth.availableDevices
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch orphan devices:', error);
      return [];
    }
  }

  /**
   * Validate a serial number format
   */
  async validateSerial(serialNumber: string): Promise<{ is_valid: boolean; error?: string; device_type?: string }> {
    try {
      const response = await axios.post<{
        is_valid: boolean;
        error?: string;
        device_type?: string;
      }>(
        `${SYSTEM_B_CONFIG.baseUrl}${SYSTEM_B_ENDPOINTS.devices.validateSerial}`,
        { serial_number: serialNumber }
      );
      return response.data;
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      return {
        is_valid: false,
        error: axiosError.response?.data?.detail || 'Validation failed',
      };
    }
  }
}

export const devicesService = new DevicesService();
export default devicesService;
