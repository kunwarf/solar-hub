import React, { createContext, useContext, useState, useEffect, ReactNode, useMemo } from 'react';
import { 
  TariffConfig, 
  BillBreakdown, 
  getDefaultTariffConfig, 
  calculateBill,
  DiscoCode,
  ConsumerCategory,
  ResidentialSubcategory,
  ConnectionType,
} from '@/data/pakistanTariffs';

interface TariffContextType {
  config: TariffConfig;
  updateConfig: (updates: Partial<TariffConfig>) => void;
  resetConfig: () => void;
  calculateMonthlyBill: (unitsConsumed: number, unitsExported?: number) => BillBreakdown;
  
  // Quick setters
  setDisco: (disco: DiscoCode) => void;
  setConsumerCategory: (category: ConsumerCategory) => void;
  setResidentialSubcategory: (subcategory: ResidentialSubcategory) => void;
  setConnectionType: (type: ConnectionType) => void;
  setSanctionedLoad: (load: number) => void;
  setNetMeteringEnabled: (enabled: boolean) => void;
  setFuelPriceAdjustment: (fpa: number) => void;
  setQuarterlyTariffAdjustment: (qta: number) => void;
}

const STORAGE_KEY = 'pakistan-tariff-config';

const TariffContext = createContext<TariffContextType | undefined>(undefined);

export const TariffProvider = ({ children }: { children: ReactNode }) => {
  const [config, setConfig] = useState<TariffConfig>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        return { ...getDefaultTariffConfig(), ...JSON.parse(saved) };
      } catch {
        return getDefaultTariffConfig();
      }
    }
    return getDefaultTariffConfig();
  });

  // Save to localStorage on changes
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  }, [config]);

  const updateConfig = (updates: Partial<TariffConfig>) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };

  const resetConfig = () => {
    const defaultConfig = getDefaultTariffConfig();
    setConfig(defaultConfig);
    localStorage.removeItem(STORAGE_KEY);
  };

  const calculateMonthlyBill = (unitsConsumed: number, unitsExported: number = 0): BillBreakdown => {
    return calculateBill(unitsConsumed, unitsExported, config);
  };

  // Quick setters
  const setDisco = (disco: DiscoCode) => updateConfig({ disco });
  const setConsumerCategory = (category: ConsumerCategory) => {
    updateConfig({ 
      consumerCategory: category,
      residentialSubcategory: category === 'residential' ? 'protected' : undefined,
    });
  };
  const setResidentialSubcategory = (subcategory: ResidentialSubcategory) => updateConfig({ residentialSubcategory: subcategory });
  const setConnectionType = (type: ConnectionType) => updateConfig({ connectionType: type });
  const setSanctionedLoad = (load: number) => updateConfig({ sanctionedLoad: load });
  const setNetMeteringEnabled = (enabled: boolean) => updateConfig({ netMeteringEnabled: enabled });
  const setFuelPriceAdjustment = (fpa: number) => updateConfig({ fuelPriceAdjustment: fpa });
  const setQuarterlyTariffAdjustment = (qta: number) => updateConfig({ quarterlyTariffAdjustment: qta });

  const value = useMemo(() => ({
    config,
    updateConfig,
    resetConfig,
    calculateMonthlyBill,
    setDisco,
    setConsumerCategory,
    setResidentialSubcategory,
    setConnectionType,
    setSanctionedLoad,
    setNetMeteringEnabled,
    setFuelPriceAdjustment,
    setQuarterlyTariffAdjustment,
  }), [config]);

  return (
    <TariffContext.Provider value={value}>
      {children}
    </TariffContext.Provider>
  );
};

export const useTariff = () => {
  const context = useContext(TariffContext);
  if (!context) {
    throw new Error('useTariff must be used within a TariffProvider');
  }
  return context;
};
