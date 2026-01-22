import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export interface WizardData {
  // Profile
  firstName: string;
  lastName: string;
  city: string;
  contactPreference: 'email' | 'sms' | 'whatsapp';
  
  // Device
  deviceCode: string;
  deviceConnected: boolean;
  
  // Tariff
  disco: string;
  
  // Goal
  monthlyGoal: number;
  
  // Progress
  currentStep: number;
  completed: boolean;
  tourCompleted: boolean;
}

interface SetupWizardContextType {
  isOpen: boolean;
  data: WizardData;
  currentStep: number;
  totalSteps: number;
  openWizard: () => void;
  closeWizard: () => void;
  nextStep: () => void;
  prevStep: () => void;
  goToStep: (step: number) => void;
  updateData: (updates: Partial<WizardData>) => void;
  completeWizard: () => void;
  resetWizard: () => void;
  shouldShowWizard: boolean;
  startTour: () => void;
  endTour: () => void;
  isTourActive: boolean;
}

const defaultData: WizardData = {
  firstName: '',
  lastName: '',
  city: '',
  contactPreference: 'email',
  deviceCode: '',
  deviceConnected: false,
  disco: '',
  monthlyGoal: 10000,
  currentStep: 0,
  completed: false,
  tourCompleted: false,
};

const STORAGE_KEY = 'solar-setup-wizard';

const SetupWizardContext = createContext<SetupWizardContextType | undefined>(undefined);

export const SetupWizardProvider = ({ children }: { children: ReactNode }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [data, setData] = useState<WizardData>(defaultData);
  const [isTourActive, setIsTourActive] = useState(false);
  const totalSteps = 7;

  // Load saved progress on mount
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setData(parsed);
      } catch {
        // Invalid data, use defaults
      }
    }
  }, []);

  // Save progress on data change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }, [data]);

  // Check if wizard should show for new users
  const shouldShowWizard = !data.completed;

  const openWizard = () => setIsOpen(true);
  const closeWizard = () => setIsOpen(false);

  const nextStep = () => {
    if (data.currentStep < totalSteps - 1) {
      setData(prev => ({ ...prev, currentStep: prev.currentStep + 1 }));
    }
  };

  const prevStep = () => {
    if (data.currentStep > 0) {
      setData(prev => ({ ...prev, currentStep: prev.currentStep - 1 }));
    }
  };

  const goToStep = (step: number) => {
    if (step >= 0 && step < totalSteps) {
      setData(prev => ({ ...prev, currentStep: step }));
    }
  };

  const updateData = (updates: Partial<WizardData>) => {
    setData(prev => ({ ...prev, ...updates }));
  };

  const completeWizard = () => {
    setData(prev => ({ ...prev, completed: true, tourCompleted: true }));
    setIsOpen(false);
    setIsTourActive(false);
  };

  const resetWizard = () => {
    setData(defaultData);
    localStorage.removeItem(STORAGE_KEY);
  };

  const startTour = () => setIsTourActive(true);
  const endTour = () => {
    setIsTourActive(false);
    completeWizard();
  };

  return (
    <SetupWizardContext.Provider
      value={{
        isOpen,
        data,
        currentStep: data.currentStep,
        totalSteps,
        openWizard,
        closeWizard,
        nextStep,
        prevStep,
        goToStep,
        updateData,
        completeWizard,
        resetWizard,
        shouldShowWizard,
        startTour,
        endTour,
        isTourActive,
      }}
    >
      {children}
    </SetupWizardContext.Provider>
  );
};

export const useSetupWizard = () => {
  const context = useContext(SetupWizardContext);
  if (!context) {
    throw new Error('useSetupWizard must be used within a SetupWizardProvider');
  }
  return context;
};
