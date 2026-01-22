import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import { motion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Target, TrendingUp, Lightbulb } from 'lucide-react';

const GoalStep = () => {
  const { nextStep, prevStep, data, updateData } = useSetupWizard();

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-PK', {
      style: 'currency',
      currency: 'PKR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value).replace('PKR', 'Rs.');
  };

  // Calculate estimated annual savings
  const annualSavings = data.monthlyGoal * 12;

  // Difficulty indicator based on goal
  const getDifficulty = () => {
    if (data.monthlyGoal <= 10000) return { label: 'Achievable', color: 'text-green-500', bg: 'bg-green-500' };
    if (data.monthlyGoal <= 25000) return { label: 'Moderate', color: 'text-yellow-500', bg: 'bg-yellow-500' };
    return { label: 'Ambitious', color: 'text-orange-500', bg: 'bg-orange-500' };
  };

  const difficulty = getDifficulty();

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="text-center space-y-2">
        <h2 className="text-xl font-bold">Set Your Savings Goal</h2>
        <p className="text-sm text-muted-foreground">
          We'll help you track progress towards your monthly savings target.
        </p>
      </div>

      <div className="py-6">
        <motion.div
          key={data.monthlyGoal}
          initial={{ scale: 0.9 }}
          animate={{ scale: 1 }}
          className="text-center mb-8"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 mb-2">
            <Target className="h-5 w-5 text-primary" />
            <span className={`text-sm font-medium ${difficulty.color}`}>{difficulty.label}</span>
          </div>
          <p className="text-4xl font-bold text-primary">
            {formatCurrency(data.monthlyGoal)}
          </p>
          <p className="text-sm text-muted-foreground">per month</p>
        </motion.div>

        <div className="space-y-4 px-2">
          <Slider
            value={[data.monthlyGoal]}
            onValueChange={(values) => updateData({ monthlyGoal: values[0] })}
            min={1000}
            max={50000}
            step={1000}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Rs. 1,000</span>
            <span>Rs. 50,000</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-muted/50 rounded-lg p-4 text-center">
          <TrendingUp className="h-6 w-6 mx-auto text-primary mb-2" />
          <p className="text-xs text-muted-foreground">Annual Target</p>
          <p className="text-lg font-semibold">{formatCurrency(annualSavings)}</p>
        </div>
        <div className="bg-muted/50 rounded-lg p-4 text-center">
          <Lightbulb className="h-6 w-6 mx-auto text-yellow-500 mb-2" />
          <p className="text-xs text-muted-foreground">Tip</p>
          <p className="text-sm font-medium">Start conservative, adjust later</p>
        </div>
      </div>

      <div className="bg-primary/5 border border-primary/20 rounded-lg p-3">
        <p className="text-sm text-center">
          Based on typical solar systems in {data.city || 'Pakistan'}, this goal is{' '}
          <span className={`font-medium ${difficulty.color}`}>{difficulty.label.toLowerCase()}</span>.
        </p>
      </div>

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={prevStep}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={nextStep}>
          Continue
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
};

export default GoalStep;
