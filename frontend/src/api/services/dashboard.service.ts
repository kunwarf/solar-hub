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
  raw?: Record<string, any>;  // Raw telemetry for MPPT and extended metrics
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

  // Energy flows (from today's aggregate data)
  load_energy_today_kwh: number;
  grid_import_today_kwh: number;
  grid_export_today_kwh: number;

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
  import_rate_pkr: number;
  export_rate_pkr: number;
}

export interface EnergyChartPoint {
  timestamp: string;
  pv_kwh: number;
  load_kwh: number;
  grid_import_kwh: number;
  grid_export_kwh: number;
  battery_charge_kwh: number;
  battery_discharge_kwh: number;
  efficiency_pct?: number;
  self_sufficiency_pct?: number;
  temperature_c?: number;
}

export interface EnergyChartResponse {
  organization_id: string;
  site_id: string;
  site_name: string;
  period: string;
  data: EnergyChartPoint[];
}

export interface ComparisonPoint {
  label: string;
  current: number;
  previous: number;
}

export interface ComparisonData {
  organization_id: string;
  site_id: string;
  site_name: string;
  period: string;
  data: ComparisonPoint[];
  current_total: number;
  previous_total: number;
  percent_change: number;
}

export interface PeakDemandHourly {
  hour: string;
  demand_kw: number;
}

export interface PeakDemandData {
  organization_id: string;
  site_id: string;
  site_name: string;
  peak_hour: string;
  peak_demand_kw: number;
  average_demand_kw: number;
  current_demand_kw: number;
  hourly_profile: PeakDemandHourly[];
}

export interface WeatherData {
  organization_id: string;
  site_id: string;
  site_name: string;
  temperature: number;
  condition: string;
  humidity: number;
  wind_speed: number;
  solar_forecast: number;
  sunrise: string;
  sunset: string;
}

export interface LoadSheddingWindow {
  start: string;
  end: string;
  duration?: number;
  date?: string;
}

export interface LoadSheddingData {
  organization_id: string;
  site_id: string;
  site_name: string;
  stage: number;
  active: boolean;
  current_window: LoadSheddingWindow | null;
  next_window: LoadSheddingWindow | null;
  battery_reserve: number;
  estimated_coverage: number;
}

// Outages page types
export interface OutageRecord {
  id: string;
  date: string;
  start_time: string;
  end_time: string;
  duration: number;
  type: 'scheduled' | 'unscheduled' | 'unknown';
  battery_used: number;
  backup_status: 'full' | 'partial' | 'none';
}

export interface OutageAlert {
  id: string;
  type: 'grid_down' | 'grid_restored' | 'low_battery' | 'battery_critical' | 'prediction';
  message: string;
  timestamp: string;
  read: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
}

export interface DailyOutageSummary {
  date: string;
  outage_count: number;
  total_duration: number;
}

export interface MonthlyOutageStats {
  total_outages: number;
  total_duration: number;
  avg_duration: number;
  longest_outage: number;
  total_backup_time: number;
  total_battery_used: number;
  hours_avoided: number;
}

export interface GridStatusData {
  online: boolean;
  last_change: string;
  current_outage: OutageRecord | null;
  battery_level: number;
  estimated_backup_hours: number;
  current_load: number;
}

export interface OutagesData {
  organization_id: string;
  site_id: string;
  site_name: string;
  grid_status: GridStatusData;
  today_outages: OutageRecord[];
  week_summaries: DailyOutageSummary[];
  monthly_stats: MonthlyOutageStats;
  outage_history: OutageRecord[];
  alerts: OutageAlert[];
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

// AI Insights Types
export interface InsightItem {
  id: string;
  type: 'positive' | 'neutral' | 'warning' | 'tip';
  category: 'production' | 'savings' | 'consumption' | 'anomaly' | 'recommendation';
  title: string;
  message: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface WeeklyDigest {
  total_generated_kwh: number;
  total_saved_pkr: number;
  self_sufficiency_pct: number;
  prev_week_generated_kwh: number;
  prev_week_saved_pkr: number;
  prev_week_self_sufficiency_pct: number;
  generated_change_pct: number;
  saved_change_pct: number;
  self_sufficiency_change_pct: number;
  tip_of_the_week: string;
}

export interface InsightsData {
  site_id: string;
  site_name: string;
  daily_insights: InsightItem[];
  anomaly_alerts: InsightItem[];
  weekly_digest: WeeklyDigest | null;
  monthly_analysis: string | null;
  yearly_analysis: string | null;
  generated_at: string;
  source: string;
}

// Dashboard Preferences Types
export interface WidgetConfigAPI {
  id: string;
  visible: boolean;
  size: 'small' | 'medium' | 'large';
  settings?: Record<string, any>;
}

export interface PresetWidgetConfigAPI {
  id: string;
  visible: boolean;
  size: 'small' | 'medium' | 'large';
}

export interface DashboardPreferences {
  user_id: string;
  layout_preset: string;
  grid_layout: 'list' | '2x2' | '3x3';
  widget_layout: WidgetConfigAPI[];
  created_at: string;
  updated_at: string;
}

export interface DashboardPreferencesUpdate {
  layout_preset?: string;
  grid_layout?: 'list' | '2x2' | '3x3';
  widget_layout?: WidgetConfigAPI[];
}

export interface CustomPreset {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  widget_config: PresetWidgetConfigAPI[];
  created_at: string;
  updated_at: string;
}

export interface CustomPresetListResponse {
  presets: CustomPreset[];
  total: number;
}

export interface CustomPresetCreate {
  name: string;
  description?: string;
  widget_config: PresetWidgetConfigAPI[];
}

export interface CustomPresetUpdate {
  name?: string;
  description?: string;
  widget_config?: PresetWidgetConfigAPI[];
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
   * Get energy chart data with historical summaries
   * Returns hourly/daily data points depending on period
   */
  async getEnergyChart(period: string = 'day', siteId?: string): Promise<EnergyChartResponse> {
    const params: Record<string, string> = { period };
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<EnergyChartResponse>(
      API_ENDPOINTS.dashboard.energyChart,
      { params }
    );
    return response.data;
  }

