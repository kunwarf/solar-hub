/**
 * API Configuration
 *
 * This module handles API configuration and environment settings.
 * It supports both development and production environments.
 */

export const API_CONFIG = {
  // Base URL for the System A backend API
  baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',

  // WebSocket URL for real-time telemetry
  wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',

  // Enable mock mode when API is unavailable
  useMockFallback: import.meta.env.VITE_USE_MOCK_FALLBACK === 'true' || true,

  // Request timeout in milliseconds
  timeout: 30000,

  // Token storage keys
  tokenKeys: {
    accessToken: 'solar_hub_access_token',
    refreshToken: 'solar_hub_refresh_token',
    user: 'solar_hub_user',
  },

  // API version
  version: 'v1',
};

// API Endpoints mapping
export const API_ENDPOINTS = {
  // Authentication
  auth: {
    login: '/auth/login',
    register: '/auth/register',
    refresh: '/auth/refresh',
    logout: '/auth/logout',
    me: '/auth/me',
    changePassword: '/auth/change-password',
    forgotPassword: '/auth/forgot-password',
    resetPassword: '/auth/reset-password',
    verifyEmail: '/auth/verify-email',
    resendVerification: '/auth/resend-verification',
  },

  // Users
  users: {
    me: '/users/me',
    preferences: '/users/me/preferences',
    list: '/users',
    byId: (id: string) => `/users/${id}`,
    role: (id: string) => `/users/${id}/role`,
    status: (id: string) => `/users/${id}/status`,
  },

  // Organizations
  organizations: {
    create: '/organizations',
    list: '/organizations',
    byId: (id: string) => `/organizations/${id}`,
    members: (id: string) => `/organizations/${id}/members`,
    invite: (id: string) => `/organizations/${id}/invite`,
    acceptInvite: (orgId: string, memberId: string) =>
      `/organizations/${orgId}/members/${memberId}/accept`,
    memberRole: (orgId: string, userId: string) =>
      `/organizations/${orgId}/members/${userId}/role`,
    removeMember: (orgId: string, userId: string) =>
      `/organizations/${orgId}/members/${userId}`,
    transferOwnership: (id: string) => `/organizations/${id}/transfer-ownership`,
  },

  // Sites
  sites: {
    create: '/sites',
    list: '/sites',
    byId: (id: string) => `/sites/${id}`,
    status: (id: string) => `/sites/${id}/status`,
  },

  // Devices
  devices: {
    create: '/devices',
    list: '/devices',
    byId: (id: string) => `/devices/${id}`,
    command: (id: string) => `/devices/${id}/command`,
    snapshot: (id: string) => `/devices/${id}/snapshot`,
    status: (id: string) => `/devices/${id}/status`,
  },

  // Dashboards
  dashboards: {
    overview: '/dashboards/overview',
    organization: '/dashboards/organization',
    site: (siteId: string) => `/dashboards/site/${siteId}`,
    sitePower: (siteId: string) => `/dashboards/site/${siteId}/power`,
    siteEnergy: (siteId: string) => `/dashboards/site/${siteId}/energy`,
    comparison: (siteId: string) => `/dashboards/site/${siteId}/comparison`,
  },

  // Billing
  billing: {
    tariffs: '/billing/tariffs',
    discos: '/billing/tariffs/discos',
    createTariff: '/billing/tariff/create',
    simulate: '/billing/simulate',
    simulations: '/billing/simulations',
    simulationById: (id: string) => `/billing/simulations/${id}`,
    compareTariffs: '/billing/compare-tariffs',
    yearlySummary: (siteId: string) => `/billing/yearly-summary/${siteId}`,
  },

  // Alerts
  alerts: {
    list: '/alerts',
    summary: '/alerts/summary',
    rules: '/alerts/rules',
    ruleById: (id: string) => `/alerts/rules/${id}`,
    toggleRule: (id: string) => `/alerts/rules/${id}/toggle`,
    acknowledge: (id: string) => `/alerts/${id}/acknowledge`,
    resolve: (id: string) => `/alerts/${id}/resolve`,
  },

  // Discovery
  discovery: {
    scanNetwork: '/discovery/scan-network',
    scanHost: '/discovery/scan-host',
    scanStatus: (id: string) => `/discovery/scans/${id}/status`,
    scanResults: (id: string) => `/discovery/scans/${id}/results`,
  },
};

export default API_CONFIG;
