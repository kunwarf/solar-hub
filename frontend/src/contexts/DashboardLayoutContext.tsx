import { createContext, useContext, useState, useEffect, ReactNode, useCallback, useRef } from "react";
import { dashboardService } from "@/api/services/dashboard.service";
import { toast } from "sonner";

export type WidgetId = 
  | "stat-cards"
  | "energy-flow"
  | "system-diagram"
  | "energy-chart"
  | "weather"
  | "quick-actions"
  | "goal-tracking"
  | "environmental-impact"
  | "load-shedding"
  | "billing-summary"
  | "device-overview"
  | "alerts-summary"
  | "ai-insights"
  | "peak-demand";

export type WidgetCategory = "statistics" | "charts" | "status" | "actions";

export type GridLayout = "list" | "2x2" | "3x3";

export type WidgetSize = "small" | "medium" | "large";

export type LayoutPreset = "essential" | "standard" | "comprehensive" | string;

export interface WidgetConfig {
  id: WidgetId;
  name: string;
  description: string;
  category: WidgetCategory;
  icon: string;
  defaultVisible: boolean;
  defaultSize: WidgetSize;
  settings?: Record<string, unknown>;
}

export interface LayoutItem {
  id: WidgetId;
  visible: boolean;
  size: WidgetSize;
  settings: Record<string, unknown>;
}

export interface LayoutPresetConfig {
  id: LayoutPreset;
  name: string;
  description: string;
  widgets: Array<{
    id: WidgetId;
    visible: boolean;
    size: WidgetSize;
  }>;
}

interface DashboardLayoutContextType {
  layout: LayoutItem[];
  isEditMode: boolean;
  gridLayout: GridLayout;
  currentPreset: LayoutPreset;
  customPresets: LayoutPresetConfig[];
  builtInPresets: LayoutPresetConfig[];
  isLoading: boolean;
  setIsEditMode: (value: boolean) => void;
  setGridLayout: (layout: GridLayout) => void;
  toggleWidgetVisibility: (id: WidgetId) => void;
  reorderWidgets: (activeId: WidgetId, overId: WidgetId) => void;
  addWidget: (id: WidgetId) => void;
  removeWidget: (id: WidgetId) => void;
  updateWidgetSettings: (id: WidgetId, settings: Record<string, unknown>) => void;
  resizeWidget: (id: WidgetId, size: WidgetSize) => void;
  applyPreset: (presetId: LayoutPreset) => void;
  saveCustomPreset: (name: string, description: string) => void;
  deleteCustomPreset: (presetId: string) => void;
  resetToDefault: () => void;
  getWidgetConfig: (id: WidgetId) => WidgetConfig | undefined;
  visibleWidgets: LayoutItem[];
  hiddenWidgets: WidgetConfig[];
}

