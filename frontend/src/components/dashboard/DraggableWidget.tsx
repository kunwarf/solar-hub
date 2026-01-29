import { ReactNode } from "react";
import { motion } from "framer-motion";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { GripVertical, X, Settings, Maximize2, Minimize2, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDashboardLayout, WidgetId, WidgetSize } from "@/contexts/DashboardLayoutContext";

interface DraggableWidgetProps {
  id: WidgetId;
  children: ReactNode;
  className?: string;
  settingsContent?: ReactNode;
}

export function DraggableWidget({
  id,
  children,
  className,
  settingsContent,
}: DraggableWidgetProps) {
  const { isEditMode, removeWidget, getWidgetConfig, layout, resizeWidget } = useDashboardLayout();
  const config = getWidgetConfig(id);
  const currentWidget = layout.find(w => w.id === id);
  const currentSize = currentWidget?.size || "medium";

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled: !isEditMode });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  if (!isEditMode) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      ref={setNodeRef}
      style={style}
      className={cn(
        "relative group",
        isDragging && "z-50 opacity-80",
        className
      )}
      layout
    >
      {/* Edit Mode Overlay */}
      <div className={cn(
        "absolute inset-0 border-2 border-dashed rounded-lg pointer-events-none transition-colors z-10",
        isDragging ? "border-primary bg-primary/5" : "border-primary/30 group-hover:border-primary/50"
      )} />

      {/* Drag Handle */}
      <div
        {...attributes}
        {...listeners}
        className="absolute top-2 left-2 z-20 p-1.5 rounded-md bg-background/90 border border-border shadow-sm cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <GripVertical className="w-4 h-4 text-muted-foreground" />
      </div>

      {/* Widget Controls */}
      <div className="absolute top-2 right-2 z-20 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {/* Size Control */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7 bg-background/90"
              title="Change widget size"
            >
              {currentSize === "small" && <Minimize2 className="w-3.5 h-3.5" />}
              {currentSize === "medium" && <Square className="w-3.5 h-3.5" />}
              {currentSize === "large" && <Maximize2 className="w-3.5 h-3.5" />}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuLabel>Widget Size</DropdownMenuLabel>
            <DropdownMenuItem
              onClick={() => resizeWidget(id, "small")}
              className={cn(currentSize === "small" && "bg-accent")}
            >
              <Minimize2 className="w-4 h-4 mr-2" />
              Small
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => resizeWidget(id, "medium")}
              className={cn(currentSize === "medium" && "bg-accent")}
            >
              <Square className="w-4 h-4 mr-2" />
              Medium
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => resizeWidget(id, "large")}
              className={cn(currentSize === "large" && "bg-accent")}
            >
              <Maximize2 className="w-4 h-4 mr-2" />
              Large
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {settingsContent && (
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="h-7 w-7 bg-background/90"
              >
                <Settings className="w-3.5 h-3.5" />
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-64">
              <div className="space-y-3">
                <p className="font-medium text-sm">{config?.name} Settings</p>
                {settingsContent}
              </div>
            </PopoverContent>
          </Popover>
        )}

        <Button
          variant="outline"
          size="icon"
          className="h-7 w-7 bg-background/90 hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
          onClick={() => removeWidget(id)}
        >
          <X className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Widget Name Label */}
      <div className="absolute bottom-2 left-2 z-20 px-2 py-1 rounded bg-background/90 border border-border text-xs font-medium text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
        {config?.name}
      </div>

      {/* Widget Content */}
      <div className={cn(isDragging && "pointer-events-none")}>
        {children}
      </div>
    </motion.div>
  );
}
