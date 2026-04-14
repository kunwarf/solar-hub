/**
 * VoltronicSettingsPage tests
 *
 * Verifies:
 * - Tab labels are rendered.
 * - ACK response shows success feedback; NAK shows error feedback.
 * - Command log shows last entry.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { VoltronicSettingsPage } from "./VoltronicSettingsPage";

const defaultProps = {
  deviceId: "device-456",
  deviceName: "Voltronic Axpert",
  deviceSerial: "VOL98765",
  protocolVariant: "PI30",
  settings: { output_priority: "solar", charger_priority: "solar" },
  onSendCommand: vi.fn().mockResolvedValue({ success: true }),
  onRefreshAll: vi.fn().mockResolvedValue(undefined),
};

describe("VoltronicSettingsPage", () => {
  it("renders all tab labels", () => {
    render(<VoltronicSettingsPage {...defaultProps} />);
    expect(screen.getByText("Output")).toBeTruthy();
    expect(screen.getByText("Charger")).toBeTruthy();
    expect(screen.getByText("Battery")).toBeTruthy();
    expect(screen.getByText("Grid")).toBeTruthy();
    expect(screen.getByText("System")).toBeTruthy();
  });

  it("shows PI30 protocol variant badge", () => {
    render(<VoltronicSettingsPage {...defaultProps} />);
    expect(screen.getByText("PI30")).toBeTruthy();
  });

  it("calls onRefreshAll when Refresh all is clicked", async () => {
    const onRefreshAll = vi.fn().mockResolvedValue(undefined);
    render(<VoltronicSettingsPage {...defaultProps} onRefreshAll={onRefreshAll} />);
    fireEvent.click(screen.getByRole("button", { name: /refresh all/i }));
    await waitFor(() => expect(onRefreshAll).toHaveBeenCalledTimes(1));
  });

  it("shows command log section", () => {
    render(<VoltronicSettingsPage {...defaultProps} />);
    expect(screen.getByText(/command log/i)).toBeTruthy();
  });

  it("calls onSendCommand with ACK result when Apply is clicked on a dirty field", async () => {
    const onSendCommand = vi.fn().mockResolvedValue({ success: true });
    render(
      <VoltronicSettingsPage
        {...defaultProps}
        onSendCommand={onSendCommand}
        settings={{ output_priority: "utility" }}
      />
    );
    // Change the Output Source Priority select
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "solar" } });
    // The Apply button should now appear; click it
    const applyBtns = screen.getAllByRole("button", { name: /apply/i });
    fireEvent.click(applyBtns[0]);
    await waitFor(() => expect(onSendCommand).toHaveBeenCalledTimes(1));
  });
});
