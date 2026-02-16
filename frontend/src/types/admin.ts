// Admin Types

export type AdminRole =
  | "super_admin"      // Full access to everything
  | "ops_admin"        // Providers, tariffs, load shedding
  | "billing_admin"    // Subscription tiers, features
  | "device_admin"     // Device catalog, protocols
  | "firmware_admin"   // OTA firmware management
  | "read_only";       // View-only access

export type AdminPermission =
  // Configuration
  | "manage_providers"
  | "manage_tariffs"
  | "manage_load_shedding"
  // Subscriptions
  | "manage_tiers"
  | "manage_features"
  // Devices
  | "manage_devices"
  | "manage_adapters"
  | "manage_weather"
  // OTA
  | "manage_firmware"
  | "manage_campaigns"
  // Users
  | "manage_users"
  | "view_audit_log"
  | "export_data";

export interface AdminUser {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: AdminRole;
  status: "active" | "inactive";
  createdAt: string;
  lastLoginAt?: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  actor: string;       // Admin email
  actorRole: AdminRole;
  action: "create" | "update" | "delete" | "activate" | "deactivate" | "view";
  entity: string;      // "provider", "tariff", "tier", etc.
  entityId: string;
  details: {
    before?: any;
    after?: any;
    metadata?: Record<string, any>;
  };
  ipAddress?: string;
  userAgent?: string;
}

// Electricity Provider
export interface ElectricityProvider {
  id: string;
  name: string;
  shortName: string;  // "LESCO", "K-Electric"
  region: string;     // "Punjab", "Sindh"
  status: "active" | "inactive";
  tariffCount: number;
  createdAt: string;
  updatedAt: string;
}

// Tariff Plan
export interface TariffPlan {
  id: string;
  providerId: string;
  name: string;
  category: "residential" | "commercial" | "industrial";
  type: "slab" | "tou" | "flat";
  rates: {
    slabs?: Array<{
      minUnits: number;
      maxUnits: number | null;
      ratePerKwh: number;
    }>;
    touPeakRate?: number;
    touOffPeakRate?: number;
    flatRate?: number;
  };
  fixedCharges: number;
  effectiveFrom: string;
  effectiveTo: string | null;
  status: "active" | "inactive" | "draft";
}

// Load Shedding Schedule
export interface LoadSheddingSchedule {
  id: string;
  providerId: string;
  zone: string;
  dayOfWeek: number;  // 0-6
  startTime: string;  // "HH:mm"
  endTime: string;
  duration: number;   // minutes
  isActive: boolean;
}

// Subscription Tier
export interface SubscriptionTier {
  id: string;
  name: string;
  displayName: string;
  pricePerMonth: number;
  currency: "PKR";
  limits: {
    maxDevices: number;
    pollingInterval: number;  // seconds
    dataRetention: number;    // days
    maxUsers: number;
  };
  features: string[];  // Feature IDs
  isActive: boolean;
}

// Feature Flag
export interface Feature {
  id: string;
  name: string;
  description: string;
  category: "core" | "premium" | "experimental";
  enabledForTiers: string[];  // Tier IDs
  isActive: boolean;
}

// Device Catalog
export interface DeviceModel {
  id: string;
  manufacturer: string;
  model: string;
  type: "inverter" | "battery" | "meter";
  protocol: "modbus_tcp" | "modbus_rtu" | "mqtt";
  specifications: {
    maxPowerKw?: number;
    capacityKwh?: number;
    phases?: 1 | 3;
  };
  registerMapFile?: string;
  isSupported: boolean;
}

// Protocol Adapter
export interface ProtocolAdapter {
  id: string;
  name: string;
  protocol: string;
  deviceType: string;
  adapterClass: string;
  configuration: {
    defaultPort?: number;
    timeout?: number;
    retries?: number;
  };
  isActive: boolean;
}

// Weather Station
export interface WeatherStation {
  id: string;
  name: string;
  provider: string;
  apiEndpoint: string;
  apiKey?: string;
  location: {
    latitude: number;
    longitude: number;
  };
  isActive: boolean;
}
