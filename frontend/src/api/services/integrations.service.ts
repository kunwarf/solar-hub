/**
 * Integrations Service
 *
 * Manages Home Assistant MQTT integration API calls.
 */

import apiClient from '../client';
import { API_ENDPOINTS } from '../config';

export interface MqttIntegrationCreateResponse {
  integration_id: string;
  ha_username: string;
  password: string;
  broker_host: string;
  broker_port: number;
  publish_interval_seconds: number;
  message: string;
}

export interface MqttIntegrationResponse {
  integration_id: string;
  ha_username: string;
  broker_host: string;
  broker_port: number;
  enabled: boolean;
  publish_interval_seconds: number;
}

export interface PasswordRotateResponse {
  ha_username: string;
  password: string;
  message: string;
}

export interface DeviceEnrollmentItem {
  device_id: string;
  serial_number: string;
  name: string;
  manufacturer?: string | null;
  model?: string | null;
  enrolled: boolean;
}

class IntegrationsService {
  /**
   * Create a new HA MQTT integration for the current user.
   * Returns credentials including plaintext password (shown once).
   */
  async createMqttIntegration(): Promise<MqttIntegrationCreateResponse> {
    const response = await apiClient.post<MqttIntegrationCreateResponse>(
      API_ENDPOINTS.integrations.mqtt.create
    );
    return response.data;
  }

  /**
   * Get current user's MQTT integration details (no password).
   */
  async getMqttIntegration(): Promise<MqttIntegrationResponse> {
    const response = await apiClient.get<MqttIntegrationResponse>(
      API_ENDPOINTS.integrations.mqtt.get
    );
    return response.data;
  }

  /**
   * Delete the current user's MQTT integration.
   */
  async deleteMqttIntegration(): Promise<void> {
    await apiClient.delete(API_ENDPOINTS.integrations.mqtt.delete);
  }

  /**
   * Regenerate the MQTT password.
   * Returns new plaintext password (shown once).
   */
  async rotateMqttPassword(): Promise<PasswordRotateResponse> {
    const response = await apiClient.post<PasswordRotateResponse>(
      API_ENDPOINTS.integrations.mqtt.rotatePassword
    );
    return response.data;
  }

  /**
   * List all user devices with enrollment status.
   */
  async listMqttDevices(): Promise<DeviceEnrollmentItem[]> {
    const response = await apiClient.get<DeviceEnrollmentItem[]>(
      API_ENDPOINTS.integrations.mqtt.devices
    );
    return response.data;
  }

  /**
   * Enroll or unenroll a device.
   */
  async setDeviceEnrollment(
    deviceId: string,
    enrolled: boolean
  ): Promise<DeviceEnrollmentItem> {
    const response = await apiClient.put<DeviceEnrollmentItem>(
      API_ENDPOINTS.integrations.mqtt.enrollDevice(deviceId),
      { enrolled }
    );
    return response.data;
  }
}

export const integrationsService = new IntegrationsService();
export default integrationsService;
