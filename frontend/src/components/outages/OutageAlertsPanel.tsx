import { format } from 'date-fns';
import { 
  Zap, 
  ZapOff, 
  Battery, 
  AlertTriangle,
  Clock,
  CheckCircle2
} from 'lucide-react';
import { OutageAlert } from '@/data/outageData';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';

interface OutageAlertsPanelProps {
  alerts: OutageAlert[];
  className?: string;
}

export function OutageAlertsPanel({ alerts, className }: OutageAlertsPanelProps) {
  const getAlertIcon = (type: OutageAlert['type']) => {
    switch (type) {
      case 'grid_down': return ZapOff;
      case 'grid_restored': return Zap;
      case 'low_battery': return Battery;
      case 'battery_critical': return AlertTriangle;
      case 'prediction': return Clock;
      default: return Zap;
    }
  };

  const getPriorityColor = (priority: OutageAlert['priority']) => {
    switch (priority) {
      case 'critical': return 'border-l-destructive bg-destructive/5';
      case 'high': return 'border-l-orange-500 bg-orange-500/5';
      case 'medium': return 'border-l-warning bg-warning/5';
      case 'low': return 'border-l-success bg-success/5';
      default: return 'border-l-muted';
    }
  };

  const getIconColor = (type: OutageAlert['type']) => {
    switch (type) {
      case 'grid_down': return 'text-destructive';
      case 'grid_restored': return 'text-success';
      case 'low_battery': return 'text-warning';
      case 'battery_critical': return 'text-destructive';
      case 'prediction': return 'text-info';
      default: return 'text-muted-foreground';
    }
  };

  return (
    <ScrollArea className={cn("h-[300px]", className)}>
      <div className="space-y-2 pr-4">
        {alerts.map((alert) => {
          const Icon = getAlertIcon(alert.type);
          
          return (
            <div
              key={alert.id}
              className={cn(
                "p-3 rounded-lg border-l-4 border transition-colors",
                getPriorityColor(alert.priority),
                alert.read && "opacity-60"
              )}
            >
              <div className="flex items-start gap-3">
                <div className={cn(
                  "p-1.5 rounded-md bg-background",
                  getIconColor(alert.type)
                )}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-foreground">
                    {alert.message}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground">
                      {format(alert.timestamp, 'MMM d, HH:mm')}
                    </span>
                    {alert.read && (
                      <Badge variant="outline" className="text-xs py-0 h-5">
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        Read
                      </Badge>
                    )}
                  </div>
                </div>
                <Badge 
                  variant="outline" 
                  className={cn(
                    "capitalize text-xs",
                    alert.priority === 'critical' && "border-destructive text-destructive",
                    alert.priority === 'high' && "border-orange-500 text-orange-500",
                    alert.priority === 'medium' && "border-warning text-warning",
                    alert.priority === 'low' && "border-success text-success"
                  )}
                >
                  {alert.priority}
                </Badge>
              </div>
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}
