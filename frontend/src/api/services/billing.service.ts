/**
 * Billing Service
 *
 * Handles all billing-related API calls including tariffs, invoices, usage data,
 * and net metering with 3-month netting cycles.
 */

import apiClient from '../client';
import { API_ENDPOINTS } from '../config';
import type { DiscoProviderString } from '../types';

// Use string literal type for DISCO providers
type DiscoProvider = DiscoProviderString;

// =============================================================================
// Net Metering Types (3-month netting cycle)
// =============================================================================

export interface TouWindow {
  start_hour: number;
  end_hour: number;
}

export interface TouConfig {
  peak_windows: TouWindow[];
  timezone: string;
}

export interface BillingPrices {
  price_offpeak_import: number;
  price_peak_import: number;
  price_offpeak_settlement: number;
  price_peak_settlement: number;
  fixed_charge_per_billing_month: number;
}

export interface NetMeteringConfig {
  id: string;
  site_id: string;
  anchor_day: number;
  tou_config: TouConfig;
  prices: BillingPrices;
  fixed_proration_mode: string;
  net_metering_enabled: boolean;
  created_at: string;
  updated_at?: string;
}

export interface NetMeteringConfigCreate {
  site_id: string;
  anchor_day?: number;
  tou_config?: TouConfig;
  prices: BillingPrices;
  fixed_proration_mode?: string;
  net_metering_enabled?: boolean;
}

export interface RunningBill {
  site_id: string;
  date: string;
  billing_month_id?: string;
  billing_period_start: string;
  billing_period_end: string;
  days_elapsed: number;
  total_days_in_month: number;
  progress_percent: number;
  // Energy aggregates
  import_off_kwh: number;
  export_off_kwh: number;
  import_peak_kwh: number;
  export_peak_kwh: number;
  solar_generation_kwh: number;
  load_consumption_kwh: number;
  // Net import after credits
  net_import_off_kwh: number;
  net_import_peak_kwh: number;
  // Credit pools
  credits_off_cycle_kwh_balance: number;
  credits_peak_cycle_kwh_balance: number;
  // Bill components
  bill_off_energy_rs: number;
  bill_peak_energy_rs: number;
  fixed_prorated_rs: number;
  expected_cycle_credit_rs: number;
  // Totals
  bill_raw_rs_to_date: number;
  bill_credit_balance_rs_to_date: number;
  bill_final_rs_to_date: number;
  // Position
  surplus_deficit_flag: 'SURPLUS' | 'DEFICIT' | 'NEUTRAL';
  net_kwh_position: number;
  generated_at: string;
}

export interface DailySnapshot {
  id: string;
  site_id: string;
  date: string;
  billing_month_id?: string;
  import_off_kwh: number;
  export_off_kwh: number;
  import_peak_kwh: number;
  export_peak_kwh: number;
  solar_generation_kwh: number;
  load_consumption_kwh: number;
  bill_final_rs_to_date: number;
  surplus_deficit_flag: string;
  net_kwh_position: number;
  generated_at: string;
}