export const widgetConfigs: WidgetConfig[] = [
  {
    id: "stat-cards",
    name: "Statistics Cards",
    description: "Key metrics like billing, savings, and production",
    category: "statistics",
    icon: "BarChart3",
    defaultVisible: true,
    defaultSize: "large",
  },
  {
    id: "energy-flow",
    name: "Energy Flow Diagram",
    description: "Real-time power flow visualization",
    category: "charts",
    icon: "Zap",
    defaultVisible: true,
    defaultSize: "large",
  },
  {
    id: "system-diagram",
    name: "System Diagram",
    description: "Visual system hierarchy overview",
    category: "status",
    icon: "Cpu",
    defaultVisible: true,
    defaultSize: "large",
  },
  {
    id: "energy-chart",
    name: "Energy Chart",
    description: "Historical energy data with time selector",
    category: "charts",
    icon: "LineChart",
    defaultVisible: true,
    defaultSize: "large",
    settings: { period: "day" },
  },
  {
    id: "weather",
    name: "Weather Widget",
    description: "Current weather and solar forecast",
    category: "status",
    icon: "Sun",
    defaultVisible: true,
    defaultSize: "medium",
  },
  {
    id: "quick-actions",
    name: "Quick Actions",
    description: "Common system commands",
    category: "actions",
    icon: "Zap",
    defaultVisible: true,
    defaultSize: "medium",
  },
  {
    id: "goal-tracking",
    name: "Goal Progress",
    description: "Track savings and production goals",
    category: "statistics",
    icon: "Target",
    defaultVisible: true,
    defaultSize: "medium",
  },
  {
    id: "environmental-impact",
    name: "Environmental Impact",
    description: "CO2 savings and eco metrics",
    category: "statistics",
    icon: "Leaf",
    defaultVisible: true,
    defaultSize: "medium",
  },
  {
    id: "load-shedding",
    name: "Load Shedding Status",
    description: "Grid outage schedule and battery backup",
    category: "status",
    icon: "ZapOff",
    defaultVisible: true,
    defaultSize: "medium",
  },
  {
    id: "billing-summary",
    name: "Billing Summary",
    description: "Monthly billing overview",
    category: "statistics",
    icon: "Receipt",
    defaultVisible: true,
    defaultSize: "medium",
  },
  {
    id: "device-overview",
    name: "Device Status Grid",
    description: "Overview of all connected devices",
    category: "status",
    icon: "Server",
    defaultVisible: false,
    defaultSize: "large",
  },
  {
    id: "alerts-summary",
    name: "Alerts Summary",
    description: "Recent system alerts",
    category: "status",
    icon: "AlertTriangle",
    defaultVisible: false,
    defaultSize: "medium",
  },
  {
    id: "ai-insights",
    name: "AI Insights",
    description: "Smart insights and recommendations",
    category: "statistics",
    icon: "Sparkles",
    defaultVisible: true,
    defaultSize: "medium",
  },
  {
    id: "peak-demand",
    name: "Peak Demand",
    description: "Peak demand analysis with hourly profile",
    category: "statistics",
    icon: "Gauge",
    defaultVisible: true,
    defaultSize: "medium",
  },
];

// Built-in layout presets
export const builtInPresets: LayoutPresetConfig[] = [
  {
    id: "essential",
    name: "Essential",
    description: "Minimal dashboard with key metrics only",
    widgets: [
      { id: "stat-cards", visible: true, size: "large" },
      { id: "energy-flow", visible: true, size: "large" },
      { id: "quick-actions", visible: true, size: "medium" },
      { id: "weather", visible: true, size: "medium" },
      { id: "system-diagram", visible: false, size: "large" },
      { id: "energy-chart", visible: false, size: "large" },
      { id: "goal-tracking", visible: false, size: "medium" },
      { id: "environmental-impact", visible: false, size: "medium" },
      { id: "load-shedding", visible: false, size: "medium" },
      { id: "billing-summary", visible: false, size: "medium" },
      { id: "device-overview", visible: false, size: "large" },
      { id: "alerts-summary", visible: false, size: "medium" },
      { id: "ai-insights", visible: false, size: "medium" },
      { id: "peak-demand", visible: false, size: "medium" },
    ],
  },
  {
    id: "standard",
    name: "Standard",
    description: "Balanced view with core features",
    widgets: [
      { id: "stat-cards", visible: true, size: "large" },
      { id: "energy-flow", visible: true, size: "large" },
      { id: "system-diagram", visible: true, size: "large" },
      { id: "energy-chart", visible: true, size: "large" },
      { id: "weather", visible: true, size: "medium" },
      { id: "quick-actions", visible: true, size: "medium" },
      { id: "goal-tracking", visible: true, size: "medium" },
      { id: "billing-summary", visible: true, size: "medium" },
      { id: "environmental-impact", visible: false, size: "medium" },
      { id: "load-shedding", visible: false, size: "medium" },
      { id: "device-overview", visible: false, size: "large" },
      { id: "alerts-summary", visible: false, size: "medium" },
      { id: "ai-insights", visible: false, size: "medium" },
      { id: "peak-demand", visible: false, size: "medium" },
    ],
  },
  {
    id: "comprehensive",
    name: "Comprehensive",
    description: "Full dashboard with all widgets enabled",
    widgets: [
      { id: "stat-cards", visible: true, size: "large" },
      { id: "energy-flow", visible: true, size: "large" },
      { id: "system-diagram", visible: true, size: "large" },
      { id: "energy-chart", visible: true, size: "large" },
      { id: "weather", visible: true, size: "medium" },
      { id: "quick-actions", visible: true, size: "medium" },
      { id: "goal-tracking", visible: true, size: "medium" },
      { id: "environmental-impact", visible: true, size: "medium" },
      { id: "load-shedding", visible: true, size: "medium" },
      { id: "billing-summary", visible: true, size: "medium" },
      { id: "device-overview", visible: true, size: "large" },
      { id: "alerts-summary", visible: true, size: "medium" },
      { id: "ai-insights", visible: true, size: "medium" },
      { id: "peak-demand", visible: true, size: "medium" },
    ],
  },
];

