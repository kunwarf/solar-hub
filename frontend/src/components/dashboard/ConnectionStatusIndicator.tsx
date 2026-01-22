import { useTelemetry, useDataPulse } from '@/contexts/TelemetryContext';
import { cn } from '@/lib/utils';
import { Wifi, WifiOff, RefreshCw, Radio } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface ConnectionStatusIndicatorProps {
  showLabel?: boolean;
  showReconnect?: boolean;
  compact?: boolean;
  className?: string;
}

const ConnectionStatusIndicator = ({
  showLabel = true,
  showReconnect = true,
  compact = false,
  className,
}: ConnectionStatusIndicatorProps) => {
  const { connectionStatus, reconnect, retryCount, nextRetryIn } = useTelemetry();
  const isPulsing = useDataPulse(500);

  const statusConfig = {
    connecting: {
      color: 'bg-yellow-500',
      icon: <Wifi className="h-3.5 w-3.5 animate-pulse" />,
      label: 'Connecting...',
      dotClass: 'animate-pulse',
    },
    connected: {
      color: 'bg-green-500',
      icon: <Wifi className="h-3.5 w-3.5" />,
      label: 'Connected',
      dotClass: '',
    },
    reconnecting: {
      color: 'bg-yellow-500',
      icon: <RefreshCw className="h-3.5 w-3.5 animate-spin" />,
      label: nextRetryIn ? `Reconnecting in ${nextRetryIn}s...` : 'Reconnecting...',
      dotClass: 'animate-pulse',
    },
    failed: {
      color: 'bg-red-500',
      icon: <WifiOff className="h-3.5 w-3.5" />,
      label: 'Connection Failed',
      dotClass: '',
    },
  };

  const config = statusConfig[connectionStatus];

  if (compact) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={cn("flex items-center gap-1.5", className)}>
            <div className={cn("h-2 w-2 rounded-full", config.color, config.dotClass)} />
            {connectionStatus === 'connected' && isPulsing && (
              <Radio className="h-3 w-3 text-green-500 animate-ping absolute" />
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p>{config.label}</p>
          {connectionStatus === 'failed' && (
            <p className="text-xs text-muted-foreground">Click to retry</p>
          )}
        </TooltipContent>
      </Tooltip>
    );
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {/* Status dot */}
      <div className="relative flex items-center">
        <div className={cn(
          "h-2.5 w-2.5 rounded-full",
          config.color,
          config.dotClass
        )} />
        {connectionStatus === 'connected' && isPulsing && (
          <div className={cn(
            "absolute h-2.5 w-2.5 rounded-full animate-ping",
            config.color,
            "opacity-75"
          )} />
        )}
      </div>

      {/* Icon */}
      <span className={cn(
        "text-muted-foreground",
        connectionStatus === 'connected' && "text-green-600 dark:text-green-400",
        connectionStatus === 'failed' && "text-red-600 dark:text-red-400"
      )}>
        {config.icon}
      </span>

      {/* Label */}
      {showLabel && (
        <span className={cn(
          "text-xs font-medium",
          connectionStatus === 'connected' && "text-green-600 dark:text-green-400",
          connectionStatus === 'reconnecting' && "text-yellow-600 dark:text-yellow-400",
          connectionStatus === 'failed' && "text-red-600 dark:text-red-400"
        )}>
          {config.label}
        </span>
      )}

      {/* Reconnect button */}
      {showReconnect && connectionStatus === 'failed' && (
        <Button
          variant="outline"
          size="sm"
          onClick={reconnect}
          className="h-6 px-2 text-xs"
        >
          <RefreshCw className="h-3 w-3 mr-1" />
          Retry
        </Button>
      )}

      {/* Retry count indicator */}
      {connectionStatus === 'reconnecting' && retryCount > 0 && (
        <span className="text-xs text-muted-foreground">
          (attempt {retryCount + 1})
        </span>
      )}
    </div>
  );
};

export default ConnectionStatusIndicator;
