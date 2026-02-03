/**
 * Alerts Service
 *
 * Handles all alert-related API calls including fetching, acknowledging,
 * and resolving alerts.
 */

import apiClient from '../client';
import { API_ENDPOINTS } from '../config';
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
      timeZone: 'Asia/Karachi', // Display in site timezone (TODO: get from site config)
    }).replace(',', '') + ' PKT', // Add timezone indicator
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
  /**
   * Get all alerts with optional filtering and pagination
   */
  async getAlerts(
    filters?: AlertFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<ApiAlert>> {
    const response = await apiClient.get<PaginatedResponse<ApiAlert>>(
      API_ENDPOINTS.alerts.list,
      { params: { ...filters, ...pagination } }
    );
    return response.data;
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
    const response = await apiClient.get<AlertsSummary>(API_ENDPOINTS.alerts.summary);
    return response.data;
  }

  /**
   * Acknowledge an alert
   */
  async acknowledgeAlert(alertId: string): Promise<ApiAlert> {
    const response = await apiClient.post<ApiAlert>(
      API_ENDPOINTS.alerts.acknowledge(alertId)
    );
    return response.data;
  }

  /**
   * Resolve an alert
   */
  async resolveAlert(alertId: string): Promise<ApiAlert> {
    const response = await apiClient.post<ApiAlert>(
      API_ENDPOINTS.alerts.resolve(alertId)
    );
    return response.data;
  }

  /**
   * Get alert rules
   */
  async getAlertRules(): Promise<AlertRule[]> {
    const response = await apiClient.get<AlertRule[]>(API_ENDPOINTS.alerts.rules);
    return response.data;
  }

  /**
   * Get a specific alert rule
   */
  async getAlertRule(ruleId: string): Promise<AlertRule> {
    const response = await apiClient.get<AlertRule>(
      API_ENDPOINTS.alerts.ruleById(ruleId)
    );
    return response.data;
  }

  /**
   * Toggle alert rule enabled/disabled
   */
  async toggleAlertRule(ruleId: string): Promise<AlertRule> {
    const response = await apiClient.post<AlertRule>(
      API_ENDPOINTS.alerts.toggleRule(ruleId)
    );
    return response.data;
  }

  /**
   * Create a new alert rule
   */
  async createAlertRule(rule: Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>): Promise<AlertRule> {
    const response = await apiClient.post<AlertRule>(
      API_ENDPOINTS.alerts.rules,
      rule
    );
    return response.data;
  }

  /**
   * Update an existing alert rule
   */
  async updateAlertRule(
    ruleId: string,
    updates: Partial<Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>>
  ): Promise<AlertRule> {
    const response = await apiClient.patch<AlertRule>(
      API_ENDPOINTS.alerts.ruleById(ruleId),
      updates
    );
    return response.data;
  }

  /**
   * Delete an alert rule
   */
  async deleteAlertRule(ruleId: string): Promise<void> {
    await apiClient.delete(API_ENDPOINTS.alerts.ruleById(ruleId));
  }
}

export const alertsService = new AlertsService();
export default alertsService;
