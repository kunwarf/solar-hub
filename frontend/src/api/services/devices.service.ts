/**
 * Devices Service
 *
 * Handles all device-related API calls including CRUD operations and commands.
 * Falls back to mock data when API is unavailable.
 */

import apiClient, { checkApiHealth } from '../client';
import axios from 'axios';
import { API_CONFIG, API_ENDPOINTS, SYSTEM_B_CONFIG, SYSTEM_B_ENDPOINTS } from '../config';
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

// Mock devices data
const mockDevices: Device[] = [
  {
    id: 'dev-inv-001',
    site_id: 'site-001',
    organization_id: 'org-001',
    device_type: 'inverter' as DeviceType,
    name: 'Main Inverter',
    manufacturer: 'SolarEdge',
    model: 'SE10K',
    serial_number: 'SE10K-2024-001234',
    firmware_version: '4.12.25',
    status: 'online' as DeviceStatus,
    protocol: 'modbus_tcp',
    connection_config: { host: '192.168.1.100', port: 502, slave_id: 1 },
    latest_metrics: {
      power_output_w: 4800,
      energy_today_kwh: 28.5,
      energy_total_kwh: 12450,
      voltage_v: 240,
      current_a: 20,
      frequency_hz: 50,
      temperature_c: 45,
      efficiency_percent: 97.5,
      timestamp: new Date().toISOString(),
    },
    last_seen_at: new Date().toISOString(),
    metadata: { installation_date: '2024-01-15' },
    tags: ['primary', 'roof-mounted'],
    created_at: '2024-01-15T10:00:00Z',
    updated_at: new Date().toISOString(),
  },
  {
    id: 'dev-bat-001',
    site_id: 'site-001',
    organization_id: 'org-001',
    device_type: 'battery' as DeviceType,
    name: 'Home Battery',
    manufacturer: 'Tesla',
    model: 'Powerwall 2',
    serial_number: 'PW2-2024-005678',
    firmware_version: '23.44.0',
    status: 'online' as DeviceStatus,
    protocol: 'modbus_tcp',
    connection_config: { host: '192.168.1.101', port: 502, slave_id: 1 },
    latest_metrics: {
      power_output_w: -1200,
      state_of_charge: 78,
      temperature_c: 28,
      timestamp: new Date().toISOString(),
    },
    last_seen_at: new Date().toISOString(),
    metadata: { capacity_kwh: 13.5 },
    tags: ['backup', 'indoor'],
    created_at: '2024-01-15T10:00:00Z',
    updated_at: new Date().toISOString(),
  },
  {
    id: 'dev-mtr-001',
    site_id: 'site-001',
    organization_id: 'org-001',
    device_type: 'meter' as DeviceType,
    name: 'Grid Meter',
    manufacturer: 'Schneider',
    model: 'PM5560',
    serial_number: 'PM5560-2024-009012',
    firmware_version: '2.5.1',
    status: 'online' as DeviceStatus,
    protocol: 'modbus_tcp',
    connection_config: { host: '192.168.1.102', port: 502, slave_id: 1 },
    latest_metrics: {
      power_import_w: 500,
      power_export_w: 0,
      voltage_v: 230,
      current_a: 2.17,
      frequency_hz: 50,
      timestamp: new Date().toISOString(),
    },
    last_seen_at: new Date().toISOString(),
    metadata: { meter_type: 'bidirectional' },
    tags: ['grid', 'net-metering'],
    created_at: '2024-01-15T10:00:00Z',
    updated_at: new Date().toISOString(),
  },
  {
    id: 'dev-inv-002',
    site_id: 'site-001',
    organization_id: 'org-001',
    device_type: 'inverter' as DeviceType,
    name: 'Garage Inverter',
    manufacturer: 'Huawei',
    model: 'SUN2000-5KTL',
    serial_number: 'HW5K-2024-003456',
    firmware_version: '3.0.45',
    status: 'warning' as DeviceStatus,
    protocol: 'modbus_tcp',
    connection_config: { host: '192.168.1.103', port: 502, slave_id: 1 },
    latest_metrics: {
      power_output_w: 2100,
      energy_today_kwh: 12.3,
      energy_total_kwh: 5680,
      voltage_v: 238,
      current_a: 8.8,
      frequency_hz: 50,
      temperature_c: 52,
      efficiency_percent: 95.2,
      timestamp: new Date().toISOString(),
    },
    last_seen_at: new Date(Date.now() - 300000).toISOString(),
    last_error_message: 'High temperature warning',
    metadata: { installation_date: '2024-03-20' },
    tags: ['secondary', 'garage'],
    created_at: '2024-03-20T10:00:00Z',
    updated_at: new Date().toISOString(),
  },
];

interface DeviceFilters {
  device_type?: DeviceType;
  status?: DeviceStatus;
  site_id?: string;
  search?: string;
}

class DevicesService {
  private apiAvailable: boolean | null = null;

