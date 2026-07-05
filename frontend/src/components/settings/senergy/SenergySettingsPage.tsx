/**
 * SenergySettingsPage
 *
 * Settings page for Senergy hybrid inverters.
 * Key differences from Powdrive:
 *  - Some voltage registers use scale 0.1 (stored as tenths of volts)
 *  - Battery sign convention: positive = discharging — shown as an info banner
 *  - Always-visible Work Mode quick-switcher in the top bar
 *
 * Accent color: #3B82F6 (blue)
 */

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/hooks/use-toast";
import { BatteryCharging, Globe2, Sun, Shield, Settings2, Check, RefreshCw, Loader2 } from "lucide-react";
import { SettingsSection } from "../shared/SettingsSection";
import { SENERGY_SCHEMA } from "./schema";
import { SenergyTouSchedule } from "./SenergyTouSchedule";

const ACCENT = "#3B82F6";

const GROUP_ICONS: Record<string, React.ElementType> = {
  battery: BatteryCharging,
  grid_code: Globe2,
  charger: Sun,
  work_mode: Settings2,
  protection: Shield,
};

const WORK_MODE_OPTIONS: Record<string, string> = {
  "0": "Self-Consumption",
  "1": "Backup Priority",
  "2": "Feed-in Priority",
  "3": "Time-of-Use",
};

interface SenergySettingsPageProps {
  deviceId: string;
  deviceName: string;
  deviceSerial: string;
  firmwareVersion?: string;
  settings: Record<string, any>;
  lastSyncedAt?: string | null;
  onApply: (changes: Record<string, string | number | boolean>) => Promise<void>;
  onRefresh: () => Promise<void>;
  isRefreshing?: boolean;
}

