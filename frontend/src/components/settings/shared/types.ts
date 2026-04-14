/**
 * Shared types for the per-family inverter settings pages.
 *
 * These mirror the Python schema defined in
 * system_b/device_server/settings_schema.py  so that frontend pages can
 * render the correct controls from the schema without an extra API call
 * (schemas are embedded per-family page as static TypeScript constants).
 */

export type FieldType = "number" | "enum" | "bool";

export interface SettingField {
  key: string;
  label: string;
  type: FieldType;
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  /** Multiplier stored value → display value.  Write sends value / scale. */
  scale?: number;
  /** For enum fields: { rawValue: displayLabel } */
  options?: Record<string, string>;
  description?: string;
  /** Whether the user can write this field */
  writable?: boolean;
  /** If true, Apply opens a serial-confirmation dialog */
  destructive?: boolean;
}

export interface SettingGroup {
  id: string;
  label: string;
  /** Optional contextual note displayed at the top of the group */
  sign_note?: string;
  fields: SettingField[];
}

/** A flat change set: register_key → new raw value */
export type DirtyFields = Record<string, string | number | boolean>;
