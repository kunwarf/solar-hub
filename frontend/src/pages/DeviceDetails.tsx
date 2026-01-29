import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
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
import { toast } from "sonner";
import {
  ArrowLeft,
  Cpu,
  Activity,
  RefreshCw,
  Download,
  Trash2,
  Wrench,
  Wifi,
  Signal,
  Sun,
  Zap,
  Battery,
  Thermometer,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { StatCard } from "@/components/dashboard/StatCard";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

interface Device {
  id: string;
  name: string;
  serial_number: string;
  device_type: string;
  manufacturer?: string;
  model?: string;
  firmware_version?: string;
  status: string;
  connection_status: string;
  last_seen?: string;
}

interface TelemetryData {
  timestamp: string;
  power: number;
  voltage: number;
  current: number;
  temperature: number;
}

export default function DeviceDetails() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const navigate = useNavigate();
  const [device, setDevice] = useState<Device | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [telemetryData, setTelemetryData] = useState<TelemetryData[]>([]);
  const [currentMetrics, setCurrentMetrics] = useState({
    power: 0,
    voltage: 0,
    current: 0,
    temperature: 0,
  });

  useEffect(() => {
    loadDeviceData();
  }, [deviceId]);

  const loadDeviceData = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API call
      // const response = await deviceService.getDeviceById(deviceId);

      // Mock data for now
      setDevice({
        id: deviceId || "",
        name: `Device ${deviceId?.substring(0, 8)}`,
        serial_number: `SN-${deviceId?.substring(0, 12)}`,
        device_type: "inverter",
        manufacturer: "SolarTech",
        model: "ST-5000",
        firmware_version: "2.1.3",
        status: "active",
        connection_status: "online",
        last_seen: new Date().toISOString(),
      });

      // Mock telemetry data
      const mockTelemetry: TelemetryData[] = [];
      for (let i = 0; i < 24; i++) {
        mockTelemetry.push({
          timestamp: new Date(Date.now() - (23 - i) * 3600000).toISOString(),
          power: Math.random() * 5000 + 1000,
          voltage: 230 + Math.random() * 10,
          current: Math.random() * 20 + 5,
          temperature: 35 + Math.random() * 10,
        });
      }
      setTelemetryData(mockTelemetry);

      // Set current metrics (latest values)
      if (mockTelemetry.length > 0) {
        const latest = mockTelemetry[mockTelemetry.length - 1];
        setCurrentMetrics({
          power: latest.power,
          voltage: latest.voltage,
          current: latest.current,
          temperature: latest.temperature,
        });
      }
    } catch (error) {
      console.error("Failed to load device data:", error);
      toast.error("Failed to load device details");
    } finally {
      setLoading(false);
    }
  };

  const handleRestart = async () => {
    try {
      toast.info("Restarting device...");
      // TODO: Add actual restart API call
      // await deviceService.restartDevice(deviceId);
      setTimeout(() => {
        toast.success("Device restarted successfully");
      }, 2000);
    } catch (error) {
      toast.error("Failed to restart device");
    }
  };

  const handleRunDiagnostics = async () => {
    try {
      toast.info("Running diagnostics...");
      // TODO: Add actual diagnostics API call
      setTimeout(() => {
        toast.success("Diagnostics completed - No issues found");
      }, 3000);
    } catch (error) {
      toast.error("Failed to run diagnostics");
    }
  };

  const handleExportData = () => {
    toast.success("Exporting device data...");
    // TODO: Implement data export
  };

  const handleRemoveDevice = async () => {
    try {
      toast.info("Removing device...");
      // TODO: Add actual remove API call
      setTimeout(() => {
        toast.success("Device removed successfully");
        navigate("/devices");
      }, 1500);
    } catch (error) {
      toast.error("Failed to remove device");
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <AppHeader />
        <div className="container mx-auto p-3 sm:p-6">
          <Skeleton className="h-8 w-64 mb-6" />
          <Skeleton className="h-96" />
        </div>
      </AppLayout>
    );
  }

  if (!device) {
    return (
      <AppLayout>
        <AppHeader />
        <div className="container mx-auto p-3 sm:p-6">
          <div className="flex flex-col items-center justify-center py-12">
            <XCircle className="h-16 w-16 text-muted-foreground mb-4" />
            <h2 className="text-2xl font-semibold mb-2">Device Not Found</h2>
            <p className="text-muted-foreground mb-4">The requested device could not be found.</p>
            <Button onClick={() => navigate("/devices")}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Devices
            </Button>
          </div>
        </div>
      </AppLayout>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "online": return "text-green-500";
      case "offline": return "text-red-500";
      case "warning": return "text-yellow-500";
      default: return "text-gray-500";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case "online": return <CheckCircle2 className="h-4 w-4" />;
      case "offline": return <XCircle className="h-4 w-4" />;
      case "warning": return <AlertTriangle className="h-4 w-4" />;
      default: return <Activity className="h-4 w-4" />;
    }
  };

  return (
    <AppLayout>
      <AppHeader />
      <div className="container mx-auto p-3 sm:p-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div className="flex items-center gap-4">
            <Button variant="outline" size="sm" onClick={() => navigate("/devices")}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Cpu className="h-6 w-6" />
                {device.name}
              </h1>
              <p className="text-sm text-muted-foreground">
                {device.serial_number}
              </p>
            </div>
          </div>

          <div className="flex gap-2 flex-wrap">
            <Button variant="outline" size="sm" onClick={handleRestart}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Restart
            </Button>
            <Button variant="outline" size="sm" onClick={handleRunDiagnostics}>
              <Wrench className="h-4 w-4 mr-2" />
              Diagnostics
            </Button>
            <Button variant="outline" size="sm" onClick={handleExportData}>
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm">
                  <Trash2 className="h-4 w-4 mr-2" />
                  Remove
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Remove Device?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will permanently remove {device.name} from your system. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleRemoveDevice} className="bg-destructive text-destructive-foreground">
                    Remove Device
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>

        {/* Device Info Card */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Status</p>
                <div className={`flex items-center gap-2 font-medium ${getStatusColor(device.connection_status)}`}>
                  {getStatusIcon(device.connection_status)}
                  <span className="capitalize">{device.connection_status}</span>
                </div>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">Type</p>
                <p className="font-medium capitalize">{device.device_type}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">Manufacturer</p>
                <p className="font-medium">{device.manufacturer || "Unknown"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">Model</p>
                <p className="font-medium">{device.model || "Unknown"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">Firmware</p>
                <p className="font-medium">{device.firmware_version || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">Last Seen</p>
                <p className="font-medium">
                  {device.last_seen ? new Date(device.last_seen).toLocaleString() : "Never"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="telemetry">Telemetry</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="maintenance">Maintenance</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            {/* Quick Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <StatCard
                title="Power"
                value={`${(currentMetrics.power / 1000).toFixed(2)} kW`}
                icon={Zap}
                variant="solar"
                trend={5.2}
                compact
              />
              <StatCard
                title="Voltage"
                value={`${currentMetrics.voltage.toFixed(1)} V`}
                icon={Activity}
                variant="grid"
                compact
              />
              <StatCard
                title="Current"
                value={`${currentMetrics.current.toFixed(1)} A`}
                icon={Zap}
                variant="consumption"
                compact
              />
              <StatCard
                title="Temperature"
                value={`${currentMetrics.temperature.toFixed(1)}°C`}
                icon={Thermometer}
                variant="battery"
                compact
              />
            </div>

            {/* Real-time Telemetry Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Real-time Telemetry (Last 24 Hours)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={telemetryData}>
                      <defs>
                        <linearGradient id="colorPower" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="timestamp"
                        tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        stroke="hsl(var(--muted-foreground))"
                      />
                      <YAxis stroke="hsl(var(--muted-foreground))" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--popover))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                        }}
                        labelFormatter={(value) => new Date(value).toLocaleString()}
                      />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="power"
                        stroke="#F59E0B"
                        fillOpacity={1}
                        fill="url(#colorPower)"
                        name="Power (W)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="telemetry">
            <Card>
              <CardHeader>
                <CardTitle>Detailed Telemetry Data</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {telemetryData.slice(-5).reverse().map((data, index) => (
                      <Card key={index}>
                        <CardContent className="pt-4">
                          <p className="text-sm text-muted-foreground mb-2">
                            {new Date(data.timestamp).toLocaleString()}
                          </p>
                          <div className="grid grid-cols-2 gap-2 text-sm">
                            <div>Power: {(data.power / 1000).toFixed(2)} kW</div>
                            <div>Voltage: {data.voltage.toFixed(1)} V</div>
                            <div>Current: {data.current.toFixed(1)} A</div>
                            <div>Temp: {data.temperature.toFixed(1)}°C</div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="performance">
            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  Performance tracking and analytics will be displayed here.
                </p>
                {/* TODO: Add performance charts and metrics */}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="maintenance">
            <Card>
              <CardHeader>
                <CardTitle>Maintenance Log</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  Maintenance history and scheduled maintenance will be displayed here.
                </p>
                {/* TODO: Add maintenance log functionality */}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
