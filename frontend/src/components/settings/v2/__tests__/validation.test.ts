/**
 * Cross-field validation unit tests — pure logic, no React.
 */
import { describe, expect, it } from "vitest";
import {
  checkReserve,
  checkGridCharging,
  checkVoltageThresholds,
  checkSection,
  hasBlockingWarnings,
} from "../validation";

describe("checkReserve", () => {
  it("returns empty when restart is > shutdown + 5%", () => {
    expect(
      checkReserve({ battery_shutdown_capacity_pct: 20, battery_restart_capacity_pct: 30 }),
    ).toHaveLength(0);
  });

  it("warns when restart is too close to shutdown", () => {
    const warnings = checkReserve({
      battery_shutdown_capacity_pct: 20,
      battery_restart_capacity_pct: 22,
    });
    expect(warnings).toHaveLength(1);
    expect(warnings[0].key).toBe("battery_restart_capacity_pct");
    expect(warnings[0].message).toMatch(/at least 5% above/i);
  });

  it("warns when priority-load SOC is below shutdown", () => {
    const warnings = checkReserve({
      battery_shutdown_capacity_pct: 30,
      battery_restart_capacity_pct: 40,
      priority_load_soc_pct: 20,
    });
    expect(warnings).toHaveLength(1);
    expect(warnings[0].key).toBe("priority_load_soc_pct");
  });

  it("returns empty when values are undefined", () => {
    expect(checkReserve({})).toHaveLength(0);
  });
});

describe("checkGridCharging", () => {
  it("returns empty when end > start", () => {
    expect(
      checkGridCharging({ ac_charge_start_soc_pct: 20, ac_charge_end_soc_pct: 80 }),
    ).toHaveLength(0);
  });

  it("warns when end <= start", () => {
    expect(
      checkGridCharging({ ac_charge_start_soc_pct: 50, ac_charge_end_soc_pct: 50 }),
    ).toHaveLength(1);
    expect(
      checkGridCharging({ ac_charge_start_soc_pct: 60, ac_charge_end_soc_pct: 40 }),
    ).toHaveLength(1);
  });
});

describe("checkVoltageThresholds", () => {
  it("returns empty for a well-ordered set", () => {
    expect(
      checkVoltageThresholds({
        battery_bulk_voltage_v: 56.4,
        battery_float_voltage_v: 54.0,
        battery_low_voltage_v: 48.0,
        battery_restart_voltage_v: 46.0,
        battery_shutdown_voltage_v: 42.0,
      }),
    ).toHaveLength(0);
  });

  it("warns when bulk < float", () => {
    const warnings = checkVoltageThresholds({
      battery_bulk_voltage_v: 50,
      battery_float_voltage_v: 54,
    });
    expect(warnings).toHaveLength(1);
    expect(warnings[0].message).toMatch(/bulk/i);
  });

  it("warns when restart < shutdown", () => {
    const warnings = checkVoltageThresholds({
      battery_restart_voltage_v: 40,
      battery_shutdown_voltage_v: 42,
    });
    expect(warnings).toHaveLength(1);
    expect(warnings[0].message).toMatch(/restart/i);
  });
});

describe("checkSection dispatcher", () => {
  it("routes 'reserve' to checkReserve", () => {
    expect(
      checkSection("reserve", {
        battery_shutdown_capacity_pct: 20,
        battery_restart_capacity_pct: 22,
      }),
    ).toHaveLength(1);
  });

  it("returns [] for unknown section id", () => {
    expect(checkSection("bogus", { anything: 1 })).toHaveLength(0);
  });
});

describe("hasBlockingWarnings", () => {
  it("is true when a rule fires", () => {
    expect(
      hasBlockingWarnings("gridCharging", {
        ac_charge_start_soc_pct: 90,
        ac_charge_end_soc_pct: 80,
      }),
    ).toBe(true);
  });
  it("is false when clean", () => {
    expect(
      hasBlockingWarnings("gridCharging", {
        ac_charge_start_soc_pct: 20,
        ac_charge_end_soc_pct: 80,
      }),
    ).toBe(false);
  });
});
