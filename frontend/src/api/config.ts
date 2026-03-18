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
    // Device claiming (proxied to System B)
    claimDevice: (serial: string) => `/auth/devices/claim/${serial}`,
    availableDevices: '/auth/devices/available',
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
    batteryBank: (id: string) => `/devices/${id}/battery/bank`,
    unclaim: (id: string) => `/devices/${id}/unclaim`,
  },

  // Dashboards (legacy - organization/site focused)
  dashboards: {
    overview: '/dashboards/overview',
    organization: '/dashboards/organization',
    site: (siteId: string) => `/dashboards/site/${siteId}`,
    sitePower: (siteId: string) => `/dashboards/site/${siteId}/power`,
    siteEnergy: (siteId: string) => `/dashboards/site/${siteId}/energy`,
    comparison: (siteId: string) => `/dashboards/site/${siteId}/comparison`,
  },

  // Dashboard Widgets (new - device/serial focused, reads from Redis cache)
  dashboard: {
    powerFlow: '/dashboard/power-flow',
    stats: '/dashboard/stats',
    battery: '/dashboard/battery',
    deviceStatus: '/dashboard/device-status',
    alerts: '/dashboard/alerts',
    environmental: '/dashboard/environmental',
    energyChart: '/dashboard/energy-chart',
    comparison: '/dashboard/comparison',
    peakDemand: '/dashboard/peak-demand',
    weather: '/dashboard/weather',
    loadShedding: '/dashboard/load-shedding',
    billing: '/dashboard/billing',
    outages: '/dashboard/outages',
    all: '/dashboard/all',
  },

  // Billing (legacy)
  billing: {
    overview: (siteId: string) => `/billing/sites/${siteId}/overview`,
    history: (siteId: string) => `/billing/sites/${siteId}/history`,
    calculate: '/billing/calculate',
    tariffs: '/billing/tariffs',
    discos: '/billing/tariffs/discos',
    createTariff: '/billing/tariff/create',
    simulate: '/billing/simulate',
    simulations: '/billing/simulations',
    simulationById: (id: string) => `/billing/simulations/${id}`,
    compareTariffs: '/billing/compare-tariffs',
    yearlySummary: (siteId: string) => `/billing/yearly-summary/${siteId}`,
    recalculate: '/billing/recalculate',
  },

  // Net Metering Billing (3-month netting cycle)
  netMetering: {
    // Config
    getConfig: (siteId: string) => `/billing/config/${siteId}`,
    saveConfig: '/billing/config',
    // Running bill (to-date)
    runningBill: '/billing/running',
    // Daily snapshots
    dailySnapshots: '/billing/daily',
    // Billing months
    months: '/billing/months',
    monthById: (id: string) => `/billing/months/${id}`,
    // Billing cycles (3-month)
    cycles: '/billing/cycles',
    cycleById: (id: string) => `/billing/cycles/${id}`,
    closeCycle: '/billing/cycle/close',
    // Summary & trends
    summary: '/billing/summary',
    trend: '/billing/trend',
    yearly: '/billing/yearly',
    // Capacity analysis
    capacityStatus: '/billing/capacity/status',
    // Admin
    backfill: '/billing/admin/backfill',
  },

  // Tariffs (Pakistani DISCO rates)
  tariffs: {
    list: '/tariffs',
    byId: (id: string) => `/tariffs/${id}`,
    byProvider: (provider: string) => `/tariffs/provider/${provider}`,
    netMetering: (provider: string) => `/tariffs/provider/${provider}/net-metering`,
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

  // Admin (System A)
  admin: {
    // Auth
    login: '/admin/auth/login',
    logout: '/admin/auth/logout',
    me: '/admin/auth/me',
    // Providers
    providers: '/admin/providers',
    providerById: (id: string) => `/admin/providers/${id}`,
    // Tariffs
    tariffs: '/admin/tariffs',
    tariffById: (id: string) => `/admin/tariffs/${id}`,
    // Load Shedding
    loadShedding: '/admin/load-shedding',
    loadSheddingById: (id: string) => `/admin/load-shedding/${id}`,
    // Subscription Tiers
    subscriptionTiers: '/admin/subscription-tiers',
    subscriptionTierById: (id: string) => `/admin/subscription-tiers/${id}`,
    // Features
    features: '/admin/features',
    featureById: (id: string) => `/admin/features/${id}`,
    featureTiers: (id: string) => `/admin/features/${id}/tiers`,
    // Device Catalog
    deviceCatalog: '/admin/device-catalog',
    deviceCatalogById: (id: string) => `/admin/device-catalog/${id}`,
    // Protocol Adapters
    protocolAdapters: '/admin/protocol-adapters',
    protocolAdapterById: (id: string) => `/admin/protocol-adapters/${id}`,
    // Weather Stations
    weatherStations: '/admin/weather-stations',
    weatherStationById: (id: string) => `/admin/weather-stations/${id}`,
    // Admin Users
    adminUsers: '/admin/users',
    adminUserById: (id: string) => `/admin/users/${id}`,
    // Audit Log
    auditLog: '/admin/audit-log',
    auditLogById: (id: string) => `/admin/audit-log/${id}`,
  },
};

// System B API Configuration (Telemetry/Device Server)
export const SYSTEM_B_CONFIG = {
  baseUrl: import.meta.env.VITE_SYSTEM_B_API_URL || 'http://localhost:8001/api/v1',
};

// System B API Endpoints
export const SYSTEM_B_ENDPOINTS = {
  devices: {
    bySerial: (serial: string) => `/devices/serial/${serial}`,
    claim: (deviceId: string) => `/devices/${deviceId}/claim`,
    release: (deviceId: string) => `/devices/${deviceId}/release`,
    orphans: '/devices/orphan',
    validateSerial: '/devices/serial/validate',
  },

  // Firmware (OTA Management)
  firmware: {
    // Versions
    versions: '/firmware/versions',
    versionById: (id: string) => `/firmware/versions/${id}`,
    toggleVersion: (id: string) => `/firmware/versions/${id}/toggle`,
    // Files
    files: (versionId: string) => `/firmware/versions/${versionId}/files`,
    fileById: (versionId: string, fileId: string) => `/firmware/versions/${versionId}/files/${fileId}`,
    downloadFile: (versionId: string, fileId: string) => `/firmware/versions/${versionId}/files/${fileId}/download`,
    // Campaigns
    campaigns: '/firmware/campaigns',
    campaignById: (id: string) => `/firmware/campaigns/${id}`,
    activateCampaign: (id: string) => `/firmware/campaigns/${id}/activate`,
    pauseCampaign: (id: string) => `/firmware/campaigns/${id}/pause`,
    resumeCampaign: (id: string) => `/firmware/campaigns/${id}/resume`,
    cancelCampaign: (id: string) => `/firmware/campaigns/${id}/cancel`,
    campaignStatus: (id: string) => `/firmware/campaigns/${id}/status`,
    // Device Status
    deviceStatuses: '/firmware/devices/status',
    deviceStatusBySerial: (serial: string) => `/firmware/devices/${serial}/status`,
    // History
    history: '/firmware/history',
    historyById: (id: string) => `/firmware/history/${id}`,
  },
};

export default API_CONFIG;
