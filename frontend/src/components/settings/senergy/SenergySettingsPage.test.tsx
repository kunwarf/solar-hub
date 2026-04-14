/**
 * SenergySettingsPage tests
 *
 * Verifies:
 * - Battery sign-convention banner is visible in Battery group.
 * - Grid code restart warning banner is visible when Grid Code tab is active.
 * - Work Mode quick-switcher is always visible.
 * - onApply is called with correct payload for Work Mode change.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SenergySettingsPage } from "./SenergySettingsPage";

const defaultProps = {
  deviceId: "device-789",
  deviceName: "Senergy Inverter",
  deviceSerial: "SNR00001",
  settings: { work_mode: "0", battery_capacity_ah: 100 },
  lastSyncedAt: new Date().toISOString(),
  onApply: vi.fn().mockResolvedValue(undefined),
  onRefresh: vi.fn().mockResolvedValue(undefined),
};

describe("SenergySettingsPage", () => {
  it("renders the battery sign-convention note in Battery tab", () => {
    render(<SenergySettingsPage {...defaultProps} />);
    expect(
      screen.getByText(/positive battery power = discharging/i)
    ).toBeTruthy();
  });

  it("renders Work Mode quick-switcher", () => {
    render(<SenergySettingsPage {...defaultProps} />);
    expect(screen.getByText(/work mode/i)).toBeTruthy();
  });

  it("shows grid code restart warning when Grid Code tab is active", () => {
    render(<SenergySettingsPage {...defaultProps} />);
    fireEvent.click(screen.getByText("Grid Code"));
    expect(
      screen.getByText(/inverter may restart when changing grid code/i)
    ).toBeTruthy();
  });

  it("calls onApply with work_mode key when Work Mode is changed", async () => {
    const onApply = vi.fn().mockResolvedValue(undefined);
    render(<SenergySettingsPage {...defaultProps} onApply={onApply} />);
    const workModeSelects = screen.getAllByRole("combobox");
    fireEvent.change(workModeSelects[0], { target: { value: "1" } });
    await waitFor(() => {
      expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ work_mode: "1" }));
    });
  });

  it("calls onRefresh when Refresh button is clicked", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(<SenergySettingsPage {...defaultProps} onRefresh={onRefresh} />);
    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
  });
});
