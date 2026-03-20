import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
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
  Zap,
  Battery,
  Thermometer,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Unlink,
} from "lucide-react";
import { StatCard } from "@/components/dashboard/StatCard";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import devicesService from "@/api/services/devices.service";

interface TelemetryPoint {
  timestamp: string;
  power: number;
  voltage: number;
  current: number;
  temperature: number;
}

export default function DeviceDetails() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("overview");
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryPoint[]>([]);

  // Fetch device info
  const {
    data: device,
    isLoading: deviceLoading,
    error: deviceError,
  } = useQuery({
    queryKey: ["device", deviceId],
    queryFn: () => devicesService.getDevice(deviceId!),
    enabled: !!deviceId,
    retry: 1,
  });

  // Fetch realtime telemetry with auto-refresh
  const {
    data: realtimeTelemetry,
    isLoading: telemetryLoading,
  } = useQuery({
    queryKey: ["device-telemetry-realtime", deviceId],
    queryFn: () => devicesService.getRealtimeTelemetry(deviceId!),
    enabled: !!deviceId,
    refetchInterval: 30_000, // Refresh every 30 seconds
    retry: false,
  });

  // Fetch extended telemetry for performance tab
  const { data: extendedTelemetry } = useQuery({
    queryKey: ["device-telemetry-extended", deviceId],
    queryFn: () => devicesService.getExtendedTelemetry(deviceId!),
    enabled: !!deviceId && activeTab === "performance",
    retry: false,
  });

  // Fetch MPPT channels for performance tab
  const { data: mpptChannels } = useQuery({
    queryKey: ["device-mppt", deviceId],
    queryFn: () => devicesService.getMPPTChannels(deviceId!),
    enabled: !!deviceId && activeTab === "performance",
    retry: false,
  });

  // Accumulate telemetry history for the chart
  useEffect(() => {
    const tel = realtimeTelemetry?.telemetry;
    if (tel) {
      const point: TelemetryPoint = {
        timestamp: tel.timestamp || new Date().toISOString(),
        power: tel.power?.pv_total_w ?? tel.power?.pv1_w ?? 0,
        voltage: tel.grid?.voltage_v ?? 0,
        current: 0,
        temperature: tel.temperatures?.inverter_c ?? 0,
      };
      setTelemetryHistory((prev) => {
        // Keep last 24 data points
        const updated = [...prev, point].slice(-24);
        return updated;
      });
    }
  }, [realtimeTelemetry]);

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: () => devicesService.deleteDevice(deviceId!),
    onSuccess: () => {
      toast.success("Device removed successfully");
      navigate("/devices");
    },
    onError: () => {
      toast.error("Failed to remove device");
    },
  });

  // Unclaim mutation
  const unclaimMutation = useMutation({
    mutationFn: () => devicesService.unclaimDevice(deviceId!),
    onSuccess: () => {
      toast.success("Device unclaimed — it is now available to claim again");
      navigate("/devices");
    },
    onError: () => {
      toast.error("Failed to unclaim device");
    },
  });

  // Restart command
  const handleRestart = useCallback(async () => {
    try {
      toast.info("Sending restart command...");
      const result = await devicesService.sendCommand(deviceId!, { type: "restart" });
      if (result.success) {
        toast.success("Restart command sent successfully");
      } else {
        toast.error(result.error || "Failed to restart device");
      }
    } catch {
      toast.error("Failed to restart device");
    }
  }, [deviceId]);

  // Export telemetry as CSV
  const handleExportData = useCallback(() => {
    if (telemetryHistory.length === 0) {
      toast.info("No telemetry data to export");
      return;
    }
    const csv = [
      ["Timestamp", "Power (W)", "Voltage (V)", "Current (A)", "Temperature (°C)"],
      ...telemetryHistory.map((d) => [
        d.timestamp,
        d.power.toFixed(2),
        d.voltage.toFixed(2),
        d.current.toFixed(2),
        d.temperature.toFixed(2),
      ]),
    ]
      .map((row) => row.join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `device-${deviceId}-telemetry-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Telemetry data exported");
  }, [deviceId, telemetryHistory]);

  const isLoading = deviceLoading;

  if (isLoading) {
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

  if (deviceError || !device) {
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
    switch (status?.toLowerCase()) {
      case "online": return "text-green-500";
      case "offline": return "text-red-500";
      case "warning": return "text-yellow-500";
      default: return "text-gray-500";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case "online": return <CheckCircle2 className="h-4 w-4" />;
      case "offline": return <XCircle className="h-4 w-4" />;
      case "warning": return <AlertTriangle className="h-4 w-4" />;
      default: return <Activity className="h-4 w-4" />;
    }
  };

  // Current metrics from realtime telemetry
  // API response shape: { device_id, serial_number, status, last_seen, telemetry: { power, battery, temperatures, grid, ... } }
  const tel = realtimeTelemetry?.telemetry;
  const currentMetrics = tel
    ? {
        power: tel.power?.pv_total_w ?? tel.power?.pv1_w ?? 0,
        voltage: tel.grid?.voltage_v ?? 0,
        current: 0,
        temperature: tel.temperatures?.inverter_c ?? 0,
        solarPower: tel.power?.pv_total_w ?? tel.power?.pv1_w ?? 0,
        batteryPercent: tel.battery?.soc_pct ?? null,
      }
    : null;

  const connectionStatus = device.connection_status ?? device.status ?? "unknown";

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
            <Button variant="outline" size="sm" onClick={handleExportData}>
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <Unlink className="h-4 w-4 mr-2" />
                  Unclaim
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Unclaim Device?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will remove {device.name} from this site and release it back to the available device pool. The device will remain registered and can be claimed again. Use this to move the device to a different site.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => unclaimMutation.mutate()}
                    disabled={unclaimMutation.isPending}
                  >
                    Unclaim Device
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
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
                  <AlertDialogAction
                    onClick={() => deleteMutation.mutate()}
                    className="bg-destructive text-destructive-foreground"
                  >
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
                <div className={`flex items-center gap-2 font-medium ${getStatusColor(connectionStatus)}`}>
                  {getStatusIcon(connectionStatus)}
                  <span className="capitalize">{connectionStatus}</span>
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
            {currentMetrics ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <StatCard
                  title="AC Output Power"
                  value={`${(currentMetrics.power / 1000).toFixed(2)} kW`}
                  icon={Zap}
                  variant="solar"
                  compact
                />
                <StatCard
                  title="Grid Voltage"
                  value={`${currentMetrics.voltage.toFixed(1)} V`}
                  icon={Activity}
                  variant="grid"
                  compact
                />
                {currentMetrics.batteryPercent !== null ? (
                  <StatCard
                    title="Battery SOC"
                    value={`${currentMetrics.batteryPercent.toFixed(0)}%`}
                    icon={Battery}
                    variant="battery"
                    compact
                  />
                ) : (
                  <StatCard
                    title="Solar Power"
                    value={`${(currentMetrics.solarPower / 1000).toFixed(2)} kW`}
                    icon={Zap}
                    variant="solar"
                    compact
                  />
                )}
                <StatCard
                  title="Temperature"
                  value={`${currentMetrics.temperature.toFixed(1)}°C`}
                  icon={Thermometer}
                  variant="battery"
                  compact
                />
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {[1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-24" />
                ))}
              </div>
            )}

            {/* Telemetry Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Live Power Output</span>
                  {telemetryHistory.length > 0 && (
                    <Badge variant="outline" className="text-xs">
                      {telemetryHistory.length} data points
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {telemetryHistory.length === 0 ? (
                  <div className="h-80 flex items-center justify-center text-muted-foreground">
                    Waiting for telemetry data...
                  </div>
                ) : (
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={telemetryHistory}>
                        <defs>
                          <linearGradient id="colorPower" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis
                          dataKey="timestamp"
                          tickFormatter={(value) =>
                            new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                          }
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
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="telemetry">
            <Card>
              <CardHeader>
                <CardTitle>Current Telemetry Readings</CardTitle>
              </CardHeader>
              <CardContent>
                {realtimeTelemetry?.telemetry ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(realtimeTelemetry.telemetry)
                      .filter(([key]) => !["timestamp", "serial_number", "status"].includes(key))
                      .flatMap(([section, sectionVal]) =>
                        typeof sectionVal === "object" && sectionVal !== null && !Array.isArray(sectionVal)
                          ? Object.entries(sectionVal as Record<string, unknown>).map(([k, v]) => ({
                              key: `${section}.${k}`,
                              label: `${section.replace(/_/g, " ")} / ${k.replace(/_/g, " ")}`,
                              value: v,
                            }))
                          : [{ key: section, label: section.replace(/_/g, " "), value: sectionVal }]
                      )
                      .map(({ key, label, value }) => (
                        <div key={key} className="p-3 rounded-md border">
                          <p className="text-xs text-muted-foreground mb-1 capitalize">
                            {label}
                          </p>
                          <p className="font-medium text-sm">
                            {typeof value === "number"
                              ? value.toFixed(2)
                              : typeof value === "boolean"
                              ? value ? "Yes" : "No"
                              : Array.isArray(value)
                              ? value.length === 0 ? "None" : JSON.stringify(value)
                              : String(value)}
                          </p>
                        </div>
                      ))}
                  </div>
                ) : telemetryLoading ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                      <Skeleton key={i} className="h-16" />
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    No telemetry data available. The device may be offline.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="performance">
            <div className="space-y-4">
              {/* Extended Telemetry */}
              {extendedTelemetry && (
                <Card>
                  <CardHeader>
                    <CardTitle>Extended Metrics</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      {Object.entries(extendedTelemetry)
                        .filter(([key]) => !["timestamp", "device_id", "serial_number"].includes(key))
                        .map(([key, value]) => (
                          <div key={key} className="p-3 rounded-md border">
                            <p className="text-xs text-muted-foreground mb-1 capitalize">
                              {key.replace(/_/g, " ")}
                            </p>
                            <p className="font-medium text-sm">
                              {typeof value === "number" ? value.toFixed(2) : String(value)}
                            </p>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* MPPT Channels */}
              {mpptChannels && Array.isArray(mpptChannels) && mpptChannels.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>MPPT Channels</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {mpptChannels.map((channel: any, index: number) => (
                        <div key={index} className="p-4 rounded-md border">
                          <p className="font-medium mb-2">Channel {channel.channel ?? index + 1}</p>
                          <div className="space-y-1 text-sm">
                            {channel.voltage !== undefined && (
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Voltage</span>
                                <span>{channel.voltage.toFixed(1)} V</span>
                              </div>
                            )}
                            {channel.current !== undefined && (
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Current</span>
                                <span>{channel.current.toFixed(2)} A</span>
                              </div>
                            )}
                            {channel.power !== undefined && (
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Power</span>
                                <span>{(channel.power / 1000).toFixed(2)} kW</span>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {!extendedTelemetry && !mpptChannels && (
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-muted-foreground">
                      Performance data will appear here once loaded.
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>

          <TabsContent value="maintenance">
            <Card>
              <CardHeader>
                <CardTitle>Device Information</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <div>
                      <p className="text-sm text-muted-foreground">Serial Number</p>
                      <p className="font-mono font-medium">{device.serial_number}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Device Type</p>
                      <p className="font-medium capitalize">{device.device_type}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Firmware Version</p>
                      <p className="font-medium">{device.firmware_version || "Unknown"}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Manufacturer</p>
                      <p className="font-medium">{device.manufacturer || "Unknown"}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Model</p>
                      <p className="font-medium">{device.model || "Unknown"}</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div>
                      <p className="text-sm text-muted-foreground">Current Status</p>
                      <div className={`flex items-center gap-2 font-medium ${getStatusColor(connectionStatus)}`}>
                        {getStatusIcon(connectionStatus)}
                        <span className="capitalize">{connectionStatus}</span>
                      </div>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Last Seen</p>
                      <p className="font-medium">
                        {device.last_seen ? new Date(device.last_seen).toLocaleString() : "Never"}
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
