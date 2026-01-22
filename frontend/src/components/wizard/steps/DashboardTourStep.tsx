import { Button } from '@/components/ui/button';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import { motion } from 'framer-motion';
import { ArrowLeft, PartyPopper, Play, LayoutDashboard, Zap, Bell, PiggyBank } from 'lucide-react';

const DashboardTourStep = () => {
  const { prevStep, startTour, completeWizard, data } = useSetupWizard();

  const tourHighlights = [
    { 
      icon: <Zap className="h-5 w-5" />, 
      title: 'Power Flow',
      desc: 'See real-time energy flowing between solar, battery, grid, and your home'
    },
    { 
      icon: <PiggyBank className="h-5 w-5" />, 
      title: 'Savings Tracker',
      desc: 'Track your monthly savings progress towards your goal'
    },
    { 
      icon: <Bell className="h-5 w-5" />, 
      title: 'Smart Alerts',
      desc: 'Get notified about load shedding, system issues, and optimization tips'
    },
    { 
      icon: <LayoutDashboard className="h-5 w-5" />, 
      title: 'Quick Actions',
      desc: 'Control your system and access key features with one tap'
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="text-center space-y-2">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
          className="mx-auto w-16 h-16 rounded-full bg-gradient-to-br from-green-400 to-emerald-500 flex items-center justify-center mb-4"
        >
          <PartyPopper className="h-8 w-8 text-white" />
        </motion.div>
        <h2 className="text-xl font-bold">You're All Set, {data.firstName || 'there'}!</h2>
        <p className="text-sm text-muted-foreground">
          Your setup is complete. Would you like a quick tour of the dashboard?
        </p>
      </div>

      <div className="space-y-3">
        <p className="text-sm font-medium text-center">What you'll discover:</p>
        {tourHighlights.map((item, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + index * 0.1 }}
            className="flex items-start gap-3 p-3 rounded-lg bg-muted/50"
          >
            <div className="p-2 rounded-md bg-primary/10 text-primary">
              {item.icon}
            </div>
            <div>
              <h3 className="font-medium text-sm">{item.title}</h3>
              <p className="text-xs text-muted-foreground">{item.desc}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="bg-muted/30 rounded-lg p-4 text-center space-y-2">
        <p className="text-sm font-medium">Your Setup Summary</p>
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="bg-background rounded p-2">
            <p className="text-muted-foreground">Location</p>
            <p className="font-medium">{data.city || 'Not set'}</p>
          </div>
          <div className="bg-background rounded p-2">
            <p className="text-muted-foreground">Provider</p>
            <p className="font-medium">{data.disco || 'Not set'}</p>
          </div>
          <div className="bg-background rounded p-2">
            <p className="text-muted-foreground">Goal</p>
            <p className="font-medium">Rs. {(data.monthlyGoal / 1000).toFixed(0)}K/mo</p>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2 pt-4">
        <Button onClick={startTour} size="lg" className="w-full gap-2">
          <Play className="h-4 w-4" />
          Take the Tour
        </Button>
        <Button variant="ghost" size="sm" onClick={completeWizard} className="text-muted-foreground">
          Skip tour, go to dashboard
        </Button>
      </div>

      <div className="flex justify-start">
        <Button variant="outline" size="sm" onClick={prevStep}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
      </div>
    </motion.div>
  );
};

export default DashboardTourStep;
