import { useState, useEffect } from "react";
import { motion } from "framer-motion";
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
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Cpu, Plus, Trash2, Sun, Shield, Settings2, Plug, Power, Clock, Info, Zap, Battery, Edit3, Check, X
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mapApiSettingsToConfig, mapApiSettingsToTOUWindows, type InverterConfig, type TOUWindowData } from "@/lib/settings-mapper";

// ============== Reusable Components ==============

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

interface SliderRowProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  description?: string;
  onChange: (value: number) => void;
}

const SliderRow = ({ label, value, min, max, step = 1, unit = "%", description, onChange }: SliderRowProps) => {
  return (
    <div className="py-3 border-b border-border/50 last:border-0">
      <div className="flex items-center justify-between mb-2">
        <div className="flex-1">
          <p className="text-sm text-foreground">{label}</p>
          {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
        </div>
        <span className="font-mono text-sm text-foreground">{value}{unit}</span>
      </div>
      <Slider
        value={[value]}
        onValueChange={([v]) => onChange(v)}
        min={min}
        max={max}
        step={step}
        className="mt-2"
      />
    </div>
  );
};

// ============== TOU Window Components ==============

interface TOUWindowData {
  mode: string;
  startTime: string;
  endTime: string;
  power: number;
  targetSoc: number;
  enabled: boolean;
}

const TOUWindowRow = ({ windowNum, data, onUpdate, onDelete }: {
  windowNum: number;
  data: TOUWindowData;
  onUpdate: (data: TOUWindowData) => void;
  onDelete: () => void;
}) => {
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

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div>
          <Label className="text-xs text-muted-foreground mb-1.5 block">Mode</Label>
          <Select value={data.mode} onValueChange={(v) => onUpdate({ ...data, mode: v })} disabled={!data.enabled}>
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
        <div>
          <Label className="text-xs text-muted-foreground mb-1.5 block">Power (W)</Label>
          <Input
            type="number"
            value={data.power}
            onChange={(e) => onUpdate({ ...data, power: parseInt(e.target.value) })}
            className="h-9 bg-secondary/50 text-xs"
            disabled={!data.enabled}
          />
        </div>
        <div>
          <Label className="text-xs text-muted-foreground mb-1.5 block">Target SOC (%)</Label>
          <Input
            type="number"
            value={data.targetSoc}
            onChange={(e) => onUpdate({ ...data, targetSoc: parseInt(e.target.value) })}
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
  const modeColors = {
    auto: "bg-primary",
    charge: "bg-success",
    discharge: "bg-warning",
  };

  const timeToPercent = (time: string) => {
    const [h, m] = time.split(":").map(Number);
    return ((h * 60 + m) / (24 * 60)) * 100;
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
      <div className="relative h-8 bg-secondary/30 rounded-lg overflow-hidden">
        {windows.filter(w => w.enabled).map((w, i) => {
          const start = timeToPercent(w.startTime);
          const end = timeToPercent(w.endTime);
          const width = end > start ? end - start : 100 - start + end;
          return (
            <div
              key={i}
              className={cn(
                "absolute h-full flex items-center justify-center text-xs font-medium text-white",
                modeColors[w.mode as keyof typeof modeColors] || modeColors.auto
              )}
              style={{ left: `${start}%`, width: `${width}%` }}
            >
              W{i + 1}
            </div>
          );
        })}
      </div>
      <div className="flex gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-primary" />
          <span>Auto</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-success" />
          <span>Charge</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-warning" />
          <span>Discharge</span>
        </div>
      </div>
    </div>
  );
};

// ============== Types ==============

interface SolarArrayConfig {
  pv_dc_kw: number;
  tilt_deg: number;
  azimuth_deg: number;
  perf_ratio: number;
  albedo: number;
}

interface InverterConfig {
  id: string;
  name: string;
  array_id: string;
  adapter: {
    type: string;
    transport: string;
    unit_id: number;
    serial_port: string;
    baudrate: number;
    parity: string;
    stopbits: number;
    bytesize: number;
    register_map_file: string;
    host: string;
    port: number;
  };
  safety: {
    max_batt_voltage_v: number;
    max_charge_a: number;
    max_discharge_a: number;
  };
  solar: SolarArrayConfig[];
  // System - Specification
  specification: {
    driver: string;
    serialNumber: string;
    protocolVersion: number;
    maxAcOutputPower: number;
    mpptConnections: number;
    parallelMode: boolean;
    modbusNumber: number;
  };
  // System - Grid Settings
  gridSettings: {
    voltageHigh: number;
    voltageLow: number;
    frequency: number;
    frequencyHigh: number;
    frequencyLow: number;
    peakShavingEnabled: boolean;
  };
  // Power - Battery Configuration
  batteryConfig: {
    type: string;
    capacity: number;
    operation: string;
    maxDischargeCurrent: number;
    maxChargeCurrent: number;
    maxGridChargeCurrent: number;
    maxGeneratorChargeCurrent: number;
    maxGridChargerPower: number;
    maxChargerPower: number;
    maxDischargerPower: number;
  };
  // Power - Work Mode
  workMode: {
    remoteSwitch: boolean;
    gridCharge: boolean;
    generatorCharge: boolean;
    forceGeneratorOn: boolean;
    outputShutdownCapacity: number;
    stopBatteryDischargeCapacity: number;
    startBatteryDischargeCapacity: number;
    startGridChargeCapacity: number;
    offGridMode: boolean;
    offGridStartupBatteryCapacity: number;
  };
}

// Mock available USB ports
const AVAILABLE_USB_PORTS = [
  { value: "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_CVCLe12CJ06-if00-port0", label: "Prolific USB-Serial Controller (CVCLe12CJ06)" },
  { value: "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9U593Y5-if00-port0", label: "FTDI FT232R USB UART (A9U593Y5)" },
  { value: "/dev/ttyUSB0", label: "/dev/ttyUSB0" },
  { value: "/dev/ttyUSB1", label: "/dev/ttyUSB1" },
  { value: "/dev/ttyACM0", label: "/dev/ttyACM0" },
  { value: "COM1", label: "COM1 (Windows)" },
  { value: "COM3", label: "COM3 (Windows)" },
];

interface InverterConfigPageProps {
  deviceId?: string;
  deviceName?: string;
  settings?: Record<string, any>;
}

export function InverterConfigPage({ deviceId, deviceName, settings }: InverterConfigPageProps) {
  // Initialize config from actual device settings or use defaults
  const [config, setConfig] = useState<InverterConfig>(() => {
    if (settings && Object.keys(settings).length > 0) {
      console.log('[InverterConfigPage] Initializing from device settings:', Object.keys(settings).length, 'settings');
      return mapApiSettingsToConfig(settings, deviceId, deviceName);
    }
    console.log('[InverterConfigPage] Using default config (no settings provided)');
    // Default config as fallback
    return {
      id: deviceId || "powdrive2",
      name: deviceName || "Powdrive",
      array_id: "array1",
      adapter: {
        type: "powdrive",
        transport: "rtu",
        unit_id: 1,
        serial_port: "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_CVCLe12CJ06-if00-port0",
        baudrate: 9600,
        parity: "N",
        stopbits: 1,
        bytesize: 8,
        register_map_file: "register_maps/powdrive_registers.json",
        host: "192.168.1.100",
        port: 502,
      },
      safety: {
        max_batt_voltage_v: 52,
        max_charge_a: 100,
        max_discharge_a: 100,
      },
      solar: [
        { pv_dc_kw: 15.4, tilt_deg: 28, azimuth_deg: 180, perf_ratio: 0.82, albedo: 0.2 },
      ],
      specification: {
        driver: "powdrive",
        serialNumber: "2406130030",
        protocolVersion: 260,
        maxAcOutputPower: 13000,
        mpptConnections: 3,
        parallelMode: false,
        modbusNumber: 1,
      },
      gridSettings: {
        voltageHigh: 26.5,
        voltageLow: 0,
        frequency: 50.42,
        frequencyHigh: 0.52,
        frequencyLow: 0.48,
        peakShavingEnabled: false,
      },
      batteryConfig: {
        type: "Lithium Battery",
        capacity: 450,
        operation: "State of Charge",
        maxDischargeCurrent: 93,
        maxChargeCurrent: 56,
        maxGridChargeCurrent: 19,
        maxGeneratorChargeCurrent: 0,
        maxGridChargerPower: 1037,
        maxChargerPower: 3859,
        maxDischargerPower: 5000,
      },
      workMode: {
        remoteSwitch: true,
        gridCharge: false,
        generatorCharge: false,
        forceGeneratorOn: false,
        outputShutdownCapacity: 10,
        stopBatteryDischargeCapacity: 35,
        startBatteryDischargeCapacity: 40,
        startGridChargeCapacity: 50,
        offGridMode: true,
        offGridStartupBatteryCapacity: 40,
      },
    };
  });

  const [touWindows, setTouWindows] = useState<TOUWindowData[]>(() => {
    if (settings && Object.keys(settings).length > 0) {
      console.log('[InverterConfigPage] Initializing TOU windows from device settings');
      return mapApiSettingsToTOUWindows(settings);
    }
    console.log('[InverterConfigPage] Using default TOU windows');
    return [
      { mode: "auto", startTime: "00:00", endTime: "07:00", power: 100, targetSoc: 50, enabled: true },
      { mode: "auto", startTime: "07:00", endTime: "09:00", power: 1000, targetSoc: 50, enabled: true },
      { mode: "charge", startTime: "09:00", endTime: "15:00", power: 3000, targetSoc: 98, enabled: true },
      { mode: "auto", startTime: "15:00", endTime: "17:00", power: 1120, targetSoc: 98, enabled: true },
      { mode: "discharge", startTime: "17:00", endTime: "23:00", power: 2400, targetSoc: 50, enabled: true },
      { mode: "auto", startTime: "23:00", endTime: "00:00", power: 1000, targetSoc: 50, enabled: true },
    ];
  });

  // Update config when settings change
  useEffect(() => {
    if (settings && Object.keys(settings).length > 0) {
      console.log('[InverterConfigPage] Settings updated, refreshing config');
      setConfig(mapApiSettingsToConfig(settings, deviceId, deviceName));
      setTouWindows(mapApiSettingsToTOUWindows(settings));
    }
  }, [settings, deviceId, deviceName]);

  const updateAdapter = (key: keyof InverterConfig["adapter"], value: string | number) => {
    setConfig(prev => ({ ...prev, adapter: { ...prev.adapter, [key]: value } }));
  };

  const updateSafety = (key: keyof InverterConfig["safety"], value: number) => {
    setConfig(prev => ({ ...prev, safety: { ...prev.safety, [key]: value } }));
  };

  const updateSpecification = (key: keyof InverterConfig["specification"], value: string | number | boolean) => {
    setConfig(prev => ({ ...prev, specification: { ...prev.specification, [key]: value } }));
  };

  const updateGridSettings = (key: keyof InverterConfig["gridSettings"], value: number | boolean) => {
    setConfig(prev => ({ ...prev, gridSettings: { ...prev.gridSettings, [key]: value } }));
  };

  const updateBatteryConfig = (key: keyof InverterConfig["batteryConfig"], value: string | number) => {
    setConfig(prev => ({ ...prev, batteryConfig: { ...prev.batteryConfig, [key]: value } }));
  };

  const updateWorkMode = (key: keyof InverterConfig["workMode"], value: number | boolean) => {
    setConfig(prev => ({ ...prev, workMode: { ...prev.workMode, [key]: value } }));
  };

  const updateSolarArray = (index: number, key: keyof SolarArrayConfig, value: number) => {
    setConfig(prev => ({
      ...prev,
      solar: prev.solar.map((arr, i) => i === index ? { ...arr, [key]: value } : arr),
    }));
  };

  const addSolarArray = () => {
    setConfig(prev => ({
      ...prev,
      solar: [...prev.solar, { pv_dc_kw: 5.0, tilt_deg: 25, azimuth_deg: 180, perf_ratio: 0.80, albedo: 0.2 }],
    }));
  };

  const removeSolarArray = (index: number) => {
    setConfig(prev => ({ ...prev, solar: prev.solar.filter((_, i) => i !== index) }));
  };

  const addTouWindow = () => {
    if (touWindows.length >= 6) return;
    setTouWindows(prev => [
      ...prev,
      { mode: "auto", startTime: "00:00", endTime: "06:00", power: 1000, targetSoc: 50, enabled: true },
    ]);
  };

  const updateTouWindow = (index: number, data: TOUWindowData) => {
    setTouWindows(prev => prev.map((w, i) => i === index ? data : w));
  };

  const deleteTouWindow = (index: number) => {
    setTouWindows(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <Tabs defaultValue="system" className="w-full">
      <TabsList className="grid w-full grid-cols-3 mb-4">
        <TabsTrigger value="system" className="gap-2">
          <Settings2 className="w-4 h-4 hidden sm:inline" />
          System
        </TabsTrigger>
        <TabsTrigger value="power" className="gap-2">
          <Power className="w-4 h-4 hidden sm:inline" />
          Power
        </TabsTrigger>
        <TabsTrigger value="scheduling" className="gap-2">
          <Clock className="w-4 h-4 hidden sm:inline" />
          Scheduling
        </TabsTrigger>
      </TabsList>

      {/* ============== SYSTEM TAB ============== */}
      <TabsContent value="system" className="space-y-4">
        <Accordion type="multiple" defaultValue={["general", "specification", "grid", "adapter", "safety", "solar"]} className="space-y-2">
          
          {/* General Settings */}
          <AccordionItem value="general" className="glass-card border-none">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-solar" />
                <span>Device Identity</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Device ID</Label>
                  <Input value={config.id} onChange={(e) => setConfig(prev => ({ ...prev, id: e.target.value }))} className="bg-secondary/50 font-mono" />
                </div>
                <div className="space-y-2">
                  <Label>Device Name</Label>
                  <Input value={config.name} onChange={(e) => setConfig(prev => ({ ...prev, name: e.target.value }))} className="bg-secondary/50" />
                </div>
              </div>
              <div className="space-y-2 mt-4">
                <Label>Array Assignment</Label>
                <Select value={config.array_id} onValueChange={(v) => setConfig(prev => ({ ...prev, array_id: v }))}>
                  <SelectTrigger className="bg-secondary/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="array1">Array 1</SelectItem>
                    <SelectItem value="array2">Array 2</SelectItem>
                    <SelectItem value="array3">Array 3</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Specification */}
          <AccordionItem value="specification" className="glass-card border-none">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-primary" />
                <span>Specification</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <SettingRow label="Driver" value={config.specification.driver} />
              <SettingRow label="Serial Number" value={config.specification.serialNumber} />
              <SettingRow label="Protocol Version" value={config.specification.protocolVersion} />
              <SettingRow label="Max AC Output Power" value={config.specification.maxAcOutputPower} unit="kW" editable onEdit={(v) => updateSpecification("maxAcOutputPower", parseFloat(v))} />
              <SettingRow label="MPPT Connections" value={config.specification.mpptConnections} />
              <ToggleRow label="Parallel Mode" checked={config.specification.parallelMode} onCheckedChange={(v) => updateSpecification("parallelMode", v)} />
              <SettingRow label="Modbus Number" value={config.specification.modbusNumber} />
            </AccordionContent>
          </AccordionItem>

          {/* Grid Settings */}
          <AccordionItem value="grid" className="glass-card border-none">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-grid" />
                <span>Grid Settings</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <SettingRow label="Grid Voltage High" value={config.gridSettings.voltageHigh} unit="V" editable onEdit={(v) => updateGridSettings("voltageHigh", parseFloat(v))} />
              <SettingRow label="Grid Voltage Low" value={config.gridSettings.voltageLow || "—"} unit="V" editable onEdit={(v) => updateGridSettings("voltageLow", parseFloat(v))} />
              <SettingRow label="Grid Frequency" value={config.gridSettings.frequency} unit="Hz" editable onEdit={(v) => updateGridSettings("frequency", parseFloat(v))} />
              <SettingRow label="Grid Frequency High" value={config.gridSettings.frequencyHigh} unit="Hz" editable onEdit={(v) => updateGridSettings("frequencyHigh", parseFloat(v))} />
              <SettingRow label="Grid Frequency Low" value={config.gridSettings.frequencyLow} unit="Hz" editable onEdit={(v) => updateGridSettings("frequencyLow", parseFloat(v))} />
              <ToggleRow label="Grid Peak Shaving" description="Limit power drawn from grid during peak times" checked={config.gridSettings.peakShavingEnabled} onCheckedChange={(v) => updateGridSettings("peakShavingEnabled", v)} />
            </AccordionContent>
          </AccordionItem>

          {/* Adapter Settings */}
          <AccordionItem value="adapter" className="glass-card border-none">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <Plug className="w-4 h-4 text-primary" />
                <span>Adapter / Communication</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Adapter Type</Label>
                  <Select value={config.adapter.type} onValueChange={(v) => updateAdapter("type", v)}>
                    <SelectTrigger className="bg-secondary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="powdrive">Powdrive</SelectItem>
                      <SelectItem value="sunsynk">Sunsynk</SelectItem>
                      <SelectItem value="growatt">Growatt</SelectItem>
                      <SelectItem value="deye">Deye</SelectItem>
                      <SelectItem value="solis">Solis</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Transport</Label>
                  <Select value={config.adapter.transport} onValueChange={(v) => updateAdapter("transport", v)}>
                    <SelectTrigger className="bg-secondary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="rtu">RTU (Serial)</SelectItem>
                      <SelectItem value="tcp">TCP (Network)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {config.adapter.transport === "rtu" ? (
                <>
                  <div className="space-y-2">
                    <Label>Serial Port</Label>
                    <Select value={config.adapter.serial_port} onValueChange={(v) => updateAdapter("serial_port", v)}>
                      <SelectTrigger className="bg-secondary/50 font-mono text-xs">
                        <SelectValue placeholder="Select USB port..." />
                      </SelectTrigger>
                      <SelectContent>
                        {AVAILABLE_USB_PORTS.map((port) => (
                          <SelectItem key={port.value} value={port.value} className="font-mono text-xs">{port.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div className="space-y-2">
                      <Label>Unit ID</Label>
                      <Input type="number" value={config.adapter.unit_id} onChange={(e) => updateAdapter("unit_id", parseInt(e.target.value))} className="bg-secondary/50" min={1} max={247} />
                    </div>
                    <div className="space-y-2">
                      <Label>Baudrate</Label>
                      <Select value={config.adapter.baudrate.toString()} onValueChange={(v) => updateAdapter("baudrate", parseInt(v))}>
                        <SelectTrigger className="bg-secondary/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="4800">4800</SelectItem>
                          <SelectItem value="9600">9600</SelectItem>
                          <SelectItem value="19200">19200</SelectItem>
                          <SelectItem value="38400">38400</SelectItem>
                          <SelectItem value="57600">57600</SelectItem>
                          <SelectItem value="115200">115200</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Parity</Label>
                      <Select value={config.adapter.parity} onValueChange={(v) => updateAdapter("parity", v)}>
                        <SelectTrigger className="bg-secondary/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="N">None (N)</SelectItem>
                          <SelectItem value="E">Even (E)</SelectItem>
                          <SelectItem value="O">Odd (O)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Stop Bits</Label>
                      <Select value={config.adapter.stopbits.toString()} onValueChange={(v) => updateAdapter("stopbits", parseInt(v))}>
                        <SelectTrigger className="bg-secondary/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="1">1</SelectItem>
                          <SelectItem value="2">2</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Byte Size</Label>
                      <Select value={config.adapter.bytesize.toString()} onValueChange={(v) => updateAdapter("bytesize", parseInt(v))}>
                        <SelectTrigger className="bg-secondary/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="7">7</SelectItem>
                          <SelectItem value="8">8</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Register Map File</Label>
                      <Input value={config.adapter.register_map_file} onChange={(e) => updateAdapter("register_map_file", e.target.value)} className="bg-secondary/50 font-mono text-xs" />
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>IP Address</Label>
                      <Input value={config.adapter.host} onChange={(e) => updateAdapter("host", e.target.value)} className="bg-secondary/50 font-mono" placeholder="192.168.1.100" />
                    </div>
                    <div className="space-y-2">
                      <Label>Port</Label>
                      <Input type="number" value={config.adapter.port} onChange={(e) => updateAdapter("port", parseInt(e.target.value))} className="bg-secondary/50" min={1} max={65535} />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Unit ID</Label>
                      <Input type="number" value={config.adapter.unit_id} onChange={(e) => updateAdapter("unit_id", parseInt(e.target.value))} className="bg-secondary/50" min={1} max={247} />
                    </div>
                    <div className="space-y-2">
                      <Label>Register Map File</Label>
                      <Input value={config.adapter.register_map_file} onChange={(e) => updateAdapter("register_map_file", e.target.value)} className="bg-secondary/50 font-mono text-xs" />
                    </div>
                  </div>
                </>
              )}
            </AccordionContent>
          </AccordionItem>

          {/* Safety Limits */}
          <AccordionItem value="safety" className="glass-card border-none">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-warning" />
                <span>Safety Limits</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4 space-y-4">
              <SliderRow label="Max Battery Voltage" value={config.safety.max_batt_voltage_v} min={40} max={60} step={0.5} unit=" V" onChange={(v) => updateSafety("max_batt_voltage_v", v)} />
              <SliderRow label="Max Charge Current" value={config.safety.max_charge_a} min={10} max={200} step={5} unit=" A" onChange={(v) => updateSafety("max_charge_a", v)} />
              <SliderRow label="Max Discharge Current" value={config.safety.max_discharge_a} min={10} max={200} step={5} unit=" A" onChange={(v) => updateSafety("max_discharge_a", v)} />
            </AccordionContent>
          </AccordionItem>

          {/* Solar Arrays */}
          <AccordionItem value="solar" className="glass-card border-none">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <Sun className="w-4 h-4 text-solar" />
                <span>Solar Arrays</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4 space-y-4">
              <div className="flex justify-end">
                <Button size="sm" variant="outline" onClick={addSolarArray} className="gap-2">
                  <Plus className="w-4 h-4" />
                  Add Array
                </Button>
              </div>
              {config.solar.map((arr, index) => (
                <div key={index} className="bg-secondary/20 rounded-lg p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Solar Array {index + 1}</span>
                    {config.solar.length > 1 && (
                      <Button variant="ghost" size="sm" onClick={() => removeSolarArray(index)} className="text-destructive hover:text-destructive">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label className="text-xs">PV DC Power (kW)</Label>
                      <Input type="number" value={arr.pv_dc_kw} onChange={(e) => updateSolarArray(index, "pv_dc_kw", parseFloat(e.target.value))} className="bg-secondary/50" step={0.1} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">Tilt Angle (°)</Label>
                      <Input type="number" value={arr.tilt_deg} onChange={(e) => updateSolarArray(index, "tilt_deg", parseInt(e.target.value))} className="bg-secondary/50" min={0} max={90} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">Azimuth (°)</Label>
                      <Input type="number" value={arr.azimuth_deg} onChange={(e) => updateSolarArray(index, "azimuth_deg", parseInt(e.target.value))} className="bg-secondary/50" min={0} max={360} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">Performance Ratio</Label>
                      <Input type="number" value={arr.perf_ratio} onChange={(e) => updateSolarArray(index, "perf_ratio", parseFloat(e.target.value))} className="bg-secondary/50" step={0.01} min={0.5} max={1} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">Albedo</Label>
                      <Input type="number" value={arr.albedo} onChange={(e) => updateSolarArray(index, "albedo", parseFloat(e.target.value))} className="bg-secondary/50" step={0.05} min={0} max={1} />
                    </div>
                  </div>
                </div>
              ))}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </TabsContent>

      {/* ============== POWER TAB ============== */}
      <TabsContent value="power" className="space-y-4">
        <Accordion type="multiple" defaultValue={["battery-config", "work-mode"]} className="space-y-2">
          
          {/* Battery Configuration */}
          <AccordionItem value="battery-config" className="glass-card border-none">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <Battery className="w-4 h-4 text-battery" />
                <span>Battery Configuration</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <SettingRow label="Battery Type" value={config.batteryConfig.type} editable onEdit={(v) => updateBatteryConfig("type", v)} />
              <SettingRow label="Battery Capacity" value={config.batteryConfig.capacity} unit="Ah" editable onEdit={(v) => updateBatteryConfig("capacity", parseInt(v))} />
              <SettingRow label="Battery Operation" value={config.batteryConfig.operation} editable onEdit={(v) => updateBatteryConfig("operation", v)} />
              <SettingRow label="Max Discharge Current" value={config.batteryConfig.maxDischargeCurrent} unit="A" editable onEdit={(v) => updateBatteryConfig("maxDischargeCurrent", parseInt(v))} />
              <SettingRow label="Max Charge Current" value={config.batteryConfig.maxChargeCurrent} unit="A" editable onEdit={(v) => updateBatteryConfig("maxChargeCurrent", parseInt(v))} />
              <SettingRow label="Max Grid Charge Current" value={config.batteryConfig.maxGridChargeCurrent} unit="A" editable onEdit={(v) => updateBatteryConfig("maxGridChargeCurrent", parseInt(v))} />
              <SettingRow label="Max Generator Charge Current" value={config.batteryConfig.maxGeneratorChargeCurrent} unit="A" editable onEdit={(v) => updateBatteryConfig("maxGeneratorChargeCurrent", parseInt(v))} />
              <SettingRow label="Max Grid Charger Power" value={config.batteryConfig.maxGridChargerPower} unit="W" editable onEdit={(v) => updateBatteryConfig("maxGridChargerPower", parseInt(v))} />
              <SettingRow label="Max Charger Power" value={config.batteryConfig.maxChargerPower} unit="W" description="Maximum total charging power" editable onEdit={(v) => updateBatteryConfig("maxChargerPower", parseInt(v))} />
              <SettingRow label="Max Discharger Power" value={config.batteryConfig.maxDischargerPower} unit="W" description="Maximum discharging power" editable onEdit={(v) => updateBatteryConfig("maxDischargerPower", parseInt(v))} />
            </AccordionContent>
          </AccordionItem>

          {/* Work Mode */}
          <AccordionItem value="work-mode" className="glass-card border-none">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-primary" />
                <span>Work Mode</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <ToggleRow label="Remote Switch" checked={config.workMode.remoteSwitch} onCheckedChange={(v) => updateWorkMode("remoteSwitch", v)} />
              <ToggleRow label="Grid Charge" checked={config.workMode.gridCharge} onCheckedChange={(v) => updateWorkMode("gridCharge", v)} />
              <ToggleRow label="Generator Charge" checked={config.workMode.generatorCharge} onCheckedChange={(v) => updateWorkMode("generatorCharge", v)} />
              <ToggleRow label="Force Generator On" checked={config.workMode.forceGeneratorOn} onCheckedChange={(v) => updateWorkMode("forceGeneratorOn", v)} />
              
              <SliderRow label="Output Shutdown Capacity" value={config.workMode.outputShutdownCapacity} min={0} max={100} onChange={(v) => updateWorkMode("outputShutdownCapacity", v)} />
              <SliderRow label="Stop Battery Discharge Capacity" value={config.workMode.stopBatteryDischargeCapacity} min={0} max={100} onChange={(v) => updateWorkMode("stopBatteryDischargeCapacity", v)} />
              <SliderRow label="Start Battery Discharge Capacity" value={config.workMode.startBatteryDischargeCapacity} min={0} max={100} onChange={(v) => updateWorkMode("startBatteryDischargeCapacity", v)} />
              <SliderRow label="Start Grid Charge Capacity" value={config.workMode.startGridChargeCapacity} min={0} max={100} onChange={(v) => updateWorkMode("startGridChargeCapacity", v)} />
              
              <ToggleRow label="Off-Grid Mode" description="Enable inverter operation without grid connection" checked={config.workMode.offGridMode} onCheckedChange={(v) => updateWorkMode("offGridMode", v)} />
              <SliderRow label="Off-Grid Startup Battery Capacity" value={config.workMode.offGridStartupBatteryCapacity} min={0} max={100} description="Minimum battery capacity to start in off-grid mode" onChange={(v) => updateWorkMode("offGridStartupBatteryCapacity", v)} />
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </TabsContent>

      {/* ============== SCHEDULING TAB ============== */}
      <TabsContent value="scheduling" className="space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 space-y-4"
        >
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Clock className="w-4 h-4 text-primary" />
                Time of Use (TOU) Windows
              </h3>
              <p className="text-xs text-muted-foreground mt-1">Configure up to 6 bidirectional windows</p>
            </div>
            {touWindows.length < 6 && (
              <Button size="sm" variant="outline" onClick={addTouWindow} className="gap-2">
                <Plus className="w-4 h-4" />
                Add Window
              </Button>
            )}
          </div>

          <TOUTimeline windows={touWindows} />
        </motion.div>

        <div className="space-y-3">
          {touWindows.map((window, index) => (
            <TOUWindowRow
              key={index}
              windowNum={index + 1}
              data={window}
              onUpdate={(data) => updateTouWindow(index, data)}
              onDelete={() => deleteTouWindow(index)}
            />
          ))}
        </div>
      </TabsContent>
    </Tabs>
  );
}
