import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import { X, ChevronRight, ChevronLeft } from 'lucide-react';

interface TourStep {
  target: string;
  title: string;
  description: string;
}

const tourSteps: TourStep[] = [
  {
    target: '[data-tour="power-flow"]',
    title: 'Power Flow Diagram',
    description: 'This shows real-time energy flowing between your solar panels, battery, grid, and home. Green arrows indicate power generation, red indicates consumption.',
  },
  {
    target: '[data-tour="stats"]',
    title: 'Key Statistics',
    description: 'Quick overview of your solar production, consumption, and savings. Tap any card for more details.',
  },
  {
    target: '[data-tour="savings"]',
    title: 'Savings Tracker',
    description: 'Track your progress towards your monthly savings goal. This updates daily based on your actual solar production.',
  },
  {
    target: '[data-tour="quick-actions"]',
    title: 'Quick Actions',
    description: 'One-tap access to common actions like adjusting battery mode, checking alerts, or viewing your bill.',
  },
];

const DashboardTour = () => {
  const { isTourActive, endTour } = useSetupWizard();
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!isTourActive) {
      setCurrentStep(0);
      return;
    }

    const findTarget = () => {
      const step = tourSteps[currentStep];
      const element = document.querySelector(step.target);
      
      if (element) {
        const rect = element.getBoundingClientRect();
        setTargetRect(rect);
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        setTargetRect(null);
      }
    };

    const timer = setTimeout(findTarget, 300);
    const handleResize = () => findTarget();
    window.addEventListener('resize', handleResize);
    
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
    };
  }, [currentStep, isTourActive]);

  const handleNext = () => {
    if (currentStep < tourSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      endTour();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    endTour();
  };

  if (!isTourActive) return null;

  const step = tourSteps[currentStep];

  return (
    <AnimatePresence>
      {isTourActive && (
        <>
          {/* Background overlay - clicking skips tour */}
          <div 
            className="fixed inset-0 bg-black/70 z-[9998]"
            onClick={handleSkip}
            aria-hidden="true"
          />

          {/* Spotlight highlight on target */}
          {targetRect && (
            <div
              className="fixed pointer-events-none z-[9998]"
              style={{
                top: targetRect.top - 8,
                left: targetRect.left - 8,
                width: targetRect.width + 16,
                height: targetRect.height + 16,
                borderRadius: '12px',
                boxShadow: '0 0 0 9999px rgba(0,0,0,0.7)',
                border: '2px solid hsl(var(--primary))',
              }}
            />
          )}

          {/* Modal card - must be above overlay */}
          <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 pointer-events-none">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-md bg-background border rounded-xl shadow-2xl p-5 pointer-events-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Close button */}
              <button
                type="button"
                onClick={handleSkip}
                className="absolute top-3 right-3 h-8 w-8 rounded-md flex items-center justify-center hover:bg-muted transition-colors"
              >
                <X className="h-4 w-4" />
              </button>

              {/* Progress dots */}
              <div className="flex items-center justify-center gap-2 mb-4">
                {tourSteps.map((_, index) => (
                  <div
                    key={index}
                    className={`h-2 rounded-full transition-all ${
                      index === currentStep 
                        ? 'w-6 bg-primary' 
                        : index < currentStep 
                          ? 'w-2 bg-primary/50' 
                          : 'w-2 bg-muted-foreground/30'
                    }`}
                  />
                ))}
              </div>

              {/* Content */}
              <div className="text-center space-y-3 mb-6">
                <h3 className="text-lg font-semibold">{step.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {step.description}
                </p>
              </div>

              {/* Navigation buttons */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handlePrev}
                  disabled={currentStep === 0}
                  className="flex-1 h-9 px-3 rounded-md border border-input bg-background text-sm font-medium hover:bg-accent hover:text-accent-foreground disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-1"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Back
                </button>
                <button
                  type="button"
                  onClick={handleNext}
                  className="flex-1 h-9 px-3 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 flex items-center justify-center gap-1"
                >
                  {currentStep === tourSteps.length - 1 ? (
                    'Finish Tour'
                  ) : (
                    <>
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </div>

              {/* Skip hint */}
              <p className="text-xs text-muted-foreground text-center mt-4">
                Click outside or press × to skip
              </p>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
};

export default DashboardTour;
