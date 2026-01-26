import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Bell,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Zap,
  ZapOff,
  Battery,
  Search,
  Settings
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { NotificationSettingsPanel } from "@/components/settings/NotificationSettingsPanel";
import { alertsService, type UIAlert } from "@/api/services/alerts.service";

type AlertSeverity = "critical" | "warning" | "info" | "resolved";
type AlertCategory = "load-shedding" | "device" | "performance" | "billing" | "system";

const severityConfig = {
  critical: {
    icon: AlertCircle,
    bgColor: "bg-destructive/10",
    borderColor: "border-destructive/30",
    iconColor: "text-destructive",
    badgeVariant: "destructive" as const,
  },
  warning: {
    icon: AlertTriangle,
    bgColor: "bg-warning/10",
    borderColor: "border-warning/30",
    iconColor: "text-warning",
    badgeVariant: "secondary" as const,
  },
  info: {
    icon: Info,
    bgColor: "bg-info/10",
    borderColor: "border-info/30",
    iconColor: "text-info",
    badgeVariant: "secondary" as const,
  },
  resolved: {
    icon: CheckCircle2,
    bgColor: "bg-success/10",
    borderColor: "border-success/30",
    iconColor: "text-success",
    badgeVariant: "outline" as const,
  },
};

const categoryIcons = {
  "load-shedding": ZapOff,
  device: Battery,
  performance: Zap,
  billing: Info,
  system: AlertCircle,
};

