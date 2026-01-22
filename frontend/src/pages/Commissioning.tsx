import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  HardHat,
  LogOut,
  CheckCircle2,
  Circle,
  Loader2,
  Wrench,
  Power,
  Wifi,
  Plus,
  PlayCircle,
  Activity,
  Settings,
  Send,
  HelpCircle,
  Clock,
  Signal,
  Gauge,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Terminal,
  Info,
  User,
  Mail,
  CheckCheck,
  Zap,
  Thermometer,
  Battery,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useUserRole } from "@/contexts/UserRoleContext";
import { format, formatDistanceToNow } from "date-fns";

type ChecklistItemStatus = "pending" | "in-progress" | "completed" | "failed";

interface ChecklistItem {
  id: string;
  title: string;
  description: string;
  status: ChecklistItemStatus;
  action?: "add-device" | "run-test" | "preview" | "verify" | "notify";
}

interface DiagnosticResult {
  latency: number;
  packetLoss: number;
  signalStrength: number;
  timestamp: string;
}

const CommissioningPage = () => {
  const navigate = useNavigate();
  const { currentUser, isInstaller, hasPermission } = useUserRole();
  
  const [checklist, setChecklist] = useState<ChecklistItem[]>([
    { id: "physical", title: "Device physically installed", description: "Confirm the device is mounted and secured properly", status: "completed" },
    { id: "powered", title: "Device powered on", description: "Verify power indicator lights are active", status: "completed" },
    { id: "network", title: "Network connectivity verified", description: "Device connected to local network or RS485 bus", status: "completed" },
    { id: "registered", title: "Device registered in platform", description: "Add the device to the monitoring system", status: "pending", action: "add-device" },
    { id: "communication", title: "Communication test passed", description: "Verify two-way communication with device", status: "pending", action: "run-test" },
    { id: "telemetry", title: "Basic telemetry received", description: "Confirm data is flowing from device", status: "pending", action: "preview" },
    { id: "config", title: "Configuration verified", description: "Review and confirm key parameters", status: "pending", action: "verify" },
    { id: "handoff", title: "Owner notified / Handoff complete", description: "Send completion notice to system owner", status: "pending", action: "notify" },
  ]);

  const [isRunningTest, setIsRunningTest] = useState(false);
  const [diagnosticResult, setDiagnosticResult] = useState<DiagnosticResult | null>(null);
  const [isRawDataOpen, setIsRawDataOpen] = useState(false);
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  
  // Configuration state
  const [deviceConfig, setDeviceConfig] = useState({
    name: "Senergy 5kW Inverter",
    pollingInterval: 30,
    alertThresholds: {
      lowBattery: 20,
      highTemp: 55,
    },
    networkSettings: {
      ip: "192.168.1.100",
      port: 502,
      slaveId: 1,
    },
  });

  // Handoff state
  const [ownerEmail, setOwnerEmail] = useState("ahmad.khan@example.com");
  const [handoffMessage, setHandoffMessage] = useState("");
  const [isHandoffSent, setIsHandoffSent] = useState(false);

  // Mock raw telemetry data
  const rawTelemetry = {
    timestamp: new Date().toISOString(),
    device_id: "INV_001",
    model: "Senergy 5kW",
    firmware: "v2.3.1",
    data: {
      pv_power: 4250,
      pv_voltage: 380.5,
      pv_current: 11.2,
      battery_soc: 85,
      battery_voltage: 52.4,
      battery_current: 15.3,
      grid_power: -1200,
      load_power: 3050,
      inverter_temp: 42.5,
      status: "normal",
    },
  };

  const completedCount = checklist.filter(item => item.status === "completed").length;
  const progress = (completedCount / checklist.length) * 100;

  const updateChecklistItem = (id: string, status: ChecklistItemStatus) => {
    setChecklist(prev => prev.map(item => 
      item.id === id ? { ...item, status } : item
    ));
  };

  const handleRunTest = async () => {
    setIsRunningTest(true);
    updateChecklistItem("communication", "in-progress");
    
    // Simulate test
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const result: DiagnosticResult = {
      latency: Math.floor(Math.random() * 50) + 10,
      packetLoss: Math.random() * 2,
      signalStrength: Math.floor(Math.random() * 30) + 70,
      timestamp: new Date().toISOString(),
    };
    
    setDiagnosticResult(result);
    setIsRunningTest(false);
    
    if (result.packetLoss < 5 && result.latency < 100) {
      updateChecklistItem("communication", "completed");
      toast.success("Communication test passed!");
    } else {
      updateChecklistItem("communication", "failed");
      toast.error("Communication test failed. Check connection.");
    }
  };

  const handlePreviewTelemetry = () => {
    updateChecklistItem("telemetry", "completed");
    setIsRawDataOpen(true);
    toast.success("Telemetry data received successfully");
  };

  const handleVerifyConfig = () => {
    updateChecklistItem("config", "completed");
    setIsConfigOpen(true);
    toast.success("Configuration verified");
  };

  const handleSendHandoff = () => {
    if (!ownerEmail.trim()) {
      toast.error("Please enter owner email");
      return;
    }
    
    setIsHandoffSent(true);
    updateChecklistItem("handoff", "completed");
    toast.success(`Handoff notification sent to ${ownerEmail}`);
  };

  const handleExitCommissioning = () => {
    navigate("/devices");
  };

  const getStatusIcon = (status: ChecklistItemStatus) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="w-5 h-5 text-success" />;
      case "in-progress":
        return <Loader2 className="w-5 h-5 text-primary animate-spin" />;
      case "failed":
        return <AlertTriangle className="w-5 h-5 text-destructive" />;
      default:
        return <Circle className="w-5 h-5 text-muted-foreground" />;
    }
  };

  const getSignalStrengthColor = (strength: number) => {
    if (strength >= 80) return "text-success";
    if (strength >= 60) return "text-warning";
    return "text-destructive";
  };

  // Access check
  if (!hasPermission("commissioning_mode") && !hasPermission("manage_devices")) {
    return (
      <AppLayout>
        <AppHeader title="Commissioning" subtitle="Access restricted" />
        <div className="p-6 flex flex-col items-center justify-center min-h-[400px]">
          <HardHat className="w-16 h-16 text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold text-foreground mb-2">Installer Access Required</h2>
          <p className="text-muted-foreground text-center max-w-md">
            This page is only available to installers during the commissioning period.
          </p>
          <Button variant="outline" className="mt-6" onClick={() => navigate("/devices")}>
            Back to Devices
          </Button>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      {/* Commissioning Mode Banner */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-amber-500/20 border-b border-amber-500/30 px-6 py-4"
      >
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-amber-500/30 flex items-center justify-center">
              <HardHat className="w-6 h-6 text-amber-600" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-amber-700 dark:text-amber-400">Commissioning Mode</h2>
                <Badge className="bg-amber-500/30 text-amber-700 dark:text-amber-300 border-amber-500/50">
                  Active
                </Badge>
              </div>
              <div className="flex items-center gap-3 text-sm text-amber-600/80 dark:text-amber-300/80">
                <span className="flex items-center gap-1">
                  <User className="w-4 h-4" />
                  {currentUser.name}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  Expires {formatDistanceToNow(new Date(currentUser.installerExpiresAt || Date.now() + 7 * 24 * 60 * 60 * 1000), { addSuffix: true })}
                </span>
              </div>
            </div>
          </div>
          
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" className="gap-2 border-amber-500/50 text-amber-700 hover:bg-amber-500/20">
                <LogOut className="w-4 h-4" />
                Exit Commissioning
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Exit Commissioning Mode?</AlertDialogTitle>
                <AlertDialogDescription>
                  {completedCount < checklist.length 
                    ? `You have ${checklist.length - completedCount} incomplete steps. Are you sure you want to exit?`
                    : "All commissioning steps are complete. You can safely exit."
                  }
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleExitCommissioning}>
                  Exit
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </motion.div>

      <AppHeader 
        title="Device Commissioning" 
        subtitle="Step-by-step device setup and verification"
      />
      
      <div className="p-6 space-y-6">
        {/* Progress Overview */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Commissioning Progress</h3>
              <p className="text-sm text-muted-foreground">
                {completedCount} of {checklist.length} steps completed
              </p>
            </div>
            <div className="text-2xl font-bold text-primary">{Math.round(progress)}%</div>
          </div>
          <Progress value={progress} className="h-3" />
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Checklist */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-2 glass-card p-6"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                <CheckCheck className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-foreground">Installation Checklist</h3>
                <p className="text-sm text-muted-foreground">Complete all steps to finalize commissioning</p>
              </div>
            </div>

            <div className="space-y-3">
              {checklist.map((item, index) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={cn(
                    "p-4 rounded-lg border transition-all",
                    item.status === "completed" && "bg-success/5 border-success/20",
                    item.status === "in-progress" && "bg-primary/5 border-primary/20",
                    item.status === "failed" && "bg-destructive/5 border-destructive/20",
                    item.status === "pending" && "bg-secondary/30 border-border"
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div className="mt-0.5">{getStatusIcon(item.status)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className={cn(
                          "font-medium",
                          item.status === "completed" && "text-success line-through",
                          item.status === "pending" && "text-foreground"
                        )}>
                          {item.title}
                        </p>
                        {item.status === "failed" && (
                          <Badge variant="destructive" className="text-[10px]">Failed</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">{item.description}</p>
                    </div>
                    
                    {item.status !== "completed" && (
                      <div className="shrink-0">
                        {item.action === "add-device" && (
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => {
                              navigate("/devices/manage");
                            }}
                            className="gap-1"
                          >
                            <Plus className="w-4 h-4" />
                            Add Device
                          </Button>
                        )}
                        {item.action === "run-test" && (
                          <Button 
                            size="sm" 
                            onClick={handleRunTest}
                            disabled={isRunningTest}
                            className="gap-1"
                          >
                            {isRunningTest ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <PlayCircle className="w-4 h-4" />
                            )}
                            Run Test
                          </Button>
                        )}
                        {item.action === "preview" && (
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={handlePreviewTelemetry}
                            className="gap-1"
                          >
                            <Activity className="w-4 h-4" />
                            Preview
                          </Button>
                        )}
                        {item.action === "verify" && (
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={handleVerifyConfig}
                            className="gap-1"
                          >
                            <Settings className="w-4 h-4" />
                            Verify
                          </Button>
                        )}
                        {item.action === "notify" && (
                          <Button 
                            size="sm" 
                            onClick={() => document.getElementById("handoff-section")?.scrollIntoView({ behavior: "smooth" })}
                            className="gap-1"
                          >
                            <Send className="w-4 h-4" />
                            Notify
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Diagnostic Tools */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="space-y-6"
          >
            <div className="glass-card p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                  <Gauge className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground">Diagnostics</h3>
                  <p className="text-sm text-muted-foreground">Connection health</p>
                </div>
              </div>

              {diagnosticResult ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-secondary/30">
                      <p className="text-xs text-muted-foreground">Latency</p>
                      <p className="text-lg font-bold text-foreground">{diagnosticResult.latency}ms</p>
                    </div>
                    <div className="p-3 rounded-lg bg-secondary/30">
                      <p className="text-xs text-muted-foreground">Packet Loss</p>
                      <p className="text-lg font-bold text-foreground">{diagnosticResult.packetLoss.toFixed(1)}%</p>
                    </div>
                  </div>
                  
                  <div className="p-3 rounded-lg bg-secondary/30">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs text-muted-foreground">Signal Strength</p>
                      <Signal className={cn("w-5 h-5", getSignalStrengthColor(diagnosticResult.signalStrength))} />
                    </div>
                    <div className="flex items-center gap-2">
                      <Progress value={diagnosticResult.signalStrength} className="h-2 flex-1" />
                      <span className="text-sm font-medium">{diagnosticResult.signalStrength}%</span>
                    </div>
                  </div>
                  
                  <p className="text-xs text-muted-foreground">
                    Last tested: {format(new Date(diagnosticResult.timestamp), "PPp")}
                  </p>
                  
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="w-full gap-2"
                    onClick={handleRunTest}
                    disabled={isRunningTest}
                  >
                    {isRunningTest ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
                    Retest Connection
                  </Button>
                </div>
              ) : (
                <div className="text-center py-6">
                  <Wifi className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground mb-4">Run a connection test to see diagnostics</p>
                  <Button onClick={handleRunTest} disabled={isRunningTest} className="gap-2">
                    {isRunningTest ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
                    Run Test
                  </Button>
                </div>
              )}
            </div>

            {/* Help Button */}
            <Button 
              variant="outline" 
              className="w-full gap-2 border-primary/30 text-primary hover:bg-primary/10"
              onClick={() => toast.info("Installer support: +92-XXX-XXXXXXX")}
            >
              <HelpCircle className="w-5 h-5" />
              Need Help?
            </Button>
          </motion.div>
        </div>

        {/* Raw Telemetry Data */}
        <Collapsible open={isRawDataOpen} onOpenChange={setIsRawDataOpen}>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card"
          >
            <CollapsibleTrigger className="w-full p-6 flex items-center justify-between hover:bg-accent/30 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                  <Terminal className="w-5 h-5 text-primary" />
                </div>
                <div className="text-left">
                  <h3 className="text-lg font-semibold text-foreground">Raw Telemetry Data</h3>
                  <p className="text-sm text-muted-foreground">View device data stream</p>
                </div>
              </div>
              {isRawDataOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </CollapsibleTrigger>
            
            <CollapsibleContent>
              <div className="px-6 pb-6 space-y-4">
                {/* Telemetry Preview Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-secondary/30">
                    <div className="flex items-center gap-2 mb-1">
                      <Zap className="w-4 h-4 text-primary" />
                      <span className="text-xs text-muted-foreground">PV Power</span>
                    </div>
                    <p className="text-lg font-bold text-foreground">{rawTelemetry.data.pv_power}W</p>
                  </div>
                  <div className="p-3 rounded-lg bg-secondary/30">
                    <div className="flex items-center gap-2 mb-1">
                      <Battery className="w-4 h-4 text-success" />
                      <span className="text-xs text-muted-foreground">Battery SOC</span>
                    </div>
                    <p className="text-lg font-bold text-foreground">{rawTelemetry.data.battery_soc}%</p>
                  </div>
                  <div className="p-3 rounded-lg bg-secondary/30">
                    <div className="flex items-center gap-2 mb-1">
                      <Zap className="w-4 h-4 text-info" />
                      <span className="text-xs text-muted-foreground">Grid Power</span>
                    </div>
                    <p className="text-lg font-bold text-foreground">{rawTelemetry.data.grid_power}W</p>
                  </div>
                  <div className="p-3 rounded-lg bg-secondary/30">
                    <div className="flex items-center gap-2 mb-1">
                      <Thermometer className="w-4 h-4 text-warning" />
                      <span className="text-xs text-muted-foreground">Temperature</span>
                    </div>
                    <p className="text-lg font-bold text-foreground">{rawTelemetry.data.inverter_temp}°C</p>
                  </div>
                </div>
                
                {/* JSON View */}
                <div className="p-4 rounded-lg bg-slate-900 overflow-x-auto">
                  <pre className="text-xs text-green-400 font-mono">
                    {JSON.stringify(rawTelemetry, null, 2)}
                  </pre>
                </div>
                
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Info className="w-4 h-4" />
                  <span>Data refreshed every {deviceConfig.pollingInterval} seconds</span>
                </div>
              </div>
            </CollapsibleContent>
          </motion.div>
        </Collapsible>

        {/* Configuration Panel */}
        <Collapsible open={isConfigOpen} onOpenChange={setIsConfigOpen}>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="glass-card"
          >
            <CollapsibleTrigger className="w-full p-6 flex items-center justify-between hover:bg-accent/30 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                  <Settings className="w-5 h-5 text-primary" />
                </div>
                <div className="text-left">
                  <h3 className="text-lg font-semibold text-foreground">Device Configuration</h3>
                  <p className="text-sm text-muted-foreground">Review and adjust settings</p>
                </div>
              </div>
              {isConfigOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </CollapsibleTrigger>
            
            <CollapsibleContent>
              <div className="px-6 pb-6 space-y-6">
                {/* Device Name */}
                <div className="space-y-2">
                  <Label htmlFor="device-name">Device Name</Label>
                  <Input
                    id="device-name"
                    value={deviceConfig.name}
                    onChange={(e) => setDeviceConfig({ ...deviceConfig, name: e.target.value })}
                    className="bg-secondary/50"
                  />
                </div>
                
                {/* Polling Interval */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>Polling Interval</Label>
                    <span className="text-sm font-medium">{deviceConfig.pollingInterval}s</span>
                  </div>
                  <Slider
                    value={[deviceConfig.pollingInterval]}
                    min={5}
                    max={60}
                    step={5}
                    onValueChange={([value]) => setDeviceConfig({ ...deviceConfig, pollingInterval: value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    Note: Faster polling may increase subscription costs
                  </p>
                </div>
                
                {/* Alert Thresholds */}
                <div className="space-y-4">
                  <Label>Alert Thresholds</Label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Low Battery</span>
                        <span className="font-medium">{deviceConfig.alertThresholds.lowBattery}%</span>
                      </div>
                      <Slider
                        value={[deviceConfig.alertThresholds.lowBattery]}
                        min={10}
                        max={50}
                        step={5}
                        onValueChange={([value]) => setDeviceConfig({ 
                          ...deviceConfig, 
                          alertThresholds: { ...deviceConfig.alertThresholds, lowBattery: value }
                        })}
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">High Temperature</span>
                        <span className="font-medium">{deviceConfig.alertThresholds.highTemp}°C</span>
                      </div>
                      <Slider
                        value={[deviceConfig.alertThresholds.highTemp]}
                        min={40}
                        max={70}
                        step={5}
                        onValueChange={([value]) => setDeviceConfig({ 
                          ...deviceConfig, 
                          alertThresholds: { ...deviceConfig.alertThresholds, highTemp: value }
                        })}
                      />
                    </div>
                  </div>
                </div>
                
                {/* Network Settings */}
                <div className="space-y-4">
                  <Label>Network Settings</Label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="ip" className="text-xs text-muted-foreground">IP Address</Label>
                      <Input
                        id="ip"
                        value={deviceConfig.networkSettings.ip}
                        onChange={(e) => setDeviceConfig({
                          ...deviceConfig,
                          networkSettings: { ...deviceConfig.networkSettings, ip: e.target.value }
                        })}
                        className="bg-secondary/50 font-mono"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="port" className="text-xs text-muted-foreground">Port</Label>
                      <Input
                        id="port"
                        type="number"
                        value={deviceConfig.networkSettings.port}
                        onChange={(e) => setDeviceConfig({
                          ...deviceConfig,
                          networkSettings: { ...deviceConfig.networkSettings, port: parseInt(e.target.value) }
                        })}
                        className="bg-secondary/50 font-mono"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="slave-id" className="text-xs text-muted-foreground">Slave ID</Label>
                      <Input
                        id="slave-id"
                        type="number"
                        value={deviceConfig.networkSettings.slaveId}
                        onChange={(e) => setDeviceConfig({
                          ...deviceConfig,
                          networkSettings: { ...deviceConfig.networkSettings, slaveId: parseInt(e.target.value) }
                        })}
                        className="bg-secondary/50 font-mono"
                      />
                    </div>
                  </div>
                </div>
                
                <Button className="w-full gap-2" onClick={() => toast.success("Configuration saved")}>
                  <CheckCircle2 className="w-4 h-4" />
                  Save Configuration
                </Button>
              </div>
            </CollapsibleContent>
          </motion.div>
        </Collapsible>

        {/* Handoff Section */}
        <motion.div
          id="handoff-section"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-success/20 flex items-center justify-center">
              <Send className="w-5 h-5 text-success" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">System Handoff</h3>
              <p className="text-sm text-muted-foreground">Notify system owner and complete commissioning</p>
            </div>
          </div>

          {isHandoffSent ? (
            <div className="text-center py-8">
              <CheckCircle2 className="w-16 h-16 mx-auto text-success mb-4" />
              <h4 className="text-xl font-semibold text-foreground mb-2">Handoff Complete!</h4>
              <p className="text-muted-foreground mb-4">
                Notification sent to {ownerEmail}
              </p>
              <Button variant="outline" onClick={() => navigate("/devices")} className="gap-2">
                <ExternalLink className="w-4 h-4" />
                View Devices
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="owner-email">Owner Email</Label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="owner-email"
                      type="email"
                      value={ownerEmail}
                      onChange={(e) => setOwnerEmail(e.target.value)}
                      className="pl-10 bg-secondary/50"
                      placeholder="owner@example.com"
                    />
                  </div>
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="handoff-message">Additional Notes (Optional)</Label>
                <Textarea
                  id="handoff-message"
                  value={handoffMessage}
                  onChange={(e) => setHandoffMessage(e.target.value)}
                  placeholder="Any special instructions or notes for the owner..."
                  rows={3}
                  className="bg-secondary/50"
                />
              </div>
              
              <div className="p-4 rounded-lg bg-info/10 border border-info/20">
                <div className="flex items-start gap-3">
                  <Info className="w-5 h-5 text-info shrink-0 mt-0.5" />
                  <div className="text-sm text-info">
                    <p className="font-medium mb-1">Handoff includes:</p>
                    <ul className="list-disc list-inside space-y-1 text-info/80">
                      <li>Commissioning completion confirmation</li>
                      <li>Device configuration summary</li>
                      <li>Installer contact information</li>
                      <li>Quick start guide link</li>
                    </ul>
                  </div>
                </div>
              </div>
              
              <div className="flex gap-3">
                <Button 
                  onClick={handleSendHandoff}
                  className="flex-1 gap-2"
                  disabled={completedCount < checklist.length - 1}
                >
                  <Send className="w-4 h-4" />
                  Send Handoff Notification
                </Button>
              </div>
              
              {completedCount < checklist.length - 1 && (
                <p className="text-xs text-muted-foreground text-center">
                  Complete all previous steps before sending handoff
                </p>
              )}
            </div>
          )}
        </motion.div>
      </div>
    </AppLayout>
  );
};

export default CommissioningPage;
