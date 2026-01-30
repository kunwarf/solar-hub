import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
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
import {
  Info,
  Zap,
  Battery,
  Settings2,
  Clock,
  Power,
  Cpu,
  Edit3,
  Check,
  X,
  Plus,
  Trash2,
  Loader2,
  RefreshCw,
  Save,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { deviceCommandsService } from "@/api/services/device-commands.service";
import { mapSettingsToRegisters, mapRegistersToSettings } from "@/lib/register-field-mapping";
import { loadDeviceSettings, saveDeviceSettings, updateSettingsFromDevice } from "@/lib/device-settings-storage";
import { toast } from "@/hooks/use-toast";

interface SettingRowProps {
  label: string;
  value: string | number;
  unit?: string;
  description?: string;
  editable?: boolean;
  onEdit?: (value: string) => void;
}

const SettingRow = ({ label, value, unit, description, editable, onEdit }: SettingRowProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(String(value));

  const handleSave = () => {
    onEdit?.(editValue);
    setIsEditing(false);
  };

  return (
    <div className="flex items-center justify-between py-3 border-b border-border/50 last:border-0">
      <div className="flex-1">
        <p className="text-sm text-foreground">{label}</p>
        {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
      </div>
      <div className="flex items-center gap-2">
        {isEditing ? (
          <>
            <Input
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="w-24 h-8 text-right bg-secondary/50"
            />
            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={handleSave}>
              <Check className="h-4 w-4 text-success" />
            </Button>
            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setIsEditing(false)}>
              <X className="h-4 w-4 text-destructive" />
            </Button>
          </>
        ) : (
          <>
            <span className="font-mono text-sm text-foreground">
              {value}{unit && <span className="text-muted-foreground ml-1">{unit}</span>}
            </span>
            {editable && (
              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setIsEditing(true)}>
                <Edit3 className="h-3 w-3 text-primary" />
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
};

interface ToggleRowProps {
  label: string;
  description?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

const ToggleRow = ({ label, description, checked, onCheckedChange }: ToggleRowProps) => {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border/50 last:border-0">
      <div className="flex-1">
        <p className="text-sm text-foreground">{label}</p>
        {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
};

interface TOUWindowData {
  mode: string;
  startTime: string;
  endTime: string;
  power: number;
  targetSoc: number;
  enabled: boolean;
}

interface TOUWindowRowProps {
  windowNum: number;
  data: TOUWindowData;
  onUpdate: (data: TOUWindowData) => void;
  onDelete: () => void;
}

const TOUWindowRow = ({ windowNum, data, onUpdate, onDelete }: TOUWindowRowProps) => {
  const modeColors = {
    auto: "bg-primary/20 text-primary border-primary/30",
    charge: "bg-success/20 text-success border-success/30",
    discharge: "bg-warning/20 text-warning border-warning/30",
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "glass-card p-4 border transition-all",
        data.enabled ? "opacity-100" : "opacity-50"
      )}
    >
      {/* Header with toggle and delete */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={cn(
            "px-2.5 py-1 rounded-full text-xs font-medium border",
            modeColors[data.mode as keyof typeof modeColors] || modeColors.auto
          )}>
            Window {windowNum}
          </div>
          <Switch
            checked={data.enabled}
            onCheckedChange={(v) => onUpdate({ ...data, enabled: v })}
          />
        </div>
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
          onClick={onDelete}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Inline editing fields */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        {/* Mode Selection */}
        <div className="col-span-2 sm:col-span-1">
          <Label className="text-xs text-muted-foreground mb-1.5 block">Mode</Label>
          <Select 
            value={data.mode} 
            onValueChange={(v) => onUpdate({ ...data, mode: v })}
            disabled={!data.enabled}
          >
            <SelectTrigger className="h-9 bg-secondary/50 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="auto">Auto</SelectItem>
              <SelectItem value="charge">Charge</SelectItem>
              <SelectItem value="discharge">Discharge</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Start Time */}
        <div>
          <Label className="text-xs text-muted-foreground mb-1.5 block">Start</Label>
          <Input
            type="time"
            value={data.startTime}
            onChange={(e) => onUpdate({ ...data, startTime: e.target.value })}
            className="h-9 bg-secondary/50 text-xs"
            disabled={!data.enabled}
          />
        </div>

        {/* End Time */}
        <div>
          <Label className="text-xs text-muted-foreground mb-1.5 block">End</Label>
          <Input
            type="time"
            value={data.endTime}
            onChange={(e) => onUpdate({ ...data, endTime: e.target.value })}
            className="h-9 bg-secondary/50 text-xs"
            disabled={!data.enabled}
          />
        </div>

        {/* Power */}
        <div>
          <Label className="text-xs text-muted-foreground mb-1.5 block">Power (W)</Label>
          <Input
            type="number"
            value={data.power}
            onChange={(e) => onUpdate({ ...data, power: Number(e.target.value) })}
            className="h-9 bg-secondary/50 text-xs"
            disabled={!data.enabled}
          />
        </div>

        {/* Target SOC */}
        <div>
          <Label className="text-xs text-muted-foreground mb-1.5 block">Target SOC (%)</Label>
          <Input
            type="number"
            value={data.targetSoc}
            onChange={(e) => onUpdate({ ...data, targetSoc: Number(e.target.value) })}
            className="h-9 bg-secondary/50 text-xs"
            min={0}
            max={100}
            disabled={!data.enabled}
          />
        </div>
      </div>
    </motion.div>
  );
};

const TOUTimeline = ({ windows }: { windows: TOUWindowData[] }) => {
  const getPosition = (time: string) => {
    const [hours, minutes] = time.split(":").map(Number);
    return ((hours * 60 + minutes) / (24 * 60)) * 100;
  };

  const modeColors = {
    auto: "bg-primary",
    charge: "bg-success",
    discharge: "bg-warning",
  };

  const enabledWindows = windows.filter(w => w.enabled);

  return (
    <div className="mb-6">
      <div className="flex justify-between text-xs text-muted-foreground mb-2">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
      <div className="relative h-8 bg-secondary/30 rounded-lg overflow-hidden">
        {enabledWindows.map((window, idx) => {
          const start = getPosition(window.startTime);
          const end = getPosition(window.endTime);
          const width = end > start ? end - start : (100 - start) + end;
          const originalIdx = windows.indexOf(window);
          return (
            <div
              key={idx}
              className={cn(
                "absolute top-1 bottom-1 rounded-md opacity-80",
                modeColors[window.mode as keyof typeof modeColors] || modeColors.auto
              )}
              style={{
                left: `${start}%`,
                width: `${width}%`,
              }}
            >
              <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-white">
                W{originalIdx + 1}
              </span>
            </div>
          );
        })}
      </div>
      <div className="flex gap-4 mt-3 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-primary" />
          <span className="text-muted-foreground">Auto</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-success" />
          <span className="text-muted-foreground">Charge</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-warning" />
          <span className="text-muted-foreground">Discharge</span>
        </div>
      </div>
    </div>
  );
};

interface InverterSettingsPageProps {
  deviceId: string;
}

export function InverterSettingsPage({ deviceId }: InverterSettingsPageProps) {
  // Loading and error states
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Original settings from device (for change detection)
  const [originalSettings, setOriginalSettings] = useState<Record<string, any>>({});

  // Current settings (edited by user)
  const [touWindows, setTouWindows] = useState<TOUWindowData[]>([
    { mode: "auto", startTime: "00:00", endTime: "07:00", power: 100, targetSoc: 50, enabled: true },
    { mode: "auto", startTime: "07:00", endTime: "09:00", power: 1000, targetSoc: 50, enabled: true },
    { mode: "charge", startTime: "09:00", endTime: "15:00", power: 3000, targetSoc: 98, enabled: true },
    { mode: "auto", startTime: "15:00", endTime: "17:00", power: 1120, targetSoc: 98, enabled: true },
    { mode: "discharge", startTime: "17:00", endTime: "23:00", power: 2400, targetSoc: 50, enabled: true },
    { mode: "auto", startTime: "23:00", endTime: "00:00", power: 1000, targetSoc: 50, enabled: true },
  ]);

  const [gridSettings, setGridSettings] = useState({
    peakShavingEnabled: false,
    maxExportPower: 13000,
    solarSellEnabled: true,
    solarPriority: "load-first", // "battery-first" or "load-first"
  });

  const [specification, setSpecification] = useState({
    parallelMode: false,
  });

  const [batterySettings, setbatterySettings] = useState({
    batteryCapacity: 1010,
    maxChargeCurrent: 75,
    maxDischargeCurrent: 100,
  });

  const [workMode, setWorkMode] = useState({
    remoteSwitch: true,
    gridCharge: false,
    generatorCharge: false,
    forceGeneratorOn: false,
    outputShutdownCapacity: 10,
    stopBatteryDischarge: 35,
    startBatteryDischarge: 40,
    startGridCharge: 30,
    offGridMode: true,
    offGridStartupCapacity: 40,
  });

  const [workModeDetail, setWorkModeDetail] = useState({
    workMode: "zero-export",
    solarExportWhenFull: true,
    energyPattern: "load-first",
    maxSellPower: 15.6,
    maxSolarPower: 15.6,
    gridTrickleFeed: 20,
    maxFeedInPower: 12000,
  });

  const [auxiliarySettings, setAuxiliarySettings] = useState({
    generatorConnectedToGrid: false,
    generatorPeakShaving: false,
  });

  // Load settings from device on mount
  useEffect(() => {
    loadSettingsFromDevice();
  }, [deviceId]);

  // Track changes
  useEffect(() => {
    if (Object.keys(originalSettings).length > 0) {
      // Compare current state with original
      const changed = JSON.stringify(getCurrentSettings()) !== JSON.stringify(originalSettings);
      setHasChanges(changed);
    }
  }, [gridSettings, batterySettings, workMode, workModeDetail, auxiliarySettings, touWindows]);

  const getCurrentSettings = () => {
    return {
      ...gridSettings,
      ...batterySettings,
      ...workMode,
      ...workModeDetail,
      ...auxiliarySettings,
      // TOU windows would need separate handling
    };
  };

  const loadSettingsFromDevice = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Try to load from cache first
      const cached = loadDeviceSettings(deviceId);
      if (cached && !cached.isStale) {
        applySettingsToState(cached.settings);
        setOriginalSettings(cached.settings);
        setIsLoading(false);

        // Still query device in background to update cache
        queryDeviceInBackground();
        return;
      }

      // Query device
      await queryDevice();
    } catch (err: any) {
      console.error("Failed to load settings:", err);
      setError(err.message || "Failed to load device settings");

      // Try cache as fallback
      const cached = loadDeviceSettings(deviceId);
      if (cached) {
        applySettingsToState(cached.settings);
        setOriginalSettings(cached.settings);
        toast({
          title: "Using Cached Settings",
          description: "Could not reach device, showing cached settings",
          variant: "destructive",
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const queryDevice = async () => {
    const response = await deviceCommandsService.querySettings(deviceId);

    // Poll for completion
    const result = await deviceCommandsService.waitForCommand(
      deviceId,
      response.command_id,
      30000
    );

    if (result.status === 'completed' && result.result?.settings) {
      const settings = result.result.settings;

      // Save to cache
      updateSettingsFromDevice(deviceId, 'inverter', settings);

      // Apply to UI state
      applySettingsToState(settings);
      setOriginalSettings(settings);
    } else {
      throw new Error(result.error || "Failed to query settings");
    }
  };

  const queryDeviceInBackground = async () => {
    try {
      await queryDevice();
    } catch (err) {
      // Silent fail for background update
      console.warn("Background settings update failed:", err);
    }
  };

  const applySettingsToState = (settings: Record<string, any>) => {
    // Map register values to UI state
    // This is a simplified version - you'd map all fields properly
    if (settings.max_export_power_w !== undefined) {
      setGridSettings(prev => ({ ...prev, maxExportPower: settings.max_export_power_w }));
    }
    if (settings.solar_sell !== undefined) {
      setGridSettings(prev => ({ ...prev, solarSellEnabled: settings.solar_sell === 1 }));
    }
    if (settings.solar_priority !== undefined) {
      setGridSettings(prev => ({
        ...prev,
        solarPriority: settings.solar_priority === 0 ? "battery-first" : "load-first"
      }));
    }
    if (settings.battery_capacity_ah !== undefined) {
      setbatterySettings(prev => ({ ...prev, batteryCapacity: settings.battery_capacity_ah }));
    }
    if (settings.battery_max_charge_current_a !== undefined) {
      setbatterySettings(prev => ({ ...prev, maxChargeCurrent: settings.battery_max_charge_current_a }));
    }
    if (settings.battery_max_discharge_current_a !== undefined) {
      setbatterySettings(prev => ({ ...prev, maxDischargeCurrent: settings.battery_max_discharge_current_a }));
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);

    try {
      // Get changed fields
      const currentSettings = getCurrentSettings();
      const changedFields: Record<string, any> = {};

      for (const [key, value] of Object.entries(currentSettings)) {
        if (originalSettings[key] !== value) {
          changedFields[key] = value;
        }
      }

      if (Object.keys(changedFields).length === 0) {
        toast({ title: "No changes to save" });
        return;
      }

      // Map UI fields to register IDs
      const registerUpdates = mapSettingsToRegisters('inverter', changedFields);

      // Send update command
      const response = await deviceCommandsService.updateSettings(
        deviceId,
        registerUpdates,
        true
      );

      // Poll for completion
      const result = await deviceCommandsService.waitForCommand(
        deviceId,
        response.command_id,
        60000 // 60 second timeout for writes
      );

      if (result.status === 'completed') {
        // Update cache
        if (result.result?.settings) {
          updateSettingsFromDevice(deviceId, 'inverter', result.result.settings);
          setOriginalSettings(getCurrentSettings());
        }

        setHasChanges(false);
        toast({
          title: "Settings Updated",
          description: `Successfully updated ${Object.keys(changedFields).length} settings`,
        });
      } else {
        throw new Error(result.error || "Update failed");
      }
    } catch (err: any) {
      console.error("Failed to save settings:", err);
      setError(err.message || "Failed to save settings");
      toast({
        title: "Save Failed",
        description: err.message || "Could not update device settings",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRefresh = () => {
    loadSettingsFromDevice();
  };

  const updateTOUWindow = (index: number, data: TOUWindowData) => {
    const newWindows = [...touWindows];
    newWindows[index] = data;
    setTouWindows(newWindows);
  };

  const deleteTOUWindow = (index: number) => {
    setTouWindows(touWindows.filter((_, i) => i !== index));
  };

  const addTOUWindow = () => {
    if (touWindows.length >= 6) return;
    setTouWindows([
      ...touWindows,
      { mode: "auto", startTime: "00:00", endTime: "06:00", power: 1000, targetSoc: 50, enabled: true }
    ]);
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
        <p className="text-sm text-muted-foreground">Loading device settings...</p>
      </div>
    );
  }

  // Error state
  if (error && Object.keys(originalSettings).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="text-destructive mb-4">Failed to load settings</div>
        <p className="text-sm text-muted-foreground mb-4">{error}</p>
        <Button onClick={handleRefresh} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with Save/Refresh buttons */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Inverter Settings</h2>
          <p className="text-sm text-muted-foreground">
            Configure your inverter parameters
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleRefresh}
            variant="outline"
            size="sm"
            disabled={isLoading || isSaving}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
            Refresh
          </Button>
          <Button
            onClick={handleSave}
            size="sm"
            disabled={!hasChanges || isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Warning if using cached data */}
      {error && (
        <div className="bg-warning/10 border border-warning/20 rounded-lg p-3">
          <p className="text-sm text-warning">
            ⚠️ Device offline - showing cached settings from{" "}
            {new Date(loadDeviceSettings(deviceId)?.lastQueriedAt || "").toLocaleString()}
          </p>
        </div>
      )}

      {/* Changes indicator */}
      {hasChanges && (
        <div className="bg-primary/10 border border-primary/20 rounded-lg p-3">
          <p className="text-sm text-primary">
            💡 You have unsaved changes. Click "Save Changes" to apply them to the device.
          </p>
        </div>
      )}

      <Tabs defaultValue="system" className="w-full">
        <TabsList className="grid w-full grid-cols-3 mb-6">
          <TabsTrigger value="system" className="gap-2">
            <Cpu className="w-4 h-4 hidden sm:block" />
            System
          </TabsTrigger>
          <TabsTrigger value="power" className="gap-2">
            <Power className="w-4 h-4 hidden sm:block" />
            Power
          </TabsTrigger>
          <TabsTrigger value="scheduling" className="gap-2">
            <Clock className="w-4 h-4 hidden sm:block" />
            Scheduling
          </TabsTrigger>
        </TabsList>

      {/* SYSTEM TAB */}
      <TabsContent value="system" className="space-y-4">
        <Accordion type="multiple" defaultValue={["specification", "grid"]} className="space-y-3">
          <AccordionItem value="specification" className="glass-card border-0 px-4">
            <AccordionTrigger className="hover:no-underline py-4">
              <div className="flex items-center gap-3">
                <Info className="w-5 h-5 text-primary" />
                <span className="font-semibold">Specification</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pb-4">
              <SettingRow label="Driver" value="powdrive" />
              <SettingRow label="Serial Number" value="2406130030" />
              <SettingRow label="Protocol Version" value="260" />
              <SettingRow label="Max AC Output Power" value="356935.3" unit="kW" />
              <SettingRow label="MPPT Connections" value="3" />
              <ToggleRow 
                label="Parallel Mode" 
                checked={specification.parallelMode}
                onCheckedChange={(v) => setSpecification({...specification, parallelMode: v})}
              />
              <SettingRow label="Modbus Number" value="1" />
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="grid" className="glass-card border-0 px-4">
            <AccordionTrigger className="hover:no-underline py-4">
              <div className="flex items-center gap-3">
                <Zap className="w-5 h-5 text-grid" />
                <span className="font-semibold">Grid Settings</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pb-4">
              <SettingRow label="Grid Voltage High" value="26.5" unit="V" editable />
              <SettingRow label="Grid Voltage Low" value="—" editable />
              <SettingRow label="Grid Frequency" value="50.42" unit="Hz" />
              <SettingRow label="Grid Frequency High" value="0.52" unit="Hz" editable />
              <SettingRow label="Grid Frequency Low" value="0.48" unit="Hz" editable />
              <ToggleRow 
                label="Grid Peak Shaving" 
                description="Limit power drawn from grid during peak times"
                checked={gridSettings.peakShavingEnabled}
                onCheckedChange={(v) => setGridSettings({...gridSettings, peakShavingEnabled: v})}
              />
              {gridSettings.peakShavingEnabled && (
                <SettingRow label="Grid Peak Shaving Power" value="8" unit="kW" editable />
              )}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </TabsContent>

      {/* POWER TAB */}
      <TabsContent value="power" className="space-y-4">
        <Accordion type="multiple" defaultValue={["battery-type", "work-mode"]} className="space-y-3">
          <AccordionItem value="battery-type" className="glass-card border-0 px-4">
            <AccordionTrigger className="hover:no-underline py-4">
              <div className="flex items-center gap-3">
                <Battery className="w-5 h-5 text-battery" />
                <span className="font-semibold">Battery Configuration</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pb-4">
              <SettingRow label="Battery Type" value="Lithium Battery" editable />
              <SettingRow
                label="Battery Capacity"
                value={batterySettings.batteryCapacity}
                unit="Ah"
                editable
                onEdit={(v) => setbatterySettings({...batterySettings, batteryCapacity: parseInt(v)})}
              />
              <SettingRow label="Battery Operation" value="State of Charge" editable />
              <div className="border-t border-border/50 my-3" />
              <SettingRow
                label="Max Discharge Current"
                value={batterySettings.maxDischargeCurrent}
                unit="A"
                editable
                onEdit={(v) => setbatterySettings({...batterySettings, maxDischargeCurrent: parseInt(v)})}
              />
              <SettingRow
                label="Max Charge Current"
                value={batterySettings.maxChargeCurrent}
                unit="A"
                editable
                onEdit={(v) => setbatterySettings({...batterySettings, maxChargeCurrent: parseInt(v)})}
              />
              <SettingRow label="Max Grid Charge Current" value="19" unit="A" editable />
              <SettingRow label="Max Generator Charge Current" value="0" unit="A" editable />
              <SettingRow label="Max Grid Charger Power" value="1037" unit="W" editable />
              <SettingRow label="Max Charger Power" value="3059" unit="W" editable description="Maximum total charging power" />
              <SettingRow label="Max Discharger Power" value="5080" unit="W" editable description="Maximum discharging power" />
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="work-mode" className="glass-card border-0 px-4">
            <AccordionTrigger className="hover:no-underline py-4">
              <div className="flex items-center gap-3">
                <Settings2 className="w-5 h-5 text-warning" />
                <span className="font-semibold">Work Mode</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pb-4 space-y-1">
              <ToggleRow 
                label="Remote Switch" 
                checked={workMode.remoteSwitch} 
                onCheckedChange={(v) => setWorkMode({...workMode, remoteSwitch: v})} 
              />
              <ToggleRow 
                label="Grid Charge" 
                checked={workMode.gridCharge} 
                onCheckedChange={(v) => setWorkMode({...workMode, gridCharge: v})} 
              />
              <ToggleRow 
                label="Generator Charge" 
                checked={workMode.generatorCharge} 
                onCheckedChange={(v) => setWorkMode({...workMode, generatorCharge: v})} 
              />
              <ToggleRow 
                label="Force Generator On" 
                checked={workMode.forceGeneratorOn} 
                onCheckedChange={(v) => setWorkMode({...workMode, forceGeneratorOn: v})} 
              />
              
              <div className="space-y-3 pt-4">
                <div>
                  <div className="flex justify-between mb-2">
                    <Label className="text-sm">Output Shutdown Capacity</Label>
                    <span className="text-sm font-mono">{workMode.outputShutdownCapacity}%</span>
                  </div>
                  <Slider
                    value={[workMode.outputShutdownCapacity]}
                    onValueChange={([v]) => setWorkMode({...workMode, outputShutdownCapacity: v})}
                    max={50}
                    min={5}
                    step={5}
                  />
                </div>
                <div>
                  <div className="flex justify-between mb-2">
                    <Label className="text-sm">Stop Battery Discharge Capacity</Label>
                    <span className="text-sm font-mono">{workMode.stopBatteryDischarge}%</span>
                  </div>
                  <Slider
                    value={[workMode.stopBatteryDischarge]}
                    onValueChange={([v]) => setWorkMode({...workMode, stopBatteryDischarge: v})}
                    max={80}
                    min={10}
                    step={5}
                  />
                </div>
                <div>
                  <div className="flex justify-between mb-2">
                    <Label className="text-sm">Start Battery Discharge Capacity</Label>
                    <span className="text-sm font-mono">{workMode.startBatteryDischarge}%</span>
                  </div>
                  <Slider
                    value={[workMode.startBatteryDischarge]}
                    onValueChange={([v]) => setWorkMode({...workMode, startBatteryDischarge: v})}
                    max={90}
                    min={20}
                    step={5}
                  />
                </div>
                <div>
                  <div className="flex justify-between mb-2">
                    <Label className="text-sm">Start Grid Charge Capacity</Label>
                    <span className="text-sm font-mono">{workMode.startGridCharge}%</span>
                  </div>
                  <Slider
                    value={[workMode.startGridCharge]}
                    onValueChange={([v]) => setWorkMode({...workMode, startGridCharge: v})}
                    max={50}
                    min={10}
                    step={5}
                  />
                </div>
              </div>

              <div className="border-t border-border/50 pt-4 mt-4 space-y-1">
                <ToggleRow 
                  label="Off-Grid Mode" 
                  description="Enable inverter operation without grid connection"
                  checked={workMode.offGridMode} 
                  onCheckedChange={(v) => setWorkMode({...workMode, offGridMode: v})} 
                />
                {workMode.offGridMode && (
                  <div className="pt-2">
                    <div className="flex justify-between mb-2">
                      <Label className="text-sm">Off-Grid Startup Battery Capacity</Label>
                      <span className="text-sm font-mono">{workMode.offGridStartupCapacity}%</span>
                    </div>
                    <Slider
                      value={[workMode.offGridStartupCapacity]}
                      onValueChange={([v]) => setWorkMode({...workMode, offGridStartupCapacity: v})}
                      max={80}
                      min={20}
                      step={5}
                    />
                    <p className="text-xs text-muted-foreground mt-1">Minimum battery capacity to start in off-grid mode</p>
                  </div>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="work-mode-detail" className="glass-card border-0 px-4">
            <AccordionTrigger className="hover:no-underline py-4">
              <div className="flex items-center gap-3">
                <Settings2 className="w-5 h-5 text-primary" />
                <span className="font-semibold">Work Mode Detail</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pb-4 space-y-4">
              <div className="space-y-2">
                <Label>Work Mode</Label>
                <Select value={workModeDetail.workMode} onValueChange={(v) => setWorkModeDetail({...workModeDetail, workMode: v})}>
                  <SelectTrigger className="bg-secondary/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="zero-export">Zero Export to Load</SelectItem>
                    <SelectItem value="feed-in">Feed-in Priority</SelectItem>
                    <SelectItem value="self-use">Self-Use Priority</SelectItem>
                    <SelectItem value="backup">Backup Mode</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <ToggleRow 
                label="Solar Export When Battery Full" 
                checked={workModeDetail.solarExportWhenFull} 
                onCheckedChange={(v) => setWorkModeDetail({...workModeDetail, solarExportWhenFull: v})} 
              />

              <div className="space-y-2">
                <Label>Energy Pattern</Label>
                <Select value={workModeDetail.energyPattern} onValueChange={(v) => setWorkModeDetail({...workModeDetail, energyPattern: v})}>
                  <SelectTrigger className="bg-secondary/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="load-first">Load First</SelectItem>
                    <SelectItem value="battery-first">Battery First</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div className="space-y-2">
                  <Label>Max Sell Power (kW)</Label>
                  <Input
                    type="number"
                    value={workModeDetail.maxSellPower}
                    onChange={(e) => setWorkModeDetail({...workModeDetail, maxSellPower: Number(e.target.value)})}
                    className="bg-secondary/50"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Max Solar Power (kW)</Label>
                  <Input
                    type="number"
                    value={workModeDetail.maxSolarPower}
                    onChange={(e) => setWorkModeDetail({...workModeDetail, maxSolarPower: Number(e.target.value)})}
                    className="bg-secondary/50"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Grid Trickle Feed (W)</Label>
                  <Input
                    type="number"
                    value={workModeDetail.gridTrickleFeed}
                    onChange={(e) => setWorkModeDetail({...workModeDetail, gridTrickleFeed: Number(e.target.value)})}
                    className="bg-secondary/50"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Max Feed-in Grid Power (W)</Label>
                  <Input
                    type="number"
                    value={workModeDetail.maxFeedInPower}
                    onChange={(e) => setWorkModeDetail({...workModeDetail, maxFeedInPower: Number(e.target.value)})}
                    className="bg-secondary/50"
                  />
                  <p className="text-xs text-muted-foreground">Maximum power that can be fed into the grid</p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="auxiliary" className="glass-card border-0 px-4">
            <AccordionTrigger className="hover:no-underline py-4">
              <div className="flex items-center gap-3">
                <Power className="w-5 h-5 text-muted-foreground" />
                <span className="font-semibold">Auxiliary / Generator</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pb-4">
              <SettingRow label="Auxiliary Port" value="Generator Input" editable />
              <ToggleRow 
                label="Generator Connected to Grid Input" 
                checked={auxiliarySettings.generatorConnectedToGrid}
                onCheckedChange={(v) => setAuxiliarySettings({...auxiliarySettings, generatorConnectedToGrid: v})}
              />
              <ToggleRow 
                label="Generator Peak Shaving" 
                checked={auxiliarySettings.generatorPeakShaving}
                onCheckedChange={(v) => setAuxiliarySettings({...auxiliarySettings, generatorPeakShaving: v})}
              />
              {auxiliarySettings.generatorPeakShaving && (
                <SettingRow label="Generator Peak Shaving Power" value="8" unit="kW" editable />
              )}
              <SettingRow label="Generator Stop Capacity" value="—" editable />
              <SettingRow label="Generator Start Capacity" value="30" unit="%" editable />
              <SettingRow label="Generator Max Run Time" value="24" unit="h" editable />
              <SettingRow label="Generator Down Time" value="0" unit="h" editable />
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </TabsContent>

      {/* SCHEDULING TAB */}
      <TabsContent value="scheduling" className="space-y-4">
        <div className="glass-card p-4 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Clock className="w-5 h-5 text-primary" />
              <div>
                <h3 className="font-semibold">Time of Use (TOU) Windows</h3>
                <p className="text-sm text-muted-foreground">Configure up to 6 bidirectional windows</p>
              </div>
            </div>
            {touWindows.length < 6 && (
              <Button
                size="sm"
                variant="outline"
                onClick={addTOUWindow}
                className="gap-1.5"
              >
                <Plus className="h-4 w-4" />
                Add Window
              </Button>
            )}
          </div>

          {/* Visual Timeline */}
          <TOUTimeline windows={touWindows} />

          {/* Window Rows */}
          <div className="space-y-3">
            {touWindows.map((window, idx) => (
              <TOUWindowRow
                key={idx}
                windowNum={idx + 1}
                data={window}
                onUpdate={(data) => updateTOUWindow(idx, data)}
                onDelete={() => deleteTOUWindow(idx)}
              />
            ))}
          </div>

          {touWindows.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <Clock className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>No TOU windows configured</p>
              <Button
                size="sm"
                variant="outline"
                onClick={addTOUWindow}
                className="mt-3 gap-1.5"
              >
                <Plus className="h-4 w-4" />
                Add First Window
              </Button>
            </div>
          )}
        </div>
      </TabsContent>
    </Tabs>
  );
}
