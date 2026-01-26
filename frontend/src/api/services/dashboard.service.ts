/**
 * Dashboard Service
 *
 * Handles dashboard and telemetry data API calls.
 */

import apiClient, { checkApiHealth } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  DashboardOverview,
  SiteDashboard,
  PowerChartData,
  EnergyChartData,
  PowerSnapshot,
} from '../types';

// New widget API response types (from Redis cache)
// Each response includes site context and per-device breakdown

// Per-device breakdown types
export interface DevicePowerData {
  serial_number: string;
  pv_power_w: number;
  grid_power_w: number;
  load_power_w: number;
  battery_power_w: number;
  battery_soc_pct: number;
  is_charging: boolean;
  online: boolean;
}

export interface DeviceStatsData {
  serial_number: string;
  energy_today_kwh: number;
  peak_power_kw: number;
  online: boolean;
}

export interface DeviceBatteryData {
  serial_number: string;
  soc_pct: number;
  power_w: number;
  is_charging: boolean;
  online: boolean;
}

export interface DeviceStatusItem {
  serial_number: string;
  status: string;
  last_seen: number | null;
  working_mode: string | null;
  faults: string[];
  warnings: string[];
  online: boolean;
}

// Site-level response types with aggregated data
export interface PowerFlowData {
  // Context
  organization_id: string;
  site_id: string;
  site_name: string;
  timestamp: string | null;

  // Aggregated power (sum of all devices)
  pv_power_w: number;
  grid_power_w: number;
  load_power_w: number;
  battery_power_w: number;
  battery_soc_pct: number;  // Average across devices
  is_charging: boolean;
  grid_connected: boolean;

  // Status
  online: boolean;
  stale: boolean;
  devices_online: number;
  devices_total: number;

  // Per-device breakdown
  devices: DevicePowerData[];
}

export interface StatsData {
  organization_id: string;
  site_id: string;
  site_name: string;

  // Aggregated stats (sum of all devices)
  energy_today_kwh: number;
  energy_month_kwh: number;
  peak_power_kw: number;
  co2_saved_kg: number;
  online: boolean;
  devices_online: number;
  devices_total: number;

  // Per-device breakdown
  devices: DeviceStatsData[];
}

export interface BatteryStatusData {
  organization_id: string;
  site_id: string;
  site_name: string;

  // Aggregated battery stats
  avg_soc_pct: number;
  total_power_w: number;
  is_charging: boolean;
  online: boolean;
  devices_online: number;
  devices_total: number;

  // Per-device breakdown
  devices: DeviceBatteryData[];
}

export interface DeviceStatusData {
  organization_id: string;
  site_id: string;
  site_name: string;

  // Site-level status summary
  devices_online: number;
  devices_offline: number;
  devices_total: number;
  total_faults: number;
  total_warnings: number;
  grid_connected: boolean;

  // Per-device breakdown
  devices: DeviceStatusItem[];
}

export interface AlertItem {
  id: string;
  serial_number: string;
  severity: string;
  message: string;
  timestamp: string;
}

export interface AlertsData {
  organization_id: string;
  site_id: string;
  site_name: string;

  // Site-level alerts (aggregated from all devices)
  active_alerts: AlertItem[];
  total_count: number;
  critical_count: number;
}

export interface EnvironmentalData {
  organization_id: string;
  site_id: string;
  site_name: string;

  // Site-level environmental impact (sum of all devices)
  co2_avoided_kg: number;
  trees_equivalent: number;
  coal_avoided_kg: number;
}

export interface BillingData {
  organization_id: string;
  site_id: string;
  site_name: string;

  // Site-level billing (sum of all devices)
  estimated_savings_today: number;
  estimated_savings_month: number;
  grid_import_cost: number;
  grid_export_credit: number;
}

export interface AllWidgetsData {
  power_flow: PowerFlowData;
  stats: StatsData;
  battery: BatteryStatusData;
  device_status: DeviceStatusData;
  alerts: AlertsData;
  environmental: EnvironmentalData;
  billing: BillingData;
}

class DashboardService {
  /**
   * Get organization dashboard overview
   */
  async getOverview(): Promise<DashboardOverview> {
    const response = await apiClient.get<DashboardOverview>(
      API_ENDPOINTS.dashboards.overview
    );
    return response.data;
  }

  /**
   * Get site-specific dashboard
   */
  async getSiteDashboard(siteId: string): Promise<SiteDashboard> {
    const response = await apiClient.get<SiteDashboard>(
      API_ENDPOINTS.dashboards.site(siteId)
    );
    return response.data;
  }

