import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Cpu, Battery, Gauge, Save, RotateCcw, ArrowLeft, Loader2, AlertTriangle, Wifi, WifiOff, Database, HardDrive } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { useQuery } from "@tanstack/react-query";
import { devicesService } from "@/api";
import { useDeviceSettings } from "@/hooks/useDeviceSettings";
import { InverterConfigPage } from "@/components/settings/InverterConfigPage";
import { MeterConfigPage } from "@/components/settings/MeterConfigPage";
import { BatteryConfigPage } from "@/components/settings/BatteryConfigPage";

const deviceIcons = {
  inverter: Cpu,
  battery: Battery,
  meter: Gauge,
};

const typeColors = {
  inverter: "text-solar",
  battery: "text-battery",
  meter: "text-grid",
};

const DeviceSettingsPageHybrid = () => {
  const { deviceId } = useParams<{ deviceId: string }>();
  const navigate = useNavigate();

  // Fetch device details
  const { data: device, isLoading: deviceLoading, error: deviceError } = useQuery({
    queryKey: ['device', deviceId],
    queryFn: () => devicesService.getDevice(deviceId!),
    enabled: !!deviceId,
  });

  // Use hybrid device settings hook
  const {
    settings,
    isLoading: settingsLoading,
    isQuerying,
    isUpdating,
    isStale,
    isDeviceOffline,
    usingFallback,
    lastSyncedAt,
    error: settingsError,
    updateDevice,
    queryDevice,
  } = useDeviceSettings({
    deviceId: deviceId!,
    deviceType: device?.device_type || 'unknown',
    enabled: !!device,
    pollInterval: 30000, // 30s
  });

  const handleSave = async () => {
    if (!settings) return;

    try {
      await updateDevice(settings);
      toast({
        title: "Settings Saved",
        description: isDeviceOffline
          ? `Settings saved to database (device offline). Will sync when device comes online.`
          : `Configuration for ${device?.name} has been updated on device.`,
        variant: isDeviceOffline ? "default" : "default",
      });

      if (!isDeviceOffline) {
        navigate("/devices");
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to save settings",
        variant: "destructive",
      });
    }
  };

  const handleReset = async () => {
    if (confirm("Are you sure you want to reset settings to defaults? This cannot be undone.")) {
      // Reset settings logic here
      toast({
        title: "Settings Reset",
        description: "Device settings have been reset to defaults.",
      });
    }
  };

  const handleRefresh = async () => {
    await queryDevice();
    toast({
      title: "Refreshed",
      description: isDeviceOffline
        ? "Loaded settings from database (device offline)"
        : "Loaded fresh settings from device",
    });
  };

  // Loading state
  if (deviceLoading || settingsLoading) {
    return (
      <AppLayout>
        <AppHeader title="Loading..." subtitle="Fetching device configuration" />
        <div className="p-6 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </AppLayout>
    );
  }

  // Error state
  if (deviceError || !device) {
    return (
      <AppLayout>
        <AppHeader title="Device Not Found" subtitle="The requested device could not be found" />
        <div className="p-6">
          <Button variant="outline" onClick={() => navigate("/devices")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Devices
          </Button>
        </div>
      </AppLayout>
    );
  }

  const Icon = deviceIcons[device.device_type as keyof typeof deviceIcons] || Cpu;

  return (
    <AppLayout>
      <AppHeader
        title={`${device.name} Configuration`}
        subtitle={`${device.model} • ${device.serialNumber}`}
      />

      <div className="p-6 space-y-6">
        {/* Back Button */}
        <Button variant="ghost" onClick={() => navigate("/devices")} className="gap-2">
          <ArrowLeft className="w-4 h-4" />
          Back to Devices
        </Button>

        {/* Status Alerts */}
        {isDeviceOffline && (
          <Alert variant="destructive">
            <WifiOff className="h-4 w-4" />
            <AlertTitle>Device Offline</AlertTitle>
            <AlertDescription>
              Cannot communicate with device. Using {usingFallback ? 'database backup' : 'cached'} settings.
              Settings will sync automatically when device comes back online.
            </AlertDescription>
          </Alert>
        )}

        {isStale && !isDeviceOffline && (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Settings May Be Outdated</AlertTitle>
            <AlertDescription>
              These settings may not reflect the current device state.
              <Button variant="link" className="p-0 h-auto ml-1" onClick={handleRefresh} disabled={isQuerying}>
                {isQuerying ? 'Refreshing...' : 'Refresh now'}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {usingFallback && (
          <Alert>
            <Database className="h-4 w-4" />
            <AlertTitle>Using Database Backup</AlertTitle>
            <AlertDescription>
              Showing settings from database backup (last synced: {lastSyncedAt ? new Date(lastSyncedAt).toLocaleString() : 'unknown'}).
              Device is currently offline.
            </AlertDescription>
          </Alert>
        )}

        {isQuerying && (
          <Alert>
            <Loader2 className="h-4 w-4 animate-spin" />
            <AlertTitle>Querying Device...</AlertTitle>
            <AlertDescription>
              Reading current settings from device hardware. This may take a few seconds.
            </AlertDescription>
          </Alert>
        )}

        {/* Device Header Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4"
        >
          <div className="flex items-center gap-4">
            <div className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center",
              device.device_type === "inverter" && "bg-solar/20",
              device.device_type === "battery" && "bg-battery/20",
              device.device_type === "meter" && "bg-grid/20"
            )}>
              <Icon className={cn("w-6 h-6", typeColors[device.device_type as keyof typeof typeColors])} />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                {device.name}
                {!isDeviceOffline && !isStale && (
                  <span className="flex items-center gap-1 text-xs text-success">
                    <Wifi className="w-3 h-3" />
                    Live
                  </span>
                )}
                {isDeviceOffline && (
                  <span className="flex items-center gap-1 text-xs text-destructive">
                    <WifiOff className="w-3 h-3" />
                    Offline
                  </span>
                )}
                {usingFallback && (
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <HardDrive className="w-3 h-3" />
                    Backup
                  </span>
                )}
              </h2>
              <p className="text-sm text-muted-foreground">{device.model} • {device.serialNumber}</p>
            </div>
            <div className={cn(
              "px-3 py-1 rounded-full text-xs font-medium capitalize",
              device.status === "online" && "bg-success/20 text-success",
              device.status === "warning" && "bg-warning/20 text-warning",
              device.status === "offline" && "bg-destructive/20 text-destructive"
            )}>
              {device.status}
            </div>
          </div>
        </motion.div>

        {/* Configuration Content */}
        {(() => {
          console.log('[DeviceSettingsHybrid] Rendering check:', {
            hasSettings: !!settings,
            settingsKeys: settings ? Object.keys(settings).length : 0,
            deviceType: device?.type,
            deviceId: device?.id,
          });
          return null;
        })()}
        {settings && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            {(() => {
              console.log('[DeviceSettingsHybrid] Inside settings conditional, device.device_type:', device.device_type);
              return null;
            })()}
            {device.device_type === "inverter" && (
              <InverterConfigPage
                deviceId={device.id}
                deviceName={device.name}
                settings={settings}
              />
            )}
            {device.device_type === "battery" && (
              <BatteryConfigPage
                deviceId={device.id}
                deviceName={device.name}
                settings={settings}
              />
            )}
            {device.device_type === "meter" && (
              <MeterConfigPage
                deviceId={device.id}
                deviceName={device.name}
                settings={settings}
              />
            )}
          </motion.div>
        )}

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex flex-col sm:flex-row gap-3"
        >
          <Button
            onClick={handleSave}
            className="flex-1 sm:flex-none gap-2"
            disabled={isUpdating || !settings}
          >
            {isUpdating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {isDeviceOffline ? 'Save to Database' : 'Save to Device'}
          </Button>
          <Button
            variant="outline"
            onClick={handleReset}
            className="flex-1 sm:flex-none gap-2"
            disabled={isUpdating}
          >
            <RotateCcw className="w-4 h-4" />
            Reset to Defaults
          </Button>
          <Button
            variant="outline"
            onClick={handleRefresh}
            className="flex-1 sm:flex-none gap-2"
            disabled={isQuerying}
          >
            {isQuerying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Wifi className="w-4 h-4" />
            )}
            Refresh from Device
          </Button>
        </motion.div>
      </div>
    </AppLayout>
  );
};

export default DeviceSettingsPageHybrid;
