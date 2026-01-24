/**
 * API Types
 *
 * TypeScript interfaces matching the System A backend schemas.
 * These types ensure type safety between frontend and backend.
 */

// ============================================================================
// Enums
// ============================================================================

export enum UserRole {
  SUPER_ADMIN = 'super_admin',
  OWNER = 'owner',
  ADMIN = 'admin',
  MANAGER = 'manager',
  VIEWER = 'viewer',
  INSTALLER = 'installer',
}

export enum UserStatus {
  ACTIVE = 'active',
  PENDING = 'pending',
  SUSPENDED = 'suspended',
  DEACTIVATED = 'deactivated',
}

export enum DeviceType {
  INVERTER = 'inverter',
  METER = 'meter',
  BATTERY = 'battery',
  WEATHER_STATION = 'weather_station',
  SENSOR = 'sensor',
  GATEWAY = 'gateway',
  OTHER = 'other',
}

export enum DeviceStatus {
  ONLINE = 'online',
  OFFLINE = 'offline',
  ERROR = 'error',
  MAINTENANCE = 'maintenance',
  UNKNOWN = 'unknown',
}

export enum SiteStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  MAINTENANCE = 'maintenance',
  DECOMMISSIONED = 'decommissioned',
}

export enum GridConnectionType {
  ON_GRID = 'on_grid',
  OFF_GRID = 'off_grid',
  HYBRID = 'hybrid',
}

export enum AlertSeverity {
  INFO = 'info',
  WARNING = 'warning',
  CRITICAL = 'critical',
}

export enum AlertStatus {
  ACTIVE = 'active',
  ACKNOWLEDGED = 'acknowledged',
  RESOLVED = 'resolved',
  EXPIRED = 'expired',
}

export enum DiscoProvider {
  LESCO = 'lesco',
  FESCO = 'fesco',
  IESCO = 'iesco',
  GEPCO = 'gepco',
  MEPCO = 'mepco',
  PESCO = 'pesco',
  HESCO = 'hesco',
  SEPCO = 'sepco',
  QESCO = 'qesco',
  TESCO = 'tesco',
  KESCO = 'kesco', // Karachi
  KELECTRIC = 'kelectric',
}

// Type alias for string literals (used in services)
export type DiscoProviderString =
  | 'lesco' | 'fesco' | 'iesco' | 'gepco' | 'mepco'
  | 'pesco' | 'hesco' | 'sepco' | 'qesco' | 'tesco' | 'kesco';

// ============================================================================
// User & Authentication
// ============================================================================

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role: UserRole;
  status: UserStatus;
  is_verified: boolean;
  preferences: UserPreferences;
  created_at: string;
  updated_at: string;
}

export interface UserPreferences {
  timezone: string;
  language: string;
  currency: string;
  date_format: string;
  dark_mode: boolean;
  notifications_enabled: boolean;
  email_notifications: boolean;
  sms_notifications: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  device_serial?: string;
}

export interface SiteInfo {
  id: string;
  name: string;
  is_default: boolean;
}

export interface DeviceClaimInfo {
  id: string;
  serial_number: string;
  device_type: string;
  manufacturer?: string;
  status: string;
}

export interface RegisterResponse {
  success: boolean;
  message: string;
  user: User;
  site?: SiteInfo;
  device?: DeviceClaimInfo;
}

// ============================================================================
// Organization
// ============================================================================

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description?: string;
  owner_id: string;
  status: 'active' | 'inactive';
  settings: OrganizationSettings;
  created_at: string;
  updated_at: string;
}

export interface OrganizationSettings {
  max_sites: number;
  max_users: number;
  alert_email_enabled: boolean;
  alert_sms_enabled: boolean;
}

export interface OrganizationMember {
  user_id: string;
  organization_id: string;
  role: UserRole;
  joined_at: string;
  user: User;
}

// ============================================================================
// Site
// ============================================================================

export interface Site {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  status: SiteStatus;
  address: Address;
  geo_location: GeoLocation;
  timezone: string;
  configuration: SiteConfiguration;
  created_at: string;
  updated_at: string;
}

export interface Address {
  street?: string;
  city: string;
  state?: string;
  postal_code?: string;
  country: string;
}

export interface GeoLocation {
  latitude: number;
  longitude: number;
}

export interface SiteConfiguration {
  system_capacity_kw: number;
  panel_count: number;
  panel_wattage: number;
  inverter_capacity_kw: number;
  battery_capacity_kwh?: number;
  grid_connection_type: GridConnectionType;
  net_metering_enabled: boolean;
  disco_provider: DiscoProvider;
  tariff_category: string;
}

// ============================================================================
// Device
// ============================================================================