  /**
   * Get real-time power snapshot
   */
  async getCurrentPower(siteId: string): Promise<PowerSnapshot> {
    const response = await apiClient.get<PowerSnapshot>(
      API_ENDPOINTS.dashboards.sitePower(siteId)
    );
    return response.data;
  }

  /**
   * Get power chart data
   */
  async getPowerChartData(siteId: string, hours: number = 24): Promise<PowerChartData> {
    const response = await apiClient.get<PowerChartData>(
      API_ENDPOINTS.dashboards.sitePower(siteId),
      { params: { hours } }
    );
    return response.data;
  }

  /**
   * Get energy chart data
   */
  async getEnergyChartData(siteId: string, days: number = 7): Promise<EnergyChartData> {
    const response = await apiClient.get<EnergyChartData>(
      API_ENDPOINTS.dashboards.siteEnergy(siteId),
      { params: { days } }
    );
    return response.data;
  }

  /**
   * Check API connectivity status
   */
  async checkConnectivity(): Promise<{ connected: boolean; latency?: number }> {
    const start = Date.now();
    const connected = await checkApiHealth();
    const latency = Date.now() - start;
    return { connected, latency: connected ? latency : undefined };
  }

  // =========================================================================
  // New Widget APIs (read from Redis cache via System A)
  // Site-level aggregation with per-device breakdown
  // =========================================================================

  /**
   * Get real-time power flow data from Redis cache
   * Returns aggregated data for all devices in the site
   */
  async getPowerFlow(siteId?: string): Promise<PowerFlowData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<PowerFlowData>(
      API_ENDPOINTS.dashboard.powerFlow,
      { params }
    );
    return response.data;
  }

  /**
   * Get statistics data for stats cards
   * Returns aggregated stats for all devices in the site
   */
  async getStats(siteId?: string): Promise<StatsData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<StatsData>(
      API_ENDPOINTS.dashboard.stats,
      { params }
    );
    return response.data;
  }

  /**
   * Get battery status
   * Returns aggregated battery stats for all devices in the site
   */
  async getBatteryStatus(siteId?: string): Promise<BatteryStatusData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<BatteryStatusData>(
      API_ENDPOINTS.dashboard.battery,
      { params }
    );
    return response.data;
  }

  /**
   * Get device status
   * Returns status of all devices in the site
   */
  async getDeviceStatus(siteId?: string): Promise<DeviceStatusData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<DeviceStatusData>(
      API_ENDPOINTS.dashboard.deviceStatus,
      { params }
    );
    return response.data;
  }

  /**
   * Get active alerts
   * Returns alerts from all devices in the site
   */
  async getAlerts(siteId?: string): Promise<AlertsData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<AlertsData>(
      API_ENDPOINTS.dashboard.alerts,
      { params }
    );
    return response.data;
  }

  /**
   * Get environmental impact data
   * Returns aggregated environmental impact for all devices in the site
   */
  async getEnvironmental(siteId?: string): Promise<EnvironmentalData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<EnvironmentalData>(
      API_ENDPOINTS.dashboard.environmental,
      { params }
    );
    return response.data;
  }

  /**
   * Get billing summary
   * Returns aggregated billing for all devices in the site
   */
  async getBilling(siteId?: string): Promise<BillingData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<BillingData>(
      API_ENDPOINTS.dashboard.billing,
      { params }
    );
    return response.data;
  }

  /**
   * Get all widget data in a single request (for initial load)
   * Returns aggregated data for all devices in the site with per-device breakdown
   */
  async getAllWidgets(siteId?: string): Promise<AllWidgetsData> {
    try {
      const params: Record<string, string> = {};
      if (siteId) params.site_id = siteId;

      const response = await apiClient.get<AllWidgetsData>(
        API_ENDPOINTS.dashboard.all,
        { params }
      );
      return response.data;
    } catch {
      // Fallback to individual fetches if bulk endpoint fails
      const [powerFlow, stats, battery, deviceStatus, alerts, environmental, billing] =
        await Promise.all([
          this.getPowerFlow(siteId),
          this.getStats(siteId),
          this.getBatteryStatus(siteId),
          this.getDeviceStatus(siteId),
          this.getAlerts(siteId),
          this.getEnvironmental(siteId),
          this.getBilling(siteId),
        ]);

      return {
        power_flow: powerFlow,
        stats,
        battery,
        device_status: deviceStatus,
        alerts,
        environmental,
        billing,
      };
    }
  }
}

export const dashboardService = new DashboardService();
export default dashboardService;
