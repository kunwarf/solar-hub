/**
 * Dashboard Service
 *
 * Handles dashboard and telemetry data API calls.
 * Falls back to mock data when API is unavailable.
 */

import apiClient, { checkApiHealth } from '../client';
import { API_CONFIG, API_ENDPOINTS } from '../config';
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

// Mock dashboard data
const mockDashboardOverview: DashboardOverview = {
  organization_id: 'mock-org-1',
  total_sites: 2,
  total_devices: 6,
  devices_online: 5,
  devices_offline: 1,
  total_power_kw: 4.8,
  total_energy_today_kwh: 28.5,
  total_energy_month_kwh: 856.2,
  self_consumption_percent: 72,
  grid_export_kwh: 8.2,
  grid_import_kwh: 3.1,
  battery_soc_avg: 78,
  co2_avoided_kg: 13.5,
  savings_today_pkr: 712,
  savings_month_pkr: 21360,
  alerts_active: 2,
  alerts_warning: 1,
  alerts_critical: 0,
  last_updated: new Date().toISOString(),
};

// Generate realistic mock power data based on time of day
function generateMockPowerSnapshot(): PowerSnapshot {
  const hour = new Date().getHours();
  const isDaytime = hour >= 6 && hour <= 18;
  const isPeak = hour >= 11 && hour <= 15;

  let solarPower = 0;
  if (isDaytime) {
    // Bell curve for solar production
    const solarHours = hour - 6;
    const maxHours = 6; // Peak at noon
    solarPower = Math.max(0, 5.5 * Math.sin((Math.PI * solarHours) / 12) + Math.random() * 0.5);
    if (isPeak) solarPower *= 1.1;
  }

  const consumption = 1.2 + Math.random() * 2; // 1.2-3.2 kW base load
  const batteryPower = solarPower > consumption ? -(solarPower - consumption) * 0.3 : 0.5;
  const gridPower = consumption - solarPower - batteryPower;

  return {
    solar_power_kw: Math.round(solarPower * 100) / 100,
    battery_power_kw: Math.round(batteryPower * 100) / 100,
    grid_power_kw: Math.round(gridPower * 100) / 100,
    consumption_kw: Math.round(consumption * 100) / 100,
    battery_soc: Math.round(60 + Math.random() * 30),
    is_exporting: gridPower < 0,
    timestamp: new Date().toISOString(),
  };
}

// Generate mock chart data
function generateMockPowerChartData(hours: number = 24): PowerChartData {
  const now = new Date();
  const timestamps: string[] = [];
  const solarPower: number[] = [];
  const consumption: number[] = [];
  const gridPower: number[] = [];
  const batteryPower: number[] = [];
  const batterySoc: number[] = [];

  for (let i = hours; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60 * 60 * 1000);
    timestamps.push(time.toISOString());

    const hour = time.getHours();
    const isDaytime = hour >= 6 && hour <= 18;

    // Solar follows sun pattern
    let solar = 0;
    if (isDaytime) {
      solar = Math.max(0, 5.5 * Math.sin((Math.PI * (hour - 6)) / 12)) + (Math.random() - 0.5) * 0.5;
    }
    solarPower.push(Math.round(solar * 100) / 100);

    // Consumption varies throughout day
    const baseLoad = 1.2;
    const morningPeak = hour >= 7 && hour <= 9 ? 1.5 : 0;
    const eveningPeak = hour >= 18 && hour <= 22 ? 2 : 0;
    const cons = baseLoad + morningPeak + eveningPeak + Math.random() * 0.8;
    consumption.push(Math.round(cons * 100) / 100);

    // Battery behavior
    const battSoc = 50 + (solar > cons ? 20 : -10) + Math.random() * 10;
    batterySoc.push(Math.min(100, Math.max(0, Math.round(battSoc))));

    const batt = solar > cons ? -(solar - cons) * 0.3 : Math.min(0.5, cons - solar);
    batteryPower.push(Math.round(batt * 100) / 100);

    // Grid fills the gap
    const grid = cons - solar - batt;
    gridPower.push(Math.round(grid * 100) / 100);
  }

  return {
    timestamps,
    solar_power: solarPower,
    consumption,
    grid_power: gridPower,
    battery_power: batteryPower,
    battery_soc: batterySoc,
  };
}