  private async isApiAvailable(): Promise<boolean> {
    if (this.apiAvailable !== null) {
      return this.apiAvailable;
    }
    this.apiAvailable = await checkApiHealth();
    setTimeout(() => {
      this.apiAvailable = null;
    }, 30000);
    return this.apiAvailable;
  }

  /**
   * List devices with pagination and filters
   */
  async listDevices(
    filters?: DeviceFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<Device>> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<PaginatedResponse<Device>>(
          API_ENDPOINTS.devices.list,
          { params: { ...filters, ...pagination } }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch devices, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      let filtered = [...mockDevices];

      if (filters?.device_type) {
        filtered = filtered.filter((d) => d.device_type === filters.device_type);
      }
      if (filters?.status) {
        filtered = filtered.filter((d) => d.status === filters.status);
      }
      if (filters?.site_id) {
        filtered = filtered.filter((d) => d.site_id === filters.site_id);
      }
      if (filters?.search) {
        const search = filters.search.toLowerCase();
        filtered = filtered.filter(
          (d) =>
            d.name.toLowerCase().includes(search) ||
            d.serial_number.toLowerCase().includes(search)
        );
      }

      const page = pagination?.page || 1;
      const pageSize = pagination?.page_size || 20;
      const start = (page - 1) * pageSize;
      const items = filtered.slice(start, start + pageSize);

      return {
        items,
        total: filtered.length,
        page,
        page_size: pageSize,
        pages: Math.ceil(filtered.length / pageSize),
      };
    }

    throw new Error('API unavailable');
  }

  /**
   * Get single device by ID
   */
  async getDevice(deviceId: string): Promise<Device> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<Device>(
          API_ENDPOINTS.devices.byId(deviceId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch device, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const device = mockDevices.find((d) => d.id === deviceId);
      if (device) {
        return device;
      }
    }

    throw new Error('Device not found');
  }

  /**
   * Create new device
   */
  async createDevice(
    data: Partial<Device>
  ): Promise<{ success: boolean; device?: Device; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const newDevice: Device = {
        id: `dev-${Date.now()}`,
        site_id: data.site_id || 'site-001',
        organization_id: data.organization_id || 'org-001',
        device_type: data.device_type || ('inverter' as DeviceType),
        name: data.name || 'New Device',
        manufacturer: data.manufacturer || 'Unknown',
        model: data.model || 'Unknown',
        serial_number: data.serial_number || `SN-${Date.now()}`,
        firmware_version: data.firmware_version,
        status: 'offline' as DeviceStatus,
        protocol: data.protocol || 'modbus_tcp',
        connection_config: data.connection_config || {},
        metadata: data.metadata || {},
        tags: data.tags || [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      mockDevices.push(newDevice);
      return { success: true, device: newDevice };
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Update device
   */
  async updateDevice(
    deviceId: string,
    data: Partial<Device>
  ): Promise<{ success: boolean; device?: Device; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const index = mockDevices.findIndex((d) => d.id === deviceId);
      if (index >= 0) {
        mockDevices[index] = {
          ...mockDevices[index],
          ...data,
          updated_at: new Date().toISOString(),
        };
        return { success: true, device: mockDevices[index] };
      }
      return { success: false, error: 'Device not found' };
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Delete device
   */
  async deleteDevice(
    deviceId: string
  ): Promise<{ success: boolean; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.delete(API_ENDPOINTS.devices.byId(deviceId));
        return { success: true };
      } catch (error: unknown) {
        const apiError = error as { message?: string };
        return { success: false, error: apiError.message || 'Failed to delete device' };
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const index = mockDevices.findIndex((d) => d.id === deviceId);
      if (index >= 0) {
        mockDevices.splice(index, 1);
        return { success: true };
      }
      return { success: false, error: 'Device not found' };
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Send command to device
   */
  async sendCommand(
    deviceId: string,
    command: DeviceCommand
  ): Promise<{ success: boolean; result?: unknown; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      return { success: true, result: { message: 'Command sent (mock)' } };
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Update device status
   */
  async updateStatus(
    deviceId: string,
    status: DeviceStatus
  ): Promise<{ success: boolean; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.put(API_ENDPOINTS.devices.status(deviceId), { status });
        return { success: true };
      } catch (error: unknown) {
        const apiError = error as { message?: string };
        return { success: false, error: apiError.message || 'Failed to update status' };
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const device = mockDevices.find((d) => d.id === deviceId);
      if (device) {
        device.status = status;
        return { success: true };
      }
      return { success: false, error: 'Device not found' };
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Get device metrics/snapshot
   */
  async getDeviceMetrics(deviceId: string): Promise<DeviceMetrics | null> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<DeviceMetrics>(
          API_ENDPOINTS.devices.snapshot(deviceId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch device metrics:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const device = mockDevices.find((d) => d.id === deviceId);
      return device?.latest_metrics || null;
    }

    return null;
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
      // We need to get the serial number - the ClaimDevice page passes it
      // But the request has site_id, we need to call with serial
      // The ClaimDevice page should pass serial_number

      // For now, try the System B endpoint as fallback
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