  /**
   * Get period-over-period comparison data
   * Returns current vs previous period energy generation
   */
  async getComparison(period: string = 'week', siteId?: string): Promise<ComparisonData> {
    const params: Record<string, string> = { period };
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<ComparisonData>(
      API_ENDPOINTS.dashboard.comparison,
      { params }
    );
    return response.data;
  }

  /**
   * Get peak demand analysis
   * Returns today's peak demand with hourly profile
   */
  async getPeakDemand(siteId?: string): Promise<PeakDemandData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<PeakDemandData>(
      API_ENDPOINTS.dashboard.peakDemand,
      { params }
    );
    return response.data;
  }

  /**
   * Get weather data derived from site telemetry
   */
  async getWeather(siteId?: string): Promise<WeatherData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<WeatherData>(
      API_ENDPOINTS.dashboard.weather,
      { params }
    );
    return response.data;
  }

  /**
   * Get load shedding / grid status
   */
  async getLoadShedding(siteId?: string): Promise<LoadSheddingData> {
    const params: Record<string, string> = {};
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<LoadSheddingData>(
      API_ENDPOINTS.dashboard.loadShedding,
      { params }
    );
    return response.data;
  }

  /**
   * Get outages page data with history and statistics
   */
  async getOutages(days: number = 30, siteId?: string): Promise<OutagesData> {
    const params: Record<string, string | number> = { days };
    if (siteId) params.site_id = siteId;

    const response = await apiClient.get<OutagesData>(
      API_ENDPOINTS.dashboard.outages,
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

  // =========================================================================
  // AI Insights
  // =========================================================================

  /**
   * Get AI insights for the site.
   * Returns daily insights, anomaly alerts, and weekly digest from real telemetry.
   */
  async getInsights(siteId?: string, importRatePkr?: number): Promise<InsightsData> {
    const params: Record<string, string | number> = {};
    if (siteId) params.site_id = siteId;
    if (importRatePkr !== undefined) params.import_rate_pkr = importRatePkr;

    const response = await apiClient.get<InsightsData>('/insights', { params });
    return response.data;
  }

  /**
   * Submit thumbs-up or thumbs-down feedback for an insight.
   */
  async submitInsightFeedback(insightId: string, positive: boolean): Promise<void> {
    await apiClient.post(`/insights/${insightId}/feedback`, {
      insight_id: insightId,
      positive,
    });
  }

  // =========================================================================
  // AI Chat
  // =========================================================================

  /**
   * Send a free-form question to the AI chat backend.
   * Returns a plain-text reply based on real telemetry data.
   * Claude (claude-haiku) is used when AI_API_KEY is set on the server.
   */
  async sendChatMessage(
    message: string,
    siteId?: string,
    importRatePkr?: number,
  ): Promise<{ reply: string }> {
    const body: Record<string, string | number> = { message };
    if (siteId) body.site_id = siteId;
    if (importRatePkr !== undefined) body.import_rate_pkr = importRatePkr;

    const response = await apiClient.post<{ reply: string }>('/chat', body);
    return response.data;
  }

  // =========================================================================
  // Dashboard Preferences & Custom Presets
  // =========================================================================

  /**
   * Get current user's dashboard preferences
   */
  async getPreferences(): Promise<DashboardPreferences> {
    const response = await apiClient.get<DashboardPreferences>(
      '/users/me/dashboard/preferences'
    );
    return response.data;
  }

  /**
   * Update current user's dashboard preferences
   */
  async updatePreferences(data: DashboardPreferencesUpdate): Promise<DashboardPreferences> {
    const response = await apiClient.put<DashboardPreferences>(
      '/users/me/dashboard/preferences',
      data
    );
    return response.data;
  }

  /**
   * List current user's custom presets
   */
  async listPresets(params?: { limit?: number; offset?: number }): Promise<CustomPresetListResponse> {
    const response = await apiClient.get<CustomPresetListResponse>(
      '/users/me/dashboard/presets',
      { params }
    );
    return response.data;
  }

  /**
   * Create a new custom preset
   */
  async createPreset(data: CustomPresetCreate): Promise<CustomPreset> {
    const response = await apiClient.post<CustomPreset>(
      '/users/me/dashboard/presets',
      data
    );
    return response.data;
  }

  /**
   * Get a specific custom preset
   */
  async getPreset(presetId: string): Promise<CustomPreset> {
    const response = await apiClient.get<CustomPreset>(
      `/users/me/dashboard/presets/${presetId}`
    );
    return response.data;
  }

  /**
   * Update a custom preset
   */
  async updatePreset(presetId: string, data: CustomPresetUpdate): Promise<CustomPreset> {
    const response = await apiClient.put<CustomPreset>(
      `/users/me/dashboard/presets/${presetId}`,
      data
    );
    return response.data;
  }

  /**
   * Delete a custom preset
   */
  async deletePreset(presetId: string): Promise<{ message: string }> {
    const response = await apiClient.delete<{ message: string }>(
      `/users/me/dashboard/presets/${presetId}`
    );
    return response.data;
  }
}

export const dashboardService = new DashboardService();
export default dashboardService;
