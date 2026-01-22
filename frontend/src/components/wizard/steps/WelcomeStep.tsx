import { Button } from '@/components/ui/button';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import { motion } from 'framer-motion';
import { Sun, Zap, PiggyBank, Bell } from 'lucide-react';

interface WelcomeStepProps {
  onSkip: () => void;
}

const WelcomeStep = ({ onSkip }: WelcomeStepProps) => {
  const { nextStep } = useSetupWizard();

  const features = [
    { icon: <Sun className="h-5 w-5" />, title: 'Monitor Solar Production', desc: 'Real-time tracking of your solar panels' },
    { icon: <Zap className="h-5 w-5" />, title: 'Optimize Energy Usage', desc: 'Smart scheduling to maximize savings' },
    { icon: <PiggyBank className="h-5 w-5" />, title: 'Track Your Savings', desc: 'See exactly how much you\'re saving' },
    { icon: <Bell className="h-5 w-5" />, title: 'Stay Informed', desc: 'Alerts for load shedding and system health' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center space-y-6"
    >
      <div className="space-y-2">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
          className="mx-auto w-20 h-20 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center mb-4"
        >
          <Sun className="h-10 w-10 text-white" />
        </motion.div>
        <h2 className="text-2xl font-bold">Welcome to Solar Monitor!</h2>
        <p className="text-muted-foreground">
          Let's get you set up in just a few minutes. We'll help you connect your devices and start tracking your savings.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
        {features.map((feature, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + index * 0.1 }}
            className="flex items-start gap-3 p-3 rounded-lg bg-muted/50"
          >
            <div className="p-2 rounded-md bg-primary/10 text-primary">
              {feature.icon}
            </div>
            <div>
              <h3 className="font-medium text-sm">{feature.title}</h3>
              <p className="text-xs text-muted-foreground">{feature.desc}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="flex flex-col gap-2 pt-4">
        <Button onClick={nextStep} size="lg" className="w-full">
          Get Started
        </Button>
        <Button variant="ghost" size="sm" onClick={onSkip} className="text-muted-foreground">
          Skip for now (I'm an experienced user)
        </Button>
      </div>
    </motion.div>
  );
};

export default WelcomeStep;
