import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { AlertsPanel } from "@/components/telemetry/AlertsPanel";
import BatteryCellGrid from "@/components/telemetry/BatteryCellGrid";
import InverterTelemetry from "@/components/telemetry/InverterTelemetry";
import MeterTelemetry from "@/components/telemetry/MeterTelemetry";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  RefreshCw,
  Download,
  Clock,
  Sun,
  Battery,
  Gauge,
} from "lucide-react";
import { devices } from "@/data/mockData";
import { cn } from "@/lib/utils";

const TelemetryPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const deviceParam = searchParams.get("device");
  
  const [selectedDevice, setSelectedDevice] = useState(() => {
    // Check if device param exists and is valid
    if (deviceParam && devices.find(d => d.id === deviceParam)) {
      return deviceParam;
    }
    return devices[0].id;
  });
  const [refreshing, setRefreshing] = useState(false);

  // Update selected device when URL param changes
  useEffect(() => {
    if (deviceParam && devices.find(d => d.id === deviceParam)) {
      setSelectedDevice(deviceParam);
    }
  }, [deviceParam]);

  // Update URL when device selection changes
  const handleDeviceChange = (deviceId: string) => {
    setSelectedDevice(deviceId);
    setSearchParams({ device: deviceId });
  };

  const handleRefresh = () => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 1000);
  };

  const currentDevice = devices.find((d) => d.id === selectedDevice);

  return (
    <AppLayout>
      <AppHeader 
        title="Telemetry" 
        subtitle="Real-time device data and metrics"
      />
      
      <div className="p-4 sm:p-6 space-y-4 sm:space-y-6">
        {/* Controls */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-3 sm:p-4"
        >
          <div className="flex flex-col gap-3 sm:gap-4">
            {/* Device selector - full width on mobile */}
            <Select value={selectedDevice} onValueChange={handleDeviceChange}>
              <SelectTrigger className="w-full sm:w-[250px] bg-secondary/50">
                <SelectValue placeholder="Select device" />
              </SelectTrigger>
              <SelectContent>
                {devices.map((device) => (
                  <SelectItem key={device.id} value={device.id}>
                    {device.name} ({device.type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Actions row */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-xs sm:text-sm text-muted-foreground">
                <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                <span className="hidden xs:inline">Updated:</span>
                <span>Just now</span>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefresh}
                  disabled={refreshing}
                  className="h-8 px-2 sm:px-3"
                >
                  <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
                  <span className="hidden sm:inline ml-2">Refresh</span>
                </Button>
                <Button variant="outline" size="sm" className="h-8 px-2 sm:px-3">
                  <Download className="w-4 h-4" />
                  <span className="hidden sm:inline ml-2">Export</span>
                </Button>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Device Type Indicator */}
        {currentDevice && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-3 sm:p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                <div className={cn(
                  "p-1.5 sm:p-2 rounded-lg shrink-0",
                  currentDevice.type === "inverter" && "bg-solar/20 text-solar",
                  currentDevice.type === "battery" && "bg-battery/20 text-battery",
                  currentDevice.type === "meter" && "bg-grid/20 text-grid"
                )}>
                  {currentDevice.type === "inverter" && <Sun className="w-4 h-4 sm:w-5 sm:h-5" />}
                  {currentDevice.type === "battery" && <Battery className="w-4 h-4 sm:w-5 sm:h-5" />}
                  {currentDevice.type === "meter" && <Gauge className="w-4 h-4 sm:w-5 sm:h-5" />}
                </div>
                <div className="min-w-0">
                  <h3 className="font-semibold text-foreground text-sm sm:text-base truncate">{currentDevice.name}</h3>
                  <p className="text-xs sm:text-sm text-muted-foreground truncate">{currentDevice.model} • {currentDevice.serialNumber}</p>
                </div>
              </div>
              <div className={cn(
                "px-2 sm:px-3 py-1 rounded-full text-xs font-medium capitalize shrink-0",
                currentDevice.status === "online" && "bg-success/20 text-success",
                currentDevice.status === "warning" && "bg-warning/20 text-warning"
              )}>
                {currentDevice.status}
              </div>
            </div>
          </motion.div>
        )}

        {/* Device-Specific Telemetry View */}
        {currentDevice && (
          <>
            {currentDevice.type === "inverter" && (
              <InverterTelemetry device={currentDevice} />
            )}
            {currentDevice.type === "battery" && (
              <BatteryCellGrid device={currentDevice} />
            )}
            {currentDevice.type === "meter" && (
              <MeterTelemetry device={currentDevice} />
            )}
          </>
        )}

        {/* Alerts Panel */}
        <AlertsPanel />
      </div>
    </AppLayout>
  );
};

export default TelemetryPage;
