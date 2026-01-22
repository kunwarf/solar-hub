import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  BarChart3,
  Zap,
  Cpu,
  LineChart,
  Sun,
  Target,
  Leaf,
  ZapOff,
  Receipt,
  Server,
  AlertTriangle,
  Plus,
  Check,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useDashboardLayout, WidgetConfig, WidgetCategory } from "@/contexts/DashboardLayoutContext";

const iconMap: Record<string, React.ElementType> = {
  BarChart3,
  Zap,
  Cpu,
  LineChart,
  Sun,
  Target,
  Leaf,
  ZapOff,
  Receipt,
  Server,
  AlertTriangle,
  Sparkles,
};

const categoryLabels: Record<WidgetCategory, string> = {
  statistics: "Statistics",
  charts: "Charts",
  status: "Status",
  actions: "Actions",
};

interface WidgetPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function WidgetPicker({ open, onOpenChange }: WidgetPickerProps) {
  const { layout, addWidget, hiddenWidgets } = useDashboardLayout();
  const [selectedCategory, setSelectedCategory] = useState<WidgetCategory | "all">("all");

  const allWidgets = hiddenWidgets;
  const filteredWidgets = selectedCategory === "all"
    ? allWidgets
    : allWidgets.filter(w => w.category === selectedCategory);

  const isWidgetVisible = (id: string) => {
    return layout.find(item => item.id === id)?.visible ?? false;
  };

  const handleAddWidget = (widget: WidgetConfig) => {
    addWidget(widget.id);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Add Widget</SheetTitle>
          <SheetDescription>
            Choose widgets to add to your dashboard
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6">
          <Tabs defaultValue="all" onValueChange={(v) => setSelectedCategory(v as WidgetCategory | "all")}>
            <TabsList className="w-full grid grid-cols-5 h-auto">
              <TabsTrigger value="all" className="text-xs py-2">All</TabsTrigger>
              <TabsTrigger value="statistics" className="text-xs py-2">Stats</TabsTrigger>
              <TabsTrigger value="charts" className="text-xs py-2">Charts</TabsTrigger>
              <TabsTrigger value="status" className="text-xs py-2">Status</TabsTrigger>
              <TabsTrigger value="actions" className="text-xs py-2">Actions</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <ScrollArea className="h-[calc(100vh-200px)] mt-4">
          <div className="space-y-3 pr-4">
            <AnimatePresence mode="popLayout">
              {filteredWidgets.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center py-12"
                >
                  <Check className="w-12 h-12 mx-auto text-success mb-3" />
                  <p className="text-muted-foreground">All widgets are visible!</p>
                </motion.div>
              ) : (
                filteredWidgets.map((widget, index) => {
                  const Icon = iconMap[widget.icon] || BarChart3;
                  const isVisible = isWidgetVisible(widget.id);
                  
                  return (
                    <motion.div
                      key={widget.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      transition={{ delay: index * 0.05 }}
                      className={cn(
                        "p-4 rounded-lg border transition-all",
                        isVisible
                          ? "bg-success/10 border-success/30"
                          : "bg-secondary/30 border-border hover:border-primary/30"
                      )}
                    >
                      <div className="flex items-start gap-4">
                        <div className={cn(
                          "w-12 h-12 rounded-lg flex items-center justify-center shrink-0",
                          isVisible ? "bg-success/20" : "bg-primary/10"
                        )}>
                          <Icon className={cn(
                            "w-6 h-6",
                            isVisible ? "text-success" : "text-primary"
                          )} />
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <p className="font-medium text-foreground">{widget.name}</p>
                            <Badge variant="outline" className="text-[10px] capitalize">
                              {categoryLabels[widget.category]}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">{widget.description}</p>
                        </div>
                        
                        {!isVisible && (
                          <Button
                            size="sm"
                            onClick={() => handleAddWidget(widget)}
                            className="shrink-0 gap-1"
                          >
                            <Plus className="w-4 h-4" />
                            Add
                          </Button>
                        )}
                        
                        {isVisible && (
                          <Check className="w-5 h-5 text-success shrink-0" />
                        )}
                      </div>
                    </motion.div>
                  );
                })
              )}
            </AnimatePresence>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
