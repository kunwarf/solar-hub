import { useState, useCallback, useMemo } from "react";
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
import type { DeviceType, DeviceStatus } from "@/api/types";

const DevicesPage = () => {
  const navigate = useNavigate();
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

  const handleRefresh = useCallback(async () => {
    // Trigger haptic feedback
    if ('vibrate' in navigator) {
      navigator.vibrate(10);
    }
    await refresh();
    toast.success("Devices refreshed");
  }, [refresh]);

  // For backward compatibility, filteredDevices is now just devices from API
  const filteredDevices = devices;

  const handleConfigure = (deviceId: string) => {
    navigate(`/devices/${deviceId}/settings`);
  };

  const handleViewTelemetry = (deviceId: string) => {
    navigate(`/telemetry?device=${deviceId}`);
  };

  return (
    <AppLayout>
      <AppHeader 
        title="Devices" 
        subtitle="Manage your solar installation equipment"
      />
      
      <div className="p-6 space-y-6">
        {/* Filters */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4"
        >
          <div className="flex flex-col gap-4">
            {/* Search */}
            <div className="relative w-full">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name or serial..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-secondary/50"
              />
            </div>
            
            {/* Filter Row */}
            <div className="flex flex-wrap gap-2">
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-full sm:w-[130px] bg-secondary/50">
                  <Filter className="w-4 h-4 mr-2 flex-shrink-0" />
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
                <SelectTrigger className="w-full sm:w-[130px] bg-secondary/50">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="online">Online</SelectItem>
                  <SelectItem value="offline">Offline</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                </SelectContent>
              </Select>

              <Button className="w-full sm:w-auto gap-2" onClick={() => navigate("/devices/manage")}>
                <Plus className="w-4 h-4" />
                <span className="sm:inline">Add Device</span>
              </Button>

              <Button
                variant="outline"
                className="w-full sm:w-auto gap-2"
                onClick={() => navigate("/devices/claim")}
              >
                <QrCode className="w-4 h-4" />
                <span className="sm:inline">Claim Device</span>
              </Button>
              
              {showCommissioning && (
                <Button 
                  variant="outline" 
                  className="w-full sm:w-auto gap-2 border-amber-500/50 text-amber-600 hover:bg-amber-500/10"
                  onClick={() => navigate("/commissioning")}
                >
                  <HardHat className="w-4 h-4" />
                  <span className="sm:inline">Commissioning</span>
                </Button>
              )}
            </div>
          </div>
        </motion.div>

        {/* Device Count */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          {isLoading ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading devices...
            </span>
          ) : error ? (
            <span className="text-destructive">{error}</span>
          ) : (
            <span>Showing {filteredDevices.length} of {total} devices</span>
          )}
        </div>

        {/* Device Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredDevices.map((device, index) => {
            const cardContent = (
              <DeviceCard
                key={device.id}
                {...device}
                delay={index * 0.1}
                onConfigure={() => handleConfigure(device.id)}
                onViewTelemetry={() => handleViewTelemetry(device.id)}
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