function generateMockEnergyChartData(days: number = 7): EnergyChartData {
  const labels: string[] = [];
  const solar: number[] = [];
  const consumption: number[] = [];
  const gridImport: number[] = [];
  const gridExport: number[] = [];

  const now = new Date();

  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
    labels.push(date.toLocaleDateString('en-US', { weekday: 'short' }));

    // Vary by day with some randomness
    const baseSolar = 25 + Math.random() * 10;
    const baseConsumption = 20 + Math.random() * 8;

    solar.push(Math.round(baseSolar * 10) / 10);
    consumption.push(Math.round(baseConsumption * 10) / 10);
    gridImport.push(Math.round(Math.max(0, baseConsumption - baseSolar * 0.7) * 10) / 10);
    gridExport.push(Math.round(Math.max(0, baseSolar * 0.3 - 2) * 10) / 10);
  }

  return { labels, solar, consumption, grid_import: gridImport, grid_export: gridExport };
}

class DashboardService {
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
   * Get organization dashboard overview
   */
  async getOverview(): Promise<DashboardOverview> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<DashboardOverview>(
          API_ENDPOINTS.dashboards.overview
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch dashboard overview, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      // Update with current data
      return {
        ...mockDashboardOverview,
        ...generateMockPowerSnapshot(),
        last_updated: new Date().toISOString(),
      };
    }

