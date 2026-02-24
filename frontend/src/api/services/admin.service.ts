/**
 * Admin API Service
 *
 * Handles all admin-related API calls for System A
 * - Electricity providers
 * - Tariff plans
 * - Load shedding schedules
 * - Admin users
 * - Audit log
 *
 * Uses a dedicated adminApiClient that reads the admin token from localStorage
 * (key: 'admin_token') so it doesn't conflict with regular user sessions.
 */

import axios, { AxiosInstance } from 'axios';
import { API_CONFIG } from '../config';
import type {
  ElectricityProvider,
  TariffPlan,
  LoadSheddingSchedule,
  AdminUser,
  AuditLogEntry,
  AdminRole,
} from '@/types/admin';

// ---------------------------------------------------------------------------
// Admin-specific Axios instance (reads from admin_token)
// ---------------------------------------------------------------------------

export const ADMIN_TOKEN_KEY = 'admin_token';

const adminApiClient: AxiosInstance = axios.create({
  baseURL: API_CONFIG.baseUrl,
  timeout: API_CONFIG.timeout,
  headers: { 'Content-Type': 'application/json' },
});

adminApiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

adminApiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(ADMIN_TOKEN_KEY);
      localStorage.removeItem('admin_user');
      if (!window.location.pathname.includes('/admin/login')) {
        window.location.href = '/admin/login';
      }
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// Data mappers (backend snake_case → frontend camelCase)
// ---------------------------------------------------------------------------

function mapProvider(raw: any): ElectricityProvider {
  return {
    id: raw.id,
    name: raw.name,
    shortName: raw.short_name,
    region: raw.region,
    status: raw.status,
    tariffCount: raw.tariff_count ?? 0,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at ?? raw.created_at,
  };
}

function mapTariff(raw: any): TariffPlan {
  return {
    id: raw.id,
    providerId: raw.provider_id,
    name: raw.name,
    category: raw.category,
    type: raw.type,
    rates: raw.rates ?? {},
    fixedCharges: raw.fixed_charges ?? 0,
    effectiveFrom: raw.effective_from,
    effectiveTo: raw.effective_to ?? null,
    status: raw.status,
  };
}

function mapAdminUser(raw: any): AdminUser {
  return {
    id: raw.id,
    email: raw.email,
    firstName: raw.first_name,
    lastName: raw.last_name,
    role: raw.role as AdminRole,
    status: raw.status === 'active' ? 'active' : 'inactive',
    createdAt: raw.created_at,
    lastLoginAt: raw.last_login_at,
  };
}

function mapLoadShedding(raw: any): LoadSheddingSchedule {
  // Backend model differs from frontend model — adapt to a compatible shape.
  // Backend: { id, area_name, region, feeder_code, schedule, is_active, effective_from, effective_to }
  // Frontend: { id, providerId, zone, dayOfWeek, startTime, endTime, duration, isActive }
  // We use a best-effort mapping; the frontend type is legacy and will be revisited.
  return {
    id: raw.id,
    providerId: raw.provider_id ?? '',
    zone: raw.area_name ?? raw.zone ?? '',
    dayOfWeek: raw.day_of_week ?? 0,
    startTime: raw.start_time ?? '00:00',
    endTime: raw.end_time ?? '00:00',
    duration: raw.duration ?? 0,
    isActive: raw.is_active ?? true,
    // Extended backend fields stored on the object for display purposes
    ...{
      areaName: raw.area_name,
      region: raw.region,
      feederCode: raw.feeder_code,
      schedule: raw.schedule,
      effectiveFrom: raw.effective_from,
      effectiveTo: raw.effective_to,
    },
  } as LoadSheddingSchedule & Record<string, any>;
}

function mapAuditLog(raw: any): AuditLogEntry {
  return {
    id: raw.id,
    timestamp: raw.created_at,
    actor: raw.admin_email ?? '',
    actorRole: (raw.actor_role ?? 'read_only') as AdminRole,
    action: raw.action as AuditLogEntry['action'],
    entity: raw.resource_type ?? '',
    entityId: raw.resource_id ?? '',
    details: {
      before: raw.old_values,
      after: raw.new_values,
      metadata: { ip_address: raw.ip_address },
    },
    ipAddress: raw.ip_address,
  };
}

// ---------------------------------------------------------------------------
// Admin Authentication
// ---------------------------------------------------------------------------

