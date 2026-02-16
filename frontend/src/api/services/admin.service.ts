/**
 * Admin API Service
 *
 * Handles all admin-related API calls for System A
 * - Electricity providers
 * - Tariff plans
 * - Load shedding schedules
 * - Subscription tiers
 * - Feature flags
 * - Device catalog
 * - Protocol adapters
 * - Weather stations
 */

import apiClient from '../client';
import type {
  ElectricityProvider,
  TariffPlan,
  LoadSheddingSchedule,
  SubscriptionTier,
  Feature,
  DeviceModel,
  ProtocolAdapter,
  WeatherStation,
  AdminUser,
  AuditLogEntry,
} from '@/types/admin';

// Admin Authentication
export const adminAuthService = {
  login: async (email: string, password: string) => {
    const response = await apiClient.post('/admin/auth/login', { email, password });
    return response.data;
  },

  logout: async () => {
    const response = await apiClient.post('/admin/auth/logout');
    return response.data;
  },

  me: async (): Promise<AdminUser> => {
    const response = await apiClient.get('/admin/auth/me');
    return response.data;
  },
};

// Electricity Providers
export const providersService = {
  list: async (): Promise<ElectricityProvider[]> => {
    const response = await apiClient.get('/admin/providers');
    return response.data;
  },

  getById: async (id: string): Promise<ElectricityProvider> => {
    const response = await apiClient.get(`/admin/providers/${id}`);
    return response.data;
  },

  create: async (data: Omit<ElectricityProvider, 'id' | 'tariffCount' | 'createdAt' | 'updatedAt'>): Promise<ElectricityProvider> => {
    const response = await apiClient.post('/admin/providers', data);
    return response.data;
  },

  update: async (id: string, data: Partial<ElectricityProvider>): Promise<ElectricityProvider> => {
    const response = await apiClient.put(`/admin/providers/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/providers/${id}`);
  },
};

// Tariff Plans
export const tariffsService = {
  list: async (params?: { providerId?: string }): Promise<TariffPlan[]> => {
    const response = await apiClient.get('/admin/tariffs', { params });
    return response.data;
  },

  getById: async (id: string): Promise<TariffPlan> => {
    const response = await apiClient.get(`/admin/tariffs/${id}`);
    return response.data;
  },

  create: async (data: Omit<TariffPlan, 'id'>): Promise<TariffPlan> => {
    const response = await apiClient.post('/admin/tariffs', data);
    return response.data;
  },

  update: async (id: string, data: Partial<TariffPlan>): Promise<TariffPlan> => {
    const response = await apiClient.put(`/admin/tariffs/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/tariffs/${id}`);
  },
};

// Load Shedding Schedules
export const loadSheddingService = {
  list: async (params?: { providerId?: string }): Promise<LoadSheddingSchedule[]> => {
    const response = await apiClient.get('/admin/load-shedding', { params });
    return response.data;
  },

  getById: async (id: string): Promise<LoadSheddingSchedule> => {
    const response = await apiClient.get(`/admin/load-shedding/${id}`);
    return response.data;
  },

  create: async (data: Omit<LoadSheddingSchedule, 'id'>): Promise<LoadSheddingSchedule> => {
    const response = await apiClient.post('/admin/load-shedding', data);
    return response.data;
  },

  update: async (id: string, data: Partial<LoadSheddingSchedule>): Promise<LoadSheddingSchedule> => {
    const response = await apiClient.put(`/admin/load-shedding/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/load-shedding/${id}`);
  },
};

// Subscription Tiers
export const subscriptionTiersService = {
  list: async (): Promise<SubscriptionTier[]> => {
    const response = await apiClient.get('/admin/subscription-tiers');
    return response.data;
  },

  getById: async (id: string): Promise<SubscriptionTier> => {
    const response = await apiClient.get(`/admin/subscription-tiers/${id}`);
    return response.data;
  },

  create: async (data: Omit<SubscriptionTier, 'id'>): Promise<SubscriptionTier> => {
    const response = await apiClient.post('/admin/subscription-tiers', data);
    return response.data;
  },

  update: async (id: string, data: Partial<SubscriptionTier>): Promise<SubscriptionTier> => {
    const response = await apiClient.put(`/admin/subscription-tiers/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/subscription-tiers/${id}`);
  },
};

