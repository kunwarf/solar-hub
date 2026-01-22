import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from "@/components/ui/dropdown-menu";
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
import {
  Edit3,
  Check,
  Plus,
  RotateCcw,
  LayoutGrid,
  X,
  ChevronDown,
  List,
  Grid2X2,
  Grid3X3,
} from "lucide-react";
import { useDashboardLayout, GridLayout } from "@/contexts/DashboardLayoutContext";
import { WidgetPicker } from "./WidgetPicker";

export function DashboardEditControls() {
  const { isEditMode, setIsEditMode, resetToDefault, visibleWidgets, hiddenWidgets, gridLayout, setGridLayout } = useDashboardLayout();
  const [isWidgetPickerOpen, setIsWidgetPickerOpen] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const handleToggleEditMode = () => {
    setIsEditMode(!isEditMode);
  };

  const handleSaveLayout = () => {
    setIsEditMode(false);
  };

  const handleReset = () => {
    resetToDefault();
    setShowResetConfirm(false);
  };

  return (
    <>
      <AnimatePresence mode="wait">
        {isEditMode ? (
          <motion.div
            key="edit-mode"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex items-center gap-2"
          >
            <Badge variant="secondary" className="gap-1.5 bg-primary/10 text-primary border-primary/20">
              <Edit3 className="w-3 h-3" />
              Edit Mode
            </Badge>
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsWidgetPickerOpen(true)}
              className="gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Add Widget</span>
            </Button>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-1">
                  {gridLayout === "list" && <List className="w-4 h-4" />}
                  {gridLayout === "2x2" && <Grid2X2 className="w-4 h-4" />}
                  {gridLayout === "3x3" && <Grid3X3 className="w-4 h-4" />}
                  <ChevronDown className="w-3 h-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuLabel>Grid Layout</DropdownMenuLabel>
                <DropdownMenuRadioGroup value={gridLayout} onValueChange={(v) => setGridLayout(v as GridLayout)}>
                  <DropdownMenuRadioItem value="list" className="gap-2">
                    <List className="w-4 h-4" />
                    List View
                  </DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="2x2" className="gap-2">
                    <Grid2X2 className="w-4 h-4" />
                    2×2 Grid
                  </DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="3x3" className="gap-2">
                    <Grid3X3 className="w-4 h-4" />
                    3×3 Grid
                  </DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => setShowResetConfirm(true)}>
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Reset to Default
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <div className="px-2 py-1.5 text-xs text-muted-foreground">
                  {visibleWidgets.length} visible, {hiddenWidgets.length} hidden
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsEditMode(false)}
              className="gap-1.5 border-destructive/30 text-destructive hover:bg-destructive/10"
            >
              <X className="w-4 h-4" />
              <span className="hidden sm:inline">Cancel</span>
            </Button>
            
            <Button
              size="sm"
              onClick={handleSaveLayout}
              className="gap-1.5"
            >
              <Check className="w-4 h-4" />
              <span className="hidden sm:inline">Done</span>
            </Button>
          </motion.div>
        ) : (
          <motion.div
            key="normal-mode"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Button
              variant="outline"
              size="sm"
              onClick={handleToggleEditMode}
              className="gap-1.5"
            >
              <Edit3 className="w-4 h-4" />
              <span className="hidden sm:inline">Edit Layout</span>
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      <WidgetPicker
        open={isWidgetPickerOpen}
        onOpenChange={setIsWidgetPickerOpen}
      />

      <AlertDialog open={showResetConfirm} onOpenChange={setShowResetConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset Dashboard Layout?</AlertDialogTitle>
            <AlertDialogDescription>
              This will restore all widgets to their default positions and visibility. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleReset}>
              Reset Layout
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
