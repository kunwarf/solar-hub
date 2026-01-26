/**
 * Billing Service
 *
 * Handles all billing-related API calls including tariffs, invoices, and usage data.
 */

import apiClient from '../client';
import { API_ENDPOINTS } from '../config';
import type { DiscoProviderString } from '../types';

// Use string literal type for DISCO providers
type DiscoProvider = DiscoProviderString;

// Local TariffPlan interface for billing service
interface TariffSlab {
  from_kwh: number;
  to_kwh: number | null;
  rate_per_kwh: number;
  fixed_charge: number;
}

export interface TariffPlan {
  id: string;
  provider: DiscoProvider;
  category: string;
  name: string;
  description?: string;
  slabs: TariffSlab[];
  peak_rate?: number;
  off_peak_rate?: number;
  fuel_adjustment?: number;
  taxes_percent?: number;
  effective_from: string;
  effective_to?: string;
  is_active: boolean;
}

export interface BillingOverview {
  currentPeriod: {
    id: string;
    site_id: string;
    start_date: string;
    end_date: string;
    days_remaining: number;
    status: 'active' | 'closed' | 'pending';
  };
  energyProduced: number;
  energyConsumed: number;
  energyExported: number;
  energyImported: number;
  feedInRate: number;
  importRate: number;
  earnings: number;
  costs: number;
  netBalance: number;
  monthlyHistory: Array<{
    month: string;
    produced: number;
    consumed: number;
    exported: number;
    imported: number;
    earnings: number;
    costs: number;
    netBalance: number;
    lastYearBill: number;
    thisYearBill: number;
  }>;
}

export interface BillCalculation {
  consumption_kwh: number;
  base_amount: number;
  fuel_adjustment: number;
  taxes: number;
  fixed_charges: number;
  total_amount: number;
  export_credit: number;
  net_payable: number;
  breakdown: Array<{
    slab: string;
    units: number;
    rate: number;
    amount: number;
  }>;
}

class BillingService {
  /**
   * Get billing overview for a site
   */
  async getBillingOverview(siteId?: string): Promise<BillingOverview> {
    const response = await apiClient.get<BillingOverview>(
      API_ENDPOINTS.billing.overview(siteId || 'default')
    );
    return response.data;
  }

  /**
   * Get tariff plans for a DISCO provider
   */
  async getTariffPlans(provider: DiscoProvider): Promise<TariffPlan[]> {
    const response = await apiClient.get<TariffPlan[]>(
      API_ENDPOINTS.tariffs.byProvider(provider)
    );
    return response.data;
  }

  /**
   * Get all available tariff plans
   */
  async getAllTariffPlans(): Promise<TariffPlan[]> {
    const response = await apiClient.get<TariffPlan[]>(API_ENDPOINTS.tariffs.list);
    return response.data;
  }

  /**
   * Get net metering rates for a provider
   */
  async getNetMeteringRates(provider: DiscoProvider): Promise<{ export_rate: number; buy_back_rate: number }> {
    const response = await apiClient.get<{ export_rate: number; buy_back_rate: number }>(
      API_ENDPOINTS.tariffs.netMetering(provider)
    );
    return response.data;
  }

  /**
   * Calculate bill amount based on consumption and tariff
   */
  async calculateBill(params: {
    provider: DiscoProvider;
    tariff_category: string;
    consumption_kwh: number;
    export_kwh?: number;
  }): Promise<BillCalculation> {
    const response = await apiClient.post<BillCalculation>(
      API_ENDPOINTS.billing.calculate,
      params
    );
    return response.data;
  }

  /**
   * Get billing history for a site
   */
  async getBillingHistory(siteId?: string, months?: number): Promise<BillingOverview['monthlyHistory']> {
    const overview = await this.getBillingOverview(siteId);
    const history = overview.monthlyHistory;

    if (months && months < history.length) {
      return history.slice(-months);
    }

    return history;
  }
}

export const billingService = new BillingService();
export default billingService;
