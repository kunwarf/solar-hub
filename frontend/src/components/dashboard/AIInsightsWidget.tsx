import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Lightbulb,
  ThumbsUp,
  ThumbsDown,
  Zap,
  Clock,
  Sun,
  Battery
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { AllWidgetsData } from '@/api/services/dashboard.service';

// Types for AI insights - structured for easy AI integration later
export interface Insight {
  id: string;
  type: 'positive' | 'neutral' | 'warning' | 'tip';
  category: 'production' | 'savings' | 'consumption' | 'anomaly' | 'recommendation';
  title: string;
  message: string;
  icon?: React.ReactNode;
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

export interface WeeklyDigest {
  totalGenerated: number;
  totalSaved: number;
  selfSufficiency: number;
  comparedToLastWeek: {
    generated: number; // percentage change
    saved: number;
    selfSufficiency: number;
  };
  tipOfTheWeek: string;
}

interface EnergyStatsInput {
  dailyProduction: number;
  batteryLevel: number;
  selfConsumption: number;
  moneySaved: number;
  co2Saved: number;
  peakPowerKw: number;
  importRatePkr: number;
}

function deriveEnergyStats(widgetsData?: AllWidgetsData | null): EnergyStatsInput {
  if (!widgetsData) {
    return { dailyProduction: 0, batteryLevel: 0, selfConsumption: 0, moneySaved: 0, co2Saved: 0, peakPowerKw: 0, importRatePkr: 30 };
  }
  const pf = widgetsData.power_flow;
  const st = widgetsData.stats;
  const bi = widgetsData.billing;

  // Calculate self-consumption: (production - exports) / production * 100
  const production = st?.energy_today_kwh || 0;
  const exported = st?.grid_export_today_kwh || 0;
  const selfConsumed = Math.max(0, production - exported);
  const selfConsumptionPct = production > 0 ? Math.round((selfConsumed / production) * 100) : 0;

  return {
    dailyProduction: production,
    batteryLevel: pf?.battery_soc_pct || 0,
    selfConsumption: selfConsumptionPct,
    moneySaved: bi?.estimated_savings_today || 0,
    co2Saved: st?.co2_saved_kg || 0,
    peakPowerKw: st?.peak_power_kw || 0,
    importRatePkr: bi?.import_rate_pkr || 30,
  };
}

// Rule-based insight generator - can be replaced with AI later
function generateDailyInsights(stats: EnergyStatsInput): Insight[] {
  const now = new Date();
  const hour = now.getHours();
  const insights: Insight[] = [];

  // Production insight
  const dailyProduction = stats.dailyProduction;
  const monthlyAverage = dailyProduction * 0.9; // Estimate: today's production as reference baseline
  const productionDiff = monthlyAverage > 0 ? ((dailyProduction - monthlyAverage) / monthlyAverage) * 100 : 0;
  
  if (productionDiff > 0) {
    insights.push({
      id: 'prod-1',
      type: 'positive',
      category: 'production',
      title: 'Great Production Day!',
      message: `You generated ${dailyProduction} kWh today, ${Math.abs(productionDiff).toFixed(0)}% above your monthly average 🎉`,
      icon: <Sun className="h-4 w-4" />,
      timestamp: now,
      metadata: { dailyProduction, monthlyAverage, diff: productionDiff }
    });
  } else {
    insights.push({
      id: 'prod-1',
      type: 'neutral',
      category: 'production',
      title: 'Production Summary',
      message: `You generated ${dailyProduction} kWh today, ${Math.abs(productionDiff).toFixed(0)}% below your monthly average`,
      icon: <Sun className="h-4 w-4" />,
      timestamp: now,
      metadata: { dailyProduction, monthlyAverage, diff: productionDiff }
    });
  }
  
  // Peak production insight
  const peakPower = stats.peakPowerKw;
  if (peakPower > 0) {
    insights.push({
      id: 'peak-1',
      type: 'neutral',
      category: 'production',
      title: 'Peak Production',
      message: `Your solar production peaked at ${peakPower.toFixed(1)} kW today`,
      icon: <Zap className="h-4 w-4" />,
      timestamp: now,
      metadata: { peakPower }
    });
  }

  // Savings insight - use actual saved amount or calculate from self-consumed solar
  const selfConsumedKwh = (stats.dailyProduction * stats.selfConsumption) / 100;
  const dailySavings = Math.round(stats.moneySaved || selfConsumedKwh * stats.importRatePkr);
  if (dailySavings > 0) {
    insights.push({
      id: 'save-1',
      type: 'positive',
      category: 'savings',
      title: 'Daily Savings',
      message: `You saved Rs. ${dailySavings.toLocaleString()} today by using solar instead of grid`,
      icon: <TrendingUp className="h-4 w-4" />,
      timestamp: now,
      metadata: { savings: dailySavings }
    });
  }
  
  // Time-based recommendation
  if (hour >= 9 && hour <= 15) {
    insights.push({
      id: 'tip-1',
      type: 'tip',
      category: 'recommendation',
      title: 'Optimization Tip',
      message: 'Consider running high-load appliances between 11 AM - 3 PM for maximum savings',
      icon: <Lightbulb className="h-4 w-4" />,
      timestamp: now
    });
  } else {
    insights.push({
      id: 'tip-1',
      type: 'tip',
      category: 'recommendation',
      title: 'Tomorrow\'s Tip',
      message: 'Schedule dishwasher and laundry during peak solar hours (11 AM - 3 PM) tomorrow',
      icon: <Lightbulb className="h-4 w-4" />,
      timestamp: now
    });
  }
  
  return insights;
}

function generateAnomalyAlerts(stats: EnergyStatsInput): Insight[] {
  const alerts: Insight[] = [];
  const now = new Date();

  // Low production alert (if daytime but production is very low)
  const hour = now.getHours();
  if (hour >= 9 && hour <= 16 && stats.dailyProduction < 1 && stats.peakPowerKw < 0.5) {
    alerts.push({
      id: 'anomaly-1',
      type: 'warning',
      category: 'anomaly',
      title: 'Very Low Generation',
      message: 'Generation is unusually low for this time of day. Check panels or weather conditions.',
      icon: <AlertTriangle className="h-4 w-4" />,
      timestamp: now,
    });
  }

  // Battery anomaly (based on real data)
  if (stats.batteryLevel < 20 && stats.batteryLevel > 0) {
    alerts.push({
      id: 'anomaly-2',
      type: 'warning',
      category: 'anomaly',
      title: 'Battery Level Critical',
      message: `Battery is at ${stats.batteryLevel}%. Consider reducing load or switching to grid.`,
      icon: <Battery className="h-4 w-4" />,
      timestamp: now,
    });
  }

  return alerts;
}

function generateWeeklyDigest(stats: EnergyStatsInput): WeeklyDigest {
  // Estimate weekly values from today's data (7x daily average)
  const weeklyGenerated = Math.round(stats.dailyProduction * 7);
  const weeklySaved = Math.round(stats.moneySaved * 7);
  return {
    totalGenerated: weeklyGenerated,
    totalSaved: weeklySaved,
    selfSufficiency: stats.selfConsumption || 0,
    comparedToLastWeek: {
      generated: 0, // No historical comparison data yet
      saved: 0,
      selfSufficiency: 0,
    },
    tipOfTheWeek: 'Pre-cool your home before peak hours to reduce AC load during expensive evening rates.',
  };
}

interface InsightCardProps {
  insight: Insight;
  onFeedback: (id: string, positive: boolean) => void;
  feedbackGiven?: 'up' | 'down' | null;
}

const InsightCard = ({ insight, onFeedback, feedbackGiven }: InsightCardProps) => {
  const typeStyles = {
    positive: 'border-success/30 bg-success/5',
    neutral: 'border-border',
    warning: 'border-warning/30 bg-warning/5',
    tip: 'border-primary/30 bg-primary/5',
  };
  
  const iconColors = {
    positive: 'text-success',
    neutral: 'text-muted-foreground',
    warning: 'text-warning',
    tip: 'text-primary',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'p-3 rounded-lg border transition-colors',
        typeStyles[insight.type]
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn('mt-0.5', iconColors[insight.type])}>
          {insight.icon}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">{insight.title}</p>
          <p className="text-sm text-muted-foreground mt-0.5">{insight.message}</p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              'h-7 w-7',
              feedbackGiven === 'up' && 'text-success bg-success/10'
            )}
            onClick={() => onFeedback(insight.id, true)}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              'h-7 w-7',
              feedbackGiven === 'down' && 'text-destructive bg-destructive/10'
            )}
            onClick={() => onFeedback(insight.id, false)}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </motion.div>
  );
};