export const adminAuthService = {
  login: async (email: string, password: string): Promise<{ access_token: string; user: AdminUser }> => {
    const response = await adminApiClient.post('/admin/auth/login', { email, password });
    const data = response.data;
    return {
      access_token: data.access_token,
      user: mapAdminUser(data.user),
    };
  },

  logout: async (): Promise<void> => {
    try {
      await adminApiClient.post('/admin/auth/logout');
    } catch {
      // Ignore — token is discarded client-side regardless
    }
  },

  me: async (): Promise<AdminUser> => {
    const response = await adminApiClient.get('/admin/auth/me');
    return mapAdminUser(response.data);
  },
};

// ---------------------------------------------------------------------------
// Electricity Providers
// ---------------------------------------------------------------------------

export const providersService = {
  list: async (): Promise<ElectricityProvider[]> => {
    const response = await adminApiClient.get('/admin/providers', { params: { limit: 200 } });
    const data = response.data;
    const items = Array.isArray(data) ? data : (data.items ?? []);
    return items.map(mapProvider);
  },

  getById: async (id: string): Promise<ElectricityProvider> => {
    const response = await adminApiClient.get(`/admin/providers/${id}`);
    return mapProvider(response.data);
  },

  create: async (data: Pick<ElectricityProvider, 'name' | 'shortName' | 'region' | 'status'>): Promise<ElectricityProvider> => {
    const response = await adminApiClient.post('/admin/providers', {
      name: data.name,
      short_name: data.shortName,
      region: data.region,
    });
    return mapProvider(response.data);
  },

  update: async (id: string, data: Partial<ElectricityProvider>): Promise<ElectricityProvider> => {
    const payload: Record<string, any> = {};
    if (data.name !== undefined) payload.name = data.name;
    if (data.shortName !== undefined) payload.short_name = data.shortName;
    if (data.region !== undefined) payload.region = data.region;
    if (data.status !== undefined) payload.status = data.status;
    const response = await adminApiClient.put(`/admin/providers/${id}`, payload);
    return mapProvider(response.data);
  },

  delete: async (id: string): Promise<void> => {
    await adminApiClient.delete(`/admin/providers/${id}`);
  },
};

// ---------------------------------------------------------------------------
// Tariff Plans
// ---------------------------------------------------------------------------

export const tariffsService = {
  list: async (params?: { providerId?: string }): Promise<TariffPlan[]> => {
    const apiParams: Record<string, any> = { limit: 200 };
    if (params?.providerId) apiParams.provider_id = params.providerId;
    const response = await adminApiClient.get('/admin/tariffs', { params: apiParams });
    const data = response.data;
    const items = Array.isArray(data) ? data : (data.items ?? []);
    return items.map(mapTariff);
  },

  getById: async (id: string): Promise<TariffPlan> => {
    const response = await adminApiClient.get(`/admin/tariffs/${id}`);
    return mapTariff(response.data);
  },

  create: async (data: Omit<TariffPlan, 'id'>): Promise<TariffPlan> => {
    const response = await adminApiClient.post('/admin/tariffs', {
      provider_id: data.providerId,
      name: data.name,
      category: data.category,
      type: data.type,
      rates: data.rates,
      fixed_charges: data.fixedCharges,
      effective_from: data.effectiveFrom,
      effective_to: data.effectiveTo,
      status: data.status,
    });
    return mapTariff(response.data);
  },

  update: async (id: string, data: Partial<TariffPlan>): Promise<TariffPlan> => {
    const payload: Record<string, any> = {};
    if (data.name !== undefined) payload.name = data.name;
    if (data.category !== undefined) payload.category = data.category;
    if (data.type !== undefined) payload.type = data.type;
    if (data.rates !== undefined) payload.rates = data.rates;
    if (data.fixedCharges !== undefined) payload.fixed_charges = data.fixedCharges;
    if (data.effectiveFrom !== undefined) payload.effective_from = data.effectiveFrom;
    if (data.effectiveTo !== undefined) payload.effective_to = data.effectiveTo;
    if (data.status !== undefined) payload.status = data.status;
    const response = await adminApiClient.put(`/admin/tariffs/${id}`, payload);
    return mapTariff(response.data);
  },

  delete: async (id: string): Promise<void> => {
    await adminApiClient.delete(`/admin/tariffs/${id}`);
  },
};

// ---------------------------------------------------------------------------
// Load Shedding Schedules
// ---------------------------------------------------------------------------