const defaultLayout: LayoutItem[] = widgetConfigs.map(config => ({
  id: config.id,
  visible: config.defaultVisible,
  size: config.defaultSize,
  settings: config.settings || {},
}));

const STORAGE_KEY = "dashboard-layout-v1";
const GRID_LAYOUT_KEY = "dashboard-grid-layout-v1";
const PRESET_KEY = "dashboard-preset-v1";
const CUSTOM_PRESETS_KEY = "dashboard-custom-presets-v1";

const DashboardLayoutContext = createContext<DashboardLayoutContextType | undefined>(undefined);

export function DashboardLayoutProvider({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState<LayoutItem[]>(defaultLayout);
  const [isEditMode, setIsEditMode] = useState(false);
  const [gridLayout, setGridLayoutState] = useState<GridLayout>("list");
  const [currentPreset, setCurrentPreset] = useState<LayoutPreset>("standard");
  const [customPresets, setCustomPresets] = useState<LayoutPresetConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Debounce timer for API persistence
  const saveTimeoutRef = useRef<NodeJS.Timeout>();

  // Load preferences from API on mount
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        setIsLoading(true);

        // Fetch dashboard preferences
        const prefs = await dashboardService.getPreferences();

        // Convert API format to internal format
        const apiLayout: LayoutItem[] = prefs.widget_layout.map(w => ({
          id: w.id as WidgetId,
          visible: w.visible,
          size: w.size as WidgetSize,
          settings: w.settings || {},
        }));

        // Merge with defaults to handle new widgets
        const mergedLayout = widgetConfigs.map(config => {
          const savedItem = apiLayout.find(item => item.id === config.id);
          return savedItem || {
            id: config.id,
            visible: config.defaultVisible,
            size: config.defaultSize,
            settings: config.settings || {},
          };
        });

        setLayout(mergedLayout);
        setGridLayoutState(prefs.grid_layout as GridLayout);
        setCurrentPreset(prefs.layout_preset);

        // Fetch custom presets
        const presetsData = await dashboardService.listPresets();
        const convertedPresets: LayoutPresetConfig[] = presetsData.presets.map(p => ({
          id: p.id,
          name: p.name,
          description: p.description || "",
          widgets: p.widget_config.map(w => ({
            id: w.id as WidgetId,
            visible: w.visible,
            size: w.size as WidgetSize,
          })),
        }));
        setCustomPresets(convertedPresets);
      } catch (error: any) {
        console.error("Failed to load dashboard preferences from API:", error);

        // If API fails, try to migrate from localStorage
        if (error.response?.status !== 401) {
          await migrateFromLocalStorage();
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadPreferences();
  }, []);

  // Migrate from localStorage to API (one-time migration)
  const migrateFromLocalStorage = async () => {
    try {
      const savedLayout = localStorage.getItem(STORAGE_KEY);
      const savedGridLayout = localStorage.getItem(GRID_LAYOUT_KEY);
      const savedPreset = localStorage.getItem(PRESET_KEY);
      const savedCustomPresets = localStorage.getItem(CUSTOM_PRESETS_KEY);

      if (savedLayout || savedGridLayout || savedPreset) {
        console.log("Migrating dashboard preferences from localStorage to API...");

        const layoutData = savedLayout ? JSON.parse(savedLayout) : defaultLayout;
        const mergedLayout = widgetConfigs.map(config => {
          const savedItem = layoutData.find((item: LayoutItem) => item.id === config.id);
          return savedItem || {
            id: config.id,
            visible: config.defaultVisible,
            size: config.defaultSize,
            settings: config.settings || {},
          };
        });

        setLayout(mergedLayout);
        setGridLayoutState((savedGridLayout as GridLayout) || "list");
        setCurrentPreset(savedPreset || "standard");

        // Save to API
        await dashboardService.updatePreferences({
          layout_preset: savedPreset || "standard",
          grid_layout: (savedGridLayout as GridLayout) || "list",
          widget_layout: mergedLayout.map(w => ({
            id: w.id,
            visible: w.visible,
            size: w.size,
            settings: w.settings,
          })),
        });

        // Migrate custom presets
        if (savedCustomPresets) {
          const customPresetsData: LayoutPresetConfig[] = JSON.parse(savedCustomPresets);
          for (const preset of customPresetsData) {
            try {
              await dashboardService.createPreset({
                name: preset.name,
                description: preset.description,
                widget_config: preset.widgets.map(w => ({
                  id: w.id,
                  visible: w.visible,
                  size: w.size,
                })),
              });
            } catch (err) {
              console.error("Failed to migrate custom preset:", preset.name, err);
            }
          }
        }

        // Clean up localStorage after successful migration
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(GRID_LAYOUT_KEY);
        localStorage.removeItem(PRESET_KEY);
        localStorage.removeItem(CUSTOM_PRESETS_KEY);

        toast.success("Dashboard preferences migrated successfully");
      }
    } catch (error) {
      console.error("Failed to migrate from localStorage:", error);
      // Fallback to defaults if migration fails
      setLayout(defaultLayout);
      setGridLayoutState("list");
      setCurrentPreset("standard");
    }
  };

  // Debounced save to API
  const saveToAPI = useCallback(async (
    layoutData: LayoutItem[],
    gridLayoutData: GridLayout,
    presetData: LayoutPreset
  ) => {
    try {
      await dashboardService.updatePreferences({
        layout_preset: presetData,
        grid_layout: gridLayoutData,
        widget_layout: layoutData.map(w => ({
          id: w.id,
          visible: w.visible,
          size: w.size,
          settings: w.settings,
        })),
      });
    } catch (error) {
      console.error("Failed to save dashboard preferences:", error);
      toast.error("Failed to save dashboard preferences");
    }
  }, []);

  // Debounced persist to API
  useEffect(() => {
    if (isLoading) return; // Don't save during initial load

    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Debounce API call by 1 second
    saveTimeoutRef.current = setTimeout(() => {
      saveToAPI(layout, gridLayout, currentPreset);
    }, 1000);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [layout, gridLayout, currentPreset, isLoading, saveToAPI]);

  const setGridLayout = (layoutValue: GridLayout) => {
    setGridLayoutState(layoutValue);
  };

  const toggleWidgetVisibility = (id: WidgetId) => {
    setLayout(prev => prev.map(item =>
      item.id === id ? { ...item, visible: !item.visible } : item
    ));
  };

  const reorderWidgets = (activeId: WidgetId, overId: WidgetId) => {
    setLayout(prev => {
      const oldIndex = prev.findIndex(item => item.id === activeId);
      const newIndex = prev.findIndex(item => item.id === overId);
      
      if (oldIndex === -1 || newIndex === -1) return prev;
      
      const newLayout = [...prev];
      const [removed] = newLayout.splice(oldIndex, 1);
      newLayout.splice(newIndex, 0, removed);
      
      return newLayout;
    });
  };

  const addWidget = (id: WidgetId) => {
    setLayout(prev => prev.map(item =>
      item.id === id ? { ...item, visible: true } : item
    ));
  };

  const removeWidget = (id: WidgetId) => {
    setLayout(prev => prev.map(item =>
      item.id === id ? { ...item, visible: false } : item
    ));
  };

  const updateWidgetSettings = (id: WidgetId, settings: Record<string, unknown>) => {
    setLayout(prev => prev.map(item =>
      item.id === id ? { ...item, settings: { ...item.settings, ...settings } } : item
    ));
  };

  const resizeWidget = (id: WidgetId, size: WidgetSize) => {
    setLayout(prev => prev.map(item =>
      item.id === id ? { ...item, size } : item
    ));
    // When user manually resizes, switch to custom preset
    if (currentPreset !== "custom") {
      setCurrentPreset("custom");
    }
  };

  const applyPreset = (presetId: LayoutPreset) => {
    const preset = [...builtInPresets, ...customPresets].find(p => p.id === presetId);
    if (!preset) return;

    const newLayout = widgetConfigs.map(config => {
      const presetWidget = preset.widgets.find(w => w.id === config.id);
      return {
        id: config.id,
        visible: presetWidget?.visible ?? config.defaultVisible,
        size: presetWidget?.size ?? config.defaultSize,
        settings: config.settings || {},
      };
    });

    setLayout(newLayout);
    setCurrentPreset(presetId);
  };

  const saveCustomPreset = async (name: string, description: string) => {
    try {
      const newPreset = await dashboardService.createPreset({
        name,
        description,
        widget_config: layout.map(item => ({
          id: item.id,
          visible: item.visible,
          size: item.size,
        })),
      });

      const convertedPreset: LayoutPresetConfig = {
        id: newPreset.id,
        name: newPreset.name,
        description: newPreset.description || "",
        widgets: newPreset.widget_config.map(w => ({
          id: w.id as WidgetId,
          visible: w.visible,
          size: w.size as WidgetSize,
        })),
      };

      setCustomPresets(prev => [...prev, convertedPreset]);
      setCurrentPreset(newPreset.id);
      toast.success("Custom preset saved successfully");
    } catch (error) {
      console.error("Failed to save custom preset:", error);
      toast.error("Failed to save custom preset");
    }
  };

  const deleteCustomPreset = async (presetId: string) => {
    try {
      await dashboardService.deletePreset(presetId);

      setCustomPresets(prev => prev.filter(p => p.id !== presetId));

      if (currentPreset === presetId) {
        setCurrentPreset("standard");
        applyPreset("standard");
      }

      toast.success("Custom preset deleted");
    } catch (error) {
      console.error("Failed to delete custom preset:", error);
      toast.error("Failed to delete custom preset");
    }
  };

  const resetToDefault = () => {
    setLayout(defaultLayout);
    setCurrentPreset("standard");
  };

  const getWidgetConfig = (id: WidgetId) => {
    return widgetConfigs.find(config => config.id === id);
  };

  const visibleWidgets = layout.filter(item => item.visible);
  const hiddenWidgets = widgetConfigs.filter(
    config => !layout.find(item => item.id === config.id)?.visible
  );

  return (
    <DashboardLayoutContext.Provider value={{
      layout,
      isEditMode,
      gridLayout,
      currentPreset,
      customPresets,
      builtInPresets,
      isLoading,
      setIsEditMode,
      setGridLayout,
      toggleWidgetVisibility,
      reorderWidgets,
      addWidget,
      removeWidget,
      updateWidgetSettings,
      resizeWidget,
      applyPreset,
      saveCustomPreset,
      deleteCustomPreset,
      resetToDefault,
      getWidgetConfig,
      visibleWidgets,
      hiddenWidgets,
    }}>
      {children}
    </DashboardLayoutContext.Provider>
  );
}

export function useDashboardLayout() {
  const context = useContext(DashboardLayoutContext);
  if (!context) {
    throw new Error("useDashboardLayout must be used within a DashboardLayoutProvider");
  }
  return context;
}
