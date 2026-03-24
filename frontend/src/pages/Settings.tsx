import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import usersService from "@/api/services/users.service";
import { devicesService } from "@/api/services/devices.service";
import { sitesService } from "@/api/services/sites.service";
import type { UserPreferences, Device } from "@/api/types";
import { useCurrentSite } from "@/hooks/useSites";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Settings,
  Bell,
  Globe,
  Save,
  RotateCcw,
  MapPin,
  Clock,
  Home,
  Layers,
  Battery,
  Plus,
  Trash2,
  Unlink,
  ToggleLeft,
  ToggleRight,
  Zap,
  ChevronRight,
  Users,
  Loader2,
} from "lucide-react";
import { settingsData } from "@/data/mockData";
import { toast } from "@/hooks/use-toast";
import { useUserMode } from "@/hooks/use-user-mode";

interface SystemConfig {
  location: {
    latitude: string;
    longitude: string;
  };
  timezone: string;
}

interface InverterArray {
  id: string;
  name: string;
  inverters: string[];
}

interface BatteryArray {
  id: string;
  name: string;
  batteries: string[];
  attachedTo: string | null;
}

const SettingsPage = () => {
  const navigate = useNavigate();
  const { mode, toggleMode, isAdvanced } = useUserMode();
  const { currentSite } = useCurrentSite();
  const [settings, setSettings] = useState(settingsData);
  const [isSaving, setIsSaving] = useState(false);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);

  // Real devices from API
  const [availableInverters, setAvailableInverters] = useState<Device[]>([]);
  const [availableBatteries, setAvailableBatteries] = useState<Device[]>([]);

  // Map serial_number -> display label for badges
  const deviceLabel = useCallback((device: Device) =>
    device.name || `${device.manufacturer} ${device.model}`.trim() || device.serial_number
  , []);

  // Load user preferences on mount
  const loadPreferences = useCallback(async () => {
    try {
      const user = await usersService.getProfile();
      if (user.preferences) {
        setSettings((prev) => ({
          ...prev,
          notifications: {
            ...prev.notifications,
            email: user.preferences.email_notifications ?? prev.notifications.email,
            sms: user.preferences.sms_notifications ?? prev.notifications.sms,
            push: user.preferences.notifications_enabled ?? prev.notifications.push,
          },
        }));
      }
      setPreferencesLoaded(true);
    } catch {
      // Keep default settings on error
      setPreferencesLoaded(true);
    }
  }, []);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);
  const [systemConfig, setSystemConfig] = useState<SystemConfig>({
    location: {
      latitude: "31.5497",
      longitude: "74.3436",
    },
    timezone: "Asia/Karachi",
  });

  // Home Configuration — seeded from currentSite
  const [homeConfig, setHomeConfig] = useState({
    id: currentSite?.id ?? "",
    name: currentSite?.name ?? "",
    description: currentSite?.description ?? "",
  });

  // Sync homeConfig when site loads
  useEffect(() => {
    if (currentSite) {
      setHomeConfig({
        id: currentSite.id,
        name: currentSite.name,
        description: currentSite.description ?? "",
      });
    }
  }, [currentSite]);

  // Load devices from API
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [inv, bat] = await Promise.all([
          devicesService.listDevices({ device_type: "inverter" }, { page: 1, page_size: 100 }),
          devicesService.listDevices({ device_type: "battery" }, { page: 1, page_size: 100 }),
        ]);
        if (!cancelled) {
          setAvailableInverters(inv.items);
          setAvailableBatteries(bat.items);
        }
      } catch {
        // Keep empty arrays on error
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  // Inverter Arrays — loaded from localStorage keyed by site
  const lsInvKey = currentSite ? `hierarchy:${currentSite.id}:inverterArrays` : null;
  const lsBatKey = currentSite ? `hierarchy:${currentSite.id}:batteryArrays` : null;

  const [inverterArrays, setInverterArrays] = useState<InverterArray[]>([]);
  const [batteryArrays, setBatteryArrays] = useState<BatteryArray[]>([]);

  // Load persisted arrays from localStorage when site is known
  useEffect(() => {
    if (!lsInvKey || !lsBatKey) return;
    try {
      const inv = localStorage.getItem(lsInvKey);
      const bat = localStorage.getItem(lsBatKey);
      if (inv) setInverterArrays(JSON.parse(inv));
      if (bat) setBatteryArrays(JSON.parse(bat));
    } catch {
      // Ignore parse errors
    }
  }, [lsInvKey, lsBatKey]);

  // Persist arrays to localStorage on change
  useEffect(() => {
    if (lsInvKey) localStorage.setItem(lsInvKey, JSON.stringify(inverterArrays));
  }, [inverterArrays, lsInvKey]);

  useEffect(() => {
    if (lsBatKey) localStorage.setItem(lsBatKey, JSON.stringify(batteryArrays));
  }, [batteryArrays, lsBatKey]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const saves: Promise<unknown>[] = [
        usersService.updatePreferences({
          email_notifications: settings.notifications.email,
          sms_notifications: settings.notifications.sms,
          notifications_enabled: settings.notifications.push,
        } as Partial<UserPreferences>),
      ];

      // Persist site name/description if site is loaded
      if (currentSite && (homeConfig.name !== currentSite.name || homeConfig.description !== (currentSite.description ?? ""))) {
        saves.push(sitesService.updateSite(currentSite.id, {
          name: homeConfig.name,
          description: homeConfig.description,
        }));
      }

      await Promise.all(saves);
      toast({
        title: "Settings Saved",
        description: "Your configuration has been updated successfully.",
      });
    } catch {
      toast({
        title: "Save Failed",
        description: "Failed to save settings. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setSettings(settingsData);
    setSystemConfig({
      location: {
        latitude: "31.5497",
        longitude: "74.3436",
      },
      timezone: "Asia/Karachi",
    });
    setHomeConfig({
      id: currentSite?.id ?? "",
      name: currentSite?.name ?? "",
      description: currentSite?.description ?? "",
    });
    setInverterArrays([]);
    setBatteryArrays([]);
    if (lsInvKey) localStorage.removeItem(lsInvKey);
    if (lsBatKey) localStorage.removeItem(lsBatKey);
    toast({
      title: "Settings Reset",
      description: "All settings have been restored to defaults.",
    });
  };

  const handleAutoDetectLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setSystemConfig({
            ...systemConfig,
            location: {
              latitude: position.coords.latitude.toFixed(4),
              longitude: position.coords.longitude.toFixed(4),
            },
          });
          toast({
            title: "Location Detected",
            description: "Your location has been automatically detected.",
          });
        },
        () => {
          toast({
            title: "Location Error",
            description: "Unable to detect location. Please enter manually.",
            variant: "destructive",
          });
        }
      );
    }
  };

  const handleAddInverterArray = () => {
    const newArray: InverterArray = {
      id: `array${inverterArrays.length + 1}`,
      name: `New Array ${inverterArrays.length + 1}`,
      inverters: [],
    };
    setInverterArrays([...inverterArrays, newArray]);
  };

  const handleRemoveInverterArray = (id: string) => {
    setInverterArrays(inverterArrays.filter((arr) => arr.id !== id));
    setBatteryArrays(batteryArrays.map((ba) => 
      ba.attachedTo === id ? { ...ba, attachedTo: null } : ba
    ));
  };

  const handleAddBatteryArray = () => {
    const newArray: BatteryArray = {
      id: `battery_array${batteryArrays.length + 1}`,
      name: `New Battery Array ${batteryArrays.length + 1}`,
      batteries: [],
      attachedTo: null,
    };
    setBatteryArrays([...batteryArrays, newArray]);
  };

  const handleRemoveBatteryArray = (id: string) => {
    setBatteryArrays(batteryArrays.filter((arr) => arr.id !== id));
  };

  const handleAttachBatteryArray = (batteryArrayId: string, inverterArrayId: string) => {
    setBatteryArrays(batteryArrays.map((ba) =>
      ba.id === batteryArrayId ? { ...ba, attachedTo: inverterArrayId } : ba
    ));
  };

  const handleDetachBatteryArray = (batteryArrayId: string) => {
    setBatteryArrays(batteryArrays.map((ba) =>
      ba.id === batteryArrayId ? { ...ba, attachedTo: null } : ba
    ));
  };

  const toggleInverterInArray = (arrayId: string, inverter: string) => {
    setInverterArrays(inverterArrays.map((arr) => {
      if (arr.id === arrayId) {
        const hasInverter = arr.inverters.includes(inverter);
        return {
          ...arr,
          inverters: hasInverter
            ? arr.inverters.filter((i) => i !== inverter)
            : [...arr.inverters, inverter],
        };
      }
      return arr;
    }));
  };

  const toggleBatteryInArray = (arrayId: string, battery: string) => {
    setBatteryArrays(batteryArrays.map((arr) => {
      if (arr.id === arrayId) {
        const hasBattery = arr.batteries.includes(battery);
        return {
          ...arr,
          batteries: hasBattery
            ? arr.batteries.filter((b) => b !== battery)
            : [...arr.batteries, battery],
        };
      }
      return arr;
    }));
  };

  const timezones = [
    { value: "Asia/Karachi", label: "Asia/Karachi (UTC+5)" },
    { value: "America/New_York", label: "America/New_York (UTC-5)" },
    { value: "America/Los_Angeles", label: "America/Los_Angeles (UTC-8)" },
    { value: "Europe/London", label: "Europe/London (UTC+0)" },
    { value: "Europe/Berlin", label: "Europe/Berlin (UTC+1)" },
    { value: "Asia/Dubai", label: "Asia/Dubai (UTC+4)" },
    { value: "Asia/Tokyo", label: "Asia/Tokyo (UTC+9)" },
    { value: "Australia/Sydney", label: "Australia/Sydney (UTC+11)" },
  ];

  return (
    <AppLayout>
      <AppHeader 
        title="Settings" 
        subtitle="Configure your solar monitoring system"
      />
      
      <div className="p-6">
        <Tabs defaultValue="system" className="space-y-6">
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <TabsList className="glass-card p-1 flex-wrap h-auto">
              <TabsTrigger value="system" className="gap-2">
                <Settings className="w-4 h-4" />
                <span className="hidden sm:inline">System</span>
              </TabsTrigger>
              <TabsTrigger value="hierarchy" className="gap-2">
                <Layers className="w-4 h-4" />
                <span className="hidden sm:inline">Hierarchy</span>
              </TabsTrigger>
              <TabsTrigger value="notifications" className="gap-2">
                <Bell className="w-4 h-4" />
                <span className="hidden sm:inline">Notifications</span>
              </TabsTrigger>
            </TabsList>
          </motion.div>

          {/* System Settings */}
          <TabsContent value="system">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              {/* Quick Links */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                <button
                  onClick={() => navigate('/settings/tariff')}
                  className="glass-card p-4 flex items-center justify-between hover:bg-accent/50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Zap className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium">Tariff Settings</p>
                      <p className="text-sm text-muted-foreground">Configure electricity rates</p>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground" />
                </button>
                
                <button
                  onClick={() => navigate('/billing/settings')}
                  className="glass-card p-4 flex items-center justify-between hover:bg-accent/50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Globe className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium">Billing Settings</p>
                      <p className="text-sm text-muted-foreground">Configure billing preferences</p>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground" />
                </button>
                
                <button
                  onClick={() => navigate('/settings/users')}
                  className="glass-card p-4 flex items-center justify-between hover:bg-accent/50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Users className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium">User Management</p>
                      <p className="text-sm text-muted-foreground">Manage team & permissions</p>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>
              
              <Accordion type="multiple" defaultValue={["user-mode", "general", "location", "timezone"]} className="space-y-4">
                {/* User Mode Toggle */}
                <AccordionItem value="user-mode" className="glass-card border-0">
                  <AccordionTrigger className="px-6 py-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        {isAdvanced ? <ToggleRight className="w-5 h-5 text-primary" /> : <ToggleLeft className="w-5 h-5 text-primary" />}
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-foreground">User Mode</p>
                        <p className="text-sm text-muted-foreground">Switch between simple and advanced interface</p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-6 pb-6">
                    <div className="space-y-4 pt-4">
                      <div className="flex items-center justify-between p-4 rounded-lg bg-secondary/50">
                        <div className="flex items-center gap-3">
                          <div>
                            <p className="font-medium text-foreground">
                              {isAdvanced ? "Advanced Mode" : "Simple Mode"}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {isAdvanced 
                                ? "Full device parameters, hierarchy editing, raw data access" 
                                : "Simplified interface with essential controls only"
                              }
                            </p>
                          </div>
                        </div>
                        <Switch
                          checked={isAdvanced}
                          onCheckedChange={toggleMode}
                        />
                      </div>
                      
                      <div className="p-3 rounded-lg bg-info/10 border border-info/20">
                        <p className="text-sm text-info">
                          {isAdvanced 
                            ? "You have access to all technical parameters and configuration options."
                            : "Technical parameters are hidden. Enable Advanced Mode to access all features."
                          }
                        </p>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* General System Settings */}
                <AccordionItem value="general" className="glass-card border-0">
                  <AccordionTrigger className="px-6 py-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <Globe className="w-5 h-5 text-primary" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-foreground">General Settings</p>
                        <p className="text-sm text-muted-foreground">System name, currency, and preferences</p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-6 pb-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
                      <div className="space-y-2">
                        <Label htmlFor="systemName">System Name</Label>
                        <Input
                          id="systemName"
                          value={settings.system.name}
                          onChange={(e) =>
                            setSettings({
                              ...settings,
                              system: { ...settings.system, name: e.target.value },
                            })
                          }
                          className="bg-secondary/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="location">Address</Label>
                        <Input
                          id="location"
                          value={settings.system.location}
                          onChange={(e) =>
                            setSettings({
                              ...settings,
                              system: { ...settings.system, location: e.target.value },
                            })
                          }
                          className="bg-secondary/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Currency</Label>
                        <Select value={settings.system.currency}>
                          <SelectTrigger className="bg-secondary/50">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="USD">USD ($)</SelectItem>
                            <SelectItem value="EUR">EUR (€)</SelectItem>
                            <SelectItem value="GBP">GBP (£)</SelectItem>
                            <SelectItem value="PKR">PKR (₨)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Location Settings */}
                <AccordionItem value="location" className="glass-card border-0">
                  <AccordionTrigger className="px-6 py-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <MapPin className="w-5 h-5 text-primary" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-foreground">Location Settings</p>
                        <p className="text-sm text-muted-foreground">Configure system location coordinates for weather and timezone detection</p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-6 pb-6">
                    <div className="space-y-6 pt-4">
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" onClick={handleAutoDetectLocation}>
                          Auto-Detect
                        </Button>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label htmlFor="latitude">Latitude</Label>
                          <p className="text-xs text-muted-foreground">Latitude coordinate (-90 to 90)</p>
                          <Input
                            id="latitude"
                            type="number"
                            step="0.0001"
                            min="-90"
                            max="90"
                            value={systemConfig.location.latitude}
                            onChange={(e) =>
                              setSystemConfig({
                                ...systemConfig,
                                location: { ...systemConfig.location, latitude: e.target.value },
                              })
                            }
                            className="bg-secondary/50"
                          />
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="longitude">Longitude</Label>
                          <p className="text-xs text-muted-foreground">Longitude coordinate (-180 to 180)</p>
                          <Input
                            id="longitude"
                            type="number"
                            step="0.0001"
                            min="-180"
                            max="180"
                            value={systemConfig.location.longitude}
                            onChange={(e) =>
                              setSystemConfig({
                                ...systemConfig,
                                location: { ...systemConfig.location, longitude: e.target.value },
                              })
                            }
                            className="bg-secondary/50"
                          />
                        </div>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Timezone Settings */}
                <AccordionItem value="timezone" className="glass-card border-0">
                  <AccordionTrigger className="px-6 py-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <Clock className="w-5 h-5 text-primary" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-foreground">Timezone Settings</p>
                        <p className="text-sm text-muted-foreground">Configure system timezone for scheduling and reporting</p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-6 pb-6">
                    <div className="space-y-4 pt-4">
                      <div className="space-y-2">
                        <Label>Timezone</Label>
                        <p className="text-xs text-muted-foreground">System timezone (e.g., Asia/Karachi, America/New_York)</p>
                        <Select 
                          value={systemConfig.timezone}
                          onValueChange={(value) =>
                            setSystemConfig({
                              ...systemConfig,
                              timezone: value,
                            })
                          }
                        >
                          <SelectTrigger className="bg-secondary/50">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {timezones.map((tz) => (
                              <SelectItem key={tz.value} value={tz.value}>
                                {tz.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </motion.div>
          </TabsContent>

          {/* Hierarchy Configuration Tab */}
          <TabsContent value="hierarchy">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <Accordion type="multiple" defaultValue={["home", "inverters", "batteries"]} className="space-y-4">
                {/* Home Configuration */}
                <AccordionItem value="home" className="glass-card border-0">
                  <AccordionTrigger className="px-6 py-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <Home className="w-5 h-5 text-primary" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-foreground">Home Configuration</p>
                        <p className="text-sm text-muted-foreground">Top-level home settings</p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-6 pb-6">
                    <div className="space-y-4 pt-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Home ID</Label>
                          <Input
                            value={homeConfig.id}
                            onChange={(e) => setHomeConfig({ ...homeConfig, id: e.target.value })}
                            className="bg-secondary/50"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Home Name</Label>
                          <Input
                            value={homeConfig.name}
                            onChange={(e) => setHomeConfig({ ...homeConfig, name: e.target.value })}
                            className="bg-secondary/50"
                          />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label>Description</Label>
                        <Textarea
                          value={homeConfig.description}
                          onChange={(e) => setHomeConfig({ ...homeConfig, description: e.target.value })}
                          className="bg-secondary/50 min-h-[80px]"
                        />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Arrays of Inverters */}
                <AccordionItem value="inverters" className="glass-card border-0">
                  <AccordionTrigger className="px-6 py-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <Layers className="w-5 h-5 text-primary" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-foreground">Arrays of Inverters</p>
                        <p className="text-sm text-muted-foreground">Group inverters into arrays</p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-6 pb-6">
                    <div className="space-y-4 pt-4">
                      <div className="flex justify-end">
                        <Button variant="outline" size="sm" onClick={handleAddInverterArray} className="gap-2">
                          <Plus className="w-4 h-4" />
                          Add Array
                        </Button>
                      </div>

                      <div className="space-y-4">
                        {inverterArrays.map((array) => (
                          <div key={array.id} className="p-4 rounded-lg bg-secondary/30 space-y-3">
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1 space-y-3">
                                <Input
                                  value={array.id}
                                  onChange={(e) =>
                                    setInverterArrays(inverterArrays.map((a) =>
                                      a.id === array.id ? { ...a, id: e.target.value } : a
                                    ))
                                  }
                                  placeholder="Array ID"
                                  className="bg-secondary/50 w-40"
                                />
                                <Input
                                  value={array.name}
                                  onChange={(e) =>
                                    setInverterArrays(inverterArrays.map((a) =>
                                      a.id === array.id ? { ...a, name: e.target.value } : a
                                    ))
                                  }
                                  placeholder="Array Name"
                                  className="bg-secondary/50"
                                />
                              </div>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleRemoveInverterArray(array.id)}
                                className="text-destructive hover:text-destructive"
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                            <div>
                              <Label className="text-sm text-muted-foreground">Select Inverters:</Label>
                              <div className="flex flex-wrap gap-2 mt-2">
                                {availableInverters.length === 0 && (
                                  <span className="text-xs text-muted-foreground">No inverters found</span>
                                )}
                                {availableInverters.map((device) => (
                                  <Badge
                                    key={device.serial_number}
                                    variant={array.inverters.includes(device.serial_number) ? "default" : "outline"}
                                    className="cursor-pointer"
                                    onClick={() => toggleInverterInArray(array.id, device.serial_number)}
                                  >
                                    {deviceLabel(device)}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Arrays of Battery Banks */}
                <AccordionItem value="batteries" className="glass-card border-0">
                  <AccordionTrigger className="px-6 py-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <Battery className="w-5 h-5 text-primary" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-foreground">Arrays of Battery Banks</p>
                        <p className="text-sm text-muted-foreground">Group battery banks into arrays</p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-6 pb-6">
                    <div className="space-y-4 pt-4">
                      <div className="flex justify-end">
                        <Button variant="outline" size="sm" onClick={handleAddBatteryArray} className="gap-2">
                          <Plus className="w-4 h-4" />
                          Add Battery Array
                        </Button>
                      </div>

                      <div className="space-y-4">
                        {batteryArrays.map((array) => (
                          <div key={array.id} className="p-4 rounded-lg bg-secondary/30 space-y-3">
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1 space-y-3">
                                <Input
                                  value={array.id}
                                  onChange={(e) =>
                                    setBatteryArrays(batteryArrays.map((a) =>
                                      a.id === array.id ? { ...a, id: e.target.value } : a
                                    ))
                                  }
                                  placeholder="Array ID"
                                  className="bg-secondary/50 w-48"
                                />
                                <Input
                                  value={array.name}
                                  onChange={(e) =>
                                    setBatteryArrays(batteryArrays.map((a) =>
                                      a.id === array.id ? { ...a, name: e.target.value } : a
                                    ))
                                  }
                                  placeholder="Array Name"
                                  className="bg-secondary/50"
                                />
                              </div>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleRemoveBatteryArray(array.id)}
                                className="text-destructive hover:text-destructive"
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                            <div>
                              <Label className="text-sm text-muted-foreground">Select Battery Banks:</Label>
                              <div className="flex flex-wrap gap-2 mt-2">
                                {availableBatteries.length === 0 && (
                                  <span className="text-xs text-muted-foreground">No batteries found</span>
                                )}
                                {availableBatteries.map((device) => (
                                  <Badge
                                    key={device.serial_number}
                                    variant={array.batteries.includes(device.serial_number) ? "default" : "outline"}
                                    className="cursor-pointer"
                                    onClick={() => toggleBatteryInArray(array.id, device.serial_number)}
                                  >
                                    {deviceLabel(device)}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                            <div>
                              <Label className="text-sm text-muted-foreground">Attach to Inverter Array (1:1):</Label>
                              <div className="flex flex-wrap gap-2 mt-2">
                                {array.attachedTo ? (
                                  <>
                                    <Badge variant="default" className="bg-green-600">
                                      Attached to: {array.attachedTo}
                                    </Badge>
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => handleDetachBatteryArray(array.id)}
                                      className="gap-1"
                                    >
                                      <Unlink className="w-3 h-3" />
                                      Detach
                                    </Button>
                                  </>
                                ) : (
                                  <Select onValueChange={(value) => handleAttachBatteryArray(array.id, value)}>
                                    <SelectTrigger className="w-48 bg-secondary/50">
                                      <SelectValue placeholder="Select array..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                      {inverterArrays.map((ia) => (
                                        <SelectItem key={ia.id} value={ia.id}>
                                          {ia.name} ({ia.id})
                                        </SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </motion.div>
          </TabsContent>

          {/* Notification Settings */}
          <TabsContent value="notifications">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-6 space-y-6"
            >
              <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <Bell className="w-5 h-5 text-primary" />
                Notification Preferences
              </h3>

              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg bg-secondary/30">
                  <div>
                    <p className="font-medium text-foreground">Email Notifications</p>
                    <p className="text-sm text-muted-foreground">Receive alerts via email</p>
                  </div>
                  <Switch
                    checked={settings.notifications.email}
                    onCheckedChange={(checked) =>
                      setSettings({
                        ...settings,
                        notifications: { ...settings.notifications, email: checked },
                      })
                    }
                  />
                </div>

                <div className="flex items-center justify-between p-4 rounded-lg bg-secondary/30">
                  <div>
                    <p className="font-medium text-foreground">Push Notifications</p>
                    <p className="text-sm text-muted-foreground">Browser push notifications</p>
                  </div>
                  <Switch
                    checked={settings.notifications.push}
                    onCheckedChange={(checked) =>
                      setSettings({
                        ...settings,
                        notifications: { ...settings.notifications, push: checked },
                      })
                    }
                  />
                </div>

                <div className="flex items-center justify-between p-4 rounded-lg bg-secondary/30">
                  <div>
                    <p className="font-medium text-foreground">SMS Alerts</p>
                    <p className="text-sm text-muted-foreground">Critical alerts via SMS</p>
                  </div>
                  <Switch
                    checked={settings.notifications.sms}
                    onCheckedChange={(checked) =>
                      setSettings({
                        ...settings,
                        notifications: { ...settings.notifications, sms: checked },
                      })
                    }
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-border">
                <h4 className="text-sm font-medium text-foreground mb-4">Alert Thresholds</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-3">
                    <Label>Low Battery Alert (%)</Label>
                    <div className="flex items-center gap-4">
                      <Slider
                        value={[settings.notifications.alerts.lowBattery]}
                        max={50}
                        step={5}
                        className="flex-1"
                        onValueChange={([value]) =>
                          setSettings({
                            ...settings,
                            notifications: {
                              ...settings.notifications,
                              alerts: { ...settings.notifications.alerts, lowBattery: value },
                            },
                          })
                        }
                      />
                      <span className="font-mono text-sm w-12">
                        {settings.notifications.alerts.lowBattery}%
                      </span>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <Label>High Temperature Alert (°C)</Label>
                    <div className="flex items-center gap-4">
                      <Slider
                        value={[settings.notifications.alerts.highTemperature]}
                        min={40}
                        max={70}
                        step={5}
                        className="flex-1"
                        onValueChange={([value]) =>
                          setSettings({
                            ...settings,
                            notifications: {
                              ...settings.notifications,
                              alerts: { ...settings.notifications.alerts, highTemperature: value },
                            },
                          })
                        }
                      />
                      <span className="font-mono text-sm w-12">
                        {settings.notifications.alerts.highTemperature}°C
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </TabsContent>
        </Tabs>

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex flex-wrap gap-4 mt-6"
        >
          <Button onClick={handleSave} disabled={isSaving} className="gap-2">
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {isSaving ? "Saving..." : "Save Changes"}
          </Button>
          <Button variant="outline" onClick={handleReset} className="gap-2">
            <RotateCcw className="w-4 h-4" />
            Reset to Defaults
          </Button>
        </motion.div>
      </div>
    </AppLayout>
  );
};

export default SettingsPage;
