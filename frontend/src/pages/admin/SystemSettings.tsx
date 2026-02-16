import { useState } from "react";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Settings, Globe, Wifi, Database, Save } from "lucide-react";
import { toast } from "sonner";

export default function SystemSettings() {
  const { addAuditEntry } = useAdminAuth();

  // Mock system settings - replace with API calls
  const [mqttSettings, setMqttSettings] = useState({
    defaultBrokerUrl: "mqtt://localhost",
    defaultPort: 1883,
    tlsEnabled: false,
    systemUsername: "system_user",
  });

  const [locationDefaults, setLocationDefaults] = useState({
    timezone: "Asia/Karachi",
    currency: "PKR",
    dateFormat: "DD/MM/YYYY",
    defaultLatitude: 31.5204,
    defaultLongitude: 74.3587,
  });

  const [systemConfig, setSystemConfig] = useState({
    maintenanceMode: false,
    registrationEnabled: true,
    maxDevicesPerOrg: 100,
    dataRetentionDays: 365,
  });

  const handleSaveMqtt = () => {
    // TODO: API call to save MQTT settings
    addAuditEntry({
      action: "update",
      entity: "system_settings",
      entityId: "mqtt",
      details: {
        after: mqttSettings,
      },
    });
    toast.success("MQTT settings saved successfully");
  };

  const handleSaveLocation = () => {
    // TODO: API call to save location defaults
    addAuditEntry({
      action: "update",
      entity: "system_settings",
      entityId: "location",
      details: {
        after: locationDefaults,
      },
    });
    toast.success("Location defaults saved successfully");
  };

  const handleSaveSystem = () => {
    // TODO: API call to save system config
    addAuditEntry({
      action: "update",
      entity: "system_settings",
      entityId: "system",
      details: {
        after: systemConfig,
      },
    });
    toast.success("System configuration saved successfully");
  };

  const breadcrumbs = [
    { label: "Admin", href: "/admin" },
    { label: "System Settings" },
  ];

  return (
    <AdminLayout breadcrumbs={breadcrumbs}>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Settings</h1>
          <p className="text-muted-foreground mt-1">
            Configure system-wide settings and defaults
          </p>
        </div>

        {/* Settings Tabs */}
        <Tabs defaultValue="mqtt" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="mqtt">
              <Wifi className="h-4 w-4 mr-2" />
              MQTT
            </TabsTrigger>
            <TabsTrigger value="location">
              <Globe className="h-4 w-4 mr-2" />
              Location
            </TabsTrigger>
            <TabsTrigger value="system">
              <Settings className="h-4 w-4 mr-2" />
              System
            </TabsTrigger>
          </TabsList>

          {/* MQTT Settings */}
          <TabsContent value="mqtt" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Default MQTT Configuration</CardTitle>
                <CardDescription>
                  System-wide MQTT broker settings for device communication
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="brokerUrl">Broker URL</Label>
                    <Input
                      id="brokerUrl"
                      value={mqttSettings.defaultBrokerUrl}
                      onChange={(e) =>
                        setMqttSettings({ ...mqttSettings, defaultBrokerUrl: e.target.value })
                      }
                      placeholder="mqtt://broker.example.com"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="port">Port</Label>
                    <Input
                      id="port"
                      type="number"
                      value={mqttSettings.defaultPort}
                      onChange={(e) =>
                        setMqttSettings({ ...mqttSettings, defaultPort: Number(e.target.value) })
                      }
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="username">System Username</Label>
                    <Input
                      id="username"
                      value={mqttSettings.systemUsername}
                      onChange={(e) =>
                        setMqttSettings({ ...mqttSettings, systemUsername: e.target.value })
                      }
                    />
                  </div>

                  <div className="flex items-center space-x-2 pt-8">
                    <Switch
                      id="tls"
                      checked={mqttSettings.tlsEnabled}
                      onCheckedChange={(checked) =>
                        setMqttSettings({ ...mqttSettings, tlsEnabled: checked })
                      }
                    />
                    <Label htmlFor="tls">Enable TLS/SSL</Label>
                  </div>
                </div>

                <Separator />

                <Button onClick={handleSaveMqtt}>
                  <Save className="mr-2 h-4 w-4" />
                  Save MQTT Settings
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Location Settings */}
          <TabsContent value="location" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Location Defaults</CardTitle>
                <CardDescription>
                  Default location, timezone, and regional settings for new organizations
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="timezone">Default Timezone</Label>
                    <Input
                      id="timezone"
                      value={locationDefaults.timezone}
                      onChange={(e) =>
                        setLocationDefaults({ ...locationDefaults, timezone: e.target.value })
                      }
                    />
                    <p className="text-xs text-muted-foreground">IANA timezone identifier</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="currency">Currency</Label>
                    <Input
                      id="currency"
                      value={locationDefaults.currency}
                      onChange={(e) =>
                        setLocationDefaults({ ...locationDefaults, currency: e.target.value })
                      }
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="dateFormat">Date Format</Label>
                    <Input
                      id="dateFormat"
                      value={locationDefaults.dateFormat}
                      onChange={(e) =>
                        setLocationDefaults({ ...locationDefaults, dateFormat: e.target.value })
                      }
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="latitude">Default Latitude</Label>
                    <Input
                      id="latitude"
                      type="number"
                      step="0.0001"
                      value={locationDefaults.defaultLatitude}
                      onChange={(e) =>
                        setLocationDefaults({
                          ...locationDefaults,
                          defaultLatitude: Number(e.target.value),
                        })
                      }
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="longitude">Default Longitude</Label>
                    <Input
                      id="longitude"
                      type="number"
                      step="0.0001"
                      value={locationDefaults.defaultLongitude}
                      onChange={(e) =>
                        setLocationDefaults({
                          ...locationDefaults,
                          defaultLongitude: Number(e.target.value),
                        })
                      }
                    />
                  </div>
                </div>

                <Separator />

                <Button onClick={handleSaveLocation}>
                  <Save className="mr-2 h-4 w-4" />
                  Save Location Defaults
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* System Settings */}
          <TabsContent value="system" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>System Configuration</CardTitle>
                <CardDescription>
                  General system settings and operational parameters
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Maintenance Mode</Label>
                      <p className="text-sm text-muted-foreground">
                        Disable user access for system maintenance
                      </p>
                    </div>
                    <Switch
                      checked={systemConfig.maintenanceMode}
                      onCheckedChange={(checked) =>
                        setSystemConfig({ ...systemConfig, maintenanceMode: checked })
                      }
                    />
                  </div>

                  <Separator />

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>User Registration</Label>
                      <p className="text-sm text-muted-foreground">
                        Allow new users to register accounts
                      </p>
                    </div>
                    <Switch
                      checked={systemConfig.registrationEnabled}
                      onCheckedChange={(checked) =>
                        setSystemConfig({ ...systemConfig, registrationEnabled: checked })
                      }
                    />
                  </div>

                  <Separator />

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="maxDevices">Max Devices Per Organization</Label>
                      <Input
                        id="maxDevices"
                        type="number"
                        value={systemConfig.maxDevicesPerOrg}
                        onChange={(e) =>
                          setSystemConfig({
                            ...systemConfig,
                            maxDevicesPerOrg: Number(e.target.value),
                          })
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="retention">Data Retention (Days)</Label>
                      <Input
                        id="retention"
                        type="number"
                        value={systemConfig.dataRetentionDays}
                        onChange={(e) =>
                          setSystemConfig({
                            ...systemConfig,
                            dataRetentionDays: Number(e.target.value),
                          })
                        }
                      />
                    </div>
                  </div>
                </div>

                <Separator />

                <Button onClick={handleSaveSystem}>
                  <Save className="mr-2 h-4 w-4" />
                  Save System Configuration
                </Button>
              </CardContent>
            </Card>

            <Card className="border-amber-500/50 bg-amber-500/5">
              <CardHeader>
                <CardTitle className="text-amber-600 dark:text-amber-500 flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  Database Management
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Administrative database operations (use with caution)
                </p>
                <div className="flex gap-3">
                  <Button variant="outline" size="sm">
                    Backup Database
                  </Button>
                  <Button variant="outline" size="sm">
                    Clear Old Logs
                  </Button>
                  <Button variant="outline" size="sm">
                    Rebuild Indexes
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AdminLayout>
  );
}
