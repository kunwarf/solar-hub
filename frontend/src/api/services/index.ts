/**
 * API Services Index
 *
 * Centralized export of all API services.
 */

export { authService } from './auth.service';
export { dashboardService } from './dashboard.service';
export { devicesService } from './devices.service';
export { sitesService } from './sites.service';
export { billingService } from './billing.service';
export type { BillingOverview, BillCalculation } from './billing.service';
export { alertsService } from './alerts.service';
export type { UIAlert, AlertFilters } from './alerts.service';

// Re-export types
export * from '../types';
