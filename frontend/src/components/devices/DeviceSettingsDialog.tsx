import { useState } from "react";
import { motion } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Cpu, Battery, Gauge, Save, RotateCcw, 
  Zap, Thermometer, Bell, Shield, Activity 
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";

interface Device {
  id: string;
  name: string;
  type: "inverter" | "battery" | "meter";
  status: "online" | "offline" | "warning";
  model: string;
  serialNumber: string;
}

interface DeviceSettingsDialogProps {
  device: Device | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

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

// Inverter Settings Component
const InverterSettings = ({ device }: { device: Device }) => {
  const [settings, setSettings] = useState({
    maxPowerOutput: 10,
    gridExportEnabled: true,
    maxExportPower: 8,
    antiIslandingEnabled: true,
    mpptMode: "auto",
    overTempThreshold: 55,
    underVoltageThreshold: 180,
    overVoltageThreshold: 270,
    alertsEnabled: true,
  });

  return (
    <Tabs defaultValue="power" className="w-full">
      <TabsList className="grid w-full grid-cols-3 mb-4">
        <TabsTrigger value="power">Power</TabsTrigger>
        <TabsTrigger value="grid">Grid</TabsTrigger>
        <TabsTrigger value="protection">Protection</TabsTrigger>
      </TabsList>

      <TabsContent value="power" className="space-y-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-solar" />
              Max Power Output
            </Label>
            <span className="text-sm font-mono text-foreground">{settings.maxPowerOutput} kW</span>
          </div>
          <Slider
            value={[settings.maxPowerOutput]}
            onValueChange={([v]) => setSettings({ ...settings, maxPowerOutput: v })}
            max={15}
            min={1}
            step={0.5}
            className="w-full"
          />
        </div>

        <div className="space-y-3">
          <Label className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            MPPT Mode
          </Label>
          <Select
            value={settings.mpptMode}
            onValueChange={(v) => setSettings({ ...settings, mpptMode: v })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="auto">Auto (Recommended)</SelectItem>
              <SelectItem value="fixed">Fixed Voltage</SelectItem>
              <SelectItem value="scan">Full Scan</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </TabsContent>

      <TabsContent value="grid" className="space-y-4">
        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div>
            <Label className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-grid" />
              Grid Export
            </Label>
            <p className="text-xs text-muted-foreground mt-1">Allow excess power to be exported to grid</p>
          </div>
          <Switch
            checked={settings.gridExportEnabled}
            onCheckedChange={(v) => setSettings({ ...settings, gridExportEnabled: v })}
          />
        </div>

        {settings.gridExportEnabled && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="space-y-3"
          >
            <div className="flex items-center justify-between">
              <Label>Max Export Power</Label>
              <span className="text-sm font-mono text-foreground">{settings.maxExportPower} kW</span>
            </div>
            <Slider
              value={[settings.maxExportPower]}
              onValueChange={([v]) => setSettings({ ...settings, maxExportPower: v })}
              max={settings.maxPowerOutput}
              min={0}
              step={0.5}
            />
          </motion.div>
        )}

        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div>
            <Label className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-warning" />
              Anti-Islanding Protection
            </Label>
            <p className="text-xs text-muted-foreground mt-1">Disconnect during grid outages</p>
          </div>
          <Switch
            checked={settings.antiIslandingEnabled}
            onCheckedChange={(v) => setSettings({ ...settings, antiIslandingEnabled: v })}
          />
        </div>
      </TabsContent>

      <TabsContent value="protection" className="space-y-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="flex items-center gap-2">
              <Thermometer className="w-4 h-4 text-warning" />
              Over Temperature Threshold
            </Label>
            <span className="text-sm font-mono text-foreground">{settings.overTempThreshold}°C</span>
          </div>
          <Slider
            value={[settings.overTempThreshold]}
            onValueChange={([v]) => setSettings({ ...settings, overTempThreshold: v })}
            max={70}
            min={40}
            step={1}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Under Voltage (V)</Label>
            <Input
              type="number"
              value={settings.underVoltageThreshold}
              onChange={(e) => setSettings({ ...settings, underVoltageThreshold: Number(e.target.value) })}
              className="bg-secondary/50"
            />
          </div>
          <div className="space-y-2">
            <Label>Over Voltage (V)</Label>
            <Input
              type="number"
              value={settings.overVoltageThreshold}
              onChange={(e) => setSettings({ ...settings, overVoltageThreshold: Number(e.target.value) })}
              className="bg-secondary/50"
            />
          </div>
        </div>

        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div>
            <Label className="flex items-center gap-2">
              <Bell className="w-4 h-4 text-primary" />
              Protection Alerts
            </Label>
            <p className="text-xs text-muted-foreground mt-1">Get notified on protection events</p>
          </div>
          <Switch
            checked={settings.alertsEnabled}
            onCheckedChange={(v) => setSettings({ ...settings, alertsEnabled: v })}
          />
        </div>
      </TabsContent>
    </Tabs>
  );
};

// Battery Settings Component
const BatterySettings = ({ device }: { device: Device }) => {
  const [settings, setSettings] = useState({
    minSoc: 10,
    maxSoc: 95,
    chargePriority: "solar-first",
    dischargePriority: "peak-shaving",
    maxChargeRate: 50,
    maxDischargeRate: 50,
    balancingEnabled: true,
    tempProtection: true,
    lowTempThreshold: 5,
    highTempThreshold: 45,
  });

  return (
    <Tabs defaultValue="soc" className="w-full">
      <TabsList className="grid w-full grid-cols-3 mb-4">
        <TabsTrigger value="soc">SOC Limits</TabsTrigger>
        <TabsTrigger value="charging">Charging</TabsTrigger>
        <TabsTrigger value="protection">Protection</TabsTrigger>
      </TabsList>

      <TabsContent value="soc" className="space-y-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="flex items-center gap-2">
              <Battery className="w-4 h-4 text-destructive" />
              Minimum SOC
            </Label>
            <span className="text-sm font-mono text-foreground">{settings.minSoc}%</span>
          </div>
          <Slider
            value={[settings.minSoc]}
            onValueChange={([v]) => setSettings({ ...settings, minSoc: v })}
            max={50}
            min={5}
            step={5}
          />
          <p className="text-xs text-muted-foreground">Battery will stop discharging at this level</p>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="flex items-center gap-2">
              <Battery className="w-4 h-4 text-battery" />
              Maximum SOC
            </Label>
            <span className="text-sm font-mono text-foreground">{settings.maxSoc}%</span>
          </div>
          <Slider
            value={[settings.maxSoc]}
            onValueChange={([v]) => setSettings({ ...settings, maxSoc: v })}
            max={100}
            min={60}
            step={5}
          />
          <p className="text-xs text-muted-foreground">Battery will stop charging at this level</p>
        </div>
      </TabsContent>

      <TabsContent value="charging" className="space-y-4">
        <div className="space-y-3">
          <Label>Charge Priority</Label>
          <Select
            value={settings.chargePriority}
            onValueChange={(v) => setSettings({ ...settings, chargePriority: v })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="solar-first">Solar First</SelectItem>
              <SelectItem value="grid-first">Grid First</SelectItem>
              <SelectItem value="time-based">Time Based</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-3">
          <Label>Discharge Priority</Label>
          <Select
            value={settings.dischargePriority}
            onValueChange={(v) => setSettings({ ...settings, dischargePriority: v })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="peak-shaving">Peak Shaving</SelectItem>
              <SelectItem value="self-consumption">Self Consumption</SelectItem>
              <SelectItem value="backup-only">Backup Only</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Max Charge Rate</Label>
              <span className="text-sm font-mono">{settings.maxChargeRate}%</span>
            </div>
            <Slider
              value={[settings.maxChargeRate]}
              onValueChange={([v]) => setSettings({ ...settings, maxChargeRate: v })}
              max={100}
              min={10}
              step={10}
            />
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Max Discharge Rate</Label>
              <span className="text-sm font-mono">{settings.maxDischargeRate}%</span>
            </div>
            <Slider
              value={[settings.maxDischargeRate]}
              onValueChange={([v]) => setSettings({ ...settings, maxDischargeRate: v })}
              max={100}
              min={10}
              step={10}
            />
          </div>
        </div>
      </TabsContent>

      <TabsContent value="protection" className="space-y-4">
        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div>
            <Label className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-battery" />
              Cell Balancing
            </Label>
            <p className="text-xs text-muted-foreground mt-1">Automatically balance cell voltages</p>
          </div>
          <Switch
            checked={settings.balancingEnabled}
            onCheckedChange={(v) => setSettings({ ...settings, balancingEnabled: v })}
          />
        </div>

        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div>
            <Label className="flex items-center gap-2">
              <Thermometer className="w-4 h-4 text-warning" />
              Temperature Protection
            </Label>
            <p className="text-xs text-muted-foreground mt-1">Stop charging/discharging at extreme temps</p>
          </div>
          <Switch
            checked={settings.tempProtection}
            onCheckedChange={(v) => setSettings({ ...settings, tempProtection: v })}
          />
        </div>

        {settings.tempProtection && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="grid grid-cols-2 gap-4"
          >
            <div className="space-y-2">
              <Label>Low Temp Limit (°C)</Label>
              <Input
                type="number"
                value={settings.lowTempThreshold}
                onChange={(e) => setSettings({ ...settings, lowTempThreshold: Number(e.target.value) })}
                className="bg-secondary/50"
              />
            </div>
            <div className="space-y-2">
              <Label>High Temp Limit (°C)</Label>
              <Input
                type="number"
                value={settings.highTempThreshold}
                onChange={(e) => setSettings({ ...settings, highTempThreshold: Number(e.target.value) })}
                className="bg-secondary/50"
              />
            </div>
          </motion.div>
        )}
      </TabsContent>
    </Tabs>
  );
};

// Meter Settings Component
const MeterSettings = ({ device }: { device: Device }) => {
  const [settings, setSettings] = useState({
    ctRatio: 100,
    vtRatio: 1,
    phaseMode: "three-phase",
    exportDirection: "reverse",
    importDirection: "forward",
    demandPeriod: 15,
    peakDemandReset: "monthly",
    alertsEnabled: true,
    powerQualityMonitoring: true,
  });

  return (
    <Tabs defaultValue="metering" className="w-full">
      <TabsList className="grid w-full grid-cols-3 mb-4">
        <TabsTrigger value="metering">Metering</TabsTrigger>
        <TabsTrigger value="direction">Direction</TabsTrigger>
        <TabsTrigger value="demand">Demand</TabsTrigger>
      </TabsList>

      <TabsContent value="metering" className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>CT Ratio</Label>
            <Input
              type="number"
              value={settings.ctRatio}
              onChange={(e) => setSettings({ ...settings, ctRatio: Number(e.target.value) })}
              className="bg-secondary/50"
            />
            <p className="text-xs text-muted-foreground">Current transformer ratio</p>
          </div>
          <div className="space-y-2">
            <Label>VT Ratio</Label>
            <Input
              type="number"
              value={settings.vtRatio}
              onChange={(e) => setSettings({ ...settings, vtRatio: Number(e.target.value) })}
              className="bg-secondary/50"
            />
            <p className="text-xs text-muted-foreground">Voltage transformer ratio</p>
          </div>
        </div>

        <div className="space-y-3">
          <Label>Phase Configuration</Label>
          <Select
            value={settings.phaseMode}
            onValueChange={(v) => setSettings({ ...settings, phaseMode: v })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="single-phase">Single Phase</SelectItem>
              <SelectItem value="three-phase">Three Phase (3P4W)</SelectItem>
              <SelectItem value="three-phase-3w">Three Phase (3P3W)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div>
            <Label className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-grid" />
              Power Quality Monitoring
            </Label>
            <p className="text-xs text-muted-foreground mt-1">Monitor THD, voltage sags/swells</p>
          </div>
          <Switch
            checked={settings.powerQualityMonitoring}
            onCheckedChange={(v) => setSettings({ ...settings, powerQualityMonitoring: v })}
          />
        </div>
      </TabsContent>

      <TabsContent value="direction" className="space-y-4">
        <div className="space-y-3">
          <Label>Import Direction</Label>
          <Select
            value={settings.importDirection}
            onValueChange={(v) => setSettings({ ...settings, importDirection: v })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="forward">Forward (Grid → Load)</SelectItem>
              <SelectItem value="reverse">Reverse (Load → Grid)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-3">
          <Label>Export Direction</Label>
          <Select
            value={settings.exportDirection}
            onValueChange={(v) => setSettings({ ...settings, exportDirection: v })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="forward">Forward (Grid → Load)</SelectItem>
              <SelectItem value="reverse">Reverse (Load → Grid)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </TabsContent>

      <TabsContent value="demand" className="space-y-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label>Demand Period</Label>
            <span className="text-sm font-mono text-foreground">{settings.demandPeriod} min</span>
          </div>
          <Slider
            value={[settings.demandPeriod]}
            onValueChange={([v]) => setSettings({ ...settings, demandPeriod: v })}
            max={60}
            min={5}
            step={5}
          />
          <p className="text-xs text-muted-foreground">Averaging period for demand calculation</p>
        </div>

        <div className="space-y-3">
          <Label>Peak Demand Reset</Label>
          <Select
            value={settings.peakDemandReset}
            onValueChange={(v) => setSettings({ ...settings, peakDemandReset: v })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="daily">Daily</SelectItem>
              <SelectItem value="weekly">Weekly</SelectItem>
              <SelectItem value="monthly">Monthly</SelectItem>
              <SelectItem value="manual">Manual Only</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div>
            <Label className="flex items-center gap-2">
              <Bell className="w-4 h-4 text-primary" />
              Demand Alerts
            </Label>
            <p className="text-xs text-muted-foreground mt-1">Alert when demand exceeds threshold</p>
          </div>
          <Switch
            checked={settings.alertsEnabled}
            onCheckedChange={(v) => setSettings({ ...settings, alertsEnabled: v })}
          />
        </div>
      </TabsContent>
    </Tabs>
  );
};

export function DeviceSettingsDialog({ device, open, onOpenChange }: DeviceSettingsDialogProps) {
  const Icon = device ? deviceIcons[device.type] : Cpu;

  const handleSave = () => {
    toast({
      title: "Settings Saved",
      description: `Configuration for ${device?.name} has been updated.`,
    });
    onOpenChange(false);
  };

  const handleReset = () => {
    toast({
      title: "Settings Reset",
      description: "Device settings have been reset to defaults.",
    });
  };

  if (!device) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl bg-card border-border">
          <DialogHeader>
            <DialogTitle>No Device Selected</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto bg-card border-border">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <div className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center",
              device.type === "inverter" && "bg-solar/20",
              device.type === "battery" && "bg-battery/20",
              device.type === "meter" && "bg-grid/20"
            )}>
              <Icon className={cn("w-5 h-5", typeColors[device.type])} />
            </div>
            <div>
              <span className="text-foreground">{device.name} Settings</span>
              <p className="text-sm font-normal text-muted-foreground">{device.model} • {device.serialNumber}</p>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="mt-4">
          {device.type === "inverter" && <InverterSettings device={device} />}
          {device.type === "battery" && <BatterySettings device={device} />}
          {device.type === "meter" && <MeterSettings device={device} />}
        </div>

        <div className="flex justify-between mt-6 pt-4 border-t border-border">
          <Button variant="outline" onClick={handleReset}>
            <RotateCcw className="w-4 h-4 mr-2" />
            Reset to Defaults
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>
              <Save className="w-4 h-4 mr-2" />
              Save Settings
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
