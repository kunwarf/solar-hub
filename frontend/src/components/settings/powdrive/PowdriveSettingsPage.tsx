/**
 * PowdriveSettingsPage
 *
 * Settings page for Powdrive / Deye hybrid inverters.
 * Layout: collapsible left sidebar (groups) + right pane (field cards).
 * Uses the shared SettingsSection/SettingField primitives.
 *
 * Accent color: #10B981 (solar green — matches existing dashboard palette)
 */

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import {
  Battery, Zap, Plug, Shield, Calendar, Settings2, Sun, Check, RefreshCw
} from "lucide-react";
import { SettingsSection } from "../shared/SettingsSection";
import { POWDRIVE_SCHEMA } from "./schema";
import { PowdriveTouSchedule } from "./PowdriveTouSchedule";

const ACCENT = "#10B981";

const GROUP_ICONS: Record<string, React.ElementType> = {
  battery: Battery,
  charger: Zap,
  grid: Plug,
  inverter: Settings2,
  generator: Sun,
  schedule: Calendar,
  protection: Shield,
};

interface PowdriveSettingsPageProps {
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

export const PowdriveSettingsPage = ({
  deviceName,
  deviceSerial,
  firmwareVersion,
  settings,
  lastSyncedAt,
  onApply,
  onRefresh,
  isRefreshing = false,
}: PowdriveSettingsPageProps) => {
  const [activeGroup, setActiveGroup] = useState(POWDRIVE_SCHEMA[0].id);
  const [pendingChanges, setPendingChanges] = useState<Record<string, string | number | boolean>>({});

  const currentGroup = POWDRIVE_SCHEMA.find((g) => g.id === activeGroup) ?? POWDRIVE_SCHEMA[0];

  const handleFieldApply = useCallback(
    async (key: string, rawValue: string | number | boolean) => {
      const change = { [key]: rawValue };
      try {
        await onApply(change);
        toast({ title: "Setting saved", description: `${key} updated successfully.` });
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
      toast({ title: "All changes saved", description: `${Object.keys(pendingChanges).length} setting(s) updated.` });
    } catch {
      toast({ title: "Save failed", description: "Some settings could not be applied.", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            {deviceSerial}
            {firmwareVersion && <span className="ml-2 text-xs">• FW {firmwareVersion}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
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

      <div className="flex flex-col md:flex-row gap-3 md:gap-4">
        {/* Sidebar */}
        <nav className="hidden md:flex flex-col gap-1 w-44 flex-shrink-0">
          {POWDRIVE_SCHEMA.map((group) => {
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

        {/* Mobile group selector */}
        <div className="flex md:hidden gap-1 overflow-x-auto pb-2 w-full">
          {POWDRIVE_SCHEMA.map((group) => (
            <button
              key={group.id}
              onClick={() => setActiveGroup(group.id)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all",
                activeGroup === group.id
                  ? "bg-primary/10 text-foreground"
                  : "text-muted-foreground bg-secondary/20"
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
          {currentGroup.id === "schedule" ? (
            // Specialised row-per-program TOU editor.
            <PowdriveTouSchedule
              settings={settings}
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
