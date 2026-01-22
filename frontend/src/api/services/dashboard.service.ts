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
}

export const dashboardService = new DashboardService();
export default dashboardService;
