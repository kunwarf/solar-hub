/**
 * SettingField
 *
 * Renders a single writable setting with the appropriate control:
 *  - "number"  → NumberInput + optional Slider (when min/max known)
 *  - "enum"    → Select
 *  - "bool"    → Switch
 *
 * Shows an inline Apply button that activates only when the value is dirty.
 * If the field is destructive, Apply opens the ConfirmWriteDialog.
 */

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
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
import { Button } from "@/components/ui/button";
import { AlertTriangle, Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { ConfirmWriteDialog } from "./ConfirmWriteDialog";
import type { SettingField as SettingFieldType } from "./types";

interface SettingFieldProps {
  field: SettingFieldType;
  /** Current raw value from device (before scale) */
  rawValue: string | number | boolean | undefined;
  deviceSerial: string;
  /** Called when user confirms Apply. Receives the new raw value. */
  onApply: (key: string, rawValue: string | number | boolean) => Promise<void>;
  /** Last synced timestamp (ISO string) */
  lastSyncedAt?: string | null;
  /** Override accent color (CSS color string) */
  accentColor?: string;
}

export const SettingFieldCard = ({
  field,
  rawValue,
  deviceSerial,
  onApply,
  lastSyncedAt,
  accentColor = "hsl(var(--primary))",
}: SettingFieldProps) => {
  const { key, label, type, unit, min, max, step = 1, scale = 1, options, description, writable = true, destructive = false } = field;

  // Display value is rawValue * scale for numbers
  const toDisplay = useCallback(
    (raw: string | number | boolean | undefined): string => {
      if (raw === undefined || raw === null) return "";
      if (type === "number") return String(Number(raw) * scale);
      return String(raw);
    },
    [type, scale]
  );

  const toRaw = useCallback(
    (display: string): number => {
      return Number(display) / scale;
    },
    [scale]
  );

  const [displayValue, setDisplayValue] = useState<string>(toDisplay(rawValue));
  const [isDirty, setIsDirty] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [appliedOk, setAppliedOk] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleChange = (newDisplay: string) => {
    setDisplayValue(newDisplay);
    setIsDirty(newDisplay !== toDisplay(rawValue));
    setAppliedOk(false);
  };

  const doApply = async () => {
    const newRaw = type === "number"
      ? toRaw(displayValue)
      : type === "bool"
      ? displayValue === "true"
      : displayValue;

    setIsApplying(true);
    try {
      await onApply(key, newRaw);
      setIsDirty(false);
      setAppliedOk(true);
      setTimeout(() => setAppliedOk(false), 2000);
    } finally {
      setIsApplying(false);
    }
  };

  const handleApplyClick = () => {
    if (!isDirty) return;
    if (destructive) {
      setConfirmOpen(true);
    } else {
      doApply();
    }
  };

  const syncLabel = lastSyncedAt
    ? `Synced ${new Date(lastSyncedAt).toLocaleTimeString()}`
    : "Not synced";

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn(
          "glass-card p-4 rounded-xl space-y-3 transition-all",
          isDirty && "ring-1 ring-warning/40",
          appliedOk && "ring-1 ring-success/40"
        )}
      >
        {/* Header row — stacks on narrow phones so the sync-time label
            doesn't eat horizontal space next to a long field name. */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <p className="text-sm font-semibold text-foreground truncate">{label}</p>
              {destructive && (
                <AlertTriangle className="w-3.5 h-3.5 text-warning flex-shrink-0" />
              )}
            </div>
            {description && (
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{description}</p>
            )}
          </div>
          <p className="text-[10px] sm:text-xs text-muted-foreground whitespace-nowrap flex-shrink-0">{syncLabel}</p>
        </div>

        {/* Control */}
        {!writable ? (
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm" style={{ color: accentColor }}>
              {toDisplay(rawValue)} {unit}
            </span>
            <span className="text-xs text-muted-foreground">(read-only)</span>
          </div>
        ) : type === "bool" ? (
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {displayValue === "true" ? "Enabled" : "Disabled"}
            </span>
            <Switch
              checked={displayValue === "true"}
              onCheckedChange={(checked) => handleChange(String(checked))}
            />
          </div>
        ) : type === "enum" && options ? (
          <Select value={displayValue} onValueChange={handleChange}>
            <SelectTrigger className="bg-secondary/30">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(options).map(([value, optLabel]) => (
                <SelectItem key={value} value={value}>
                  {optLabel}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          /* number */
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Input
                type="number"
                inputMode="decimal"
                value={displayValue}
                min={min !== undefined ? min * scale : undefined}
                max={max !== undefined ? max * scale : undefined}
                step={step * scale}
                onChange={(e) => handleChange(e.target.value)}
                className="flex-1 sm:flex-none sm:w-28 font-mono bg-secondary/30 text-right"
              />
              {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
              {scale !== 1 && (
                <span className="text-xs text-muted-foreground/60">×{1/scale}</span>
              )}
            </div>
            {min !== undefined && max !== undefined && (
              <Slider
                value={[Number(displayValue)]}
                min={min * scale}
                max={max * scale}
                step={step * scale}
                onValueChange={([v]) => handleChange(String(v))}
                className="w-full"
              />
            )}
          </div>
        )}

        {/* Apply button */}
        <AnimatePresence>
          {writable && (isDirty || appliedOk) && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <Button
                size="sm"
                onClick={handleApplyClick}
                disabled={!isDirty || isApplying}
                className={cn(
                  "w-full gap-2 transition-all",
                  appliedOk && "bg-success text-success-foreground hover:bg-success/90"
                )}
              >
                {isApplying ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : appliedOk ? (
                  <Check className="w-4 h-4" />
                ) : destructive ? (
                  <AlertTriangle className="w-4 h-4 text-warning" />
                ) : null}
                {isApplying ? "Applying…" : appliedOk ? "Applied" : "Apply"}
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Destructive confirm dialog */}
      <ConfirmWriteDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        deviceSerial={deviceSerial}
        fieldLabel={label}
        oldValue={toDisplay(rawValue)}
        newValue={displayValue}
        onConfirm={doApply}
      />
    </>
  );
};