export const loadSheddingService = {
  list: async (params?: { providerId?: string }): Promise<any[]> => {
    const apiParams: Record<string, any> = { limit: 200 };
    if (params?.providerId) apiParams.provider_id = params.providerId;
    const response = await adminApiClient.get('/admin/load-shedding', { params: apiParams });
    const data = response.data;
    const items = Array.isArray(data) ? data : (data.items ?? []);
    return items.map(mapLoadShedding);
  },

  getById: async (id: string): Promise<any> => {
    const response = await adminApiClient.get(`/admin/load-shedding/${id}`);
    return mapLoadShedding(response.data);
  },

  create: async (data: {
    area_name: string;
    region: string;
    feeder_code?: string;
    schedule: Record<string, any>;
    effective_from?: string;
    effective_to?: string;
  }): Promise<any> => {
    const response = await adminApiClient.post('/admin/load-shedding', data);
    return mapLoadShedding(response.data);
  },

  update: async (id: string, data: {
    area_name?: string;
    region?: string;
    feeder_code?: string;
    schedule?: Record<string, any>;
    is_active?: boolean;
    effective_from?: string;
    effective_to?: string;
  }): Promise<any> => {
    const response = await adminApiClient.put(`/admin/load-shedding/${id}`, data);
    return mapLoadShedding(response.data);
  },

  delete: async (id: string): Promise<void> => {
    await adminApiClient.delete(`/admin/load-shedding/${id}`);
  },
};

// ---------------------------------------------------------------------------
// Admin Users
// ---------------------------------------------------------------------------

export const adminUsersService = {
  list: async (): Promise<AdminUser[]> => {
    const response = await adminApiClient.get('/admin/users', { params: { limit: 200 } });
    const data = response.data;
    const items = Array.isArray(data) ? data : (data.items ?? []);
    return items.map(mapAdminUser);
  },

  getById: async (id: string): Promise<AdminUser> => {
    const response = await adminApiClient.get(`/admin/users/${id}`);
    return mapAdminUser(response.data);
  },

  update: async (id: string, data: { role?: AdminRole; status?: 'active' | 'inactive' }): Promise<AdminUser> => {
    const response = await adminApiClient.put(`/admin/users/${id}`, data);
    return mapAdminUser(response.data);
  },
};

// ---------------------------------------------------------------------------
// Audit Log
// ---------------------------------------------------------------------------

export const auditLogService = {
  list: async (params?: {
    action?: string;
    resource_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditLogEntry[]> => {
    const response = await adminApiClient.get('/admin/audit-log', { params: { limit: 100, ...params } });
    const data = response.data;
    const items = Array.isArray(data) ? data : (data.items ?? []);
    return items.map(mapAuditLog);
  },
};

// ---------------------------------------------------------------------------
// AI Prompt Templates
// ---------------------------------------------------------------------------

export interface PromptVariable {
  name: string;
  description: string;
  example?: string;
}

export interface PromptTemplate {
  id: string;
  key: string;
  tier: 'hourly' | 'monthly' | 'yearly';
  prompt_type: 'system' | 'user';
  template: string;
  variables: PromptVariable[];
  version: number;
  is_active: boolean;
  model?: string;
  updated_at?: string;
}

export interface PromptTemplateVersion {
  id: string;
  template_id: string;
  version: number;
  template: string;
  changed_at: string;
  change_note?: string;
}

export const aiPromptsService = {
  list: async (): Promise<PromptTemplate[]> => {
    const response = await adminApiClient.get('/admin/ai-prompts');
    return response.data.items ?? response.data;
  },

  get: async (key: string): Promise<PromptTemplate> => {
    const response = await adminApiClient.get(`/admin/ai-prompts/${key}`);
    return response.data;
  },

  update: async (key: string, template: string, changeNote?: string): Promise<PromptTemplate> => {
    const response = await adminApiClient.put(`/admin/ai-prompts/${key}`, {
      template,
      change_note: changeNote,
    });
    return response.data;
  },

  listVersions: async (key: string): Promise<PromptTemplateVersion[]> => {
    const response = await adminApiClient.get(`/admin/ai-prompts/${key}/versions`);
    return response.data.items ?? response.data;
  },

  revert: async (key: string, version: number): Promise<PromptTemplate> => {
    const response = await adminApiClient.post(`/admin/ai-prompts/${key}/revert/${version}`);
    return response.data;
  },

  setTierModel: async (tier: string, model: string): Promise<{ tier: string; model: string }> => {
    const response = await adminApiClient.put(`/admin/ai-prompts/tier/${tier}/model`, { model });
    return response.data;
  },
};

export default {
  adminAuth: adminAuthService,
  providers: providersService,
  tariffs: tariffsService,
  loadShedding: loadSheddingService,
  adminUsers: adminUsersService,
  auditLog: auditLogService,
  aiPrompts: aiPromptsService,
};
