/**
 * Billing Service
 *
 * Handles all billing-related API calls including tariffs, invoices, and usage data.
 * Falls back to mock data when API is unavailable.
 */

import apiClient, { checkApiHealth } from '../client';
import { API_CONFIG, API_ENDPOINTS } from '../config';
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

// Mock billing data
const mockBillingData = {
  currentPeriod: {
    id: 'period-001',
    site_id: 'site-001',
    start_date: '2024-11-01',
    end_date: '2024-11-30',
    days_remaining: 12,
    status: 'active' as const,
  },
  energyProduced: 1284.6,
  energyConsumed: 892.4,
  energyExported: 392.2,
  energyImported: 124.8,
  feedInRate: 22,
  importRate: 50,
  earnings: 8628.84, // PKR
  costs: 6240.00, // PKR
  netBalance: 2388.84, // PKR (positive = credit)
  monthlyHistory: [
    { month: 'Jun', produced: 1456, consumed: 780, exported: 676, imported: 98, earnings: 14872, costs: 4900, netBalance: 9972, lastYearBill: 8500, thisYearBill: 4900 },
    { month: 'Jul', produced: 1589, consumed: 820, exported: 769, imported: 112, earnings: 16918, costs: 5600, netBalance: 11318, lastYearBill: 9200, thisYearBill: 5600 },
    { month: 'Aug', produced: 1423, consumed: 856, exported: 567, imported: 134, earnings: 12474, costs: 6700, netBalance: 5774, lastYearBill: 9800, thisYearBill: 6700 },
    { month: 'Sep', produced: 1234, consumed: 890, exported: 344, imported: 156, earnings: 7568, costs: 7800, netBalance: -232, lastYearBill: 10500, thisYearBill: 7800 },
    { month: 'Oct', produced: 1089, consumed: 912, exported: 177, imported: 189, earnings: 3894, costs: 9450, netBalance: -5556, lastYearBill: 11200, thisYearBill: 9450 },
    { month: 'Nov', produced: 1284, consumed: 892, exported: 392, imported: 125, earnings: 8628, costs: 6240, netBalance: 2388, lastYearBill: 10800, thisYearBill: 6240 },
  ],
};

// Pakistani DISCO tariff rates
const mockTariffPlans: Record<DiscoProvider, TariffPlan[]> = {
  lesco: [
    {
      id: 'lesco-residential-protected',
      provider: 'lesco',
      category: 'residential_protected',
      name: 'LESCO Residential Protected',
      description: 'Protected consumer rate for residential use up to 200 units',
      slabs: [
        { from_kwh: 0, to_kwh: 100, rate_per_kwh: 7.74, fixed_charge: 75 },
        { from_kwh: 100, to_kwh: 200, rate_per_kwh: 10.06, fixed_charge: 75 },
      ],
      fuel_adjustment: 3.23,
      taxes_percent: 17,
      effective_from: '2024-01-01',
      is_active: true,
    },
    {
      id: 'lesco-residential-unprotected',
      provider: 'lesco',
      category: 'residential_unprotected',
      name: 'LESCO Residential Unprotected',
      description: 'General residential rate above 200 units',
      slabs: [
        { from_kwh: 0, to_kwh: 200, rate_per_kwh: 27.00, fixed_charge: 150 },
        { from_kwh: 200, to_kwh: 300, rate_per_kwh: 32.00, fixed_charge: 150 },
        { from_kwh: 300, to_kwh: 700, rate_per_kwh: 37.00, fixed_charge: 200 },
        { from_kwh: 700, to_kwh: null, rate_per_kwh: 44.00, fixed_charge: 250 },
      ],
      fuel_adjustment: 3.23,
      taxes_percent: 17,
      effective_from: '2024-01-01',
      is_active: true,
    },
    {
      id: 'lesco-commercial-a1',
      provider: 'lesco',
      category: 'commercial_a1',
      name: 'LESCO Commercial A-1',
      description: 'Commercial connections up to 5kW',
      slabs: [
        { from_kwh: 0, to_kwh: null, rate_per_kwh: 40.52, fixed_charge: 400 },
      ],
      peak_rate: 46.00,
      off_peak_rate: 34.00,
      fuel_adjustment: 3.23,
      taxes_percent: 17,
      effective_from: '2024-01-01',
      is_active: true,
    },
  ],
  kesco: [
    {
      id: 'kesco-residential',
      provider: 'kesco',
      category: 'residential_protected',
      name: 'KESCO Residential',
      description: 'Karachi residential tariff',
      slabs: [
        { from_kwh: 0, to_kwh: 100, rate_per_kwh: 7.74, fixed_charge: 75 },
        { from_kwh: 100, to_kwh: 200, rate_per_kwh: 10.06, fixed_charge: 75 },
      ],
      fuel_adjustment: 3.50,
      taxes_percent: 17,
      effective_from: '2024-01-01',
      is_active: true,
    },
  ],
  iesco: [
    {
      id: 'iesco-residential',
      provider: 'iesco',
      category: 'residential_protected',
      name: 'IESCO Residential',
      description: 'Islamabad residential tariff',
      slabs: [
        { from_kwh: 0, to_kwh: 100, rate_per_kwh: 7.74, fixed_charge: 75 },
        { from_kwh: 100, to_kwh: 200, rate_per_kwh: 10.06, fixed_charge: 75 },
      ],
      fuel_adjustment: 3.23,
      taxes_percent: 17,
      effective_from: '2024-01-01',
      is_active: true,
    },
  ],
  gepco: [],
  fesco: [],
  mepco: [],
  pesco: [],
  hesco: [],
  sepco: [],
  qesco: [],
  tesco: [],
};