export const SenergySettingsPage = ({
  deviceSerial,
  firmwareVersion,
  settings,
  lastSyncedAt,
  onApply,
  onRefresh,
  isRefreshing = false,
}: SenergySettingsPageProps) => {
  const [activeGroup, setActiveGroup] = useState(SENERGY_SCHEMA[0].id);
  const [pendingChanges, setPendingChanges] = useState<Record<string, string | number | boolean>>({});
  const [workModeApplying, setWorkModeApplying] = useState(false);
  const [workModeOk, setWorkModeOk] = useState(false);

  const currentGroup = SENERGY_SCHEMA.find((g) => g.id === activeGroup) ?? SENERGY_SCHEMA[0];

  const handleFieldApply = useCallback(
    async (key: string, rawValue: string | number | boolean) => {
      const change = { [key]: rawValue };
      try {
        await onApply(change);

        // If we just applied grid_code, show a restart warning
        if (key === "grid_standard") {
          toast({
            title: "Grid code changed",
            description: "The inverter may restart to apply the new grid standard.",
          });
        } else {
          toast({ title: "Setting saved", description: `${key} updated successfully.` });
        }
      } catch {
        toast({ title: "Failed to save", description: `Could not update ${key}.`, variant: "destructive" });
        throw new Error("Apply failed");
      }
    },
    [onApply]
  );

  const handleApplyAll = async () => {
    if (Object.keys(pendingChanges).length === 0) return;
    try {
      await onApply(pendingChanges);
      setPendingChanges({});
      toast({ title: "All changes saved" });
    } catch {
      toast({ title: "Save failed", variant: "destructive" });
    }
  };

  const handleWorkModeChange = async (mode: string) => {
    setWorkModeApplying(true);
    setWorkModeOk(false);
    try {
      await onApply({ work_mode: mode });
      setWorkModeOk(true);
      setTimeout(() => setWorkModeOk(false), 2000);
      toast({ title: "Work mode updated", description: WORK_MODE_OPTIONS[mode] });
    } catch {
      toast({ title: "Failed to change work mode", variant: "destructive" });
    } finally {
      setWorkModeApplying(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top bar — inner rows wrap so Work Mode + FW + serial don't overflow narrow phones. */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 w-full sm:w-auto">
          {/* Work mode quick-switcher */}
          <div className="flex items-center gap-2 flex-1 sm:flex-none min-w-0">
            <span className="text-xs text-muted-foreground whitespace-nowrap">Work Mode</span>
            <Select
              value={settings.work_mode !== undefined ? String(settings.work_mode) : undefined}
              onValueChange={handleWorkModeChange}
              disabled={workModeApplying}
            >
              <SelectTrigger className="flex-1 sm:flex-none sm:w-40 h-8 text-xs" style={{ borderColor: ACCENT }}>
                {workModeApplying ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : workModeOk ? (
                  <Check className="w-3 h-3 text-success" />
                ) : (
                  <SelectValue placeholder="Select…" />
                )}
              </SelectTrigger>
              <SelectContent>
                {Object.entries(WORK_MODE_OPTIONS).map(([v, lbl]) => (
                  <SelectItem key={v} value={v}>{lbl}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {firmwareVersion && <span className="text-xs text-muted-foreground">FW {firmwareVersion}</span>}
          <span className="text-xs text-muted-foreground truncate">{deviceSerial}</span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {Object.keys(pendingChanges).length > 0 && (
            <Button size="sm" onClick={handleApplyAll} style={{ backgroundColor: ACCENT }} className="gap-2">
              <Check className="w-4 h-4" />
              Apply all ({Object.keys(pendingChanges).length})
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={onRefresh} disabled={isRefreshing} className="gap-2">
            <RefreshCw className={cn("w-4 h-4", isRefreshing && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="flex gap-4">
        {/* Sidebar */}
        <nav className="hidden md:flex flex-col gap-1 w-44 flex-shrink-0">
          {SENERGY_SCHEMA.map((group) => {
            const Icon = GROUP_ICONS[group.id] ?? Settings2;
            return (
              <button
                key={group.id}
                onClick={() => setActiveGroup(group.id)}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all text-left",
                  activeGroup === group.id
                    ? "bg-primary/10 text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/40"
                )}
              >
                <Icon className="w-4 h-4 flex-shrink-0" style={{ color: activeGroup === group.id ? ACCENT : undefined }} />
                {group.label}
              </button>
            );
          })}
        </nav>

        {/* Mobile tab bar */}
        <div className="flex md:hidden gap-1 overflow-x-auto pb-2 w-full">
          {SENERGY_SCHEMA.map((group) => (
            <button
              key={group.id}
              onClick={() => setActiveGroup(group.id)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all",
                activeGroup === group.id ? "bg-primary/10 text-foreground" : "text-muted-foreground bg-secondary/20"
              )}
            >
              {group.label}
            </button>
          ))}
        </div>

        {/* Settings pane */}
        <motion.div
          key={activeGroup}
          initial={{ opacity: 0, x: 10 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex-1 min-w-0"
        >
          {/* Grid code restart warning */}
          {activeGroup === "grid_code" && (
            <div className="mb-4 px-3 py-2 rounded-xl bg-warning/10 border border-warning/30 text-xs text-warning">
              Changing the Grid Code may cause the inverter to restart. Only modify if required by local regulations.
            </div>
          )}

          {currentGroup.id === "tou_charge" ? (
            <SenergyTouSchedule
              settings={settings}
              direction="charge"
              lastSyncedAt={lastSyncedAt}
              onApplyBulk={onApply}
            />
          ) : currentGroup.id === "tou_discharge" ? (
            <SenergyTouSchedule
              settings={settings}
              direction="discharge"
              lastSyncedAt={lastSyncedAt}
              onApplyBulk={onApply}
            />
          ) : (
            <>
              <h3 className="text-base font-semibold text-foreground mb-4">
                {currentGroup.label}
              </h3>
              <SettingsSection
                group={currentGroup}
                settings={settings}
                deviceSerial={deviceSerial}
                lastSyncedAt={lastSyncedAt}
                accentColor={ACCENT}
                onApply={handleFieldApply}
              />
            </>
          )}
        </motion.div>
      </div>
    </div>
  );
};
