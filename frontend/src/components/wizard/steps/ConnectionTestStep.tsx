import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, ArrowRight, CheckCircle2, XCircle, Loader2, Wifi, Server, Shield, Zap } from 'lucide-react';

type ConnectionState = 'idle' | 'connecting' | 'verifying' | 'securing' | 'success' | 'failed';

const steps = [
  { key: 'connecting', icon: <Wifi className="h-5 w-5" />, label: 'Connecting to device...' },
  { key: 'verifying', icon: <Server className="h-5 w-5" />, label: 'Verifying device identity...' },
  { key: 'securing', icon: <Shield className="h-5 w-5" />, label: 'Establishing secure connection...' },
];

const ConnectionTestStep = () => {
  const { nextStep, prevStep, data, updateData } = useSetupWizard();
  const [state, setState] = useState<ConnectionState>('idle');
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  const startConnectionTest = () => {
    setState('connecting');
    setCurrentStepIndex(0);
  };

  useEffect(() => {
    if (state === 'idle' || state === 'success' || state === 'failed') return;

    const timer = setTimeout(() => {
      if (currentStepIndex < steps.length - 1) {
        setCurrentStepIndex(prev => prev + 1);
        setState(steps[currentStepIndex + 1].key as ConnectionState);
      } else {
        // 90% chance of success for demo
        const success = Math.random() > 0.1;
        setState(success ? 'success' : 'failed');
        updateData({ deviceConnected: success });
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [state, currentStepIndex, updateData]);

  const retry = () => {
    setState('idle');
    setCurrentStepIndex(0);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="text-center space-y-2">
        <h2 className="text-xl font-bold">Connection Test</h2>
        <p className="text-sm text-muted-foreground">
          We're verifying the connection to your device.
        </p>
      </div>

      <div className="py-8">
        {state === 'idle' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center space-y-4"
          >
            <div className="mx-auto w-20 h-20 rounded-full bg-muted flex items-center justify-center">
              <Zap className="h-10 w-10 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground">
              Ready to test connection to device:
            </p>
            <p className="font-mono text-lg font-medium">{data.deviceCode}</p>
            <Button onClick={startConnectionTest} size="lg">
              Start Connection Test
            </Button>
          </motion.div>
        )}

        {(state === 'connecting' || state === 'verifying' || state === 'securing') && (
          <div className="space-y-4">
            {steps.map((step, index) => {
              const isActive = index === currentStepIndex;
              const isComplete = index < currentStepIndex;
              
              return (
                <motion.div
                  key={step.key}
                  initial={{ opacity: 0.5 }}
                  animate={{ 
                    opacity: isComplete || isActive ? 1 : 0.5,
                  }}
                  className={`flex items-center gap-4 p-4 rounded-lg border ${
                    isActive ? 'border-primary bg-primary/5' : 
                    isComplete ? 'border-green-500/50 bg-green-500/5' : 
                    'border-muted'
                  }`}
                >
                  <div className={`p-2 rounded-full ${
                    isActive ? 'bg-primary/10 text-primary' :
                    isComplete ? 'bg-green-500/10 text-green-500' :
                    'bg-muted text-muted-foreground'
                  }`}>
                    {isComplete ? (
                      <CheckCircle2 className="h-5 w-5" />
                    ) : isActive ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      step.icon
                    )}
                  </div>
                  <span className={`font-medium ${
                    isActive ? 'text-foreground' : 
                    isComplete ? 'text-green-600 dark:text-green-400' : 
                    'text-muted-foreground'
                  }`}>
                    {step.label}
                  </span>
                </motion.div>
              );
            })}
          </div>
        )}

        <AnimatePresence mode="wait">
          {state === 'success' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="text-center space-y-4"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 200, delay: 0.2 }}
                className="mx-auto w-20 h-20 rounded-full bg-green-500/10 flex items-center justify-center"
              >
                <CheckCircle2 className="h-12 w-12 text-green-500" />
              </motion.div>
              <div>
                <h3 className="text-lg font-semibold text-green-600 dark:text-green-400">
                  Connection Successful!
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Your device is now connected and ready to use.
                </p>
              </div>
            </motion.div>
          )}

          {state === 'failed' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="text-center space-y-4"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 200, delay: 0.2 }}
                className="mx-auto w-20 h-20 rounded-full bg-destructive/10 flex items-center justify-center"
              >
                <XCircle className="h-12 w-12 text-destructive" />
              </motion.div>
              <div>
                <h3 className="text-lg font-semibold text-destructive">
                  Connection Failed
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  We couldn't connect to your device. Please check that it's powered on and try again.
                </p>
              </div>
              <Button onClick={retry} variant="outline">
                Try Again
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={prevStep}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={nextStep} disabled={state !== 'success'}>
          Continue
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
};

export default ConnectionTestStep;
