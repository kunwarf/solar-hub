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
import { cn } from '@/lib/utils';
import dashboardService from '@/api/services/dashboard.service';
import type { MonthlyAnalysis, YearlyAnalysis } from '@/api/services/dashboard.service';
import { tokenStorage } from '@/api/client';

// ─── helpers ──────────────────────────────────────────────────────────────────

const MONTHS = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
];

function currentMonthLabel() {
  const d = new Date();
  return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

function currentYearLabel() {
  const d = new Date();
  // "Jan – Feb 2026" style subtitle
  const endMonth = MONTHS[d.getMonth()].slice(0, 3);
  return { year: d.getFullYear(), rangeLabel: `Jan – ${endMonth} ${d.getFullYear()}` };
}

// ─── shared sub-component ─────────────────────────────────────────────────────

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
      accent === 'warning'  && 'text-warning',
      accent === 'neutral'  && 'text-muted-foreground',
    )}>
      {icon}
    </span>
    <span className="text-muted-foreground leading-snug">{text}</span>
  </div>
);

// ─── Monthly card ─────────────────────────────────────────────────────────────

const MonthlyReportCard = ({ data }: { data: MonthlyAnalysis }) => {
  const [open, setOpen] = useState(true);
  const monthLabel = currentMonthLabel();

  return (
    <Card className="overflow-hidden">
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-primary/10 rounded-lg">
                  <Calendar className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-base leading-tight">
                    {monthLabel} — Billing Summary
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Solar savings &amp; efficiency this month
                  </p>
                </div>
                <Badge variant="outline" className="text-xs text-muted-foreground border-muted ml-1">
                  AI
                </Badge>
              </div>
              {open
                ? <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
                : <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />}
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="pt-0 space-y-4">
            {data.summary && (
              <p className="text-sm text-foreground leading-relaxed">{data.summary}</p>
            )}

            {data.highlights.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Highlights
                </p>
                <div className="space-y-1.5">
                  {data.highlights.map((h, i) => (
                    <SectionRow key={i} icon={<Sun className="h-3.5 w-3.5" />} text={h} accent="positive" />
                  ))}
                </div>
              </div>
            )}

            {data.recommendations.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Recommendations
                </p>
                <div className="space-y-1.5">
                  {data.recommendations.map((r, i) => (
                    <SectionRow key={i} icon={<Lightbulb className="h-3.5 w-3.5" />} text={r} />
                  ))}
                </div>
              </div>
            )}

            {data.load_shedding_insight && (
              <div className="bg-warning/5 border border-warning/20 rounded-lg p-3 flex items-start gap-2">
                <Zap className="h-3.5 w-3.5 text-warning mt-0.5 shrink-0" />
                <p className="text-sm text-muted-foreground">{data.load_shedding_insight}</p>
              </div>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

// ─── Yearly card ──────────────────────────────────────────────────────────────

const YearlyReportCard = ({ data }: { data: YearlyAnalysis }) => {
  const [open, setOpen] = useState(true);
  const { year, rangeLabel } = currentYearLabel();

  return (
    <Card className="overflow-hidden">
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-primary/10 rounded-lg">
                  <BarChart2 className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-base leading-tight">
                    {year} Year-to-Date
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {rangeLabel} cumulative performance
                  </p>
                </div>
                <Badge variant="outline" className="text-xs text-muted-foreground border-muted ml-1">
                  AI
                </Badge>
              </div>
              {open
                ? <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
                : <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />}
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="pt-0 space-y-4">
            {data.summary && (
              <p className="text-sm text-foreground leading-relaxed">{data.summary}</p>
            )}

            {(data.best_month || data.worst_month) && (
              <div className="grid grid-cols-2 gap-2">
                {data.best_month && (
                  <div className="bg-success/5 border border-success/20 rounded-lg p-3">
                    <div className="flex items-center gap-1 mb-1">
                      <TrendingUp className="h-3 w-3 text-success" />
                      <span className="text-xs font-semibold text-success">Best Month</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{data.best_month}</p>
                  </div>
                )}
                {data.worst_month && (
                  <div className="bg-destructive/5 border border-destructive/20 rounded-lg p-3">
                    <div className="flex items-center gap-1 mb-1">
                      <TrendingDown className="h-3 w-3 text-destructive" />
                      <span className="text-xs font-semibold text-destructive">Worst Month</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{data.worst_month}</p>
                  </div>
                )}
              </div>
            )}

            {data.trends.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Trends
                </p>
                <div className="space-y-1.5">
                  {data.trends.map((t, i) => (
                    <SectionRow key={i} icon={<BarChart2 className="h-3.5 w-3.5" />} text={t} />
                  ))}
                </div>
              </div>
            )}

            {data.recommendations.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Recommendations
                </p>
                <div className="space-y-1.5">
                  {data.recommendations.map((r, i) => (
                    <SectionRow key={i} icon={<Lightbulb className="h-3.5 w-3.5" />} text={r} />
                  ))}
                </div>
              </div>
            )}

            {data.roi_insight && (
              <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 flex items-start gap-2">
                <DollarSign className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
                <p className="text-sm text-muted-foreground">{data.roi_insight}</p>
              </div>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

// ─── Container (fetches once, renders two cards) ───────────────────────────────

interface PerformanceReportCardProps {
  siteId?: string;
  importRatePkr?: number;
}

export const PerformanceReportCard = ({ siteId, importRatePkr }: PerformanceReportCardProps) => {
  const isAuthenticated = tokenStorage.hasValidToken();
  const { data: insights } = useQuery({
    queryKey: ['insights', siteId],
    queryFn: () => dashboardService.getInsights(siteId, importRatePkr),
    enabled: isAuthenticated && !!siteId,
    staleTime: 60 * 60 * 1000,
    refetchInterval: 60 * 60 * 1000,
    retry: 1,
  });

  const monthly = insights?.monthly_analysis;
  const yearly  = insights?.yearly_analysis;

  if (!monthly && !yearly) return null;

  return (
    <>
      {monthly && <MonthlyReportCard data={monthly} />}
      {yearly  && <div className="mt-4"><YearlyReportCard data={yearly} /></div>}
    </>
  );
};

export default PerformanceReportCard;
