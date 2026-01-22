import { useState } from "react";
import { motion } from "framer-motion";
import { 
  Mail, 
  Smartphone, 
  MessageSquare, 
  Moon, 
  Bell,
  AlertCircle,
  AlertTriangle,
  Info,
  Zap,
  ZapOff,
  Battery,
  Thermometer,
  Wifi,
  WifiOff,
  Calendar,
  FileText,
  CreditCard,
  Download,
  Send,
  CheckCircle2,
  Clock,
  Settings,
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface NotificationChannel {
  id: string;
  enabled: boolean;
  value: string;
}

interface AlertConfig {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  icon: React.ElementType;
  threshold?: number;
  thresholdMin?: number;
  thresholdMax?: number;
  thresholdUnit?: string;
}

interface NotificationLog {
  id: string;
  timestamp: string;
  channel: "email" | "sms" | "in-app";
  title: string;
  status: "sent" | "failed" | "pending";
}

const mockNotificationLog: NotificationLog[] = [
  { id: "1", timestamp: "2024-01-15 14:32", channel: "email", title: "Inverter Fault Alert", status: "sent" },
  { id: "2", timestamp: "2024-01-15 14:30", channel: "in-app", title: "Grid Power Restored", status: "sent" },
  { id: "3", timestamp: "2024-01-15 12:15", channel: "sms", title: "Low Battery Warning", status: "sent" },
  { id: "4", timestamp: "2024-01-15 10:00", channel: "email", title: "Daily Summary", status: "sent" },
  { id: "5", timestamp: "2024-01-14 22:45", channel: "in-app", title: "Grid Failure Detected", status: "sent" },
  { id: "6", timestamp: "2024-01-14 18:00", channel: "email", title: "Weekly Report Ready", status: "sent" },
  { id: "7", timestamp: "2024-01-14 16:30", channel: "sms", title: "High Temperature Alert", status: "failed" },
  { id: "8", timestamp: "2024-01-14 14:00", channel: "in-app", title: "Device Back Online", status: "sent" },
  { id: "9", timestamp: "2024-01-14 09:00", channel: "email", title: "Performance Drop Warning", status: "sent" },
  { id: "10", timestamp: "2024-01-13 20:00", channel: "in-app", title: "Firmware Update Available", status: "sent" },
];

export function NotificationSettingsPanel() {
  // Notification Channels
  const [channels, setChannels] = useState({
    email: { enabled: true, value: "user@example.com" },
    sms: { enabled: false, value: "+92-300-0000000" },
    inApp: { enabled: true, value: "" },
  });

  // Quiet Hours
  const [quietHours, setQuietHours] = useState({
    enabled: true,
    startTime: "23:00",
    endTime: "07:00",
    allowCritical: true,
  });

  // Critical Alerts (default: all ON)
  const [criticalAlerts, setCriticalAlerts] = useState<AlertConfig[]>([
    { id: "device_offline", name: "Device Offline", description: "When any device goes offline", enabled: true, icon: WifiOff },
    { id: "inverter_fault", name: "Inverter Fault", description: "Inverter error or malfunction", enabled: true, icon: Zap },
    { id: "battery_fault", name: "Battery Fault", description: "Battery system errors", enabled: true, icon: Battery },
    { id: "grid_failure", name: "Grid Failure", description: "Grid power outage detected", enabled: true, icon: ZapOff },
  ]);

  // Warning Alerts (default: all ON)
  const [warningAlerts, setWarningAlerts] = useState<AlertConfig[]>([
    { id: "low_battery", name: "Low Battery", description: "Battery below threshold", enabled: true, icon: Battery, threshold: 20, thresholdMin: 10, thresholdMax: 50, thresholdUnit: "%" },
    { id: "high_temperature", name: "High Temperature", description: "Device temperature above limit", enabled: true, icon: Thermometer, threshold: 45, thresholdMin: 40, thresholdMax: 60, thresholdUnit: "°C" },
    { id: "performance_drop", name: "Performance Drop", description: "Below expected output", enabled: true, icon: AlertTriangle, threshold: 25, thresholdMin: 10, thresholdMax: 50, thresholdUnit: "%" },
    { id: "communication_unstable", name: "Communication Unstable", description: "Intermittent device connection", enabled: true, icon: Wifi },
  ]);

  // Informational Alerts (default: OFF except subscription)
  const [infoAlerts, setInfoAlerts] = useState<AlertConfig[]>([
    { id: "device_online", name: "Device Back Online", description: "When a device reconnects", enabled: false, icon: CheckCircle2 },
    { id: "daily_summary", name: "Daily Summary", description: "Daily performance report", enabled: false, icon: FileText },
    { id: "weekly_report", name: "Weekly Report Ready", description: "Weekly analytics available", enabled: false, icon: Calendar },
    { id: "subscription_expiring", name: "Subscription Expiring", description: "30 days before expiry", enabled: true, icon: CreditCard },
    { id: "firmware_update", name: "Firmware Update Available", description: "New device firmware", enabled: false, icon: Download },
  ]);

  const [notificationLog] = useState<NotificationLog[]>(mockNotificationLog);

  const toggleAlert = (
    alerts: AlertConfig[],
    setAlerts: React.Dispatch<React.SetStateAction<AlertConfig[]>>,
    id: string
  ) => {
    setAlerts(alerts.map(a => a.id === id ? { ...a, enabled: !a.enabled } : a));
  };

  const updateThreshold = (
    alerts: AlertConfig[],
    setAlerts: React.Dispatch<React.SetStateAction<AlertConfig[]>>,
    id: string,
    value: number
  ) => {
    setAlerts(alerts.map(a => a.id === id ? { ...a, threshold: value } : a));
  };

  const handleTestNotification = () => {
    const enabledChannels = [];
    if (channels.email.enabled) enabledChannels.push("Email");
    if (channels.sms.enabled) enabledChannels.push("SMS");
    if (channels.inApp.enabled) enabledChannels.push("In-App");

    if (enabledChannels.length === 0) {
      toast.error("No notification channels enabled");
      return;
    }

    toast.success(`Test notification sent to: ${enabledChannels.join(", ")}`);
  };

  const validatePakistaniPhone = (phone: string): boolean => {
    const pattern = /^\+92-[0-9]{3}-[0-9]{7}$/;
    return pattern.test(phone);
  };

  const channelIcons = {
    email: Mail,
    sms: MessageSquare,
    "in-app": Bell,
  };

  const statusColors = {
    sent: "text-success",
    failed: "text-destructive",
    pending: "text-warning",
  };

  return (
    <div className="space-y-6">
      {/* Notification Channels */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
            <Bell className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-foreground">Notification Channels</h3>
            <p className="text-sm text-muted-foreground">Choose how you want to receive alerts</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Email */}
          <div className="p-4 rounded-lg bg-secondary/30 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Mail className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="font-medium text-foreground">Email Notifications</p>
                  <p className="text-sm text-muted-foreground">Receive alerts via email</p>
                </div>
              </div>
              <Switch
                checked={channels.email.enabled}
                onCheckedChange={(checked) => setChannels({ ...channels, email: { ...channels.email, enabled: checked } })}
              />
            </div>
            {channels.email.enabled && (
              <div className="pl-8">
                <Label htmlFor="email-input" className="text-sm text-muted-foreground">Email Address</Label>
                <Input
                  id="email-input"
                  type="email"
                  value={channels.email.value}
                  onChange={(e) => setChannels({ ...channels, email: { ...channels.email, value: e.target.value } })}
                  placeholder="your@email.com"
                  className="mt-1 bg-background/50"
                />
              </div>
            )}
          </div>

          {/* SMS */}
          <div className="p-4 rounded-lg bg-secondary/30 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="font-medium text-foreground">SMS Notifications</p>
                  <p className="text-sm text-muted-foreground">Receive alerts via SMS</p>
                </div>
              </div>
              <Switch
                checked={channels.sms.enabled}
                onCheckedChange={(checked) => setChannels({ ...channels, sms: { ...channels.sms, enabled: checked } })}
              />
            </div>
            {channels.sms.enabled && (
              <div className="pl-8 space-y-2">
                <Label htmlFor="phone-input" className="text-sm text-muted-foreground">Phone Number (Pakistan)</Label>
                <Input
                  id="phone-input"
                  type="tel"
                  value={channels.sms.value}
                  onChange={(e) => setChannels({ ...channels, sms: { ...channels.sms, value: e.target.value } })}
                  placeholder="+92-300-0000000"
                  className={cn(
                    "mt-1 bg-background/50",
                    channels.sms.value && !validatePakistaniPhone(channels.sms.value) && "border-destructive"
                  )}
                />
                {channels.sms.value && !validatePakistaniPhone(channels.sms.value) && (
                  <p className="text-xs text-destructive">Format: +92-XXX-XXXXXXX</p>
                )}
              </div>
            )}
          </div>

          {/* In-App */}
          <div className="p-4 rounded-lg bg-secondary/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Smartphone className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="font-medium text-foreground">In-App Notifications</p>
                  <p className="text-sm text-muted-foreground">Show alerts in the application</p>
                </div>
              </div>
              <Switch
                checked={channels.inApp.enabled}
                onCheckedChange={(checked) => setChannels({ ...channels, inApp: { ...channels.inApp, enabled: checked } })}
              />
            </div>
          </div>
        </div>
      </motion.div>

      {/* Quiet Hours */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
              <Moon className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Quiet Hours</h3>
              <p className="text-sm text-muted-foreground">Silence non-critical alerts during specific hours</p>
            </div>
          </div>
          <Switch
            checked={quietHours.enabled}
            onCheckedChange={(enabled) => setQuietHours({ ...quietHours, enabled })}
          />
        </div>

        {quietHours.enabled && (
          <div className="space-y-4 pl-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">Start Time</Label>
                <Input
                  type="time"
                  value={quietHours.startTime}
                  onChange={(e) => setQuietHours({ ...quietHours, startTime: e.target.value })}
                  className="bg-background/50"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">End Time</Label>
                <Input
                  type="time"
                  value={quietHours.endTime}
                  onChange={(e) => setQuietHours({ ...quietHours, endTime: e.target.value })}
                  className="bg-background/50"
                />
              </div>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-destructive/10 border border-destructive/20">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-destructive" />
                <div>
                  <p className="font-medium text-foreground">Allow Critical Alerts</p>
                  <p className="text-sm text-muted-foreground">Still receive critical alerts during quiet hours</p>
                </div>
              </div>
              <Switch
                checked={quietHours.allowCritical}
                onCheckedChange={(checked) => setQuietHours({ ...quietHours, allowCritical: checked })}
              />
            </div>
          </div>
        )}
      </motion.div>

      {/* Alert Configuration */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card p-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
            <Settings className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-foreground">Alert Configuration</h3>
            <p className="text-sm text-muted-foreground">Configure which alerts you want to receive</p>
          </div>
        </div>

        <Accordion type="multiple" defaultValue={["critical", "warning", "info"]} className="space-y-3">
          {/* Critical Alerts */}
          <AccordionItem value="critical" className="border rounded-lg bg-destructive/5 border-destructive/20">
            <AccordionTrigger className="px-4 py-3 hover:no-underline">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-destructive" />
                <span className="font-medium text-foreground">Critical Alerts</span>
                <Badge variant="destructive" className="text-xs">
                  {criticalAlerts.filter(a => a.enabled).length}/{criticalAlerts.length}
                </Badge>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="space-y-3">
                {criticalAlerts.map((alert) => (
                  <div key={alert.id} className="flex items-center justify-between p-3 rounded-lg bg-background/50">
                    <div className="flex items-center gap-3">
                      <alert.icon className="w-4 h-4 text-muted-foreground" />
                      <div>
                        <p className="font-medium text-sm text-foreground">{alert.name}</p>
                        <p className="text-xs text-muted-foreground">{alert.description}</p>
                      </div>
                    </div>
                    <Switch
                      checked={alert.enabled}
                      onCheckedChange={() => toggleAlert(criticalAlerts, setCriticalAlerts, alert.id)}
                    />
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Warning Alerts */}
          <AccordionItem value="warning" className="border rounded-lg bg-warning/5 border-warning/20">
            <AccordionTrigger className="px-4 py-3 hover:no-underline">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-warning" />
                <span className="font-medium text-foreground">Warning Alerts</span>
                <Badge className="text-xs bg-warning/20 text-warning border-warning/30">
                  {warningAlerts.filter(a => a.enabled).length}/{warningAlerts.length}
                </Badge>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="space-y-4">
                {warningAlerts.map((alert) => (
                  <div key={alert.id} className="p-3 rounded-lg bg-background/50 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <alert.icon className="w-4 h-4 text-muted-foreground" />
                        <div>
                          <p className="font-medium text-sm text-foreground">{alert.name}</p>
                          <p className="text-xs text-muted-foreground">{alert.description}</p>
                        </div>
                      </div>
                      <Switch
                        checked={alert.enabled}
                        onCheckedChange={() => toggleAlert(warningAlerts, setWarningAlerts, alert.id)}
                      />
                    </div>
                    {alert.enabled && alert.threshold !== undefined && (
                      <div className="pl-7 space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Threshold</span>
                          <span className="font-mono font-medium text-foreground">
                            {alert.threshold}{alert.thresholdUnit}
                          </span>
                        </div>
                        <Slider
                          value={[alert.threshold]}
                          min={alert.thresholdMin}
                          max={alert.thresholdMax}
                          step={1}
                          onValueChange={([value]) => updateThreshold(warningAlerts, setWarningAlerts, alert.id, value)}
                          className="w-full"
                        />
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>{alert.thresholdMin}{alert.thresholdUnit}</span>
                          <span>{alert.thresholdMax}{alert.thresholdUnit}</span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Informational Alerts */}
          <AccordionItem value="info" className="border rounded-lg bg-info/5 border-info/20">
            <AccordionTrigger className="px-4 py-3 hover:no-underline">
              <div className="flex items-center gap-3">
                <Info className="w-5 h-5 text-info" />
                <span className="font-medium text-foreground">Informational Alerts</span>
                <Badge variant="outline" className="text-xs">
                  {infoAlerts.filter(a => a.enabled).length}/{infoAlerts.length}
                </Badge>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="space-y-3">
                {infoAlerts.map((alert) => (
                  <div key={alert.id} className="flex items-center justify-between p-3 rounded-lg bg-background/50">
                    <div className="flex items-center gap-3">
                      <alert.icon className="w-4 h-4 text-muted-foreground" />
                      <div>
                        <p className="font-medium text-sm text-foreground">{alert.name}</p>
                        <p className="text-xs text-muted-foreground">{alert.description}</p>
                      </div>
                    </div>
                    <Switch
                      checked={alert.enabled}
                      onCheckedChange={() => toggleAlert(infoAlerts, setInfoAlerts, alert.id)}
                    />
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </motion.div>

      {/* Test Notification */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="glass-card p-6"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
              <Send className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Test Notification</h3>
              <p className="text-sm text-muted-foreground">Send a test alert to all enabled channels</p>
            </div>
          </div>
          <Button onClick={handleTestNotification} className="gap-2">
            <Send className="w-4 h-4" />
            Send Test
          </Button>
        </div>
      </motion.div>

      {/* Recent Notifications Log */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass-card p-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
            <Clock className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-foreground">Recent Notifications</h3>
            <p className="text-sm text-muted-foreground">Last 10 notifications sent</p>
          </div>
        </div>

        <div className="space-y-2">
          {notificationLog.map((log) => {
            const ChannelIcon = channelIcons[log.channel];
            return (
              <div
                key={log.id}
                className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-background/50">
                    <ChannelIcon className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="font-medium text-sm text-foreground">{log.title}</p>
                    <p className="text-xs text-muted-foreground font-mono">{log.timestamp}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px] capitalize">
                    {log.channel}
                  </Badge>
                  <span className={cn("text-xs font-medium capitalize", statusColors[log.status])}>
                    {log.status}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}
