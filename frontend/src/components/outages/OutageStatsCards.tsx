import { motion } from 'framer-motion';
import { 
  Zap, 
  Clock, 
  Timer, 
  Battery, 
  Sun,
  TrendingUp
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { formatDuration } from '@/data/outageData';
import { cn } from '@/lib/utils';

interface OutageStatsCardsProps {
  stats: {
    totalOutages: number;
    avgDuration: number;
    longestOutage: number;
    totalBackupTime: number;
    totalBatteryUsed: number;
    hoursAvoided: number;
  };
  className?: string;
}

export function OutageStatsCards({ stats, className }: OutageStatsCardsProps) {
  const cards = [
    {
      title: 'Total Outages',
      value: stats.totalOutages,
      suffix: '',
      icon: Zap,
      color: 'text-destructive',
      bg: 'bg-destructive/10',
    },
    {
      title: 'Avg Duration',
      value: formatDuration(stats.avgDuration),
      suffix: '',
      icon: Clock,
      color: 'text-orange-500',
      bg: 'bg-orange-500/10',
    },
    {
      title: 'Longest Outage',
      value: formatDuration(stats.longestOutage),
      suffix: '',
      icon: Timer,
      color: 'text-warning',
      bg: 'bg-warning/10',
    },
    {
      title: 'Backup Provided',
      value: formatDuration(stats.totalBackupTime),
      suffix: '',
      icon: Battery,
      color: 'text-battery',
      bg: 'bg-battery/10',
    },
    {
      title: 'Battery Used',
      value: stats.totalBatteryUsed,
      suffix: ' kWh',
      icon: TrendingUp,
      color: 'text-info',
      bg: 'bg-info/10',
    },
    {
      title: 'Darkness Avoided',
      value: stats.hoursAvoided,
      suffix: ' hrs',
      icon: Sun,
      color: 'text-solar',
      bg: 'bg-solar/10',
      special: true,
    },
  ];

  return (
    <div className={cn("grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4", className)}>
      {cards.map((card, index) => (
        <motion.div
          key={card.title}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.05 }}
        >
          <Card className={cn(
            "h-full",
            card.special && "border-solar/30 bg-gradient-to-br from-solar/5 to-transparent"
          )}>
            <CardContent className="p-4">
              <div className={cn("p-2 rounded-lg w-fit mb-3", card.bg)}>
                <card.icon className={cn("h-5 w-5", card.color)} />
              </div>
              <p className="text-2xl font-bold text-foreground">
                {card.value}{card.suffix}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {card.title}
              </p>
              {card.special && (
                <p className="text-xs text-solar mt-1 font-medium">
                  ☀️ Thanks to solar!
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}
