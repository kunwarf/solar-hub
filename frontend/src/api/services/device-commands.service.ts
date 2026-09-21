/**
 * Device Commands API Service
 *
 * Provides methods for sending commands to physical devices and querying their current settings.
 */

import apiClient from '../client';

// ============== Types ==============

export interface QuerySettingsRequest {
  setting_keys?: string[];
}

export interface QuerySettingsResponse {
  command_id: string;
  status: string;
  settings?: Record<string, any>;
  message?: string;
}

export interface UpdateSettingsRequest {
  settings: Record<string, any>;
  apply_immediately?: boolean;
}

export interface UpdateSettingsResponse {
  command_id: string;
  status: string;
  message: string;
}

export interface CommandStatusResponse {
  command_id: string;
  status: string; // pending, sent, acknowledged, completed, failed, timeout
  progress?: number; // 0-100
  result?: Record<string, any>;
  error?: string;
  created_at: string;
  updated_at?: string;
}

// ============== Schema Types ==============

export interface SettingsSchemaField {
  key: string;
  label: string;
  type: "number" | "enum" | "bool";
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  scale?: number;
  options?: Record<string, string>;
  description?: string;
  writable?: boolean;
  destructive?: boolean;
}

export interface SettingsSchemaGroup {
  id: string;
  label: string;
  sign_note?: string;
  fields: SettingsSchemaField[];
}

export interface SettingsSchema {
  version: string;
  family: "powdrive" | "senergy" | "voltronic" | string;
  groups: SettingsSchemaGroup[];
}

// ============== API Service ==============

class DeviceCommandsService {
  /**
   * Fetch the settings schema for a given inverter protocol.
   * The schema defines each writable field's label, type, units, min/max, and enum options.
   */
  async getSettingsSchema(protocol: string): Promise<SettingsSchema> {
    const response = await apiClient.get<SettingsSchema>(
      `/devices/settings-schema/${encodeURIComponent(protocol)}`
    );
    return response.data;
  }

  /**
   * Query current settings from physical device
   */
  async querySettings(
    deviceId: string,
    settingKeys?: string[]
  ): Promise<QuerySettingsResponse> {
    const response = await apiClient.post<QuerySettingsResponse>(
      `/devices/${deviceId}/commands/query-settings`,
      { setting_keys: settingKeys }
    );
    return response.data;
  }

  /**
   * Update settings on physical device
   */
  async updateSettings(
    deviceId: string,
    settings: Record<string, any>,
    applyImmediately: boolean = true
  ): Promise<UpdateSettingsResponse> {
    const response = await apiClient.post<UpdateSettingsResponse>(
      `/devices/${deviceId}/commands/update-settings`,
      {
        settings,
        apply_immediately: applyImmediately,
      }
    );
    return response.data;
  }

  /**
   * Get command execution status
   */
  async getCommandStatus(
    deviceId: string,
    commandId: string
  ): Promise<CommandStatusResponse> {
    const response = await apiClient.get<CommandStatusResponse>(
      `/devices/${deviceId}/commands/${commandId}/status`
    );
    return response.data;
  }

  /**
   * Poll command status until completion or timeout
   */
  async waitForCommand(
    deviceId: string,
    commandId: string,
    timeoutMs: number = 30000,
    pollIntervalMs: number = 1000
  ): Promise<CommandStatusResponse> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const status = await this.getCommandStatus(deviceId, commandId);

      if (['completed', 'failed', 'timeout'].includes(status.status)) {
        return status;
      }

      // Wait before polling again
      await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
    }

    throw new Error('Command timed out');
  }

  /**
   * List recent commands for device
   */
  async listCommands(
    deviceId: string,
    limit: number = 10
  ): Promise<CommandStatusResponse[]> {
    const response = await apiClient.get<CommandStatusResponse[]>(
      `/devices/${deviceId}/commands`,
      { params: { limit } }
    );
    return response.data;
  }

  /**
   * Reboot the ESP32 datalogger itself (NOT the connected inverter).
   *
   * Delivery path: System A creates a datalogger-scope command in System B's
   * queue; the ESP32 firmware polls GET /commands/pending/{id}?scope=datalogger
   * every ~30s and executes machine.reset() locally.  Expect the device to go
   * offline briefly after this returns success, then reconnect.
   *
   * The datalogger acks and reports success BEFORE resetting, so the returned
   * status transitions to 'completed' at reboot-arm time (~2s before actual
   * reset).  Watching device offline/online telemetry is the real confirmation.
   *
   * siteId/deviceSerial args kept for signature parity with other command
   * methods, but System A looks them up server-side from device_id — the args
   * are unused here.
   */
  async rebootDatalogger(
    deviceId: string,
    _siteId?: string,
    _deviceSerial?: string
  ): Promise<CommandStatusResponse> {
    // System A proxies to System B and handles auth / device lookup.
    const createResp = await apiClient.post<{ command_id: string; status: string }>(
      `/devices/${deviceId}/commands/reboot-datalogger`,
      {}
    );

    // Poll until the datalogger acks + reports.  Poll interval 5s vs firmware
    // poll cadence 30s means most polls will see 'pending' until the firmware
    // wakes.  Total timeout 90s = 3 firmware cycles, enough to survive one
    // missed poll.
    return this.waitForCommand(deviceId, createResp.data.command_id, 90000, 5000);
  }
}

export const deviceCommandsService = new DeviceCommandsService();
