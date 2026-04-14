/**
 * VoltronicSettingsPage
 *
 * Settings page for Voltronic inverters (PI30 / PI18 / PI16 / PI17 / PI34).
 * Voltronic uses named text commands — NOT Modbus registers — so the layout
 * is command-oriented: each field has its own Apply and shows ACK/NAK.
 *
 * Accent color: #A855F7 (purple)
 */

import { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/hooks/use-toast";
import { Terminal, Settings2, AlertTriangle, Loader2, Check, ChevronDown, RefreshCw } from "lucide-react";
import { ConfirmWriteDialog } from "../shared/ConfirmWriteDialog";

const ACCENT = "#A855F7";

// ============================================================
// Voltronic command schema (embedded — mirrors Python schema)
// ============================================================

interface VoltronicField {
  key: string;
  label: string;
  cmdCode: string; // e.g. "POP", "MCHGC"
  type: "number" | "enum" | "bool";
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: Record<string, string>;
  description?: string;
  destructive?: boolean;
  /** For bool: enable command → disableCommand pair */
  enableCmd?: string;
  disableCmd?: string;
}

interface VoltronicGroup {
  id: string;
  label: string;
  fields: VoltronicField[];
}

const VOLTRONIC_SCHEMA: VoltronicGroup[] = [
  {
    id: "output",
    label: "Output",
    fields: [
      {
        key: "output_priority", label: "Output Source Priority", cmdCode: "POP",
        type: "enum",
        options: { utility: "Utility First", solar: "Solar First", sbu: "Solar → Battery → Utility" },
        description: "Determines which source powers the output",
      },
      {
        key: "output_mode", label: "Output Mode", cmdCode: "POPM",
        type: "enum",
        options: { single: "Single unit", parallel: "Parallel", phase_1_3: "Phase 1/3", phase_2_3: "Phase 2/3", phase_3_3: "Phase 3/3" },
      },
    ],
  },
  {
    id: "charger",
    label: "Charger",
    fields: [
      {
        key: "charger_priority", label: "Charger Source Priority", cmdCode: "PCP",
        type: "enum",
        options: { utility: "Utility First", solar: "Solar First", solar_utility: "Solar + Utility", solar_only: "Solar Only" },
      },
      {
        key: "max_charging_current", label: "Max Total Charging Current", cmdCode: "MCHGC",
        type: "number", unit: "A", min: 10, max: 120, step: 1,
      },
      {
        key: "max_ac_charging_current", label: "Max AC (Grid) Charging Current", cmdCode: "MUCHGC",
        type: "number", unit: "A", min: 2, max: 100, step: 1,
      },
    ],
  },
  {
    id: "battery",
    label: "Battery",
    fields: [
      {
        key: "battery_type", label: "Battery Type", cmdCode: "PBATCD",
        type: "enum",
        options: { agm: "AGM", flooded: "Flooded / Wet", user: "User-defined" },
        destructive: true,
        description: "Changing battery type resets voltage thresholds.",
      },
      {
        key: "bulk_voltage", label: "Bulk Charge Voltage", cmdCode: "PBCV",
        type: "number", unit: "V", min: 20, max: 62, step: 0.1,
      },
      {
        key: "float_voltage", label: "Float Charge Voltage", cmdCode: "PBDV",
        type: "number", unit: "V", min: 20, max: 62, step: 0.1,
      },
      {
        key: "low_voltage_cutoff", label: "Low Voltage Cutoff", cmdCode: "PSDV",
        type: "number", unit: "V", min: 20, max: 50, step: 0.1,
        description: "Battery voltage below which output disconnects",
      },
      {
        key: "recharge_voltage", label: "Re-charge Trigger Voltage", cmdCode: "PBCVV",
        type: "number", unit: "V", min: 20, max: 58, step: 0.1,
      },
    ],
  },
  {
    id: "grid",
    label: "Grid",
    fields: [
      {
        key: "input_voltage_range", label: "AC Input Voltage Range", cmdCode: "PGR",
        type: "enum",
        options: { appliance: "Appliance (wide range)", ups: "UPS (narrow range)" },
        description: "Narrow range rejects brownouts; wide range tolerates voltage sag",
      },
      {
        key: "grid_max_charging_current", label: "Grid Max Charging Current", cmdCode: "MUCHGC",
        type: "number", unit: "A", min: 2, max: 100, step: 1,
      },
    ],
  },
  {
    id: "system",
    label: "System",
    fields: [
      {
        key: "buzzer", label: "Buzzer", cmdCode: "PE/PD",
        type: "bool", enableCmd: "enable_buzzer", disableCmd: "disable_buzzer",
        description: "Enable/disable audible alarm",
      },
      {
        key: "overload_bypass", label: "Overload Bypass", cmdCode: "PE/PD",
        type: "bool", enableCmd: "enable_overload_bypass", disableCmd: "disable_overload_bypass",
        description: "Pass load through when inverter is overloaded",
      },
      {
        key: "solar_feed_to_grid", label: "Solar Feed-to-Grid", cmdCode: "PE/PD",
        type: "bool", enableCmd: "enable_solar_feed_to_grid", disableCmd: "disable_solar_feed_to_grid",
        description: "Allow surplus solar to export to utility",
      },
      {
        key: "lcd_backlight", label: "LCD Backlight Always On", cmdCode: "PE/PD",
        type: "bool", enableCmd: "enable_lcd_backlight", disableCmd: "disable_lcd_backlight_timeout",
      },
      {
        key: "factory_defaults", label: "Restore Factory Defaults", cmdCode: "PF",
        type: "bool",
        destructive: true,
        description: "WARNING: Resets ALL settings to factory defaults. Cannot be undone.",
      },
    ],
  },
];

// ============================================================
// Command log entry
// ============================================================

interface LogEntry {
  id: string;
  timestamp: Date;
  cmdCode: string;
  value: string;
  result: "ack" | "nak" | "pending";
  error?: string;
}

// ============================================================
// Single Command Card
// ============================================================

interface CommandCardProps {
  field: VoltronicField;
  currentValue: string | undefined;
  deviceSerial: string;
  onSend: (field: VoltronicField, value: string) => Promise<{ success: boolean; error?: string }>;
  onLogEntry: (entry: Omit<LogEntry, "id" | "timestamp">) => void;
}

const CommandCard = ({ field, currentValue, deviceSerial, onSend, onLogEntry }: CommandCardProps) => {
  const [editValue, setEditValue] = useState<string>(currentValue ?? "");
  const [isDirty, setIsDirty] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [lastResult, setLastResult] = useState<"ack" | "nak" | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleChange = (v: string) => {
    setEditValue(v);
    setIsDirty(v !== (currentValue ?? ""));
    setLastResult(null);
    setLastError(null);
  };

  const doSend = async () => {
    setIsSending(true);
    setLastResult(null);
    setLastError(null);
    try {
      const result = await onSend(field, editValue);
      const outcome = result.success ? "ack" : "nak";
      setLastResult(outcome);
      if (!result.success) setLastError(result.error ?? "NAK received from device");
      onLogEntry({ cmdCode: field.cmdCode, value: editValue, result: outcome, error: result.error });
      if (result.success) {
        setIsDirty(false);
        toast({ title: "Command sent", description: `${field.label} → ${editValue}` });
      } else {
        toast({ title: "Command rejected", description: result.error ?? "Device returned NAK", variant: "destructive" });
      }
    } catch (e: any) {
      setLastResult("nak");
      setLastError(e?.message ?? "Unknown error");
      onLogEntry({ cmdCode: field.cmdCode, value: editValue, result: "nak", error: e?.message });
    } finally {
      setIsSending(false);
    }
  };

  const handleApplyClick = () => {
    if (!isDirty) return;
    if (field.destructive) {
      setConfirmOpen(true);
    } else {
      doSend();
    }
  };

  return (
    <>
      <div className={cn(
        "glass-card p-4 rounded-xl space-y-3",
        lastResult === "ack" && "ring-1 ring-success/40",
        lastResult === "nak" && "ring-1 ring-destructive/40",
      )}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-secondary/60 text-muted-foreground">
                {field.cmdCode}
              </span>
              <p className="text-sm font-semibold text-foreground">{field.label}</p>
              {field.destructive && <AlertTriangle className="w-3.5 h-3.5 text-warning" />}
            </div>
            {field.description && (
              <p className="text-xs text-muted-foreground mt-0.5">{field.description}</p>
            )}
          </div>
          {lastResult === "ack" && <Check className="w-4 h-4 text-success flex-shrink-0" />}
          {lastResult === "nak" && <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0" />}
        </div>

        {/* Control */}
        {field.type === "bool" ? (
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">{editValue === "true" ? "Enabled" : "Disabled"}</span>
            <Switch
              checked={editValue === "true"}
              onCheckedChange={(c) => handleChange(String(c))}
            />
          </div>
        ) : field.type === "enum" && field.options ? (
          <Select value={editValue} onValueChange={handleChange}>
            <SelectTrigger className="bg-secondary/30">
              <SelectValue placeholder="Select…" />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(field.options).map(([v, lbl]) => (
                <SelectItem key={v} value={v}>{lbl}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <div className="flex items-center gap-2">
            <Input
              type="number"
              value={editValue}
              min={field.min}
              max={field.max}
              step={field.step}
              onChange={(e) => handleChange(e.target.value)}
              className="w-28 font-mono bg-secondary/30 text-right"
            />
            {field.unit && <span className="text-sm text-muted-foreground">{field.unit}</span>}
          </div>
        )}

        {/* NAK error */}
        {lastResult === "nak" && lastError && (
          <p className="text-xs text-destructive">{lastError}</p>
        )}

        {/* Apply */}
        <Button
          size="sm"
          onClick={handleApplyClick}
          disabled={!isDirty || isSending}
          className={cn(
            "w-full gap-2",
            lastResult === "ack" && "bg-success text-success-foreground hover:bg-success/90",
            lastResult === "nak" && "bg-destructive/80"
          )}
          style={isDirty && lastResult === null ? { backgroundColor: ACCENT } : undefined}
        >
          {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          {isSending ? "Sending…" : lastResult === "ack" ? "Sent ✓" : "Apply"}
        </Button>
      </div>

      <ConfirmWriteDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        deviceSerial={deviceSerial}
        fieldLabel={field.label}
        oldValue={currentValue ?? "—"}
        newValue={editValue}
        onConfirm={doSend}
      />
    </>
  );
};

// ============================================================
// Main page
// ============================================================

interface VoltronicSettingsPageProps {
  deviceId: string;
  deviceName: string;
  deviceSerial: string;
  protocolVariant?: string; // "PI30" | "PI18" | ...
  firmwareVersion?: string;
  settings: Record<string, any>;
  onSendCommand: (commandKey: string, value: string | number | boolean) => Promise<{ success: boolean; error?: string }>;
  onRefreshAll: () => Promise<void>;
  isRefreshing?: boolean;
}

export const VoltronicSettingsPage = ({
  deviceSerial,
  protocolVariant = "PI30",
  firmwareVersion,
  settings,
  onSendCommand,
  onRefreshAll,
  isRefreshing = false,
}: VoltronicSettingsPageProps) => {
  const [commandLog, setCommandLog] = useState<LogEntry[]>([]);
  const [logOpen, setLogOpen] = useState(false);
  const logIdRef = useRef(0);

  const addLogEntry = useCallback((entry: Omit<LogEntry, "id" | "timestamp">) => {
    setCommandLog((prev) => [
      { ...entry, id: String(logIdRef.current++), timestamp: new Date() },
      ...prev.slice(0, 19), // keep last 20
    ]);
  }, []);

  const handleSend = useCallback(
    async (field: VoltronicField, value: string) => {
      const cmdKey = field.type === "bool"
        ? value === "true"
          ? field.enableCmd ?? field.key
          : field.disableCmd ?? field.key
        : `set_${field.key}`;
      return onSendCommand(cmdKey, value);
    },
    [onSendCommand]
  );

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs px-2 py-0.5 rounded-full border text-muted-foreground" style={{ borderColor: ACCENT, color: ACCENT }}>
            {protocolVariant}
          </span>
          {firmwareVersion && <span className="text-xs text-muted-foreground">FW {firmwareVersion}</span>}
          <span className="text-xs text-muted-foreground">{deviceSerial}</span>
        </div>
        <Button size="sm" variant="outline" onClick={onRefreshAll} disabled={isRefreshing} className="gap-2">
          <RefreshCw className={cn("w-4 h-4", isRefreshing && "animate-spin")} />
          Refresh all
        </Button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue={VOLTRONIC_SCHEMA[0].id}>
        <TabsList className="flex-wrap h-auto gap-1">
          {VOLTRONIC_SCHEMA.map((group) => (
            <TabsTrigger key={group.id} value={group.id}>{group.label}</TabsTrigger>
          ))}
        </TabsList>

        {VOLTRONIC_SCHEMA.map((group) => (
          <TabsContent key={group.id} value={group.id} className="mt-4">
            <div className="space-y-3">
              {group.fields.map((field) => (
                <CommandCard
                  key={field.key}
                  field={field}
                  currentValue={settings[field.key] !== undefined ? String(settings[field.key]) : undefined}
                  deviceSerial={deviceSerial}
                  onSend={handleSend}
                  onLogEntry={addLogEntry}
                />
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>

      {/* Command log */}
      <div className="glass-card rounded-xl overflow-hidden">
        <button
          onClick={() => setLogOpen((v) => !v)}
          className="flex items-center justify-between w-full px-4 py-3 text-sm font-medium text-foreground hover:bg-secondary/20 transition-colors"
        >
          <span className="flex items-center gap-2">
            <Terminal className="w-4 h-4" style={{ color: ACCENT }} />
            Command Log ({commandLog.length})
          </span>
          <ChevronDown className={cn("w-4 h-4 transition-transform", logOpen && "rotate-180")} />
        </button>

        <AnimatePresence>
          {logOpen && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: "auto" }}
              exit={{ height: 0 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-3 space-y-1 max-h-48 overflow-y-auto">
                {commandLog.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No commands sent yet.</p>
                ) : (
                  commandLog.map((entry) => (
                    <div key={entry.id} className="flex items-center gap-2 text-xs font-mono">
                      <span className="text-muted-foreground w-16 flex-shrink-0">
                        {entry.timestamp.toLocaleTimeString()}
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-secondary/60">{entry.cmdCode}</span>
                      <span className="text-foreground">{entry.value}</span>
                      <span className={cn(
                        "ml-auto px-1.5 py-0.5 rounded text-xs",
                        entry.result === "ack" && "bg-success/20 text-success",
                        entry.result === "nak" && "bg-destructive/20 text-destructive",
                        entry.result === "pending" && "bg-secondary/40 text-muted-foreground"
                      )}>
                        {entry.result.toUpperCase()}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