// Feature Flags
export const featuresService = {
  list: async (): Promise<Feature[]> => {
    const response = await apiClient.get('/admin/features');
    return response.data;
  },

  getById: async (id: string): Promise<Feature> => {
    const response = await apiClient.get(`/admin/features/${id}`);
    return response.data;
  },

  update: async (id: string, data: Partial<Feature>): Promise<Feature> => {
    const response = await apiClient.put(`/admin/features/${id}`, data);
    return response.data;
  },

  updateTiers: async (id: string, tierIds: string[]): Promise<Feature> => {
    const response = await apiClient.put(`/admin/features/${id}/tiers`, { tierIds });
    return response.data;
  },
};

// Device Catalog
export const deviceCatalogService = {
  list: async (): Promise<DeviceModel[]> => {
    const response = await apiClient.get('/admin/device-catalog');
    return response.data;
  },

  getById: async (id: string): Promise<DeviceModel> => {
    const response = await apiClient.get(`/admin/device-catalog/${id}`);
    return response.data;
  },

  create: async (data: Omit<DeviceModel, 'id'>): Promise<DeviceModel> => {
    const response = await apiClient.post('/admin/device-catalog', data);
    return response.data;
  },

  update: async (id: string, data: Partial<DeviceModel>): Promise<DeviceModel> => {
    const response = await apiClient.put(`/admin/device-catalog/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/device-catalog/${id}`);
  },
};

// Protocol Adapters
export const protocolAdaptersService = {
  list: async (): Promise<ProtocolAdapter[]> => {
    const response = await apiClient.get('/admin/protocol-adapters');
    return response.data;
  },

  getById: async (id: string): Promise<ProtocolAdapter> => {
    const response = await apiClient.get(`/admin/protocol-adapters/${id}`);
    return response.data;
  },

  update: async (id: string, data: Partial<ProtocolAdapter>): Promise<ProtocolAdapter> => {
    const response = await apiClient.put(`/admin/protocol-adapters/${id}`, data);
    return response.data;
  },
};

// Weather Stations
export const weatherStationsService = {
  list: async (): Promise<WeatherStation[]> => {
    const response = await apiClient.get('/admin/weather-stations');
    return response.data;
  },

  getById: async (id: string): Promise<WeatherStation> => {
    const response = await apiClient.get(`/admin/weather-stations/${id}`);
    return response.data;
  },

  create: async (data: Omit<WeatherStation, 'id'>): Promise<WeatherStation> => {
    const response = await apiClient.post('/admin/weather-stations', data);
    return response.data;
  },

  update: async (id: string, data: Partial<WeatherStation>): Promise<WeatherStation> => {
    const response = await apiClient.put(`/admin/weather-stations/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/weather-stations/${id}`);
  },
};

// Admin Users
export const adminUsersService = {
  list: async (): Promise<AdminUser[]> => {
    const response = await apiClient.get('/admin/users');
    return response.data;
  },

  getById: async (id: string): Promise<AdminUser> => {
    const response = await apiClient.get(`/admin/users/${id}`);
    return response.data;
  },

  create: async (data: Omit<AdminUser, 'id' | 'createdAt' | 'lastLoginAt'>): Promise<AdminUser> => {
    const response = await apiClient.post('/admin/users', data);
    return response.data;
  },

  update: async (id: string, data: Partial<AdminUser>): Promise<AdminUser> => {
    const response = await apiClient.put(`/admin/users/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/users/${id}`);
  },
};

// Audit Log
export const auditLogService = {
  list: async (params?: {
    action?: string;
    entity?: string;
    actor?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
  }): Promise<AuditLogEntry[]> => {
    const response = await apiClient.get('/admin/audit-log', { params });
    return response.data;
  },

  getById: async (id: string): Promise<AuditLogEntry> => {
    const response = await apiClient.get(`/admin/audit-log/${id}`);
    return response.data;
  },

  create: async (data: Omit<AuditLogEntry, 'id' | 'timestamp'>): Promise<AuditLogEntry> => {
    const response = await apiClient.post('/admin/audit-log', data);
    return response.data;
  },
};

export default {
  adminAuth: adminAuthService,
  providers: providersService,
  tariffs: tariffsService,
  loadShedding: loadSheddingService,
  subscriptionTiers: subscriptionTiersService,
  features: featuresService,
  deviceCatalog: deviceCatalogService,
  protocolAdapters: protocolAdaptersService,
  weatherStations: weatherStationsService,
  adminUsers: adminUsersService,
  auditLog: auditLogService,
};
