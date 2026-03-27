import { useState, useCallback, useMemo, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { DeviceCard } from "@/components/devices/DeviceCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, SearchSuggestions } from "@/components/ui/empty-state";
import { Plus, Search, Filter, HardHat, Activity, Settings, RefreshCw, Loader2, QrCode } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useUserRole } from "@/contexts/UserRoleContext";
import { SwipeableItem } from "@/components/mobile/SwipeableItem";
import { FloatingActionButton } from "@/components/mobile/MobileActionButtons";
import { toast } from "sonner";
import { useIsMobile } from "@/hooks/use-mobile";
import { useDevicesForUI } from "@/hooks/useDevices";
import { dashboardService, type DevicePowerData } from "@/api";
import devicesService from "@/api/services/devices.service";
import type { DeviceType, DeviceStatus } from "@/api/types";

const DevicesPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission, isInstaller } = useUserRole();
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const showCommissioning = hasPermission("commissioning_mode") || isInstaller;

  // Build API filters
  const apiFilters = useMemo(() => ({
    device_type: typeFilter !== "all" ? typeFilter as DeviceType : undefined,
    status: statusFilter !== "all" ? statusFilter as DeviceStatus : undefined,
    search: searchQuery || undefined,
  }), [typeFilter, statusFilter, searchQuery]);

  // Fetch devices from API
  const { devices, total, isLoading, error, refresh } = useDevicesForUI({
    filters: apiFilters,
    autoRefresh: true,
    refreshInterval: 30000,
  });

  // Fetch real-time telemetry from power-flow API
  const [telemetryMap, setTelemetryMap] = useState<Map<string, DevicePowerData>>(new Map());

  const fetchTelemetry = useCallback(async () => {
    try {
      const powerFlow = await dashboardService.getPowerFlow();
      if (powerFlow.devices && powerFlow.devices.length > 0) {
        const newMap = new Map<string, DevicePowerData>();
        for (const device of powerFlow.devices) {
          newMap.set(device.serial_number, device);
        }
        setTelemetryMap(newMap);
      }
    } catch (err) {
      console.warn('Failed to fetch power flow telemetry:', err);
    }
  }, []);

  // Initial fetch and polling for telemetry
  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, [fetchTelemetry]);

  const handleRefresh = useCallback(async () => {
    // Trigger haptic feedback
    if ('vibrate' in navigator) {
      navigator.vibrate(10);
    }
    await Promise.all([refresh(), fetchTelemetry()]);
    toast.success("Devices refreshed");
  }, [refresh, fetchTelemetry]);

  // For backward compatibility, filteredDevices is now just devices from API
  const filteredDevices = devices;

  const handleViewDetails = (deviceId: string) => {
    navigate(`/devices/${deviceId}`);
  };

  const handleConfigure = (deviceId: string) => {
    navigate(`/devices/${deviceId}/settings`);
  };

  const handleViewTelemetry = (deviceId: string) => {
    navigate(`/telemetry?device=${deviceId}`);
  };

  const unclaimMutation = useMutation({
    mutationFn: (deviceId: string) => devicesService.unclaimDevice(deviceId),
    onSuccess: () => {
      toast.success("Device unclaimed successfully");
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    },
    onError: () => toast.error("Failed to unclaim device"),
  });

  const removeMutation = useMutation({
    mutationFn: (deviceId: string) => devicesService.deleteDevice(deviceId),
    onSuccess: () => {
      toast.success("Device removed successfully");
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    },
    onError: () => toast.error("Failed to remove device"),
  });

  return (
    <AppLayout>
      <AppHeader 
        title="Devices" 
        subtitle="Manage your solar installation equipment"
      />
      
      <div className="p-3 sm:p-6 space-y-3 sm:space-y-6">
        {/* Filters */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-3 sm:p-4"
        >
          <div className="flex flex-col gap-3 sm:gap-4">
            {/* Search */}
            <div className="relative w-full">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name or serial..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-secondary/50 h-9 sm:h-10 text-sm"
              />
            </div>

            {/* Filter Row */}
            <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-full sm:w-[130px] bg-secondary/50 h-9 sm:h-10 text-xs sm:text-sm">
                  <Filter className="w-3.5 h-3.5 sm:w-4 sm:h-4 mr-1.5 sm:mr-2 flex-shrink-0" />
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="inverter">Inverters</SelectItem>
                  <SelectItem value="battery">Batteries</SelectItem>
                  <SelectItem value="meter">Meters</SelectItem>
                </SelectContent>
              </Select>

              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-[130px] bg-secondary/50 h-9 sm:h-10 text-xs sm:text-sm">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="online">Online</SelectItem>
                  <SelectItem value="offline">Offline</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                </SelectContent>
              </Select>

              <Button className="w-full sm:w-auto gap-1.5 sm:gap-2 h-9 sm:h-10 text-xs sm:text-sm" onClick={() => navigate("/devices/manage")}>
                <Plus className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                <span>Add</span>
              </Button>

              <Button
                variant="outline"
                className="w-full sm:w-auto gap-1.5 sm:gap-2 h-9 sm:h-10 text-xs sm:text-sm"
                onClick={() => navigate("/devices/claim")}
              >
                <QrCode className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                <span>Claim</span>
              </Button>

              {showCommissioning && (
                <Button
                  variant="outline"
                  className="col-span-2 sm:col-span-1 sm:w-auto gap-1.5 sm:gap-2 h-9 sm:h-10 text-xs sm:text-sm border-amber-500/50 text-amber-600 hover:bg-amber-500/10"
                  onClick={() => navigate("/commissioning")}
                >
                  <HardHat className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  <span>Commissioning</span>
                </Button>
              )}
            </div>
          </div>
        </motion.div>

        {/* Device Count */}
        <div className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground">
          {isLoading ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 animate-spin" />
              Loading devices...
            </span>
          ) : error ? (
            <span className="text-destructive">{error}</span>
          ) : (
            <span>Showing {filteredDevices.length} of {total} devices</span>
          )}
        </div>

        {/* Device Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-6">
          {filteredDevices.map((device, index) => {
            // Get real-time telemetry for this device by serial number
            const deviceTelemetry = telemetryMap.get(device.serialNumber);
            const cardContent = (
              <DeviceCard
                key={device.id}
                {...device}
                telemetry={deviceTelemetry}
                delay={index * 0.1}
                onViewDetails={() => handleViewDetails(device.id)}
                onConfigure={() => handleConfigure(device.id)}
                onViewTelemetry={() => handleViewTelemetry(device.id)}
                onUnclaim={() => unclaimMutation.mutate(device.id)}
                onRemove={() => removeMutation.mutate(device.id)}
              />
            );

            // Wrap in SwipeableItem on mobile
            if (isMobile) {
              return (
                <SwipeableItem
                  key={device.id}
                  onSwipeLeft={() => handleViewTelemetry(device.id)}
                  onSwipeRight={() => handleConfigure(device.id)}
                  leftAction={{
                    icon: <Activity className="w-5 h-5" />,
                    label: "Telemetry",
                    color: "text-primary",
                    bgColor: "bg-primary/20",
                  }}
                  rightAction={{
                    icon: <Settings className="w-5 h-5" />,
                    label: "Settings",
                    color: "text-muted-foreground",
                    bgColor: "bg-muted",
                  }}
                >
                  {cardContent}
                </SwipeableItem>
              );
            }

            return cardContent;
          })}
        </div>

        {filteredDevices.length === 0 && devices.length > 0 && (
          <EmptyState
            type="no-results"
            title="No Devices Found"
            description="No devices match your current filters. Try adjusting your search criteria."
          >
            <SearchSuggestions
              suggestions={["Inverter", "Battery", "Online"]}
              onSuggestionClick={(s) => setSearchQuery(s)}
            />
          </EmptyState>
        )}

        {!isLoading && filteredDevices.length === 0 && total === 0 && (
          <EmptyState
            type="no-devices"
            action={{
              label: "Add Your First Device",
              onClick: () => navigate("/devices/manage"),
            }}
          />
        )}
      </div>

      {/* Floating Refresh Button (mobile only) */}
      <FloatingActionButton
        icon={<RefreshCw className={`w-6 h-6 ${isLoading ? 'animate-spin' : ''}`} />}
        onClick={handleRefresh}
        label="Refresh devices"
        position="bottom-right"
      />
    </AppLayout>
  );
};

export default DevicesPage;
