import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { billingService } from "@/api/services/billing.service";
import type { NetMeteringConfig, NetMeteringConfigCreate } from "@/api/services/billing.service";

interface PeakWindow {
  id: string;
  start: string;
  end: string;
}

interface BillingConfig {
  currency: string;
  anchorDay: number;
  offPeakPrice: number;
  peakPrice: number;
  offPeakSettlement: number;
  peakSettlement: number;
  peakWindows: PeakWindow[];
  fixedCharge: number;
  forecastMethod: string;
  lookbackMonths: number;
  defaultMonthsAhead: number;
}

interface BillingConfigContextType {
  config: BillingConfig;
  setConfig: React.Dispatch<React.SetStateAction<BillingConfig>>;
  formatCurrency: (value: number) => string;
  getCurrencySymbol: () => string;
  // Backend sync
  loadFromBackend: (siteId: string) => Promise<void>;
  saveToBackend: (siteId: string) => Promise<NetMeteringConfig>;
  isSyncing: boolean;
  lastSyncedAt: Date | null;
}

const defaultConfig: BillingConfig = {
  currency: "PKR",
  anchorDay: 16,
  offPeakPrice: 50,
  peakPrice: 60,
  offPeakSettlement: 22,
  peakSettlement: 22,
  peakWindows: [{ id: "1", start: "17:00", end: "22:00" }],
  fixedCharge: 1000,
  forecastMethod: "trend",
  lookbackMonths: 12,
  defaultMonthsAhead: 1,
};

const currencySymbols: Record<string, string> = {
  PKR: "₨",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

// Convert time string "HH:MM" to hour number
function timeToHour(time: string): number {
  const [hours] = time.split(":").map(Number);
  return hours;
}

// Convert hour number to time string "HH:00"
function hourToTime(hour: number): string {
  return `${hour.toString().padStart(2, "0")}:00`;
}

// Convert backend config to frontend format
function backendToFrontend(backendConfig: NetMeteringConfig): BillingConfig {
  return {
    currency: "PKR", // Default, not stored in backend
    anchorDay: backendConfig.anchor_day,
    offPeakPrice: backendConfig.prices.price_offpeak_import,
    peakPrice: backendConfig.prices.price_peak_import,
    offPeakSettlement: backendConfig.prices.price_offpeak_settlement,
    peakSettlement: backendConfig.prices.price_peak_settlement,
    peakWindows: backendConfig.tou_config.peak_windows.map((w, i) => ({
      id: (i + 1).toString(),
      start: hourToTime(w.start_hour),
      end: hourToTime(w.end_hour),
    })),
    fixedCharge: backendConfig.prices.fixed_charge_per_billing_month,
    forecastMethod: "trend",
    lookbackMonths: 12,
    defaultMonthsAhead: 1,
  };
}

// Convert frontend config to backend format
function frontendToBackend(frontendConfig: BillingConfig, siteId: string): NetMeteringConfigCreate {
  return {
    site_id: siteId,
    anchor_day: frontendConfig.anchorDay,
    tou_config: {
      peak_windows: frontendConfig.peakWindows.map((w) => ({
        start_hour: timeToHour(w.start),
        end_hour: timeToHour(w.end),
      })),
      timezone: "Asia/Karachi",
    },
    prices: {
      price_offpeak_import: frontendConfig.offPeakPrice,
      price_peak_import: frontendConfig.peakPrice,
      price_offpeak_settlement: frontendConfig.offPeakSettlement,
      price_peak_settlement: frontendConfig.peakSettlement,
      fixed_charge_per_billing_month: frontendConfig.fixedCharge,
    },
    fixed_proration_mode: "none",
    net_metering_enabled: true,
  };
}

const BillingConfigContext = createContext<BillingConfigContextType | undefined>(undefined);

export function BillingConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<BillingConfig>(defaultConfig);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null);

  const getCurrencySymbol = () => currencySymbols[config.currency] || config.currency;

  const formatCurrency = (value: number) => {
    return `${getCurrencySymbol()}${value.toFixed(2)}`;
  };

  const loadFromBackend = useCallback(async (siteId: string) => {
    setIsSyncing(true);
    try {
      const backendConfig = await billingService.getNetMeteringConfig(siteId);
      setConfig(backendToFrontend(backendConfig));
      setLastSyncedAt(new Date());
    } catch (err) {
      // Config might not exist yet, use defaults
      console.log("No billing config found, using defaults");
    } finally {
      setIsSyncing(false);
    }
  }, []);

  const saveToBackend = useCallback(
    async (siteId: string): Promise<NetMeteringConfig> => {
      setIsSyncing(true);
      try {
        const backendConfig = frontendToBackend(config, siteId);
        const result = await billingService.saveNetMeteringConfig(backendConfig);
        setLastSyncedAt(new Date());
        return result;
      } finally {
        setIsSyncing(false);
      }
    },
    [config]
  );

  return (
    <BillingConfigContext.Provider
      value={{
        config,
        setConfig,
        formatCurrency,
        getCurrencySymbol,
        loadFromBackend,
        saveToBackend,
        isSyncing,
        lastSyncedAt,
      }}
    >
      {children}
    </BillingConfigContext.Provider>
  );
}

export function useBillingConfig() {
  const context = useContext(BillingConfigContext);
  if (context === undefined) {
    throw new Error("useBillingConfig must be used within a BillingConfigProvider");
  }
  return context;
}

export { defaultConfig };
export type { BillingConfig, PeakWindow };
