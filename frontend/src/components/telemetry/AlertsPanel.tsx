import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, AlertCircle, Info, CheckCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { alertsService, type UIAlert } from "@/api/services/alerts.service";

interface Alert {
  id: string;
  timestamp: string;
  title: string;
  message: string;
  severity: "critical" | "warning" | "info" | "resolved";
  device?: string;
}

const severityConfig = {
  critical: {
    icon: AlertCircle,
    bgColor: "bg-destructive/10",
    borderColor: "border-destructive/30",
    iconColor: "text-destructive",
    badgeColor: "bg-destructive/20 text-destructive",
  },
  warning: {
    icon: AlertTriangle,
    bgColor: "bg-warning/10",
    borderColor: "border-warning/30",
    iconColor: "text-warning",
    badgeColor: "bg-warning/20 text-warning",
  },
  info: {
    icon: Info,
    bgColor: "bg-primary/10",
    borderColor: "border-primary/30",
    iconColor: "text-primary",
    badgeColor: "bg-primary/20 text-primary",
  },
  resolved: {
    icon: CheckCircle,
    bgColor: "bg-success/10",
    borderColor: "border-success/30",
    iconColor: "text-success",
    badgeColor: "bg-success/20 text-success",
  },
};

function mapUIAlertToLocal(uiAlert: UIAlert): Alert {
  return {
    id: uiAlert.id,
    timestamp: uiAlert.timestamp,
    title: uiAlert.title,
    message: uiAlert.message,
    severity: uiAlert.severity,
    device: uiAlert.device,
  };
}

export function AlertsPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const result = await alertsService.getAlertsForUI(
          undefined,
          { page: 1, page_size: 5 }
        );
        setAlerts(result.alerts.map(mapUIAlertToLocal));
      } catch (error) {
        console.error('Failed to fetch alerts:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAlerts();
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card overflow-hidden"
    >
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-warning" />
          <h3 className="text-lg font-semibold text-foreground">Active Alerts</h3>
        </div>
        <span className="text-xs text-muted-foreground px-2 py-1 bg-secondary rounded-full">
          {alerts.filter(a => a.severity !== "resolved").length} active
        </span>
      </div>

      <div className="p-4 space-y-3">
        {isLoading ? (
          <div className="text-center py-8 text-muted-foreground">
            <p className="text-sm">Loading alerts...</p>
          </div>
        ) : alerts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <CheckCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No active alerts</p>
            <p className="text-sm">All systems are operating normally</p>
          </div>
        ) : (
          alerts.map((alert, index) => {
            const config = severityConfig[alert.severity];
            const Icon = config.icon;

            return (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className={cn(
                  "p-4 rounded-lg border transition-colors",
                  config.bgColor,
                  config.borderColor
                )}
              >
                <div className="flex items-start gap-3">
                  <div className={cn("p-2 rounded-lg", config.bgColor)}>
                    <Icon className={cn("w-5 h-5", config.iconColor)} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-foreground">{alert.title}</h4>
                      <span className={cn("text-xs px-2 py-0.5 rounded-full capitalize", config.badgeColor)}>
                        {alert.severity}
                      </span>
                    </div>

                    <p className="text-sm text-muted-foreground mb-2">{alert.message}</p>

                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="font-mono">{alert.timestamp}</span>
                      {alert.device && (
                        <span className="text-foreground/70">{alert.device}</span>
                      )}
                    </div>
                  </div>

                  {alert.severity !== "resolved" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </motion.div>
            );
          })
        )}
      </div>
    </motion.div>
  );
}
