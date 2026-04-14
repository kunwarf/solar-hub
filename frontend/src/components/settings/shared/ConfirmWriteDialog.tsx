/**
 * ConfirmWriteDialog
 *
 * Shown before writing a destructive setting (battery type, grid code, etc.).
 * Requires the user to type the device serial number to confirm.
 */

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertTriangle } from "lucide-react";

interface ConfirmWriteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  deviceSerial: string;
  fieldLabel: string;
  oldValue: string | number;
  newValue: string | number;
  onConfirm: () => void;
}

export const ConfirmWriteDialog = ({
  open,
  onOpenChange,
  deviceSerial,
  fieldLabel,
  oldValue,
  newValue,
  onConfirm,
}: ConfirmWriteDialogProps) => {
  const [inputSerial, setInputSerial] = useState("");
  const isMatch = !!deviceSerial && inputSerial.trim().toUpperCase() === deviceSerial.trim().toUpperCase();

  const handleConfirm = () => {
    if (!isMatch) return;
    onConfirm();
    setInputSerial("");
    onOpenChange(false);
  };

  const handleCancel = () => {
    setInputSerial("");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-warning">
            <AlertTriangle className="w-5 h-5" />
            Confirm Destructive Change
          </DialogTitle>
          <DialogDescription>
            You are about to change a critical setting. This may affect inverter
            operation or require a restart.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Diff preview */}
          <div className="glass-card p-3 rounded-xl space-y-1 text-sm">
            <p className="text-muted-foreground">Setting</p>
            <p className="font-semibold text-foreground">{fieldLabel}</p>
            <div className="flex items-center gap-3 mt-2">
              <span className="bg-destructive/20 text-destructive px-2 py-0.5 rounded font-mono text-xs">
                {String(oldValue)}
              </span>
              <span className="text-muted-foreground">→</span>
              <span className="bg-success/20 text-success px-2 py-0.5 rounded font-mono text-xs">
                {String(newValue)}
              </span>
            </div>
          </div>

          {/* Serial confirmation */}
          <div className="space-y-2">
            <Label htmlFor="serial-confirm" className="text-sm">
              Type the device serial number to confirm:
              <span className="ml-1 font-mono text-xs text-warning">{deviceSerial}</span>
            </Label>
            <Input
              id="serial-confirm"
              placeholder="Enter serial number..."
              value={inputSerial}
              onChange={(e) => setInputSerial(e.target.value)}
              className={isMatch ? "border-success" : ""}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={!isMatch}
          >
            Apply Change
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
