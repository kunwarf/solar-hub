import { useTelemetry, useDataPulse } from '@/contexts/TelemetryContext';
import { cn } from '@/lib/utils';
import { Radio } from 'lucide-react';

interface LiveIndicatorProps {
  className?: string;
  showLabel?: boolean;
}

const LiveIndicator = ({ className, showLabel = true }: LiveIndicatorProps) => {
  const { isLive, lastUpdated } = useTelemetry();
  const isPulsing = useDataPulse(500);

  if (!isLive) return null;

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <div className="relative flex items-center justify-center">
        <div className={cn(
          "h-2 w-2 rounded-full bg-red-500",
          isPulsing && "animate-pulse"
        )} />
        {isPulsing && (
          <div className="absolute h-2 w-2 rounded-full bg-red-500 animate-ping opacity-75" />
        )}
      </div>
      {showLabel && (
        <span className="text-xs font-semibold text-red-500 uppercase tracking-wide">
          Live
        </span>
      )}
    </div>
  );
};

export default LiveIndicator;
