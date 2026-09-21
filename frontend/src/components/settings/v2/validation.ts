/**
 * Per-section cross-field invariant checks.
 *
 * Returns human-readable warning strings that render inline under the
 * offending slider or at the top of the section.  Empty array = clean.
 *
 * Rules live here (not inside sections) so they're testable in isolation
 * and can be shared across families where the invariant is universal
 * (e.g. "restart SOC > shutdown SOC + 5%").
 */

export interface CrossFieldWarning {
  /** Which field key the warning attaches to (for inline placement) or
   *  null to render as a section-top summary line. */
  key: string | null;
  message: string;
}

/** Check reserve card: restart > shutdown + 5%, priority_load >= shutdown. */
export function checkReserve(values: {
  battery_shutdown_capacity_pct?: number;
  battery_restart_capacity_pct?: number;
  priority_load_soc_pct?: number;
}): CrossFieldWarning[] {
  const out: CrossFieldWarning[] = [];
  const shutdown = values.battery_shutdown_capacity_pct;
  const restart = values.battery_restart_capacity_pct;
  const priority = values.priority_load_soc_pct;
  if (shutdown != null && restart != null && restart < shutdown + 5) {
    out.push({
      key: "battery_restart_capacity_pct",
      message: `Restart SOC should be at least 5% above shutdown SOC (${shutdown}%). Setting it lower can cause charge/discharge chattering.`,
    });
  }
  if (priority != null && shutdown != null && priority < shutdown) {
    out.push({
      key: "priority_load_soc_pct",
      message: `Priority-load SOC (${priority}%) is below shutdown SOC (${shutdown}%). Priority load won't have a fallback.`,
    });
  }
  return out;
}

/** Check grid charging card: end SOC > start SOC. */
export function checkGridCharging(values: {
  ac_charge_start_soc_pct?: number;
  ac_charge_end_soc_pct?: number;
}): CrossFieldWarning[] {
  const out: CrossFieldWarning[] = [];
  const start = values.ac_charge_start_soc_pct;
  const end = values.ac_charge_end_soc_pct;
  if (start != null && end != null && end <= start) {
    out.push({
      key: "ac_charge_end_soc_pct",
      message: `End SOC (${end}%) must be higher than start SOC (${start}%), otherwise the inverter will never stop charging.`,
    });
  }
  return out;
}

/** Check battery voltage thresholds: bulk > float > low > restart > shutdown. */
export function checkVoltageThresholds(values: {
  battery_bulk_voltage_v?: number;
  battery_float_voltage_v?: number;
  battery_low_voltage_v?: number;
  battery_restart_voltage_v?: number;
  battery_shutdown_voltage_v?: number;
}): CrossFieldWarning[] {
  const out: CrossFieldWarning[] = [];
  const b = values.battery_bulk_voltage_v;
  const f = values.battery_float_voltage_v;
  const l = values.battery_low_voltage_v;
  const r = values.battery_restart_voltage_v;
  const s = values.battery_shutdown_voltage_v;
  if (b != null && f != null && b < f) {
    out.push({
      key: null,
      message: `Bulk voltage (${b} V) must be higher than float (${f} V).`,
    });
  }
  if (f != null && l != null && f < l) {
    out.push({
      key: null,
      message: `Float voltage (${f} V) must be higher than low-voltage alarm (${l} V).`,
    });
  }
  if (l != null && r != null && l < r) {
    out.push({
      key: null,
      message: `Low-voltage alarm (${l} V) must be higher than restart (${r} V).`,
    });
  }
  if (r != null && s != null && r < s) {
    out.push({
      key: null,
      message: `Restart voltage (${r} V) must be higher than shutdown (${s} V), otherwise the inverter can't recover from cutoff.`,
    });
  }
  return out;
}

/** Dispatch by section id.  Returns [] for sections with no rules. */
export function checkSection(sectionId: string, values: Record<string, any>): CrossFieldWarning[] {
  switch (sectionId) {
    case "reserve":
      return checkReserve(values);
    case "gridCharging":
      return checkGridCharging(values);
    case "voltageThresholds":
      return checkVoltageThresholds(values);
    default:
      return [];
  }
}

/** Any warning at all?  Used to disable Apply when invariants are violated. */
export function hasBlockingWarnings(sectionId: string, values: Record<string, any>): boolean {
  return checkSection(sectionId, values).length > 0;
}