const AlertCenterPage = () => {
  const [alerts, setAlerts] = useState<UIAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState<AlertCategory | "all">("all");

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const result = await alertsService.getAlertsForUI();
        setAlerts(result.alerts);
      } catch (error) {
        console.error('Failed to fetch alerts:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAlerts();
  }, []);

  const filteredAlerts = alerts.filter(alert => {
    const matchesSearch = alert.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         alert.message.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSeverity = severityFilter === "all" || alert.severity === severityFilter;
    const matchesCategory = categoryFilter === "all" || alert.category === categoryFilter;
    return matchesSearch && matchesSeverity && matchesCategory;
  });

  const unacknowledgedCount = alerts.filter(a => !a.acknowledged && a.severity !== "resolved").length;
  const criticalCount = alerts.filter(a => a.severity === "critical" && !a.acknowledged).length;

  const acknowledgeAlert = async (id: string) => {
    try {
      await alertsService.acknowledgeAlert(id);
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: true } : a));
      toast.success("Alert acknowledged");
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
      toast.error("Failed to acknowledge alert");
    }
  };

  const acknowledgeAll = () => {
    const unacknowledged = alerts.filter(a => !a.acknowledged);
    Promise.all(unacknowledged.map(a => alertsService.acknowledgeAlert(a.id).catch(() => null)));
    setAlerts(prev => prev.map(a => ({ ...a, acknowledged: true })));
    toast.success("All alerts acknowledged");
  };

  const clearResolved = () => {
    setAlerts(prev => prev.filter(a => a.severity !== "resolved"));
    toast.success("Resolved alerts cleared");
  };

  return (
    <AppLayout>
      <AppHeader
        title="Alert Center"
        subtitle="Monitor and manage system alerts"
      />

      <div className="p-6 space-y-6">
        {/* Alert Summary Bar */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          <div className="glass-card p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-destructive/20 flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-destructive" />
            </div>
            <div>
              <p className="text-2xl font-bold text-destructive">{criticalCount}</p>
              <p className="text-xs text-muted-foreground">Critical</p>
            </div>
          </div>

          <div className="glass-card p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-warning/20 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-warning" />
            </div>
            <div>
              <p className="text-2xl font-bold text-warning">
                {alerts.filter(a => a.severity === "warning" && !a.acknowledged).length}
              </p>
              <p className="text-xs text-muted-foreground">Warnings</p>
            </div>
          </div>

          <div className="glass-card p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
              <Bell className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{unacknowledgedCount}</p>
              <p className="text-xs text-muted-foreground">Unread</p>
            </div>
          </div>

          <div className="glass-card p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-success/20 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-2xl font-bold text-success">
                {alerts.filter(a => a.severity === "resolved").length}
              </p>
              <p className="text-xs text-muted-foreground">Resolved</p>
            </div>
          </div>
        </motion.div>

        <Tabs defaultValue="alerts" className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="alerts" className="gap-2">
              <Bell className="w-4 h-4" />
              Alerts
              {unacknowledgedCount > 0 && (
                <Badge variant="destructive" className="ml-1 h-5 px-1.5">
                  {unacknowledgedCount}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="preferences" className="gap-2">
              <Settings className="w-4 h-4" />
              Preferences
            </TabsTrigger>
          </TabsList>

          {/* Alerts Tab */}
          <TabsContent value="alerts" className="mt-6 space-y-4">
            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search alerts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>

              <Select value={severityFilter} onValueChange={(v) => setSeverityFilter(v as AlertSeverity | "all")}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="Severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Severity</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>

              <Select value={categoryFilter} onValueChange={(v) => setCategoryFilter(v as AlertCategory | "all")}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="load-shedding">Load Shedding</SelectItem>
                  <SelectItem value="device">Device</SelectItem>
                  <SelectItem value="performance">Performance</SelectItem>
                  <SelectItem value="billing">Billing</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>

              <div className="flex gap-2 ml-auto">
                <Button variant="outline" size="sm" onClick={acknowledgeAll} disabled={unacknowledgedCount === 0}>
                  Acknowledge All
                </Button>
                <Button variant="outline" size="sm" onClick={clearResolved}>
                  Clear Resolved
                </Button>
              </div>
            </div>

            {/* Alert List */}
            <div className="space-y-3">
              <AnimatePresence>
                {isLoading ? (
                  <div className="text-center py-12">
                    <p className="text-muted-foreground">Loading alerts...</p>
                  </div>
                ) : filteredAlerts.length === 0 ? (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-center py-12"
                  >
                    <CheckCircle2 className="w-12 h-12 mx-auto text-success mb-4" />
                    <p className="text-muted-foreground">No alerts match your filters</p>
                  </motion.div>
                ) : (
                  filteredAlerts.map((alert, index) => {
                    const config = severityConfig[alert.severity];
                    const SeverityIcon = config.icon;
                    const CategoryIcon = categoryIcons[alert.category];

                    return (
                      <motion.div
                        key={alert.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        transition={{ delay: index * 0.05 }}
                        className={cn(
                          "glass-card p-4 border-l-4 transition-all",
                          config.bgColor,
                          config.borderColor,
                          !alert.acknowledged && "ring-1 ring-inset ring-primary/20"
                        )}
                      >
                        <div className="flex items-start gap-4">
                          <div className={cn("p-2 rounded-lg", config.bgColor)}>
                            <SeverityIcon className={cn("w-5 h-5", config.iconColor)} />
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <h4 className={cn(
                                "font-medium text-foreground",
                                !alert.acknowledged && "font-semibold"
                              )}>
                                {alert.title}
                              </h4>
                              <Badge variant={config.badgeVariant} className="capitalize text-[10px]">
                                {alert.severity}
                              </Badge>
                              <Badge variant="outline" className="text-[10px] gap-1">
                                <CategoryIcon className="w-3 h-3" />
                                {alert.category}
                              </Badge>
                            </div>

                            <p className="text-sm text-muted-foreground mb-2">{alert.message}</p>

                            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                              <span className="font-mono">{alert.timestamp}</span>
                              {alert.device && (
                                <span className="text-foreground/70">{alert.device}</span>
                              )}
                            </div>
                          </div>

                          {!alert.acknowledged && alert.severity !== "resolved" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => acknowledgeAlert(alert.id)}
                              className="shrink-0"
                            >
                              Acknowledge
                            </Button>
                          )}
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </AnimatePresence>
            </div>
          </TabsContent>

          {/* Notification Preferences Tab */}
          <TabsContent value="preferences" className="mt-6">
            <NotificationSettingsPanel />
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
};

export default AlertCenterPage;
