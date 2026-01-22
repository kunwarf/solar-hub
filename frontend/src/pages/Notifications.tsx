import { useState } from "react";
import { motion } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Bell, 
  BellOff, 
  Check, 
  Trash2, 
  AlertTriangle, 
  Info, 
  CheckCircle2,
  Battery,
  Zap,
  Sun,
  Settings,
  Mail,
  Smartphone
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface Notification {
  id: string;
  type: "warning" | "info" | "success" | "error";
  title: string;
  message: string;
  time: string;
  read: boolean;
  category: "system" | "device" | "billing" | "energy";
}

// Mock notifications data
const mockNotifications: Notification[] = [
  { id: "1", type: "warning", title: "Battery Low Warning", message: "Battery Pack 2 is at 15%. Consider charging soon.", time: "5 minutes ago", read: false, category: "device" },
  { id: "2", type: "success", title: "Grid Export Peak", message: "Exported 8.2 kWh today - your best day this week!", time: "1 hour ago", read: false, category: "energy" },
  { id: "3", type: "info", title: "Firmware Update Available", message: "Inverter Array 1 has a new firmware update available.", time: "2 hours ago", read: false, category: "system" },
  { id: "4", type: "success", title: "Monthly Savings Report", message: "You saved $127.50 on your electricity bill this month.", time: "1 day ago", read: true, category: "billing" },
  { id: "5", type: "warning", title: "High Consumption Alert", message: "Home consumption exceeded 5 kW for over 2 hours.", time: "2 days ago", read: true, category: "energy" },
  { id: "6", type: "info", title: "Scheduled Maintenance", message: "System maintenance scheduled for Sunday 2:00 AM.", time: "3 days ago", read: true, category: "system" },
  { id: "7", type: "error", title: "Connection Lost", message: "Meter connection was temporarily lost and restored.", time: "4 days ago", read: true, category: "device" },
  { id: "8", type: "success", title: "Self-Sufficiency Goal", message: "Achieved 95% self-sufficiency yesterday!", time: "5 days ago", read: true, category: "energy" },
];

const notificationIcons = {
  warning: AlertTriangle,
  info: Info,
  success: CheckCircle2,
  error: AlertTriangle,
};

const notificationColors = {
  warning: "text-warning bg-warning/10 border-warning/30",
  info: "text-primary bg-primary/10 border-primary/30",
  success: "text-success bg-success/10 border-success/30",
  error: "text-destructive bg-destructive/10 border-destructive/30",
};

const categoryIcons = {
  system: Settings,
  device: Battery,
  billing: Zap,
  energy: Sun,
};

