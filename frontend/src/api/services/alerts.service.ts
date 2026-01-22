/**
 * Alerts Service
 *
 * Handles all alert-related API calls including fetching, acknowledging,
 * and resolving alerts. Falls back to mock data when API is unavailable.
 */

import apiClient, { checkApiHealth } from '../client';
import { API_CONFIG, API_ENDPOINTS } from '../config';
import type {
  Alert as ApiAlert,
  AlertRule,
  AlertSeverity,
  AlertStatus,
  AlertsSummary,
  PaginatedResponse,
  PaginationParams,
} from '../types';

// UI Alert interface (used by components)
export interface UIAlert {
  id: string;
  timestamp: string;
  title: string;
  message: string;
  severity: 'critical' | 'warning' | 'info' | 'resolved';
  category: 'load-shedding' | 'device' | 'performance' | 'billing' | 'system';
  device?: string;
  deviceId?: string;
  siteId?: string;
  acknowledged: boolean;
}

// Alert filters for API
export interface AlertFilters {
  severity?: AlertSeverity;
  status?: AlertStatus;
  site_id?: string;
  device_id?: string;
  start_date?: string;
  end_date?: string;
}

// Mock alerts data
const mockAlerts: ApiAlert[] = [
  {
    id: 'alert-001',
    rule_id: 'rule-001',
    organization_id: 'org-001',
    site_id: 'site-001',
    device_id: 'device-001',
    severity: 'warning' as AlertSeverity,
    status: 'active' as AlertStatus,
    title: 'Load Shedding Stage 4 Announced',
    message: 'Your next slot is 16:00-18:30. Battery backup activated.',
    metric_name: 'grid_status',
    metric_value: 0,
    threshold: 1,
    triggered_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 mins ago
  },
  {
    id: 'alert-002',
    rule_id: 'rule-002',
    organization_id: 'org-001',
    site_id: 'site-001',
    device_id: 'device-002',
    severity: 'warning' as AlertSeverity,
    status: 'active' as AlertStatus,
    title: 'Battery Temperature High',
    message: 'Battery Pack A temperature is 38°C, above the recommended 35°C threshold.',
    metric_name: 'temperature_c',
    metric_value: 38,
    threshold: 35,
    triggered_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    device: {
      id: 'device-002',
      site_id: 'site-001',
      organization_id: 'org-001',
      device_type: 'battery' as const,
      name: 'Battery Pack A',
      manufacturer: 'Pylontech',
      model: 'US3000C',
      serial_number: 'BAT-2024-002',
      status: 'online' as const,
      protocol: 'modbus_tcp',
      connection_config: {},
      metadata: {},
      tags: [],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-15T14:28:00Z',
    },
  },
  {
    id: 'alert-003',
    rule_id: 'rule-003',
    organization_id: 'org-001',
    site_id: 'site-001',
    device_id: 'device-003',
    severity: 'critical' as AlertSeverity,
    status: 'active' as AlertStatus,
    title: 'Inverter Communication Lost',
    message: 'Unable to communicate with Inverter 2 for the past 5 minutes.',
    metric_name: 'connection_status',
    metric_value: 0,
    threshold: 1,
    triggered_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    device: {
      id: 'device-003',
      site_id: 'site-001',
      organization_id: 'org-001',
      device_type: 'inverter' as const,
      name: 'Inverter 2',
      manufacturer: 'SolarMax',
      model: 'SMX-5000',
      serial_number: 'INV-2024-003',
      status: 'offline' as const,
      protocol: 'modbus_tcp',
      connection_config: {},
      metadata: {},
      tags: [],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-15T13:45:00Z',
    },
  },
  {
    id: 'alert-004',
    rule_id: 'rule-004',
    organization_id: 'org-001',
    site_id: 'site-001',
    severity: 'info' as AlertSeverity,
    status: 'acknowledged' as AlertStatus,
    title: 'Grid Export Limit Reached',
    message: 'Daily grid export limit of 50 kWh reached. Excess production being stored.',
    metric_name: 'energy_export_kwh',
    metric_value: 50,
    threshold: 50,
    triggered_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    acknowledged_by: 'user-001',
    acknowledged_at: new Date(Date.now() - 3.5 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'alert-005',
    rule_id: 'rule-005',
    organization_id: 'org-001',
    site_id: 'site-001',
    severity: 'warning' as AlertSeverity,
    status: 'acknowledged' as AlertStatus,
    title: 'Solar Production Below Expected',
    message: 'Solar production is 25% below forecast. Possible cloud cover or panel issue.',
    metric_name: 'production_percent',
    metric_value: 75,
    threshold: 100,
    triggered_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    acknowledged_by: 'user-001',
    acknowledged_at: new Date(Date.now() - 5.5 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'alert-006',
    rule_id: 'rule-001',
    organization_id: 'org-001',
    site_id: 'site-001',
    severity: 'info' as AlertSeverity,
    status: 'resolved' as AlertStatus,
    title: 'Load Shedding Ended',
    message: 'Load shedding window has ended. Grid power restored.',
    metric_name: 'grid_status',
    metric_value: 1,
    threshold: 1,
    triggered_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    resolved_by: 'system',
    resolved_at: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(),
  },
];

// Mock alert rules
const mockAlertRules: AlertRule[] = [
  {
    id: 'rule-001',
    organization_id: 'org-001',
    name: 'Load Shedding Detection',
    description: 'Alert when grid power is lost due to load shedding',
    condition: {
      metric: 'grid_status',
      operator: 'eq',
      threshold: 0,
      duration_seconds: 30,
    },
    severity: 'warning' as AlertSeverity,
    notification_channels: ['email', 'push'],
    is_active: true,
    cooldown_minutes: 30,
    auto_resolve_minutes: 180,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'rule-002',
    organization_id: 'org-001',
    name: 'Battery Temperature Warning',
    description: 'Alert when battery temperature exceeds safe threshold',
    condition: {
      metric: 'temperature_c',
      operator: 'gt',
      threshold: 35,
      duration_seconds: 60,
      device_type: 'battery' as const,
    },
    severity: 'warning' as AlertSeverity,
    notification_channels: ['email', 'push', 'sms'],
    is_active: true,
    cooldown_minutes: 15,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'rule-003',
    organization_id: 'org-001',
    name: 'Device Offline Critical',
    description: 'Alert when device goes offline for extended period',
    condition: {
      metric: 'connection_status',
      operator: 'eq',
      threshold: 0,
      duration_seconds: 300,
    },
    severity: 'critical' as AlertSeverity,
    notification_channels: ['email', 'push', 'sms'],
    is_active: true,
    cooldown_minutes: 60,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

// Mock alerts summary
const mockAlertsSummary: AlertsSummary = {
  total: mockAlerts.length,
  active: mockAlerts.filter(a => a.status === 'active').length,
  acknowledged: mockAlerts.filter(a => a.status === 'acknowledged').length,
  by_severity: {
    info: mockAlerts.filter(a => a.severity === 'info').length,
    warning: mockAlerts.filter(a => a.severity === 'warning').length,
    critical: mockAlerts.filter(a => a.severity === 'critical').length,
  },
};

/**
 * Determine alert category based on metric name and context
 */
function determineCategory(alert: ApiAlert): UIAlert['category'] {
  const metric = alert.metric_name.toLowerCase();
  const title = alert.title.toLowerCase();

  if (metric.includes('grid') || title.includes('load shedding') || title.includes('grid')) {
    return 'load-shedding';
  }
  if (metric.includes('temperature') || metric.includes('connection') || alert.device_id) {
    return 'device';
  }
  if (metric.includes('production') || metric.includes('efficiency') || metric.includes('energy')) {
    return 'performance';
  }
  if (metric.includes('bill') || metric.includes('tariff') || title.includes('billing')) {
    return 'billing';
  }
  return 'system';
}

/**
 * Convert API alert to UI alert format
 */
export function convertAlertToUI(alert: ApiAlert): UIAlert {
  // Map API severity to UI severity
  let uiSeverity: UIAlert['severity'];
  if (alert.status === 'resolved') {
    uiSeverity = 'resolved';
  } else {
    switch (alert.severity) {
      case 'critical':
        uiSeverity = 'critical';
        break;
      case 'warning':
        uiSeverity = 'warning';
        break;
      default:
        uiSeverity = 'info';
    }
  }

  return {
    id: alert.id,
    timestamp: new Date(alert.triggered_at).toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).replace(',', ''),
    title: alert.title,
    message: alert.message,
    severity: uiSeverity,
    category: determineCategory(alert),
    device: alert.device?.name,
    deviceId: alert.device_id,
    siteId: alert.site_id,
    acknowledged: alert.status === 'acknowledged' || alert.status === 'resolved',
  };
}

class AlertsService {
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
   * Get all alerts with optional filtering and pagination
   */
  async getAlerts(
    filters?: AlertFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<ApiAlert>> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<PaginatedResponse<ApiAlert>>(
          API_ENDPOINTS.alerts.list,
          { params: { ...filters, ...pagination } }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch alerts, using mock data:', error);
      }
    }

    // Mock fallback with filtering
    if (API_CONFIG.useMockFallback) {
      let filtered = [...mockAlerts];

      if (filters?.severity) {
        filtered = filtered.filter(a => a.severity === filters.severity);
      }
      if (filters?.status) {
        filtered = filtered.filter(a => a.status === filters.status);
      }
      if (filters?.site_id) {
        filtered = filtered.filter(a => a.site_id === filters.site_id);
      }
      if (filters?.device_id) {
        filtered = filtered.filter(a => a.device_id === filters.device_id);
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
   * Get alerts formatted for UI components
   */
  async getAlertsForUI(
    filters?: AlertFilters,
    pagination?: PaginationParams
  ): Promise<{ alerts: UIAlert[]; total: number }> {
    const response = await this.getAlerts(filters, pagination);
    return {
      alerts: response.items.map(convertAlertToUI),
      total: response.total,
    };
  }

  /**
   * Get alerts summary (counts by severity and status)
   */
  async getAlertsSummary(): Promise<AlertsSummary> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<AlertsSummary>(API_ENDPOINTS.alerts.summary);
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch alerts summary, using mock data:', error);
      }
    }

    if (API_CONFIG.useMockFallback) {
      return mockAlertsSummary;
    }

    throw new Error('API unavailable');
  }

  /**
   * Acknowledge an alert
   */
  async acknowledgeAlert(alertId: string): Promise<ApiAlert> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.post<ApiAlert>(
          API_ENDPOINTS.alerts.acknowledge(alertId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to acknowledge alert via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const alertIndex = mockAlerts.findIndex(a => a.id === alertId);
      if (alertIndex >= 0) {
        mockAlerts[alertIndex] = {
          ...mockAlerts[alertIndex],
          status: 'acknowledged' as AlertStatus,
          acknowledged_by: 'current-user',
          acknowledged_at: new Date().toISOString(),
        };
        return mockAlerts[alertIndex];
      }
      throw new Error('Alert not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Resolve an alert
   */
  async resolveAlert(alertId: string): Promise<ApiAlert> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.post<ApiAlert>(
          API_ENDPOINTS.alerts.resolve(alertId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to resolve alert via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const alertIndex = mockAlerts.findIndex(a => a.id === alertId);
      if (alertIndex >= 0) {
        mockAlerts[alertIndex] = {
          ...mockAlerts[alertIndex],
          status: 'resolved' as AlertStatus,
          resolved_by: 'current-user',
          resolved_at: new Date().toISOString(),
        };
        return mockAlerts[alertIndex];
      }
      throw new Error('Alert not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Get alert rules
   */
  async getAlertRules(): Promise<AlertRule[]> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<AlertRule[]>(API_ENDPOINTS.alerts.rules);
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch alert rules, using mock data:', error);
      }
    }

    if (API_CONFIG.useMockFallback) {
      return mockAlertRules;
    }

    throw new Error('API unavailable');
  }

  /**
   * Get a specific alert rule
   */
  async getAlertRule(ruleId: string): Promise<AlertRule> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<AlertRule>(
          API_ENDPOINTS.alerts.ruleById(ruleId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch alert rule, using mock data:', error);
      }
    }

    if (API_CONFIG.useMockFallback) {
      const rule = mockAlertRules.find(r => r.id === ruleId);
      if (rule) return rule;
      throw new Error('Alert rule not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Toggle alert rule enabled/disabled
   */
  async toggleAlertRule(ruleId: string): Promise<AlertRule> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.post<AlertRule>(
          API_ENDPOINTS.alerts.toggleRule(ruleId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to toggle alert rule via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const ruleIndex = mockAlertRules.findIndex(r => r.id === ruleId);
      if (ruleIndex >= 0) {
        mockAlertRules[ruleIndex] = {
          ...mockAlertRules[ruleIndex],
          is_active: !mockAlertRules[ruleIndex].is_active,
          updated_at: new Date().toISOString(),
        };
        return mockAlertRules[ruleIndex];
      }
      throw new Error('Alert rule not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Create a new alert rule
   */
  async createAlertRule(rule: Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>): Promise<AlertRule> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.post<AlertRule>(
          API_ENDPOINTS.alerts.rules,
          rule
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to create alert rule via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const newRule: AlertRule = {
        ...rule,
        id: `rule-${Date.now()}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      mockAlertRules.push(newRule);
      return newRule;
    }

    throw new Error('API unavailable');
  }

  /**
   * Update an existing alert rule
   */
  async updateAlertRule(
    ruleId: string,
    updates: Partial<Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>>
  ): Promise<AlertRule> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.patch<AlertRule>(
          API_ENDPOINTS.alerts.ruleById(ruleId),
          updates
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to update alert rule via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const ruleIndex = mockAlertRules.findIndex(r => r.id === ruleId);
      if (ruleIndex >= 0) {
        mockAlertRules[ruleIndex] = {
          ...mockAlertRules[ruleIndex],
          ...updates,
          updated_at: new Date().toISOString(),
        };
        return mockAlertRules[ruleIndex];
      }
      throw new Error('Alert rule not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Delete an alert rule
   */
  async deleteAlertRule(ruleId: string): Promise<void> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.delete(API_ENDPOINTS.alerts.ruleById(ruleId));
        return;
      } catch (error) {
        console.warn('Failed to delete alert rule via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const ruleIndex = mockAlertRules.findIndex(r => r.id === ruleId);
      if (ruleIndex >= 0) {
        mockAlertRules.splice(ruleIndex, 1);
        return;
      }
      throw new Error('Alert rule not found');
    }

    throw new Error('API unavailable');
  }
}

export const alertsService = new AlertsService();
export default alertsService;
