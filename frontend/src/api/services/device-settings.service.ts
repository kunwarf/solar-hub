/**
 * Device Settings API Service
 *
 * Provides methods for managing device-specific configuration settings.
 * Settings vary by device type (inverter, battery, meter) and manufacturer.
 */

import apiClient from '../client';

// ============== Types ==============

export interface DeviceSettings {
  id: string;
  device_id: string;
  device_type: string;
  manufacturer?: string;
  model?: string;
  settings: Record<string, any>;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface DeviceSettingsUpdate {
  settings: Record<string, any>;
}

export interface DeviceSettingsResetResponse {
  message: string;
  settings: Record<string, any>;
}

// ============== API Service ==============

class DeviceSettingsService {
  /**
   * Get device settings
   * Returns custom settings if they exist, otherwise returns defaults
   */
  async getDeviceSettings(deviceId: string): Promise<DeviceSettings> {
    const response = await apiClient.get<DeviceSettings>(
      `/devices/${deviceId}/settings`
    );
    return response.data;
  }

  /**
   * Update device settings
   * Creates new settings record if none exists
   */
  async updateDeviceSettings(
    deviceId: string,
    settings: Record<string, any>
  ): Promise<DeviceSettings> {
    const response = await apiClient.put<DeviceSettings>(
      `/devices/${deviceId}/settings`,
      { settings }
    );
    return response.data;
  }

  /**
   * Reset device settings to defaults
   * Deletes custom settings and returns default configuration
   */
  async resetDeviceSettings(deviceId: string): Promise<DeviceSettingsResetResponse> {
    const response = await apiClient.post<DeviceSettingsResetResponse>(
      `/devices/${deviceId}/settings/reset`
    );
    return response.data;
  }

  /**
   * Delete device settings
   * Device will revert to using defaults
   */
  async deleteDeviceSettings(deviceId: string): Promise<void> {
    await apiClient.delete(`/devices/${deviceId}/settings`);
  }
}

export const deviceSettingsService = new DeviceSettingsService();