// Net metering rates
const netMeteringRates: Record<DiscoProvider, { export_rate: number; buy_back_rate: number }> = {
  lesco: { export_rate: 22.0, buy_back_rate: 20.0 },
  kesco: { export_rate: 21.5, buy_back_rate: 19.5 },
  iesco: { export_rate: 22.0, buy_back_rate: 20.0 },
  gepco: { export_rate: 21.0, buy_back_rate: 19.0 },
  fesco: { export_rate: 21.0, buy_back_rate: 19.0 },
  mepco: { export_rate: 21.0, buy_back_rate: 19.0 },
  pesco: { export_rate: 20.5, buy_back_rate: 18.5 },
  hesco: { export_rate: 20.0, buy_back_rate: 18.0 },
  sepco: { export_rate: 20.0, buy_back_rate: 18.0 },
  qesco: { export_rate: 19.5, buy_back_rate: 17.5 },
  tesco: { export_rate: 20.0, buy_back_rate: 18.0 },
};

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
  private apiAvailable: boolean | null = null;

  private async isApiAvailable(): Promise<boolean> {
    if (this.apiAvailable !== null) {
      return this.apiAvailable;
    }
    this.apiAvailable = await checkApiHealth();
    setTimeout(() => {
      this.apiAvailable = null;
    }, 30000);
    return this.apiAvailable;
  }

  /**
   * Get billing overview for a site
   */
  async getBillingOverview(siteId?: string): Promise<BillingOverview> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<BillingOverview>(
          API_ENDPOINTS.billing.overview(siteId || 'default')
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch billing overview, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      return mockBillingData;
    }

    throw new Error('API unavailable');
  }

  /**
   * Get tariff plans for a DISCO provider
   */
  async getTariffPlans(provider: DiscoProvider): Promise<TariffPlan[]> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<TariffPlan[]>(
          API_ENDPOINTS.tariffs.byProvider(provider)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch tariff plans, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      return mockTariffPlans[provider] || [];
    }

    throw new Error('API unavailable');
  }

  /**
   * Get all available tariff plans
   */
  async getAllTariffPlans(): Promise<TariffPlan[]> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<TariffPlan[]>(API_ENDPOINTS.tariffs.list);
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch all tariff plans, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      return Object.values(mockTariffPlans).flat();
    }

    throw new Error('API unavailable');
  }

  /**
   * Get net metering rates for a provider
   */
  async getNetMeteringRates(provider: DiscoProvider): Promise<{ export_rate: number; buy_back_rate: number }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<{ export_rate: number; buy_back_rate: number }>(
          API_ENDPOINTS.tariffs.netMetering(provider)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch net metering rates, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      return netMeteringRates[provider] || { export_rate: 20.0, buy_back_rate: 18.0 };
    }

    throw new Error('API unavailable');
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
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.post<BillCalculation>(
          API_ENDPOINTS.billing.calculate,
          params
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to calculate bill via API, using local calculation:', error);
      }
    }

    // Mock fallback - local calculation
    if (API_CONFIG.useMockFallback) {
      return this.calculateBillLocally(params);
    }

    throw new Error('API unavailable');
  }

  /**
   * Local bill calculation (fallback)
   */
  private calculateBillLocally(params: {
    provider: DiscoProvider;
    tariff_category: string;
    consumption_kwh: number;
    export_kwh?: number;
  }): BillCalculation {
    const tariffs = mockTariffPlans[params.provider] || [];
    const tariff = tariffs.find(t => t.category === params.tariff_category) || tariffs[0];

    if (!tariff) {
      return {
        consumption_kwh: params.consumption_kwh,
        base_amount: params.consumption_kwh * 30,
        fuel_adjustment: params.consumption_kwh * 3.23,
        taxes: params.consumption_kwh * 30 * 0.17,
        fixed_charges: 150,
        total_amount: params.consumption_kwh * 30 * 1.17 + 150,
        export_credit: (params.export_kwh || 0) * 22,
        net_payable: params.consumption_kwh * 30 * 1.17 + 150 - (params.export_kwh || 0) * 22,
        breakdown: [],
      };
    }

    let remaining = params.consumption_kwh;
    let baseAmount = 0;
    const breakdown: Array<{ slab: string; units: number; rate: number; amount: number }> = [];

    for (const slab of tariff.slabs) {
      if (remaining <= 0) break;

      const slabMax = slab.to_kwh !== null ? slab.to_kwh - slab.from_kwh : remaining;
      const units = Math.min(remaining, slabMax);
      const amount = units * slab.rate_per_kwh;

      breakdown.push({
        slab: slab.to_kwh !== null ? `${slab.from_kwh}-${slab.to_kwh}` : `${slab.from_kwh}+`,
        units,
        rate: slab.rate_per_kwh,
        amount,
      });

      baseAmount += amount;
      remaining -= units;
    }

    const fuelAdjustment = params.consumption_kwh * (tariff.fuel_adjustment || 3.23);
    const taxes = baseAmount * ((tariff.taxes_percent || 17) / 100);
    const fixedCharges = tariff.slabs[0]?.fixed_charge || 150;
    const totalAmount = baseAmount + fuelAdjustment + taxes + fixedCharges;

    const rates = netMeteringRates[params.provider];
    const exportCredit = (params.export_kwh || 0) * rates.export_rate;
    const netPayable = Math.max(0, totalAmount - exportCredit);

    return {
      consumption_kwh: params.consumption_kwh,
      base_amount: baseAmount,
      fuel_adjustment: fuelAdjustment,
      taxes,
      fixed_charges: fixedCharges,
      total_amount: totalAmount,
      export_credit: exportCredit,
      net_payable: netPayable,
      breakdown,
    };
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
