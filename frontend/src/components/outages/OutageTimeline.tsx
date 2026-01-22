import { useMemo } from 'react';
import { format, startOfDay, endOfDay, differenceInMinutes } from 'date-fns';
import { cn } from '@/lib/utils';
import { OutageRecord, formatDuration } from '@/data/outageData';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface OutageTimelineProps {
  outages: OutageRecord[];
  date?: Date;
  className?: string;
}

export function OutageTimeline({ outages, date = new Date(), className }: OutageTimelineProps) {
  const dayStart = startOfDay(date);
  const dayEnd = endOfDay(date);
  const totalMinutes = 24 * 60;

  const segments = useMemo(() => {
    return outages.map(outage => {
      const startOffset = Math.max(0, differenceInMinutes(outage.startTime, dayStart));
      const endOffset = Math.min(totalMinutes, differenceInMinutes(outage.endTime, dayStart));
      const width = ((endOffset - startOffset) / totalMinutes) * 100;
      const left = (startOffset / totalMinutes) * 100;

      return {
        ...outage,
        left,
        width,
      };
    });
  }, [outages, dayStart]);

  const hours = Array.from({ length: 25 }, (_, i) => i);

  return (
    <div className={cn("space-y-2", className)}>
      {/* Timeline bar */}
      <div className="relative h-10 bg-success/20 rounded-lg overflow-hidden border border-border">
        {/* Grid lines */}
        {hours.map(hour => (
          <div
            key={hour}
            className="absolute top-0 bottom-0 w-px bg-border/50"
            style={{ left: `${(hour / 24) * 100}%` }}
          />
        ))}
        
        {/* Outage segments */}
        <TooltipProvider>
          {segments.map(segment => (
            <Tooltip key={segment.id}>
              <TooltipTrigger asChild>
                <div
                  className={cn(
                    "absolute top-1 bottom-1 rounded cursor-pointer transition-opacity hover:opacity-80",
                    segment.type === 'scheduled' && "bg-destructive/80",
                    segment.type === 'unscheduled' && "bg-orange-500/80",
                    segment.type === 'unknown' && "bg-muted-foreground/80"
                  )}
                  style={{
                    left: `${segment.left}%`,
                    width: `${Math.max(segment.width, 0.5)}%`,
                  }}
                />
              </TooltipTrigger>
              <TooltipContent>
                <div className="text-sm space-y-1">
                  <p className="font-semibold">
                    {format(segment.startTime, 'HH:mm')} - {format(segment.endTime, 'HH:mm')}
                  </p>
                  <p>Duration: {formatDuration(segment.duration)}</p>
                  <p className="capitalize">Type: {segment.type}</p>
                  <p>Battery used: {segment.batteryUsed} kWh</p>
                </div>
              </TooltipContent>
            </Tooltip>
          ))}
        </TooltipProvider>
      </div>

      {/* Hour labels */}
      <div className="relative h-4 text-xs text-muted-foreground">
        {[0, 6, 12, 18, 24].map(hour => (
          <span
            key={hour}
            className="absolute transform -translate-x-1/2"
            style={{ left: `${(hour / 24) * 100}%` }}
          >
            {hour === 24 ? '00' : hour.toString().padStart(2, '0')}:00
          </span>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-success/50" />
          <span className="text-muted-foreground">Grid Online</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-destructive/80" />
          <span className="text-muted-foreground">Scheduled</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-orange-500/80" />
          <span className="text-muted-foreground">Unscheduled</span>
        </div>
      </div>
    </div>
  );
}
