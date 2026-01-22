import { createContext, useContext, useState, useEffect, ReactNode } from "react";

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
  | "ai-insights";

export type WidgetCategory = "statistics" | "charts" | "status" | "actions";

export type GridLayout = "list" | "2x2" | "3x3";

export interface WidgetConfig {
  id: WidgetId;
  name: string;
  description: string;
  category: WidgetCategory;
  icon: string;
  defaultVisible: boolean;
  settings?: Record<string, unknown>;
}

export interface LayoutItem {
  id: WidgetId;
  visible: boolean;
  settings: Record<string, unknown>;
}

interface DashboardLayoutContextType {
  layout: LayoutItem[];
  isEditMode: boolean;
  gridLayout: GridLayout;
  setIsEditMode: (value: boolean) => void;
  setGridLayout: (layout: GridLayout) => void;
  toggleWidgetVisibility: (id: WidgetId) => void;
  reorderWidgets: (activeId: WidgetId, overId: WidgetId) => void;
  addWidget: (id: WidgetId) => void;
  removeWidget: (id: WidgetId) => void;
  updateWidgetSettings: (id: WidgetId, settings: Record<string, unknown>) => void;
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
  },
  {
    id: "energy-flow",
    name: "Energy Flow Diagram",
    description: "Real-time power flow visualization",
    category: "charts",
    icon: "Zap",
    defaultVisible: true,
  },
  {
    id: "system-diagram",
    name: "System Diagram",
    description: "Visual system hierarchy overview",
    category: "status",
    icon: "Cpu",
    defaultVisible: true,
  },
  {
    id: "energy-chart",
    name: "Energy Chart",
    description: "Historical energy data with time selector",
    category: "charts",
    icon: "LineChart",
    defaultVisible: true,
    settings: { period: "day" },
  },
  {
    id: "weather",
    name: "Weather Widget",
    description: "Current weather and solar forecast",
    category: "status",
    icon: "Sun",
    defaultVisible: true,
  },
  {
    id: "quick-actions",
    name: "Quick Actions",
    description: "Common system commands",
    category: "actions",
    icon: "Zap",
    defaultVisible: true,
  },
  {
    id: "goal-tracking",
    name: "Goal Progress",
    description: "Track savings and production goals",
    category: "statistics",
    icon: "Target",
    defaultVisible: true,
  },
  {
    id: "environmental-impact",
    name: "Environmental Impact",
    description: "CO2 savings and eco metrics",
    category: "statistics",
    icon: "Leaf",
    defaultVisible: true,
  },
  {
    id: "load-shedding",
    name: "Load Shedding Status",
    description: "Grid outage schedule and battery backup",
    category: "status",
    icon: "ZapOff",
    defaultVisible: true,
  },
  {
    id: "billing-summary",
    name: "Billing Summary",
    description: "Monthly billing overview",
    category: "statistics",
    icon: "Receipt",
    defaultVisible: true,
  },
  {
    id: "device-overview",
    name: "Device Status Grid",
    description: "Overview of all connected devices",
    category: "status",
    icon: "Server",
    defaultVisible: false,
  },
  {
    id: "alerts-summary",
    name: "Alerts Summary",
    description: "Recent system alerts",
    category: "status",
    icon: "AlertTriangle",
    defaultVisible: false,
  },
  {
    id: "ai-insights",
    name: "AI Insights",
    description: "Smart insights and recommendations",
    category: "statistics",
    icon: "Sparkles",
    defaultVisible: true,
  },
];

const defaultLayout: LayoutItem[] = widgetConfigs.map(config => ({
  id: config.id,
  visible: config.defaultVisible,
  settings: config.settings || {},
}));

const STORAGE_KEY = "dashboard-layout-v1";
const GRID_LAYOUT_KEY = "dashboard-grid-layout-v1";

const DashboardLayoutContext = createContext<DashboardLayoutContextType | undefined>(undefined);

export function DashboardLayoutProvider({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState<LayoutItem[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        // Merge with defaults to handle new widgets
        const mergedLayout = widgetConfigs.map(config => {
          const savedItem = parsed.find((item: LayoutItem) => item.id === config.id);
          return savedItem || {
            id: config.id,
            visible: config.defaultVisible,
            settings: config.settings || {},
          };
        });
        return mergedLayout;
      }
    } catch (e) {
      console.error("Failed to load dashboard layout", e);
    }
    return defaultLayout;
  });

  const [isEditMode, setIsEditMode] = useState(false);
  const [gridLayout, setGridLayoutState] = useState<GridLayout>(() => {
    try {
      const saved = localStorage.getItem(GRID_LAYOUT_KEY);
      return (saved as GridLayout) || "list";
    } catch {
      return "list";
    }
  });

  const setGridLayout = (layout: GridLayout) => {
    setGridLayoutState(layout);
    try {
      localStorage.setItem(GRID_LAYOUT_KEY, layout);
    } catch (e) {
      console.error("Failed to save grid layout", e);
    }
  };

  // Persist layout changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
    } catch (e) {
      console.error("Failed to save dashboard layout", e);
    }
  }, [layout]);

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

  const resetToDefault = () => {
    setLayout(defaultLayout);
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
      setIsEditMode,
      setGridLayout,
      toggleWidgetVisibility,
      reorderWidgets,
      addWidget,
      removeWidget,
      updateWidgetSettings,
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
