import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Cpu, Battery, Gauge, Save, RotateCcw, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { devices } from "@/data/mockData";
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

const DeviceSettingsPage = () => {
  const { deviceId } = useParams<{ deviceId: string }>();
  const navigate = useNavigate();
  
  const device = devices.find(d => d.id === deviceId);

  const handleSave = () => {
    toast({
      title: "Settings Saved",
      description: `Configuration for ${device?.name} has been updated.`,
    });
    navigate("/devices");
  };

  const handleReset = () => {
    toast({
      title: "Settings Reset",
      description: "Device settings have been reset to defaults.",
    });
  };

  if (!device) {
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

  const Icon = deviceIcons[device.type];

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

        {/* Device Header Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4"
        >
          <div className="flex items-center gap-4">
            <div className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center",
              device.type === "inverter" && "bg-solar/20",
              device.type === "battery" && "bg-battery/20",
              device.type === "meter" && "bg-grid/20"
            )}>
              <Icon className={cn("w-6 h-6", typeColors[device.type])} />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-foreground">{device.name}</h2>
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
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {device.type === "inverter" && (
            <InverterConfigPage deviceId={device.id} deviceName={device.name} />
          )}
          {device.type === "battery" && (
            <BatteryConfigPage deviceId={device.id} deviceName={device.name} />
          )}
          {device.type === "meter" && (
            <MeterConfigPage deviceId={device.id} deviceName={device.name} />
          )}
        </motion.div>

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex flex-col sm:flex-row gap-3"
        >
          <Button onClick={handleSave} className="flex-1 sm:flex-none gap-2">
            <Save className="w-4 h-4" />
            Save Configuration
          </Button>
          <Button variant="outline" onClick={handleReset} className="flex-1 sm:flex-none gap-2">
            <RotateCcw className="w-4 h-4" />
            Reset to Defaults
          </Button>
        </motion.div>
      </div>
    </AppLayout>
  );
};

export default DeviceSettingsPage;
