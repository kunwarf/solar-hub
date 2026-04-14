/**
 * ConfirmWriteDialog tests
 *
 * Verifies that:
 * - The dialog renders the field label, old value, and new value.
 * - The Apply button is disabled until the user types the exact device serial.
 * - Confirming calls the onConfirm callback and closes the dialog.
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ConfirmWriteDialog } from "./ConfirmWriteDialog";

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  deviceSerial: "SH01GWAT9Q7YDV90",
  fieldLabel: "Battery Type",
  oldValue: "Lead-acid",
  newValue: "Lithium",
  onConfirm: vi.fn(),
};

describe("ConfirmWriteDialog", () => {
  it("renders the field label, old and new values", () => {
    render(<ConfirmWriteDialog {...defaultProps} />);
    expect(screen.getByText("Battery Type")).toBeTruthy();
    expect(screen.getByText("Lead-acid")).toBeTruthy();
    expect(screen.getByText("Lithium")).toBeTruthy();
  });

  it("disables Apply button until correct serial is typed", () => {
    render(<ConfirmWriteDialog {...defaultProps} />);
    const applyBtn = screen.getByRole("button", { name: /apply change/i });
    expect(applyBtn).toBeDisabled();

    const input = screen.getByPlaceholderText(/enter serial number/i);
    fireEvent.change(input, { target: { value: "WRONG123" } });
    expect(applyBtn).toBeDisabled();

    fireEvent.change(input, { target: { value: "SH01GWAT9Q7YDV90" } });
    expect(applyBtn).not.toBeDisabled();
  });

  it("calls onConfirm when Apply is clicked with correct serial", () => {
    const onConfirm = vi.fn();
    render(<ConfirmWriteDialog {...defaultProps} onConfirm={onConfirm} />);
    const input = screen.getByPlaceholderText(/enter serial number/i);
    fireEvent.change(input, { target: { value: "SH01GWAT9Q7YDV90" } });
    const applyBtn = screen.getByRole("button", { name: /apply change/i });
    fireEvent.click(applyBtn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("matches serial case-insensitively", () => {
    const onConfirm = vi.fn();
    render(<ConfirmWriteDialog {...defaultProps} onConfirm={onConfirm} />);
    const input = screen.getByPlaceholderText(/enter serial number/i);
    fireEvent.change(input, { target: { value: "sh01gwat9q7ydv90" } });
    const applyBtn = screen.getByRole("button", { name: /apply change/i });
    expect(applyBtn).not.toBeDisabled();
    fireEvent.click(applyBtn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
