/**
 * API Services Index
 *
 * Centralized export of all API services.
 */

export { authService } from './auth.service';
export { dashboardService } from './dashboard.service';
export type {
  // Per-device breakdown types
  DevicePowerData,
  DeviceStatsData,
  DeviceBatteryData,
  DeviceStatusItem,
  // Site-level response types
  PowerFlowData,
  StatsData,
  BatteryStatusData,
  DeviceStatusData,
  AlertItem,
  AlertsData,
  EnvironmentalData,
  BillingData,
  AllWidgetsData,
} from './dashboard.service';
export { devicesService } from './devices.service';
export { deviceSettingsService } from './device-settings.service';
export type { DeviceSettings, DeviceSettingsUpdate, DeviceSettingsResetResponse } from './device-settings.service';
export { deviceCommandsService } from './device-commands.service';
export type {
  QuerySettingsRequest,
  QuerySettingsResponse,
  UpdateSettingsRequest,
  UpdateSettingsResponse,
  CommandStatusResponse,
} from './device-commands.service';
export { sitesService } from './sites.service';
export { billingService } from './billing.service';
export type { BillingOverview, BillCalculation } from './billing.service';
export { alertsService } from './alerts.service';
export type { UIAlert, AlertFilters } from './alerts.service';
export { usersService } from './users.service';
export type { UserFilters } from './users.service';
export { organizationsService } from './organizations.service';
export type { OrganizationFilters, InviteRequest } from './organizations.service';

// Re-export types
export * from '../types';
