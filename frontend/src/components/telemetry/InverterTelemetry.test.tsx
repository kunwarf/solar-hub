/**
 * InverterTelemetry — Today's Peaks section tests.
 *
 * Verifies:
 * - "Today's Peaks" card row renders when peak data is provided.
 * - All four tile labels are present.
 * - Peak values are displayed in kW with two decimal places.
 * - "Peak at HH:mm" timestamp is rendered.
 * - Section is NOT rendered when all peaks are null.
 * - Section is NOT rendered when peaks prop is absent.
 * - Individual null peak shows "—" placeholder.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import InverterTelemetry from "./InverterTelemetry";

// Minimal mock of useTelemetryData so tests don't hit the network
vi.mock("@/hooks/useTelemetryData", () => ({
  useTelemetryData: () => ({
    metrics: null,
    mpptChannels: [],
    historicalData: [],
    isLoading: false,
    error: null,
  }),
}));

const device = {
  id: "dev-001",
  name: "Test Inverter",
  serialNumber: "SN123456",
  metrics: [],
};

const telemetry = {
  serial_number: "SN123456",
  pv_power_w: 3000,
  grid_power_w: -1200,
  load_power_w: 2000,
  battery_power_w: 500,
  battery_soc_pct: 75,
  is_charging: false,
  online: true,
};

const fullPeaks = {
  max_pv_today:     { value_kw: 5.12, occurred_at: "2026-04-14T08:23:00Z" },
  max_load_today:   { value_kw: 3.20, occurred_at: "2026-04-14T13:05:00Z" },
  max_export_today: { value_kw: 2.40, occurred_at: "2026-04-14T09:10:00Z" },
  max_import_today: { value_kw: 1.50, occurred_at: "2026-04-14T19:45:00Z" },
  site_timezone: "Asia/Karachi",
};

describe("InverterTelemetry — Today's Peaks", () => {
  it("renders the 'Today's Peaks' heading when peak data is provided", () => {
    render(<InverterTelemetry device={device} telemetry={telemetry} peaks={fullPeaks} />);
    expect(screen.getByText("Today's Peaks")).toBeTruthy();
  });

  it("renders all four tile labels", () => {
    render(<InverterTelemetry device={device} telemetry={telemetry} peaks={fullPeaks} />);
    expect(screen.getByText(/max solar/i)).toBeTruthy();
    expect(screen.getByText(/max load/i)).toBeTruthy();
    expect(screen.getByText(/max export/i)).toBeTruthy();
    expect(screen.getByText(/max import/i)).toBeTruthy();
  });

  it("displays peak values in kW", () => {
    render(<InverterTelemetry device={device} telemetry={telemetry} peaks={fullPeaks} />);
    // 5.12 kW solar
    expect(screen.getByText("5.12")).toBeTruthy();
    // 3.20 kW load
    expect(screen.getByText("3.20")).toBeTruthy();
  });

  it("shows 'Peak at HH:mm' timestamp for each tile", () => {
    render(<InverterTelemetry device={device} telemetry={telemetry} peaks={fullPeaks} />);
    const peakAtNodes = screen.getAllByText(/peak at/i);
    expect(peakAtNodes.length).toBeGreaterThanOrEqual(4);
  });

  it("does NOT render the section when all peaks are null", () => {
    const nullPeaks = {
      max_pv_today:     null,
      max_load_today:   null,
      max_export_today: null,
      max_import_today: null,
    };
    render(<InverterTelemetry device={device} telemetry={telemetry} peaks={nullPeaks} />);
    expect(screen.queryByText("Today's Peaks")).toBeNull();
  });

  it("does NOT render the section when peaks prop is absent", () => {
    render(<InverterTelemetry device={device} telemetry={telemetry} />);
    expect(screen.queryByText("Today's Peaks")).toBeNull();
  });

  it("shows '—' for a null individual peak", () => {
    const partialPeaks = {
      max_pv_today:     { value_kw: 4.0, occurred_at: "2026-04-14T09:00:00Z" },
      max_load_today:   null,
      max_export_today: null,
      max_import_today: null,
    };
    render(<InverterTelemetry device={device} telemetry={telemetry} peaks={partialPeaks} />);
    // Section is visible (pv has data)
    expect(screen.getByText("Today's Peaks")).toBeTruthy();
    // Null tiles show em dash
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
  });

  it("converts occurred_at UTC to the provided site timezone", () => {
    // 08:23 UTC = 13:23 PKT (UTC+5)
    const pkiPeaks = {
      max_pv_today: { value_kw: 5.0, occurred_at: "2026-04-14T08:23:00Z" },
      site_timezone: "Asia/Karachi",
    };
    render(<InverterTelemetry device={device} telemetry={telemetry} peaks={pkiPeaks} />);
    // Should show local PKT time "13:23"
    expect(screen.getByText(/13:23/)).toBeTruthy();
  });
});
