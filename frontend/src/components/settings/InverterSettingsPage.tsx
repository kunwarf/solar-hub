/**
 * REFACTORED InverterSettingsPage using useDeviceSettings hook
 *
 * This version:
 * 1. Uses the useDeviceSettings hook instead of manual state management
 * 2. Prevents repeated API calls
 * 3. Has better error handling and loading states
 * 4. Properly displays settings from the device
 */

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Info,
  Zap,
  Battery,
  Settings2,
  Clock,
  Power,
  Cpu,
  Edit3,
  Check,
  X,
  Plus,
  Trash2,
  Loader2,
  RefreshCw,
  Save,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useDeviceSettings } from "@/hooks/useDeviceSettings";
import { toast } from "@/hooks/use-toast";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface InverterSettingsPageProps {
  deviceId: string;
}

export function InverterSettingsPage({ deviceId }: InverterSettingsPageProps) {
  // Use the useDeviceSettings hook - this handles all caching, polling, and state management
  const {
    settings,
    isLoading,
    isQuerying,
    isUpdating,
    isStale,
    isDeviceOffline,
    usingFallback,
    lastSyncedAt,
    error,
    queryDevice,
    updateDevice,
    refresh,
  } = useDeviceSettings({
    deviceId,
    deviceType: 'inverter',
    enabled: true,
    pollInterval: 60000, // Poll every 60 seconds instead of on every mount
  });

  const [hasChanges, setHasChanges] = useState(false);
  const [localSettings, setLocalSettings] = useState<Record<string, any>>({});

  // Initialize local settings when device settings load
  useEffect(() => {
    if (settings) {
      console.log('[InverterSettings] Settings loaded from device:', settings);
      setLocalSettings({ ...settings });
      setHasChanges(false);
    }
  }, [settings]);

  // Track changes
  useEffect(() => {
    if (settings && Object.keys(localSettings).length > 0) {
      const changed = JSON.stringify(localSettings) !== JSON.stringify(settings);
      setHasChanges(changed);
    }
  }, [localSettings, settings]);

  const handleSave = async () => {
    if (!hasChanges) {
      toast({ title: "No changes to save" });
      return;
    }

    try {
      await updateDevice(localSettings);
      toast({
        title: "Settings Updated",
        description: "Successfully updated device settings",
      });
      setHasChanges(false);
    } catch (err: any) {
      console.error("Failed to save settings:", err);
      toast({
        title: "Save Failed",
        description: err.message || "Could not update device settings",
        variant: "destructive",
      });
    }
  };

  const handleRefresh = async () => {
    console.log('[InverterSettings] Manual refresh triggered');
    await refresh();
  };

  const updateLocalSetting = (key: string, value: any) => {
    setLocalSettings(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
        <p className="text-sm text-muted-foreground">Loading device settings...</p>
      </div>
    );
  }

  // Error state (only if no settings available at all)
  if (error && !settings) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-destructive mb-4" />
        <div className="text-destructive mb-2 font-semibold">Failed to load settings</div>
        <p className="text-sm text-muted-foreground mb-4">{error.message}</p>
        <Button onClick={handleRefresh} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  // No settings loaded yet
  if (!settings || Object.keys(settings).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-warning mb-4" />
        <div className="text-warning mb-2 font-semibold">No settings available</div>
        <p className="text-sm text-muted-foreground mb-4">
          Unable to load settings from the device
        </p>
        <Button onClick={handleRefresh} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Query Device
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with Save/Refresh buttons */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Inverter Settings</h2>
          <p className="text-sm text-muted-foreground">
            Configure your inverter parameters
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleRefresh}
            variant="outline"
            size="sm"
            disabled={isLoading || isQuerying || isUpdating}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", isQuerying && "animate-spin")} />
            Refresh
          </Button>
          <Button
            onClick={handleSave}
            size="sm"
            disabled={!hasChanges || isUpdating}
          >
            {isUpdating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Status Alerts */}
      {isDeviceOffline && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Device is offline. {usingFallback && "Showing cached settings from " + new Date(lastSyncedAt || "").toLocaleString()}
          </AlertDescription>
        </Alert>
      )}

      {isStale && !isDeviceOffline && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Settings may be outdated. Click Refresh to get the latest values.
          </AlertDescription>
        </Alert>
      )}

      {hasChanges && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            You have unsaved changes. Click "Save Changes" to apply them to the device.
          </AlertDescription>
        </Alert>
      )}

      {/* Settings Display */}
      <div className="glass-card p-6">
        <h3 className="text-lg font-semibold mb-4">Current Settings</h3>

        {/* Display all settings in a simple grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(localSettings).map(([key, value]) => (
            <div key={key} className="border-b border-border/50 pb-2">
              <Label className="text-sm text-muted-foreground">{key}</Label>
              <div className="flex items-center gap-2 mt-1">
                <Input
                  value={typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  onChange={(e) => {
                    try {
                      // Try to parse as JSON first
                      const parsed = JSON.parse(e.target.value);
                      updateLocalSetting(key, parsed);
                    } catch {
                      // If not JSON, treat as string/number
                      const numValue = Number(e.target.value);
                      updateLocalSetting(key, isNaN(numValue) ? e.target.value : numValue);
                    }
                  }}
                  className="bg-secondary/50 text-sm"
                />
              </div>
            </div>
          ))}
        </div>

        {/* Debug Info */}
        <div className="mt-6 p-4 bg-secondary/30 rounded text-xs font-mono">
          <div>Last Synced: {lastSyncedAt ? new Date(lastSyncedAt).toLocaleString() : 'Never'}</div>
          <div>Device Offline: {isDeviceOffline ? 'Yes' : 'No'}</div>
          <div>Using Fallback: {usingFallback ? 'Yes' : 'No'}</div>
          <div>Stale: {isStale ? 'Yes' : 'No'}</div>
          <div>Total Settings: {Object.keys(localSettings).length}</div>
        </div>
      </div>
    </div>
  );
}