const NotificationsPage = () => {
  const [notifications, setNotifications] = useState<Notification[]>(mockNotifications);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  
  // Notification preferences
  const [preferences, setPreferences] = useState({
    emailAlerts: true,
    pushNotifications: true,
    systemAlerts: true,
    deviceAlerts: true,
    billingAlerts: true,
    energyAlerts: true,
    dailyDigest: false,
    weeklyReport: true,
  });

  const filteredNotifications = notifications.filter(n => 
    filter === "all" ? true : !n.read
  );

  const unreadCount = notifications.filter(n => !n.read).length;

  const markAsRead = (id: string) => {
    setNotifications(prev => 
      prev.map(n => n.id === id ? { ...n, read: true } : n)
    );
  };

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    toast.success("All notifications marked as read");
  };

  const deleteNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
    toast.success("Notification deleted");
  };

  const clearAll = () => {
    setNotifications([]);
    toast.success("All notifications cleared");
  };

  const updatePreference = (key: keyof typeof preferences) => {
    setPreferences(prev => ({ ...prev, [key]: !prev[key] }));
    toast.success("Preference updated");
  };

  return (
    <AppLayout>
      <AppHeader 
        title="Notifications" 
        subtitle="View alerts and manage notification preferences"
      />
      
      <div className="p-6 space-y-6">
        <Tabs defaultValue="notifications" className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="notifications" className="gap-2">
              <Bell className="w-4 h-4" />
              Notifications
              {unreadCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-primary text-primary-foreground rounded-full">
                  {unreadCount}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="preferences" className="gap-2">
              <Settings className="w-4 h-4" />
              Preferences
            </TabsTrigger>
          </TabsList>

          {/* Notifications Tab */}
          <TabsContent value="notifications" className="mt-6">
            {/* Actions Bar */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-wrap items-center justify-between gap-4 mb-6"
            >
              <div className="flex gap-2">
                <Button
                  variant={filter === "all" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilter("all")}
                >
                  All
                </Button>
                <Button
                  variant={filter === "unread" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilter("unread")}
                >
                  Unread ({unreadCount})
                </Button>
              </div>
              
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={markAllAsRead} disabled={unreadCount === 0}>
                  <Check className="w-4 h-4 mr-2" />
                  Mark all read
                </Button>
                <Button variant="outline" size="sm" onClick={clearAll} disabled={notifications.length === 0}>
                  <Trash2 className="w-4 h-4 mr-2" />
                  Clear all
                </Button>
              </div>
            </motion.div>

            {/* Notifications List */}
            <div className="space-y-3">
              {filteredNotifications.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center py-12"
                >
                  <BellOff className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">No notifications to show</p>
                </motion.div>
              ) : (
                filteredNotifications.map((notification, index) => {
                  const TypeIcon = notificationIcons[notification.type];
                  const CategoryIcon = categoryIcons[notification.category];
                  
                  return (
                    <motion.div
                      key={notification.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className={cn(
                        "glass-card p-4 border-l-4 flex items-start gap-4",
                        notificationColors[notification.type],
                        !notification.read && "bg-secondary/50"
                      )}
                    >
                      <div className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0",
                        notificationColors[notification.type].split(" ")[1]
                      )}>
                        <TypeIcon className="w-5 h-5" />
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className={cn(
                            "font-medium text-foreground",
                            !notification.read && "font-semibold"
                          )}>
                            {notification.title}
                          </h4>
                          {!notification.read && (
                            <span className="w-2 h-2 bg-primary rounded-full" />
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">{notification.message}</p>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                          <span>{notification.time}</span>
                          <span className="flex items-center gap-1">
                            <CategoryIcon className="w-3 h-3" />
                            {notification.category}
                          </span>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {!notification.read && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => markAsRead(notification.id)}
                          >
                            <Check className="w-4 h-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => deleteNotification(notification.id)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </motion.div>
                  );
                })
              )}
            </div>
          </TabsContent>

          {/* Preferences Tab */}
          <TabsContent value="preferences" className="mt-6 space-y-6">
            {/* Delivery Methods */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-6"
            >
              <h3 className="text-lg font-semibold text-foreground mb-4">Delivery Methods</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Mail className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">Email Alerts</p>
                      <p className="text-sm text-muted-foreground">Receive notifications via email</p>
                    </div>
                  </div>
                  <Switch
                    checked={preferences.emailAlerts}
                    onCheckedChange={() => updatePreference("emailAlerts")}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Smartphone className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">Push Notifications</p>
                      <p className="text-sm text-muted-foreground">Receive push notifications on your device</p>
                    </div>
                  </div>
                  <Switch
                    checked={preferences.pushNotifications}
                    onCheckedChange={() => updatePreference("pushNotifications")}
                  />
                </div>
              </div>
            </motion.div>

            {/* Alert Categories */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="glass-card p-6"
            >
              <h3 className="text-lg font-semibold text-foreground mb-4">Alert Categories</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Settings className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">System Alerts</p>
                      <p className="text-sm text-muted-foreground">Updates, maintenance, and system status</p>
                    </div>
                  </div>
                  <Switch
                    checked={preferences.systemAlerts}
                    onCheckedChange={() => updatePreference("systemAlerts")}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Battery className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">Device Alerts</p>
                      <p className="text-sm text-muted-foreground">Battery, inverter, and meter notifications</p>
                    </div>
                  </div>
                  <Switch
                    checked={preferences.deviceAlerts}
                    onCheckedChange={() => updatePreference("deviceAlerts")}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Zap className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">Billing Alerts</p>
                      <p className="text-sm text-muted-foreground">Savings reports and billing updates</p>
                    </div>
                  </div>
                  <Switch
                    checked={preferences.billingAlerts}
                    onCheckedChange={() => updatePreference("billingAlerts")}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Sun className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">Energy Alerts</p>
                      <p className="text-sm text-muted-foreground">Production, consumption, and grid status</p>
                    </div>
                  </div>
                  <Switch
                    checked={preferences.energyAlerts}
                    onCheckedChange={() => updatePreference("energyAlerts")}
                  />
                </div>
              </div>
            </motion.div>

            {/* Reports */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="glass-card p-6"
            >
              <h3 className="text-lg font-semibold text-foreground mb-4">Reports & Digests</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-foreground">Daily Digest</p>
                    <p className="text-sm text-muted-foreground">Receive a daily summary of your energy data</p>
                  </div>
                  <Switch
                    checked={preferences.dailyDigest}
                    onCheckedChange={() => updatePreference("dailyDigest")}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-foreground">Weekly Report</p>
                    <p className="text-sm text-muted-foreground">Get a comprehensive weekly performance report</p>
                  </div>
                  <Switch
                    checked={preferences.weeklyReport}
                    onCheckedChange={() => updatePreference("weeklyReport")}
                  />
                </div>
              </div>
            </motion.div>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
};

export default NotificationsPage;