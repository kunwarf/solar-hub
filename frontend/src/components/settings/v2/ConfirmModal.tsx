/**
 * Type-the-serial-to-confirm modal for destructive setting changes.
 *
 * Matches the memory's established pattern for grid-standard / battery-mode
 * writes — user must type the exact device serial before the Apply button
 * enables.  Case- and whitespace-strict on purpose.
 *
 * Reference: D:\Downloads\solar-inverter-settings.html ConfirmModal.
 */
import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { Button } from "./primitives";

export function ConfirmModal({
  fieldLabel,
  serial,
  onCancel,
  onConfirm,
}: {
  fieldLabel: string;
  serial: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const [typed, setTyped] = useState("");
  const matches = typed === serial;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xl p-5">
        <div className="flex items-start justify-between mb-1">
          <h4 className="font-semibold text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            Confirm destructive change
          </h4>
          <button
            onClick={onCancel}
            className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[13px] text-zinc-500 dark:text-zinc-400 mb-4">
          Changing{" "}
          <span className="font-medium text-zinc-700 dark:text-zinc-300">{fieldLabel}</span>{" "}
          can affect device safety behavior. Type the device serial to confirm.
        </p>
        <p className="font-mono text-[12px] tabular-nums bg-zinc-100 dark:bg-zinc-800 rounded-lg px-3 py-2 mb-3 select-all">
          {serial}
        </p>
        <input
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder="Type serial to confirm"
          className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-2.5 text-base font-mono mb-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="destructive" disabled={!matches} onClick={onConfirm}>
            Confirm change
          </Button>
        </div>
      </div>
    </div>
  );
}
