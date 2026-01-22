import { createContext, useContext, useState, ReactNode } from "react";

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

const BillingConfigContext = createContext<BillingConfigContextType | undefined>(undefined);

export function BillingConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<BillingConfig>(defaultConfig);

  const getCurrencySymbol = () => currencySymbols[config.currency] || config.currency;

  const formatCurrency = (value: number) => {
    return `${getCurrencySymbol()}${value.toFixed(2)}`;
  };

  return (
    <BillingConfigContext.Provider value={{ config, setConfig, formatCurrency, getCurrencySymbol }}>
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
