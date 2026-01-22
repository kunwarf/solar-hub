import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { 
  Trophy, 
  Star, 
  Target, 
  Zap, 
  Award,
  Crown,
  Sparkles,
  Medal,
  LucideIcon
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  unlocked: boolean;
  unlockedDate?: Date;
  color: string;
  bgColor: string;
}

interface AchievementBadgeProps {
  achievement: Achievement;
  index?: number;
}

export function AchievementBadge({ achievement, index = 0 }: AchievementBadgeProps) {
  const Icon = achievement.icon;
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <motion.div
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.1, type: 'spring', stiffness: 200 }}
            className={cn(
              "relative flex flex-col items-center p-4 rounded-xl border-2 transition-all cursor-pointer",
              achievement.unlocked 
                ? `${achievement.bgColor} border-current shadow-lg hover:scale-105` 
                : "bg-muted/30 border-muted grayscale opacity-50"
            )}
          >
            {achievement.unlocked && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: index * 0.1 + 0.3, type: 'spring' }}
                className="absolute -top-2 -right-2"
              >
                <div className="w-6 h-6 bg-success rounded-full flex items-center justify-center">
                  <Sparkles className="w-3 h-3 text-white" />
                </div>
              </motion.div>
            )}
            
            <div className={cn(
              "w-14 h-14 rounded-full flex items-center justify-center mb-2",
              achievement.unlocked ? achievement.bgColor : "bg-muted"
            )}>
              <Icon className={cn(
                "w-7 h-7",
                achievement.unlocked ? achievement.color : "text-muted-foreground"
              )} />
            </div>
            
            <span className={cn(
              "text-xs font-medium text-center",
              achievement.unlocked ? "text-foreground" : "text-muted-foreground"
            )}>
              {achievement.title}
            </span>
          </motion.div>
        </TooltipTrigger>
        <TooltipContent>
          <div className="text-sm space-y-1">
            <p className="font-semibold">{achievement.title}</p>
            <p className="text-muted-foreground">{achievement.description}</p>
            {achievement.unlocked && achievement.unlockedDate && (
              <p className="text-xs text-success">
                Unlocked: {achievement.unlockedDate.toLocaleDateString()}
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// Pre-defined achievements
export const SAVINGS_ACHIEVEMENTS: Achievement[] = [
  {
    id: 'first-10k',
    title: 'First Rs. 10,000',
    description: 'Save your first Rs. 10,000 with solar',
    icon: Star,
    unlocked: true,
    unlockedDate: new Date('2024-02-15'),
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/20',
  },
  {
    id: 'first-positive-month',
    title: 'Net Positive',
    description: 'First month with positive earnings',
    icon: Zap,
    unlocked: true,
    unlockedDate: new Date('2024-03-01'),
    color: 'text-green-500',
    bgColor: 'bg-green-500/20',
  },
  {
    id: 'halfway-breakeven',
    title: '50% Break-even',
    description: 'Reach 50% of your break-even goal',
    icon: Target,
    unlocked: true,
    unlockedDate: new Date('2024-06-10'),
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/20',
  },
  {
    id: 'breakeven-achieved',
    title: 'Break-even!',
    description: 'Your system has paid for itself',
    icon: Trophy,
    unlocked: false,
    color: 'text-amber-500',
    bgColor: 'bg-amber-500/20',
  },
  {
    id: 'lifetime-100k',
    title: 'Rs. 100,000 Club',
    description: 'Lifetime savings exceed Rs. 100,000',
    icon: Crown,
    unlocked: true,
    unlockedDate: new Date('2024-08-20'),
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/20',
  },
  {
    id: 'carbon-warrior',
    title: 'Carbon Warrior',
    description: 'Offset 1 ton of CO2 emissions',
    icon: Award,
    unlocked: true,
    unlockedDate: new Date('2024-04-05'),
    color: 'text-emerald-500',
    bgColor: 'bg-emerald-500/20',
  },
];
