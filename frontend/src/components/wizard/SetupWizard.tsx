import { Dialog, DialogContent } from '@/components/ui/dialog';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import WizardProgress from './WizardProgress';
import WelcomeStep from './steps/WelcomeStep';
import ProfileStep from './steps/ProfileStep';
import DeviceStep from './steps/DeviceStep';
import ConnectionTestStep from './steps/ConnectionTestStep';
import TariffStep from './steps/TariffStep';
import GoalStep from './steps/GoalStep';
import DashboardTourStep from './steps/DashboardTourStep';
import { 
  Sparkles, 
  User, 
  Smartphone, 
  Wifi, 
  Receipt, 
  Target, 
  LayoutDashboard 
} from 'lucide-react';

const steps = [
  { title: 'Welcome', icon: <Sparkles className="h-4 w-4" /> },
  { title: 'Profile', icon: <User className="h-4 w-4" /> },
  { title: 'Device', icon: <Smartphone className="h-4 w-4" /> },
  { title: 'Connect', icon: <Wifi className="h-4 w-4" /> },
  { title: 'Tariff', icon: <Receipt className="h-4 w-4" /> },
  { title: 'Goal', icon: <Target className="h-4 w-4" /> },
  { title: 'Tour', icon: <LayoutDashboard className="h-4 w-4" /> },
];

const SetupWizard = () => {
  const { isOpen, closeWizard, currentStep, totalSteps, completeWizard } = useSetupWizard();

  const handleSkip = () => {
    completeWizard();
  };

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return <WelcomeStep onSkip={handleSkip} />;
      case 1:
        return <ProfileStep />;
      case 2:
        return <DeviceStep />;
      case 3:
        return <ConnectionTestStep />;
      case 4:
        return <TariffStep />;
      case 5:
        return <GoalStep />;
      case 6:
        return <DashboardTourStep />;
      default:
        return <WelcomeStep onSkip={handleSkip} />;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && closeWizard()}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto p-0">
        <div className="sticky top-0 bg-background z-10 border-b">
          <WizardProgress 
            currentStep={currentStep} 
            totalSteps={totalSteps} 
            steps={steps} 
          />
        </div>
        <div className="p-6">
          {renderStep()}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SetupWizard;
