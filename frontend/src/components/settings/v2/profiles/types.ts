/**
 * Type shapes for the v2 settings profile system.
 *
 * A "profile" is a per-family blueprint that says: which sections are on the
 * home page, which are in the hub, what fields each section contains, and
 * (for sliders) which zones are safe/warn/danger.  All UI components read
 * from these profiles — adding a new inverter family means adding one file
 * under ./profiles/, no component changes.
 *
 * Modeled after D:\Downloads\solar-inverter-settings.html DEVICE_PROFILES.
 */
import type { ComponentType, ReactNode } from "react";

/** Slider colored-zone segment.  Values are inclusive of `from`, exclusive of `to`. */
export interface Zone {
  from: number;
  to: number;
  /** Hex color like "#10b981" (green), "#f59e0b" (amber), "#f43f5e" (red). */
  color: string;
}

/** Bind a field's minimum to another field's value (+ offset).  Used for
 *  cross-slider constraints like "restart must be > shutdown + 5%". */
export interface MinFrom {
  key: string;
  offset?: number;
}

/** Field displayed as a range control inside a slider card. */
export interface SliderField {
  key: string;
  label: string;
  type?: "toggle" | "slider";
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  zones?: Zone[];
  minFrom?: MinFrom;
  formatValue?: (v: number) => string;
  /** If true, render even when the section's gating toggle is off. */
  alwaysVisible?: boolean;
  reg?: string;
}

/** Field displayed as a flat row inside a fields card. */
export interface FlatField {
  key: string;
  label: string;
  type: "number" | "select" | "toggle" | "time";
  unit?: string;
  step?: number;
  options?: string[];
  destructive?: boolean;
  reg?: string;
  /** Visible only when another field has this value. */
  showIf?: { key: string; equals: string | number | boolean };
  /** Optional per-field help text.  Populated from settings_schema.py's
   *  `description` when the profile is derived from the backend schema. */
  description?: string;
}

/** Field inside a TOU schedule window (repeats N times per section). */
export interface WindowField {
  key: string;
  label: string;
  type: "time" | "number" | "checkbox";
  unit?: string;
  step?: number;
  reg?: string;
}

/** One TOU window's saved values.  Shape mirrors WindowField `key`s. */
export type ScheduleWindow = Record<string, string | number | boolean>;

/** Strategy option in the Energy Strategy home card. */
export interface StrategyOption {
  id: string;
  label: string;
  /** Lucide icon component. */
  icon: ComponentType<{ className?: string }>;
  blurb: string;
}

/** A settings section — the atomic unit of the whole system.  Every
 *  section is a top-level key on the draft/saved state and has its own
 *  Apply/Reset/dirty flag. */
export type Section =
  | {
      kind: "slider";
      icon: ReactNode;
      title: string;
      description: string;
      tier?: "default" | "installer";
      fields: SliderField[];
      preview?: (values: Record<string, any>) => string;
    }
  | {
      kind: "fields";
      icon: ReactNode;
      title: string;
      description: string;
      tier?: "default" | "installer";
      fields: FlatField[];
      preview?: (values: Record<string, any>) => string;
    }
  | {
      kind: "schedule";
      icon: ReactNode;
      title: string;
      description: string;
      tier?: "default" | "installer";
      windowCount: number;
      toggleField: FlatField;
      windowFields: WindowField[];
      preview?: (values: { touEnabled: boolean; windows: ScheduleWindow[] }) => string;
    };

/** Per-family profile.  One file under ./profiles/ per family. */
export interface DeviceProfile {
  /** Matches device.protocol (e.g. "senergy", "powdrive", "voltronic_pi30"). */
  id: string;
  /** Marketing name shown in the header. */
  name: string;
  /** Optional rating chip next to the name. */
  ratingLabel?: string;
  /** Optional grounding note surfaced above the home grid — tells the
   *  user which vendor doc the register mapping was built from. */
  sourceNote?: string;
  /** Strategy options for the special "strategy" home card. */
  strategies: StrategyOption[];
  /** Per-strategy plain-language preview line. */
  strategyPreview: Record<string, string>;
  /** All defined sections, keyed by section id. */
  sections: Record<string, Section>;
  /** Which sections appear as full-width task cards on the home screen,
   *  in order.  "strategy" is a synthetic id that renders the strategy
   *  radio card. */
  homeCardIds: string[];
  /** Which home cards should span the full grid width (long cards). */
  spanCardIds?: string[];
  /** Which sections are browsable from the All-Settings hub. */
  hubGroupIds: string[];
  /** Initial values for every section (mirrors saved-state shape). */
  defaults: Record<string, any>;
}

/** Screen-router state.  "home" | "hub" | <sectionId>. */
export type ScreenId = "home" | "hub" | string;
