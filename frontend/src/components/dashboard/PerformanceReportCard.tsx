import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  BarChart2,
  Calendar,
  ChevronDown,
  ChevronUp,
  Sun,
  TrendingUp,
  TrendingDown,
  Lightbulb,
  Zap,
  DollarSign,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import dashboardService from '@/api/services/dashboard.service';
import { tokenStorage } from '@/api/client';

interface SectionRowProps {
  icon: React.ReactNode;
  text: string;
  accent?: 'positive' | 'warning' | 'neutral';
}

const SectionRow = ({ icon, text, accent = 'neutral' }: SectionRowProps) => (
  <div className="flex items-start gap-2.5 text-sm">
    <span className={cn(
      'mt-0.5 shrink-0',
      accent === 'positive' && 'text-success',
      accent === 'warning' && 'text-warning',
      accent === 'neutral' && 'text-muted-foreground',
    )}>
      {icon}
    </span>
    <span className="text-muted-foreground leading-snug">{text}</span>
  </div>
);

interface PerformanceReportCardProps {
  siteId?: string;
  importRatePkr?: number;
}

export const PerformanceReportCard = ({ siteId, importRatePkr }: PerformanceReportCardProps) => {
  const [isOpen, setIsOpen] = useState(true);

  const isAuthenticated = tokenStorage.hasValidToken();
  const { data: insights, isLoading } = useQuery({
    queryKey: ['insights', siteId],
    queryFn: () => dashboardService.getInsights(siteId, importRatePkr),
    enabled: isAuthenticated && !!siteId,
    staleTime: 60 * 60 * 1000,
    refetchInterval: 60 * 60 * 1000,
    retry: 1,
  });

  const monthly = insights?.monthly_analysis;
  const yearly = insights?.yearly_analysis;

  if (!monthly && !yearly && !isLoading) return null;

  return (
    <Card className="overflow-hidden">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-primary/10 rounded-lg">
                  <BarChart2 className="h-4 w-4 text-primary" />
                </div>
                <CardTitle className="text-base">Performance Report</CardTitle>
                {insights && (
                  <Badge variant="outline" className="text-xs text-muted-foreground border-muted">
                    AI
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
          <CardContent className="pt-0">
            {isLoading && (
              <p className="text-sm text-muted-foreground py-4 text-center">
                Generating performance report…
              </p>
            )}

            {(monthly || yearly) && (
              <Tabs defaultValue={monthly ? 'monthly' : 'yearly'}>
                <TabsList className="w-full mb-4">
                  {monthly && (
                    <TabsTrigger value="monthly" className="flex-1 gap-1.5">
                      <Calendar className="h-3.5 w-3.5" />
                      This Month
                    </TabsTrigger>
                  )}
                  {yearly && (
                    <TabsTrigger value="yearly" className="flex-1 gap-1.5">
                      <TrendingUp className="h-3.5 w-3.5" />
                      Year-to-Date
                    </TabsTrigger>
                  )}
                </TabsList>

                {/* ── Monthly ── */}
                {monthly && (
                  <TabsContent value="monthly" className="mt-0 space-y-4">
                    {/* Summary */}
                    {monthly.summary && (
                      <p className="text-sm text-foreground leading-relaxed">
                        {monthly.summary}
                      </p>
                    )}

                    {/* Highlights */}
                    {monthly.highlights.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Highlights
                        </p>
                        <div className="space-y-1.5">
                          {monthly.highlights.map((h, i) => (
                            <SectionRow
                              key={i}
                              icon={<Sun className="h-3.5 w-3.5" />}
                              text={h}
                              accent="positive"
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    {monthly.recommendations.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Recommendations
                        </p>
                        <div className="space-y-1.5">
                          {monthly.recommendations.map((r, i) => (
                            <SectionRow
                              key={i}
                              icon={<Lightbulb className="h-3.5 w-3.5" />}
                              text={r}
                              accent="neutral"
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Load Shedding */}
                    {monthly.load_shedding_insight && (
                      <div className="bg-muted/30 rounded-lg p-3 flex items-start gap-2">
                        <Zap className="h-3.5 w-3.5 text-warning mt-0.5 shrink-0" />
                        <p className="text-sm text-muted-foreground">
                          {monthly.load_shedding_insight}
                        </p>
                      </div>
                    )}
                  </TabsContent>
                )}

                {/* ── Yearly ── */}
                {yearly && (
                  <TabsContent value="yearly" className="mt-0 space-y-4">
                    {/* Summary */}
                    {yearly.summary && (
                      <p className="text-sm text-foreground leading-relaxed">
                        {yearly.summary}
                      </p>
                    )}

                    {/* Best / Worst month */}
                    {(yearly.best_month || yearly.worst_month) && (
                      <div className="grid grid-cols-2 gap-2">
                        {yearly.best_month && (
                          <div className="bg-success/5 border border-success/20 rounded-lg p-3">
                            <div className="flex items-center gap-1 mb-1">
                              <TrendingUp className="h-3 w-3 text-success" />
                              <span className="text-xs font-medium text-success">Best</span>
                            </div>
                            <p className="text-xs text-muted-foreground">{yearly.best_month}</p>
                          </div>
                        )}
                        {yearly.worst_month && (
                          <div className="bg-warning/5 border border-warning/20 rounded-lg p-3">
                            <div className="flex items-center gap-1 mb-1">
                              <TrendingDown className="h-3 w-3 text-warning" />
                              <span className="text-xs font-medium text-warning">Worst</span>
                            </div>
                            <p className="text-xs text-muted-foreground">{yearly.worst_month}</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Trends */}
                    {yearly.trends.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Trends
                        </p>
                        <div className="space-y-1.5">
                          {yearly.trends.map((t, i) => (
                            <SectionRow
                              key={i}
                              icon={<BarChart2 className="h-3.5 w-3.5" />}
                              text={t}
                              accent="neutral"
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    {yearly.recommendations.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Recommendations
                        </p>
                        <div className="space-y-1.5">
                          {yearly.recommendations.map((r, i) => (
                            <SectionRow
                              key={i}
                              icon={<Lightbulb className="h-3.5 w-3.5" />}
                              text={r}
                              accent="neutral"
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* ROI */}
                    {yearly.roi_insight && (
                      <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 flex items-start gap-2">
                        <DollarSign className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
                        <p className="text-sm text-muted-foreground">{yearly.roi_insight}</p>
                      </div>
                    )}
                  </TabsContent>
                )}
              </Tabs>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

export default PerformanceReportCard;