export interface BillingMonth {
  id: string;
  site_id: string;
  billing_cycle_id?: string;
  billing_month_number: number;
  year: number;
  period_start_date: string;
  period_end_date: string;
  // Energy
  import_off_kwh: number;
  export_off_kwh: number;
  import_peak_kwh: number;
  export_peak_kwh: number;
  solar_generation_kwh: number;
  load_consumption_kwh: number;
  net_import_off_kwh: number;
  net_import_peak_kwh: number;
  // Credits
  credits_applied_off_kwh: number;
  credits_applied_peak_kwh: number;
  credits_generated_off_kwh: number;
  credits_generated_peak_kwh: number;
  // Bill components
  bill_off_energy_rs: number;
  bill_peak_energy_rs: number;
  bill_fixed_rs: number;
  cycle_settlement_off_rs: number;
  cycle_settlement_peak_rs: number;
  // Totals
  bill_raw_rs: number;
  opening_credit_balance_rs: number;
  closing_credit_balance_rs: number;
  bill_final_rs: number;
  // Status
  status: string;
  is_cycle_end_month: boolean;
  finalized_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface BillingCycle {
  id: string;
  site_id: string;
  cycle_number: number;
  year: number;
  cycle_start_date: string;
  cycle_end_date: string;
  // Opening balances
  opening_credit_off_kwh: number;
  opening_credit_peak_kwh: number;
  opening_cash_credit_rs: number;
  // Cumulative energy
  total_import_off_kwh: number;
  total_export_off_kwh: number;
  total_import_peak_kwh: number;
  total_export_peak_kwh: number;
  // Credits
  credits_generated_off_kwh: number;
  credits_consumed_off_kwh: number;
  credits_generated_peak_kwh: number;
  credits_consumed_peak_kwh: number;
  closing_credit_off_kwh: number;
  closing_credit_peak_kwh: number;
  // Settlement
  settlement_off_rs: number;
  settlement_peak_rs: number;
  total_settlement_rs: number;
  closing_cash_credit_rs: number;
  // Status
  status: string;
  finalized_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface BillingSummary {
  billing_month: number;
  year: number;
  billing_period_start: string;
  billing_period_end: string;
  import_off_kwh: number;
  import_peak_kwh: number;
  export_off_kwh: number;
  export_peak_kwh: number;
  fixed_charge: number;
  bill_amount: number;
  credit_balance: number;
  days_elapsed: number;
  days_remaining: number;
  progress_percent: number;
  estimated_savings_month: number;
  total_savings_since_install: number;
}

export interface BillingTrendItem {
  year: number;
  month: number;
  period_start: string;
  period_end: string;
  import_off_kwh: number;
  import_peak_kwh: number;
  export_off_kwh: number;
  export_peak_kwh: number;
  bill_final_rs: number;
  status: string;
}

export interface CapacityStatus {
  site_id: string;
  installed_kw: number;
  required_kw_for_zero_bill: number;
  deficit_kw: number;
  status: 'under-capacity' | 'over-capacity' | 'balanced';
  annual_bill_rs: number;
  annual_import_kwh: number;
  annual_export_kwh: number;
  annual_solar_kwh: number;
  months_with_positive_bill: number;
}

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

  // ===========================================================================
  // Net Metering Billing Methods (3-month netting cycle)
  // ===========================================================================

  /**
   * Get net metering billing configuration for a site
   */
  async getNetMeteringConfig(siteId: string): Promise<NetMeteringConfig> {
    const response = await apiClient.get<NetMeteringConfig>(
      API_ENDPOINTS.netMetering.getConfig(siteId)
    );
    return response.data;
  }

  /**
   * Create or update net metering billing configuration
   */
  async saveNetMeteringConfig(config: NetMeteringConfigCreate): Promise<NetMeteringConfig> {
    const response = await apiClient.post<NetMeteringConfig>(
      API_ENDPOINTS.netMetering.saveConfig,
      config
    );
    return response.data;
  }

  /**
   * Get running bill (month-to-date)
   */
  async getRunningBill(siteId: string, asOfDate?: string): Promise<RunningBill> {
    const params: Record<string, string> = { site_id: siteId };
    if (asOfDate) params.as_of_date = asOfDate;

    const response = await apiClient.get<RunningBill>(
      API_ENDPOINTS.netMetering.runningBill,
      { params }
    );
    return response.data;
  }

  /**
   * Get daily billing snapshots
   */
  async getDailySnapshots(
    siteId: string,
    startDate?: string,
    endDate?: string,
    limit?: number
  ): Promise<{ snapshots: DailySnapshot[]; total: number }> {
    const params: Record<string, string | number> = { site_id: siteId };
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    if (limit) params.limit = limit;

    const response = await apiClient.get<{ snapshots: DailySnapshot[]; total: number }>(
      API_ENDPOINTS.netMetering.dailySnapshots,
      { params }
    );
    return response.data;
  }

  /**
   * Get billing months history
   */
  async getBillingMonths(
    siteId: string,
    limit?: number
  ): Promise<{ months: BillingMonth[]; total: number }> {
    const params: Record<string, string | number> = { site_id: siteId };
    if (limit) params.limit = limit;

    const response = await apiClient.get<{ months: BillingMonth[]; total: number }>(
      API_ENDPOINTS.netMetering.months,
      { params }
    );
    return response.data;
  }

  /**
   * Get billing cycles (3-month periods)
   */
  async getBillingCycles(
    siteId: string,
    limit?: number
  ): Promise<{ cycles: BillingCycle[]; total: number }> {
    const params: Record<string, string | number> = { site_id: siteId };
    if (limit) params.limit = limit;

    const response = await apiClient.get<{ cycles: BillingCycle[]; total: number }>(
      API_ENDPOINTS.netMetering.cycles,
      { params }
    );
    return response.data;
  }

  /**
   * Get current billing month summary
   */
  async getBillingSummary(siteId: string): Promise<BillingSummary> {
    const response = await apiClient.get<BillingSummary>(
      API_ENDPOINTS.netMetering.summary,
      { params: { site_id: siteId } }
    );
    return response.data;
  }

  /**
   * Get billing trend (multiple months)
   */
  async getBillingTrend(
    siteId: string,
    months?: number
  ): Promise<{ trend: BillingTrendItem[]; months: number }> {
    const params: Record<string, string | number> = { site_id: siteId };
    if (months) params.months = months;

    const response = await apiClient.get<{ trend: BillingTrendItem[]; months: number }>(
      API_ENDPOINTS.netMetering.trend,
      { params }
    );
    return response.data;
  }

  /**
   * Get capacity analysis (under/over-capacity)
   */
  async getCapacityStatus(siteId: string): Promise<CapacityStatus> {
    const response = await apiClient.get<CapacityStatus>(
      API_ENDPOINTS.netMetering.capacityStatus,
      { params: { site_id: siteId } }
    );
    return response.data;
  }

  /**
   * Force-close a billing cycle
   */
  async closeBillingCycle(cycleId: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post<{ success: boolean; message: string }>(
      API_ENDPOINTS.netMetering.closeCycle,
      { cycle_id: cycleId }
    );
    return response.data;
  }

  /**
   * Recalculate billing for a specific period
   * Deletes old billing records so they can be regenerated with timezone-aware data
   */
  async recalculateBilling(params: {
    site_id: string;
    period_start: string;
    period_end: string;
  }): Promise<{ status: string; deleted_count: number; message: string }> {
    const response = await apiClient.post<{ status: string; deleted_count: number; message: string }>(
      API_ENDPOINTS.billing.recalculate,
      null,
      { params }
    );
    return response.data;
  }
}

export const billingService = new BillingService();
export default billingService;