export interface Device {
  id: string;
  site_id: string;
  organization_id: string;
  device_type: DeviceType;
  name: string;
  manufacturer: string;
  model: string;
  serial_number: string;
  firmware_version?: string;
  status: DeviceStatus;
  protocol: string;
  connection_config: ConnectionConfig;
  latest_metrics?: DeviceMetrics;
  last_seen_at?: string;
  last_error_message?: string;
  metadata: Record<string, unknown>;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface ConnectionConfig {
  host?: string;
  port?: number;
  slave_id?: number;
  protocol_definition_id?: string;
}

export interface DeviceMetrics {
  power_output_w?: number;
  energy_today_kwh?: number;
  energy_total_kwh?: number;
  voltage_v?: number;
  current_a?: number;
  frequency_hz?: number;
  temperature_c?: number;
  efficiency_percent?: number;
  state_of_charge?: number;
  power_import_w?: number;
  power_export_w?: number;
  timestamp: string;
}

export interface DeviceCommand {
  command_type: string;
  parameters?: Record<string, unknown>;
}

// ============================================================================
// Dashboard & Telemetry
// ============================================================================

export interface DashboardOverview {
  organization_id: string;
  total_sites: number;
  total_devices: number;
  devices_online: number;
  devices_offline: number;
  total_power_kw: number;
  total_energy_today_kwh: number;
  total_energy_month_kwh: number;
  self_consumption_percent: number;
  grid_export_kwh: number;
  grid_import_kwh: number;
  battery_soc_avg: number;
  co2_avoided_kg: number;
  savings_today_pkr: number;
  savings_month_pkr: number;
  alerts_active: number;
  alerts_warning: number;
  alerts_critical: number;
  last_updated: string;
}

export interface SiteDashboard {
  site: Site;
  devices: Device[];
  current_power: PowerSnapshot;
  energy_today: EnergySnapshot;
  energy_month: EnergySnapshot;
  environmental_impact: EnvironmentalImpact;
  alerts_summary: AlertsSummary;
}

export interface PowerSnapshot {
  solar_power_kw: number;
  battery_power_kw: number;
  grid_power_kw: number;
  consumption_kw: number;
  battery_soc: number;
  is_exporting: boolean;
  timestamp: string;
}

export interface EnergySnapshot {
  solar_kwh: number;
  consumption_kwh: number;
  grid_import_kwh: number;
  grid_export_kwh: number;
  battery_charge_kwh: number;
  battery_discharge_kwh: number;
  self_consumption_percent: number;
}

export interface EnvironmentalImpact {
  co2_avoided_kg: number;
  trees_equivalent: number;
  coal_avoided_kg: number;
}

export interface AlertsSummary {
  total: number;
  active: number;
  acknowledged: number;
  by_severity: {
    info: number;
    warning: number;
    critical: number;
  };
}

export interface PowerChartData {
  timestamps: string[];
  solar_power: number[];
  consumption: number[];
  grid_power: number[];
  battery_power: number[];
  battery_soc: number[];
}

export interface EnergyChartData {
  labels: string[];
  solar: number[];
  consumption: number[];
  grid_import: number[];
  grid_export: number[];
}

// ============================================================================
// Billing & Tariffs
// ============================================================================

export interface TariffPlan {
  id: string;
  disco_provider: DiscoProvider;
  category: string;
  effective_from: string;
  effective_to?: string;
  rates: TariffRates;
  supports_net_metering: boolean;
  supports_tou: boolean;
  is_active: boolean;
}

export interface TariffRates {
  slabs: TariffSlab[];
  fixed_charges: number;
  meter_rent: number;
  fuel_price_adjustment: number;
  quarterly_adjustment: number;
  electricity_duty_percent: number;
  gst_percent: number;
  tv_fee: number;
  net_metering_export_rate?: number;
  tou_rates?: {
    peak: number;
    off_peak: number;
    peak_hours: string;
  };
}

export interface TariffSlab {
  min_units: number;
  max_units?: number;
  rate_per_unit: number;
}

export interface BillSimulationRequest {
  site_id: string;
  tariff_plan_id: string;
  period_start: string;
  period_end: string;
  energy_consumed_kwh: number;
  energy_exported_kwh: number;
}

export interface BillSimulationResponse {
  id: string;
  estimated_bill_pkr: number;
  estimated_savings_pkr: number;
  bill_breakdown: BillBreakdown;
  savings_breakdown: SavingsBreakdown;
}

export interface BillBreakdown {
  energy_charges: number;
  fuel_adjustment: number;
  quarterly_adjustment: number;
  fixed_charges: number;
  meter_rent: number;
  electricity_duty: number;
  gst: number;
  tv_fee: number;
  export_credit: number;
  total: number;
}

export interface SavingsBreakdown {
  avoided_import: number;
  export_revenue: number;
  total: number;
}

// ============================================================================
// Alerts
// ============================================================================

export interface AlertRule {
  id: string;
  organization_id: string;
  site_id?: string;
  name: string;
  description?: string;
  condition: AlertCondition;
  severity: AlertSeverity;
  notification_channels: string[];
  is_active: boolean;
  cooldown_minutes: number;
  auto_resolve_minutes?: number;
  created_at: string;
  updated_at: string;
}

export interface AlertCondition {
  metric: string;
  operator: 'lt' | 'lte' | 'gt' | 'gte' | 'eq' | 'ne';
  threshold: number;
  duration_seconds: number;
  device_type?: DeviceType;
}

export interface Alert {
  id: string;
  rule_id: string;
  organization_id: string;
  site_id?: string;
  device_id?: string;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  message: string;
  metric_name: string;
  metric_value: number;
  threshold: number;
  triggered_at: string;
  acknowledged_by?: string;
  acknowledged_at?: string;
  resolved_by?: string;
  resolved_at?: string;
  device?: Device;
  site?: Site;
}

// ============================================================================
// Pagination
// ============================================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

// ============================================================================
// API Response Wrappers
// ============================================================================

export interface ApiSuccessResponse<T> {
  success: true;
  data: T;
}

export interface ApiErrorResponse {
  success: false;
  error: string;
  message: string;
  details?: Record<string, unknown>;
}

export type ApiResponse<T> = ApiSuccessResponse<T> | ApiErrorResponse;
