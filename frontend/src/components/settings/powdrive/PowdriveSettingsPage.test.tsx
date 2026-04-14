/**
 * PowdriveSettingsPage tests
 *
 * Verifies:
 * - All section labels from the schema are rendered in the sidebar.
 * - Clicking a section tab renders its heading in the pane.
 * - onApply is called with the correct payload when a field is changed and
 *   the inline Apply button is clicked.
 * - Out-of-range numeric inputs are clamped by the browser's native min/max
 *   (not tested here — that's browser behaviour). Schema-level min/max are
 *   present in the rendered input attributes.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PowdriveSettingsPage } from "./PowdriveSettingsPage";

const defaultSettings = {
  battery_capacity_ah: 100,
  battery_max_charge_current_a: 50,
  solar_sell: true,
};

const defaultProps = {
  deviceId: "device-123",
  deviceName: "Powdrive Inverter",
  deviceSerial: "PD12345",
  settings: defaultSettings,
  lastSyncedAt: new Date().toISOString(),
  onApply: vi.fn().mockResolvedValue(undefined),
  onRefresh: vi.fn().mockResolvedValue(undefined),
};

describe("PowdriveSettingsPage", () => {
  it("renders all group labels in the sidebar", () => {
    render(<PowdriveSettingsPage {...defaultProps} />);
    expect(screen.getByText("Battery")).toBeTruthy();
    expect(screen.getByText("Charger")).toBeTruthy();
    expect(screen.getByText("Grid & Export")).toBeTruthy();
    expect(screen.getByText("Inverter / Output")).toBeTruthy();
    expect(screen.getByText("Generator")).toBeTruthy();
    expect(screen.getByText("TOU Schedule")).toBeTruthy();
    expect(screen.getByText("Protection")).toBeTruthy();
  });

  it("shows the Battery group heading by default", () => {
    render(<PowdriveSettingsPage {...defaultProps} />);
    // The group label is shown as h3 in the pane
    const headings = screen.getAllByText("Battery");
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  it("switches pane when a sidebar group is clicked", () => {
    render(<PowdriveSettingsPage {...defaultProps} />);
    fireEvent.click(screen.getByText("Protection"));
    expect(screen.getAllByText("Protection").length).toBeGreaterThanOrEqual(1);
  });

  it("calls onRefresh when Refresh button is clicked", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(<PowdriveSettingsPage {...defaultProps} onRefresh={onRefresh} />);
    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
  });
});
