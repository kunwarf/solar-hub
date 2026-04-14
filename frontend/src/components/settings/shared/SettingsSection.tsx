/**
 * SettingsSection
 *
 * Renders a labelled group of SettingFieldCards in a responsive grid.
 * Shows an optional contextual note (e.g. battery sign convention for Senergy).
 */

import { Info } from "lucide-react";
import { SettingFieldCard } from "./SettingField";
import type { SettingGroup, DirtyFields } from "./types";

interface SettingsSectionProps {
  group: SettingGroup;
  settings: Record<string, any>;
  deviceSerial: string;
  lastSyncedAt?: string | null;
  accentColor?: string;
  onApply: (key: string, rawValue: string | number | boolean) => Promise<void>;
  dirtyFields?: DirtyFields;
}

export const SettingsSection = ({
  group,
  settings,
  deviceSerial,
  lastSyncedAt,
  accentColor,
  onApply,
}: SettingsSectionProps) => {
  return (
    <div className="space-y-4">
      {/* Sign-convention note */}
      {group.sign_note && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-primary/5 border border-primary/20">
          <Info className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
          <p className="text-xs text-muted-foreground">{group.sign_note}</p>
        </div>
      )}

      {/* Field grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {group.fields.map((field) => (
          <SettingFieldCard
            key={field.key}
            field={field}
            rawValue={settings[field.key]}
            deviceSerial={deviceSerial}
            onApply={onApply}
            lastSyncedAt={lastSyncedAt}
            accentColor={accentColor}
          />
        ))}
      </div>
    </div>
  );
};
