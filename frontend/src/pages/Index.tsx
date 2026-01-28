import { useState, useEffect, useMemo, useCallback } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { StatCard } from "@/components/dashboard/StatCard";
import { EnergyFlowDiagram } from "@/components/dashboard/EnergyFlowDiagram";
import { EnergyChart } from "@/components/dashboard/EnergyChart";
import { BillingSummary } from "@/components/dashboard/BillingSummary";
import { VisualSystemDiagram } from "@/components/dashboard/VisualSystemDiagram";
import { WeatherWidget } from "@/components/dashboard/WeatherWidget";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { SystemStatusIndicator } from "@/components/dashboard/SystemStatusIndicator";
import { LoadSheddingTracker } from "@/components/dashboard/LoadSheddingTracker";
import { ComparisonChart } from "@/components/dashboard/ComparisonChart";
import { GoalTrackingWidget } from "@/components/dashboard/GoalTrackingWidget";
import { EnvironmentalImpactWidget } from "@/components/dashboard/EnvironmentalImpactWidget";
import { AIInsightsWidget } from "@/components/dashboard/AIInsightsWidget";
import { DashboardEditControls } from "@/components/dashboard/DashboardEditControls";
import { DraggableWidget } from "@/components/dashboard/DraggableWidget";
import SetupWizard from "@/components/wizard/SetupWizard";
import DashboardTour from "@/components/wizard/DashboardTour";
import { Sun, Battery, Home, Zap, TrendingUp, ArrowDownUp, Leaf, DollarSign, Receipt, Target, Gauge, ChevronDown, ChevronUp, Clock, Info } from "lucide-react";
import { useEnergyData } from "@/hooks/useEnergyData";
import { useUserMode } from "@/hooks/use-user-mode";
import { useSetupWizard } from "@/hooks/use-setup-wizard";
import { useTelemetry } from "@/contexts/TelemetryContext";
import { useDashboardLayout, WidgetId, GridLayout } from "@/contexts/DashboardLayoutContext";
import { DndContext, closestCenter, DragEndEvent, PointerSensor, useSensor, useSensors, DragOverlay, DragStartEvent } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy, rectSortingStrategy } from "@dnd-kit/sortable";
import ConnectionStatusIndicator from "@/components/dashboard/ConnectionStatusIndicator";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { devicesService } from "@/api/services/devices.service";

// Mock billing data for dashboard summary
const billingSummaryData = {
  currentMonthEstimate: 47.20,
  lastMonthBill: 81.38,
  exportCredits: 124.80,
  exportedKwh: 520,
  totalSavings: 4892.50,
  importRate: 0.28,
  exportRate: 0.24,
  peakHoursStart: "2PM",
  peakHoursEnd: "7PM",
};

// Mock backup time calculation (based on battery level and average consumption)
const calculateBackupTime = (batteryLevel: number, avgConsumption: number) => {
  const batteryCapacity = 13.5; // kWh (typical home battery)
  const usableEnergy = (batteryLevel / 100) * batteryCapacity;
  return avgConsumption > 0 ? (usableEnergy / avgConsumption).toFixed(1) : "0";
};

