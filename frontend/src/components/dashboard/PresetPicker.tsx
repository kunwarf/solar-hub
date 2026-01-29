import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  LayoutTemplate,
  Plus,
  Trash2,
  Check,
  Sparkles,
  Layers,
  Grid3X3,
} from "lucide-react";
import { useDashboardLayout, LayoutPreset } from "@/contexts/DashboardLayoutContext";
import { cn } from "@/lib/utils";

interface PresetPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PresetPicker({ open, onOpenChange }: PresetPickerProps) {
  const {
    currentPreset,
    builtInPresets,
    customPresets,
    applyPreset,
    saveCustomPreset,
    deleteCustomPreset,
  } = useDashboardLayout();

  const [selectedPreset, setSelectedPreset] = useState<LayoutPreset>(currentPreset);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [presetToDelete, setPresetToDelete] = useState<string | null>(null);
  const [newPresetName, setNewPresetName] = useState("");
  const [newPresetDescription, setNewPresetDescription] = useState("");

  const handleApplyPreset = () => {
    applyPreset(selectedPreset);
    onOpenChange(false);
  };

  const handleSaveCustomPreset = () => {
    if (newPresetName.trim()) {
      saveCustomPreset(newPresetName.trim(), newPresetDescription.trim());
      setNewPresetName("");
      setNewPresetDescription("");
      setShowSaveDialog(false);
      onOpenChange(false);
    }
  };

  const handleDeletePreset = () => {
    if (presetToDelete) {
      deleteCustomPreset(presetToDelete);
      setPresetToDelete(null);
      setShowDeleteConfirm(false);
    }
  };

  const allPresets = [...builtInPresets, ...customPresets];

  const getPresetIcon = (presetId: string) => {
    switch (presetId) {
      case "essential":
        return <Layers className="w-4 h-4" />;
      case "standard":
        return <Grid3X3 className="w-4 h-4" />;
      case "comprehensive":
        return <LayoutTemplate className="w-4 h-4" />;
      default:
        return <Sparkles className="w-4 h-4" />;
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Dashboard Presets</DialogTitle>
            <DialogDescription>
              Choose a preset layout or save your current layout as a custom preset
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <RadioGroup value={selectedPreset} onValueChange={setSelectedPreset}>
              {/* Built-in Presets */}
              <div className="space-y-2">
                <Label className="text-sm font-semibold text-muted-foreground">
                  Built-in Presets
                </Label>
                {builtInPresets.map((preset) => (
                  <div
                    key={preset.id}
                    className={cn(
                      "flex items-center space-x-3 border rounded-lg p-4 cursor-pointer transition-colors",
                      selectedPreset === preset.id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    )}
                    onClick={() => setSelectedPreset(preset.id)}
                  >
                    <RadioGroupItem value={preset.id} id={preset.id} />
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        {getPresetIcon(preset.id)}
                        <Label
                          htmlFor={preset.id}
                          className="text-base font-medium cursor-pointer"
                        >
                          {preset.name}
                        </Label>
                        {currentPreset === preset.id && (
                          <Badge variant="secondary" className="text-xs">
                            <Check className="w-3 h-3 mr-1" />
                            Active
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {preset.description}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {preset.widgets.filter((w) => w.visible).length} widgets visible
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Custom Presets */}
              {customPresets.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm font-semibold text-muted-foreground">
                    Custom Presets
                  </Label>
                  {customPresets.map((preset) => (
                    <div
                      key={preset.id}
                      className={cn(
                        "flex items-center space-x-3 border rounded-lg p-4 cursor-pointer transition-colors",
                        selectedPreset === preset.id
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/50"
                      )}
                      onClick={() => setSelectedPreset(preset.id)}
                    >
                      <RadioGroupItem value={preset.id} id={preset.id} />
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          {getPresetIcon(preset.id)}
                          <Label
                            htmlFor={preset.id}
                            className="text-base font-medium cursor-pointer"
                          >
                            {preset.name}
                          </Label>
                          {currentPreset === preset.id && (
                            <Badge variant="secondary" className="text-xs">
                              <Check className="w-3 h-3 mr-1" />
                              Active
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {preset.description}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {preset.widgets.filter((w) => w.visible).length} widgets visible
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setPresetToDelete(preset.id);
                          setShowDeleteConfirm(true);
                        }}
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </RadioGroup>

            {/* Actions */}
            <div className="flex justify-between items-center pt-4 border-t">
              <Button
                variant="outline"
                onClick={() => setShowSaveDialog(true)}
                className="gap-2"
              >
                <Plus className="w-4 h-4" />
                Save Current as Preset
              </Button>

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleApplyPreset}
                  disabled={selectedPreset === currentPreset}
                >
                  Apply Preset
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Save Custom Preset Dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Custom Preset</DialogTitle>
            <DialogDescription>
              Save your current dashboard layout as a custom preset
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="preset-name">Preset Name</Label>
              <Input
                id="preset-name"
                placeholder="e.g., My Custom Layout"
                value={newPresetName}
                onChange={(e) => setNewPresetName(e.target.value)}
                maxLength={50}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="preset-description">Description (Optional)</Label>
              <Textarea
                id="preset-description"
                placeholder="Describe what makes this preset useful..."
                value={newPresetDescription}
                onChange={(e) => setNewPresetDescription(e.target.value)}
                maxLength={200}
                rows={3}
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowSaveDialog(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleSaveCustomPreset}
                disabled={!newPresetName.trim()}
              >
                Save Preset
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Custom Preset?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this custom preset. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPresetToDelete(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeletePreset}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete Preset
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
