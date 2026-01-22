import { format, isSameDay, startOfWeek, addDays, isToday } from 'date-fns';
import { cn } from '@/lib/utils';
import { DailyOutageSummary, formatDuration } from '@/data/outageData';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface OutageCalendarProps {
  summaries: DailyOutageSummary[];
  className?: string;
}

export function OutageCalendar({ summaries, className }: OutageCalendarProps) {
  const today = new Date();
  const weekStart = startOfWeek(today, { weekStartsOn: 1 }); // Monday
  
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  const getSeverityColor = (outageCount: number, totalDuration: number) => {
    if (outageCount === 0) return 'bg-success/20 border-success/30';
    if (totalDuration > 360) return 'bg-destructive/30 border-destructive/40'; // > 6 hours
    if (totalDuration > 180) return 'bg-orange-500/30 border-orange-500/40'; // > 3 hours
    if (totalDuration > 60) return 'bg-warning/30 border-warning/40'; // > 1 hour
    return 'bg-warning/20 border-warning/30';
  };

  return (
    <div className={cn("", className)}>
      <div className="grid grid-cols-7 gap-2">
        {/* Day headers */}
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => (
          <div key={day} className="text-center text-xs font-medium text-muted-foreground pb-2">
            {day}
          </div>
        ))}

        {/* Day cells */}
        <TooltipProvider>
          {days.map(day => {
            const summary = summaries.find(s => isSameDay(s.date, day));
            const outageCount = summary?.outageCount ?? 0;
            const totalDuration = summary?.totalDuration ?? 0;
            const isDayToday = isToday(day);

            return (
              <Tooltip key={day.toISOString()}>
                <TooltipTrigger asChild>
                  <div
                    className={cn(
                      "aspect-square rounded-lg border-2 flex flex-col items-center justify-center cursor-pointer transition-all hover:scale-105",
                      getSeverityColor(outageCount, totalDuration),
                      isDayToday && "ring-2 ring-primary ring-offset-2 ring-offset-background"
                    )}
                  >
                    <span className={cn(
                      "text-lg font-semibold",
                      isDayToday ? "text-primary" : "text-foreground"
                    )}>
                      {format(day, 'd')}
                    </span>
                    {outageCount > 0 && (
                      <span className="text-xs text-muted-foreground">
                        {outageCount} out
                      </span>
                    )}
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <div className="text-sm space-y-1">
                    <p className="font-semibold">{format(day, 'EEEE, MMM d')}</p>
                    {outageCount > 0 ? (
                      <>
                        <p>{outageCount} outage{outageCount > 1 ? 's' : ''}</p>
                        <p>Total: {formatDuration(totalDuration)}</p>
                      </>
                    ) : (
                      <p className="text-success">No outages</p>
                    )}
                  </div>
                </TooltipContent>
              </Tooltip>
            );
          })}
        </TooltipProvider>
      </div>
    </div>
  );
}