const Index = () => {
  const { stats, chartData, widgetsData } = useEnergyData();
  const { isAdvanced } = useUserMode();
  const { shouldShowWizard, openWizard } = useSetupWizard();
  const { telemetry, isLive } = useTelemetry();
  const { visibleWidgets, isEditMode, reorderWidgets, getWidgetConfig, gridLayout } = useDashboardLayout();
  const [showAllStats, setShowAllStats] = useState(false);
  const [activeId, setActiveId] = useState<WidgetId | null>(null);
  const [firstDeviceId, setFirstDeviceId] = useState<string | undefined>();

  // Fetch first online device ID for QuickActions
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await devicesService.listDevices({ status: "online" as any }, { page: 1, page_size: 1 });
        if (!cancelled && result.items?.length > 0) {
          setFirstDeviceId(result.items[0].id);
        }
      } catch {
        // QuickActions will fall back to local-only mode without a device ID
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Drag sensors with better touch support
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as WidgetId);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);
    if (over && active.id !== over.id) {
      reorderWidgets(active.id as WidgetId, over.id as WidgetId);
    }
  };

  const isWidgetVisible = (id: WidgetId) => {
    return visibleWidgets.some(w => w.id === id);
  };

  // Get sorted widget IDs for SortableContext
  const sortedWidgetIds = useMemo(() => 
    visibleWidgets.map(w => w.id),
    [visibleWidgets]
  );

  // Use real-time telemetry data when available, fallback to mock data
  const liveStats = isLive && telemetry ? {
    solarPower: telemetry.solarPower,
    batteryPower: telemetry.batteryPower,
    batteryLevel: telemetry.batteryLevel,
    consumption: telemetry.consumption,
    gridPower: telemetry.gridPower,
    isGridExporting: telemetry.isGridExporting,
  } : {
    solarPower: stats.solarPower,
    batteryPower: stats.batteryPower,
    batteryLevel: stats.batteryLevel,
    consumption: stats.consumption,
    gridPower: stats.gridPower,
    isGridExporting: stats.isGridExporting,
  };

  const backupTimeHours = calculateBackupTime(liveStats.batteryLevel, liveStats.consumption);

  // Auto-open wizard for new users
  useEffect(() => {
    if (shouldShowWizard) {
      const timer = setTimeout(() => {
        openWizard();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [shouldShowWizard, openWizard]);

  // Priority stats - always visible (Financial focus first per requirements)
  const priorityStats = [
    {
      title: "Monthly Bill Estimate",
      value: Math.round(stats.monthlyBillAmount).toString(),
      unit: "$",
      icon: Receipt,
      variant: "financial" as const,
      tooltip: "Estimated electricity bill for current month based on usage patterns",
      delay: 0,
    },
    {
      title: "This Month Savings",
      value: Math.round(stats.moneySaved * 30).toString(),
      unit: "$",
      icon: DollarSign,
      variant: "savings" as const,
      trend: { value: 8, isPositive: true },
      tooltip: "Money saved this month by using solar instead of grid power",
      delay: 0.05,
    },
    {
      title: "Backup Time",
      value: backupTimeHours,
      unit: "hrs",
      icon: Clock,
      variant: "backup" as const,
      tooltip: "Estimated hours of backup power available based on current battery level and consumption",
      delay: 0.1,
    },
    {
      title: "CO₂ Saved Today",
      value: Math.round(stats.co2Saved).toString(),
      unit: "kg",
      icon: Leaf,
      variant: "eco" as const,
      trend: { value: 15, isPositive: true },
      tooltip: "Carbon dioxide emissions avoided by using clean solar energy",
      delay: 0.15,
    },
    {
      title: "Today's Production",
      value: Math.round(stats.dailyProduction).toString(),
      unit: "kWh",
      icon: TrendingUp,
      variant: "production" as const,
      tooltip: "Total solar energy produced today",
      delay: 0.2,
    },
    {
      title: "Self-Consumption",
      value: stats.selfConsumption.toString(),
      unit: "%",
      icon: Home,
      variant: "consumption" as const,
      tooltip: "Percentage of solar production used directly by your home",
      delay: 0.25,
    },
  ];

  // Advanced stats - only visible in advanced mode or when expanded
  const advancedStats = [
    {
      title: "Predicted vs Actual",
      value: `${Math.round(stats.dailyProduction)}/${Math.round(stats.dailyPrediction)}`,
      unit: "kWh",
      icon: Target,
      variant: "prediction" as const,
      trend: { value: Math.round((stats.dailyProduction / stats.dailyPrediction) * 100 - 100), isPositive: stats.dailyProduction >= stats.dailyPrediction },
      tooltip: "Actual production compared to predicted production based on weather forecasts",
      delay: 0.3,
    },
    {
      title: "Avg kWh/kWp",
      value: Math.round(stats.avgKwPerKwp).toString(),
      unit: "kWh/kWp",
      icon: Gauge,
      variant: "default" as const,
      tooltip: "Average energy yield per kilowatt-peak of installed solar capacity",
      delay: 0.35,
    },
  ];

  // Combine stats based on mode
  const visibleStats = isAdvanced ? [...priorityStats, ...advancedStats] : priorityStats;

  // Render widget by ID
  const renderWidget = (widgetId: WidgetId) => {
    switch (widgetId) {
      case "stat-cards":
        return (
          <>
            {/* Desktop: show based on mode */}
            <div data-tour="stats" className="hidden sm:grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
              {visibleStats.map((stat) => (
                <StatCard key={stat.title} {...stat} />
              ))}
            </div>
            {/* Mobile: Priority cards + See More */}
            <div className="sm:hidden space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {priorityStats.slice(0, 4).map((stat) => (
                  <StatCard key={stat.title} {...stat} compact />
                ))}
              </div>
              <AnimatePresence>
                {showAllStats && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.3 }}
                    className="grid grid-cols-2 gap-3 overflow-hidden"
                  >
                    {[...priorityStats.slice(4), ...(isAdvanced ? advancedStats : [])].map((stat) => (
                      <StatCard key={stat.title} {...stat} compact />
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
              {(priorityStats.length > 4 || isAdvanced) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowAllStats(!showAllStats)}
                  className="w-full text-muted-foreground hover:text-foreground"
                >
                  {showAllStats ? (
                    <>
                      <ChevronUp className="w-4 h-4 mr-2" />
                      Show Less
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-4 h-4 mr-2" />
                      See All Stats ({priorityStats.length - 4 + (isAdvanced ? advancedStats.length : 0)} more)
                    </>
                  )}
                </Button>
              )}
            </div>
          </>
        );
      case "weather":
        return <WeatherWidget />;
      case "quick-actions":
        return <QuickActions data-tour="quick-actions" deviceId={firstDeviceId} />;
      case "load-shedding":
        return <LoadSheddingTracker />;
      case "energy-flow":
        return (
          <div data-tour="power-flow">
            <EnergyFlowDiagram
              solarPower={liveStats.solarPower}
              batteryPower={liveStats.batteryPower}
              batteryLevel={liveStats.batteryLevel}
              consumption={liveStats.consumption}
              gridPower={liveStats.gridPower}
              isGridExporting={liveStats.isGridExporting}
              className="h-full"
            />
          </div>
        );
      case "billing-summary":
        return (
          <div data-tour="savings">
            <BillingSummary
              currentMonthEstimate={billingSummaryData.currentMonthEstimate}
              lastMonthBill={billingSummaryData.lastMonthBill}
              exportCredits={billingSummaryData.exportCredits}
              exportedKwh={billingSummaryData.exportedKwh}
              totalSavings={billingSummaryData.totalSavings}
              importRate={billingSummaryData.importRate}
              exportRate={billingSummaryData.exportRate}
              peakHoursStart={billingSummaryData.peakHoursStart}
              peakHoursEnd={billingSummaryData.peakHoursEnd}
              className="h-full"
            />
          </div>
        );
      case "energy-chart":
        return <EnergyChart data={chartData} title="Energy Overview - Today" />;
      case "goal-tracking":
        return <GoalTrackingWidget />;
      case "environmental-impact":
        return <EnvironmentalImpactWidget />;
      case "system-diagram":
        return <VisualSystemDiagram />;
      case "ai-insights":
        return <AIInsightsWidget />;
      default:
        return null;
    }
  };

  return (
    <AppLayout>
      {/* Setup Wizard for new users */}
      <SetupWizard />
      
      {/* Dashboard Tour overlay */}
      <DashboardTour />
      
      <AppHeader 
        title="Dashboard" 
        subtitle="Real-time energy monitoring and analytics"
        rightContent={
          <div className="flex items-center gap-1.5 sm:gap-3">
            <DashboardEditControls />
            <ConnectionStatusIndicator showLabel showReconnect />
            <SystemStatusIndicator compact />
          </div>
        }
      />

      {/* Edit Mode Instructions */}
      <AnimatePresence>
        {isEditMode && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-primary/5 border-b border-primary/20 overflow-hidden"
          >
            <div className="container mx-auto px-3 sm:px-6 py-2 sm:py-3">
              <div className="flex items-center gap-2 text-xs sm:text-sm text-primary">
                <Info className="w-4 h-4" />
                <span><strong>Edit Mode:</strong> Drag widgets by the handle to reorder. Click × to hide. Use "Add Widget" to show hidden widgets.</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      <DndContext 
        sensors={sensors} 
        collisionDetection={closestCenter} 
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext 
          items={sortedWidgetIds} 
          strategy={gridLayout === "list" ? verticalListSortingStrategy : rectSortingStrategy}
        >
          <div className={cn(
            "p-3 sm:p-6",
            gridLayout === "list" && "space-y-3 sm:space-y-6",
            gridLayout === "2x2" && "grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-6",
            gridLayout === "3x3" && "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-6"
          )}>
            {/* Render widgets in order from visibleWidgets */}
            {visibleWidgets.map((widget) => (
              <DraggableWidget 
                key={widget.id} 
                id={widget.id}
                className={cn(
                  gridLayout !== "list" && "h-full",
                  // Full-width widgets in grid mode
                  gridLayout !== "list" && (widget.id === "stat-cards" || widget.id === "energy-chart") && "md:col-span-2",
                  gridLayout === "3x3" && (widget.id === "stat-cards" || widget.id === "energy-chart") && "lg:col-span-3"
                )}
              >
                {renderWidget(widget.id)}
              </DraggableWidget>
            ))}

            {/* Production Comparison Chart (not draggable) */}
            {isWidgetVisible("energy-chart") && (
              <div className={cn(
                gridLayout === "2x2" && "md:col-span-2",
                gridLayout === "3x3" && "lg:col-span-3"
              )}>
                <ComparisonChart title="Production Comparison" />
              </div>
            )}
          </div>
        </SortableContext>

        {/* Drag Overlay */}
        <DragOverlay>
          {activeId ? (
            <div className="opacity-80 shadow-2xl rounded-lg">
              <div className="p-4 bg-card border rounded-lg">
                <p className="text-sm font-medium">{getWidgetConfig(activeId)?.name}</p>
              </div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </AppLayout>
  );
};

export default Index;