    throw new Error('API unavailable');
  }

  /**
   * Get site-specific dashboard
   */
  async getSiteDashboard(siteId: string): Promise<SiteDashboard> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<SiteDashboard>(
          API_ENDPOINTS.dashboards.site(siteId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch site dashboard, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const power = generateMockPowerSnapshot();
      return {
        site: {
          id: siteId,
          organization_id: 'mock-org-1',
          name: 'Home Solar System',
          description: 'Main residential solar installation',
          status: 'active',
          address: { city: 'Lahore', country: 'Pakistan' },
          geo_location: { latitude: 31.5204, longitude: 74.3587 },
          timezone: 'Asia/Karachi',
          configuration: {
            system_capacity_kw: 10,
            panel_count: 20,
            panel_wattage: 500,
            inverter_capacity_kw: 10,
            battery_capacity_kwh: 13.5,
            grid_connection_type: 'hybrid',
            net_metering_enabled: true,
            disco_provider: 'lesco',
            tariff_category: 'residential_protected',
          },
          created_at: '2024-01-01T00:00:00Z',
          updated_at: new Date().toISOString(),
        },
        devices: [],
        current_power: power,
        energy_today: {
          solar_kwh: 28.5,
          consumption_kwh: 22.3,
          grid_import_kwh: 3.1,
          grid_export_kwh: 9.3,
          battery_charge_kwh: 8.2,
          battery_discharge_kwh: 5.1,
          self_consumption_percent: 72,
        },
        energy_month: {
          solar_kwh: 856.2,
          consumption_kwh: 720.5,
          grid_import_kwh: 85.3,
          grid_export_kwh: 221.0,
          battery_charge_kwh: 245.8,
          battery_discharge_kwh: 198.2,
          self_consumption_percent: 74,
        },
        environmental_impact: {
          co2_avoided_kg: 406.7,
          trees_equivalent: 18.5,
          coal_avoided_kg: 342.5,
        },
        alerts_summary: {
          total: 3,
          active: 2,
          acknowledged: 1,
          by_severity: { info: 1, warning: 1, critical: 0 },
        },
      };
    }

    throw new Error('API unavailable');
  }

  /**
   * Get real-time power snapshot
   */
  async getCurrentPower(siteId?: string): Promise<PowerSnapshot> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable && siteId) {
      try {
        const response = await apiClient.get<PowerSnapshot>(
          API_ENDPOINTS.dashboards.sitePower(siteId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch power data, using mock:', error);
      }
    }

    return generateMockPowerSnapshot();
  }

  /**
   * Get power chart data
   */
  async getPowerChartData(siteId: string, hours: number = 24): Promise<PowerChartData> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<PowerChartData>(
          API_ENDPOINTS.dashboards.sitePower(siteId),
          { params: { hours } }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch power chart data, using mock:', error);
      }
    }

    return generateMockPowerChartData(hours);
  }

  /**
   * Get energy chart data
   */
  async getEnergyChartData(siteId: string, days: number = 7): Promise<EnergyChartData> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<EnergyChartData>(
          API_ENDPOINTS.dashboards.siteEnergy(siteId),
          { params: { days } }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch energy chart data, using mock:', error);
      }
    }

    return generateMockEnergyChartData(days);
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
    try {
      const params: Record<string, string> = {};
      if (siteId) params.site_id = siteId;

      const response = await apiClient.get<PowerFlowData>(
        API_ENDPOINTS.dashboard.powerFlow,
        { params }
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch power flow, using mock:', error);
      const mock = generateMockPowerSnapshot();
      const pvTotal = mock.solar_power_kw * 1000;
      const pvMain = pvTotal * 0.7;
      const pvSecondary = pvTotal * 0.3;
      return {
        organization_id: 'mock-org',
        site_id: siteId || 'mock-site',
        site_name: 'My Home',
        timestamp: new Date().toISOString(),
        pv_power_w: pvTotal,
        grid_power_w: mock.grid_power_kw * 1000,
        load_power_w: mock.consumption_kw * 1000,
        battery_power_w: mock.battery_power_kw * 1000,
        battery_soc_pct: mock.battery_soc,
        is_charging: mock.battery_power_kw < 0,
        grid_connected: true,
        online: true,
        stale: false,
        devices_online: 4,
        devices_total: 4,
        devices: [
          {
            serial_number: 'SE10K-2024-001234',
            pv_power_w: pvMain,
            grid_power_w: mock.grid_power_kw * 1000,
            load_power_w: mock.consumption_kw * 700,
            battery_power_w: mock.battery_power_kw * 1000,
            battery_soc_pct: mock.battery_soc,
            is_charging: mock.battery_power_kw < 0,
            online: true,
          },
          {
            serial_number: 'HW5K-2024-003456',
            pv_power_w: pvSecondary,
            grid_power_w: 0,
            load_power_w: mock.consumption_kw * 300,
            battery_power_w: 0,
            battery_soc_pct: 0,
            is_charging: false,
            online: true,
          },
          {
            serial_number: 'PW2-2024-005678',
            pv_power_w: 0,
            grid_power_w: 0,
            load_power_w: 0,
            battery_power_w: mock.battery_power_kw * 1000,
            battery_soc_pct: mock.battery_soc,
            is_charging: mock.battery_power_kw < 0,
            online: true,
          },
          {
            serial_number: 'PM5560-2024-009012',
            pv_power_w: 0,
            grid_power_w: mock.grid_power_kw * 1000,
            load_power_w: mock.consumption_kw * 1000,
            battery_power_w: 0,
            battery_soc_pct: 0,
            is_charging: false,
            online: true,
          },
        ],
      };
    }
  }

  /**
   * Get statistics data for stats cards
   * Returns aggregated stats for all devices in the site
   */
  async getStats(siteId?: string): Promise<StatsData> {
    try {
      const params: Record<string, string> = {};
      if (siteId) params.site_id = siteId;

      const response = await apiClient.get<StatsData>(
        API_ENDPOINTS.dashboard.stats,
        { params }
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch stats, using mock:', error);
      return {
        organization_id: 'mock-org',
        site_id: siteId || 'mock-site',
        site_name: 'My Home',
        energy_today_kwh: 28.5,
        energy_month_kwh: 856.2,
        peak_power_kw: 5.2,
        co2_saved_kg: 13.5,
        online: true,
        devices_online: 4,
        devices_total: 4,
        devices: [
          {
            serial_number: 'SE10K-2024-001234',
            energy_today_kwh: 20.0,
            peak_power_kw: 5.2,
            online: true,
          },
          {
            serial_number: 'HW5K-2024-003456',
            energy_today_kwh: 8.5,
            peak_power_kw: 3.1,
            online: true,
          },
        ],
      };
    }
  }

  /**
   * Get battery status
   * Returns aggregated battery stats for all devices in the site
   */
  async getBatteryStatus(siteId?: string): Promise<BatteryStatusData> {
    try {
      const params: Record<string, string> = {};
      if (siteId) params.site_id = siteId;

      const response = await apiClient.get<BatteryStatusData>(
        API_ENDPOINTS.dashboard.battery,
        { params }
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch battery status, using mock:', error);
      return {
        organization_id: 'mock-org',
        site_id: siteId || 'mock-site',
        site_name: 'My Home',
        avg_soc_pct: 75,
        total_power_w: 800,
        is_charging: true,
        online: true,
        devices_online: 1,
        devices_total: 1,
        devices: [{
          serial_number: 'PW2-2024-005678',
          soc_pct: 75,
          power_w: 800,
          is_charging: true,
          online: true,
        }],
      };
    }
  }

  /**
   * Get device status
   * Returns status of all devices in the site
   */
  async getDeviceStatus(siteId?: string): Promise<DeviceStatusData> {
    try {
      const params: Record<string, string> = {};
      if (siteId) params.site_id = siteId;

      const response = await apiClient.get<DeviceStatusData>(
        API_ENDPOINTS.dashboard.deviceStatus,
        { params }
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch device status, using mock:', error);
      return {
        organization_id: 'mock-org',
        site_id: siteId || 'mock-site',
        site_name: 'My Home',
        devices_online: 4,
        devices_offline: 0,
        devices_total: 4,
        total_faults: 0,
        total_warnings: 1,
        grid_connected: true,
        devices: [
          { serial_number: 'SE10K-2024-001234', status: 'online', last_seen: Math.floor(Date.now() / 1000), working_mode: 'auto', faults: [], warnings: [], online: true },
          { serial_number: 'HW5K-2024-003456', status: 'online', last_seen: Math.floor(Date.now() / 1000), working_mode: 'auto', faults: [], warnings: ['High temperature'], online: true },
          { serial_number: 'PW2-2024-005678', status: 'online', last_seen: Math.floor(Date.now() / 1000), working_mode: 'auto', faults: [], warnings: [], online: true },
          { serial_number: 'PM5560-2024-009012', status: 'online', last_seen: Math.floor(Date.now() / 1000), working_mode: 'auto', faults: [], warnings: [], online: true },
        ],
      };
    }
  }

  /**
   * Get active alerts
   * Returns alerts from all devices in the site
   */
  async getAlerts(siteId?: string): Promise<AlertsData> {
    try {
      const params: Record<string, string> = {};
      if (siteId) params.site_id = siteId;

      const response = await apiClient.get<AlertsData>(
        API_ENDPOINTS.dashboard.alerts,
        { params }
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch alerts, using mock:', error);
      return {
        organization_id: 'mock-org',
        site_id: siteId || 'mock-site',
        site_name: 'My Home',
        active_alerts: [],
        total_count: 0,
        critical_count: 0,
      };
    }
  }

  /**
   * Get environmental impact data
   * Returns aggregated environmental impact for all devices in the site
   */
  async getEnvironmental(siteId?: string): Promise<EnvironmentalData> {
    try {
      const params: Record<string, string> = {};
      if (siteId) params.site_id = siteId;

      const response = await apiClient.get<EnvironmentalData>(
        API_ENDPOINTS.dashboard.environmental,
        { params }
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch environmental data, using mock:', error);
      return {
        organization_id: 'mock-org',
        site_id: siteId || 'mock-site',
        site_name: 'My Home',
        co2_avoided_kg: 13.5,
        trees_equivalent: 0.6,
        coal_avoided_kg: 11.4,
      };
    }
  }

  /**
   * Get billing summary
   * Returns aggregated billing for all devices in the site
   */
  async getBilling(siteId?: string): Promise<BillingData> {
    try {
      const params: Record<string, string> = {};
      if (siteId) params.site_id = siteId;

      const response = await apiClient.get<BillingData>(
        API_ENDPOINTS.dashboard.billing,
        { params }
      );
      return response.data;
    } catch (error) {
      console.warn('Failed to fetch billing data, using mock:', error);
      return {
        organization_id: 'mock-org',
        site_id: siteId || 'mock-site',
        site_name: 'My Home',
        estimated_savings_today: 712,
        estimated_savings_month: 21360,
        grid_import_cost: 93,
        grid_export_credit: 279,
      };
    }
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
    } catch (error) {
      console.warn('Failed to fetch all widgets, fetching individually:', error);
      // Fallback to individual fetches
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