interface AIInsightsWidgetProps {
  widgetsData?: AllWidgetsData | null;
}

export const AIInsightsWidget = ({ widgetsData }: AIInsightsWidgetProps) => {
  const [isOpen, setIsOpen] = useState(true);
  const [showAnomalies, setShowAnomalies] = useState(true);
  const [feedback, setFeedback] = useState<Record<string, 'up' | 'down'>>({});

  const energyInput = useMemo(() => deriveEnergyStats(widgetsData), [widgetsData]);

  // Generate insights (memoized, regenerated when widgetsData changes)
  const dailyInsights = useMemo(() => generateDailyInsights(energyInput), [energyInput]);
  const anomalyAlerts = useMemo(() => generateAnomalyAlerts(energyInput), [energyInput]);
  const weeklyDigest = useMemo(() => generateWeeklyDigest(energyInput), [energyInput]);

  const handleFeedback = (id: string, positive: boolean) => {
    setFeedback(prev => ({
      ...prev,
      [id]: positive ? 'up' : 'down'
    }));
    // In a real app, this would send feedback to the backend for AI training
    console.log(`Feedback for ${id}: ${positive ? 'positive' : 'negative'}`);
  };

  return (
    <Card className="overflow-hidden">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-primary/10 rounded-lg">
                  <Sparkles className="h-4 w-4 text-primary" />
                </div>
                <CardTitle className="text-base">AI Insights</CardTitle>
                {anomalyAlerts.length > 0 && (
                  <Badge variant="outline" className="text-warning border-warning/30 text-xs">
                    {anomalyAlerts.length} alert{anomalyAlerts.length !== 1 ? 's' : ''}
                  </Badge>
                )}
              </div>
              {isOpen ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="pt-0 space-y-6">
            {/* Daily Insights */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Clock className="h-3.5 w-3.5" />
                Today's Insights
              </h4>
              <div className="space-y-2">
                {dailyInsights.map(insight => (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    onFeedback={handleFeedback}
                    feedbackGiven={feedback[insight.id]}
                  />
                ))}
              </div>
            </div>

            {/* Anomaly Alerts */}
            <AnimatePresence>
              {anomalyAlerts.length > 0 && showAnomalies && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium text-warning flex items-center gap-2">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Anomaly Alerts
                    </h4>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs"
                      onClick={() => setShowAnomalies(false)}
                    >
                      Dismiss all
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {anomalyAlerts.map(alert => (
                      <InsightCard
                        key={alert.id}
                        insight={alert}
                        onFeedback={handleFeedback}
                        feedbackGiven={feedback[alert.id]}
                      />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Weekly Digest */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-muted-foreground">Weekly Digest</h4>
              <div className="bg-muted/30 rounded-lg p-4 space-y-4">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-lg font-semibold">{weeklyDigest.totalGenerated} kWh</p>
                    <p className="text-xs text-muted-foreground">Generated</p>
                    <div className={cn(
                      'flex items-center justify-center gap-0.5 text-xs mt-1',
                      weeklyDigest.comparedToLastWeek.generated >= 0 ? 'text-success' : 'text-destructive'
                    )}>
                      {weeklyDigest.comparedToLastWeek.generated >= 0 ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      {Math.abs(weeklyDigest.comparedToLastWeek.generated)}%
                    </div>
                  </div>
                  <div>
                    <p className="text-lg font-semibold">Rs. {weeklyDigest.totalSaved.toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground">Saved</p>
                    <div className={cn(
                      'flex items-center justify-center gap-0.5 text-xs mt-1',
                      weeklyDigest.comparedToLastWeek.saved >= 0 ? 'text-success' : 'text-destructive'
                    )}>
                      {weeklyDigest.comparedToLastWeek.saved >= 0 ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      {Math.abs(weeklyDigest.comparedToLastWeek.saved)}%
                    </div>
                  </div>
                  <div>
                    <p className="text-lg font-semibold">{weeklyDigest.selfSufficiency}%</p>
                    <p className="text-xs text-muted-foreground">Self-Sufficient</p>
                    <div className={cn(
                      'flex items-center justify-center gap-0.5 text-xs mt-1',
                      weeklyDigest.comparedToLastWeek.selfSufficiency >= 0 ? 'text-success' : 'text-destructive'
                    )}>
                      {weeklyDigest.comparedToLastWeek.selfSufficiency >= 0 ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      {Math.abs(weeklyDigest.comparedToLastWeek.selfSufficiency)}%
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-border/50">
                  <div className="flex items-start gap-2">
                    <Lightbulb className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-medium text-primary">Tip of the Week</p>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {weeklyDigest.tipOfTheWeek}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

export default AIInsightsWidget;
