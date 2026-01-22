import { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Plus,
  Link,
  WifiOff,
  ArrowLeft,
} from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface DeviceConfig {
  id: string;
  name: string;
  model: string;
  connection: string;
  unitId: string;
  status: "connected" | "disconnected";
  lastUpdate: string;
}

const DeviceManagementPage = () => {
  const navigate = useNavigate();

  // Device Manager
  const [devices, setDevices] = useState<DeviceConfig[]>([
    { id: "powdrive1", name: "Powdrive", model: "Powdrive", connection: "", unitId: "1", status: "disconnected", lastUpdate: "1:30:40 PM" },
    { id: "senergy1", name: "Senergy", model: "Senergy", connection: "", unitId: "4", status: "disconnected", lastUpdate: "1:30:40 PM" },
    { id: "powdrive2", name: "Powdrive", model: "Powdrive", connection: "", unitId: "1", status: "disconnected", lastUpdate: "1:30:40 PM" },
  ]);

  const [batteryDevices, setBatteryDevices] = useState<DeviceConfig[]>([
    { id: "battery1", name: "Battery", model: "USB PYTES", connection: "", unitId: "1", status: "disconnected", lastUpdate: "1:30:40 PM" },
  ]);

  const handleAddInverter = () => {
    const newDevice: DeviceConfig = {
      id: `inverter${devices.length + 1}`,
      name: "New Inverter",
      model: "Powdrive",
      connection: "",
      unitId: "1",
      status: "disconnected",
      lastUpdate: new Date().toLocaleTimeString(),
    };
    setDevices([...devices, newDevice]);
  };

  const handleRemoveDevice = (id: string) => {
    setDevices(devices.filter((d) => d.id !== id));
  };

  const handleConnect = () => {
    toast({
      title: "Connecting...",
      description: "Attempting to connect to all devices.",
    });
  };

  const handleTestConnection = (deviceId: string) => {
    toast({
      title: "Testing Connection",
      description: `Testing connection for device ${deviceId}...`,
    });
  };

  const handleSave = () => {
    toast({
      title: "Configuration Saved",
      description: "Device settings have been saved.",
    });
  };

  return (
    <AppLayout>
      <AppHeader
        title="Device Manager"
        subtitle="Configure inverters and battery connections"
      />

      <div className="p-6 space-y-6">
        {/* Back Button */}
        <Button variant="ghost" size="sm" onClick={() => navigate("/devices")} className="gap-2">
          <ArrowLeft className="w-4 h-4" />
          Back to Devices
        </Button>

        {/* Connection Status */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4"
        >
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-muted-foreground" />
            <span className="text-sm text-muted-foreground">No active connections</span>
            <span className="text-xs text-muted-foreground ml-auto">
              Last update: {new Date().toLocaleTimeString()}
            </span>
          </div>
        </motion.div>

        {/* Devices Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="font-medium text-foreground">Devices</h3>
              <p className="text-sm text-muted-foreground">
                Configure inverters and battery connections. Multiple inverters are supported.
              </p>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleAddInverter} className="gap-2">
                <Plus className="w-4 h-4" />
                Add Inverter
              </Button>
              <Button onClick={handleConnect} variant="default" className="gap-2 bg-green-600 hover:bg-green-700">
                <Link className="w-4 h-4" />
                Connect
              </Button>
            </div>
          </div>
        </motion.div>

        {/* Inverter Devices */}
        <div className="space-y-4">
          {devices.map((device, index) => (
            <motion.div
              key={device.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + index * 0.05 }}
              className="glass-card p-4 space-y-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="font-medium text-foreground">{device.name}</span>
                  <span className="text-muted-foreground">({device.id})</span>
                  <Badge variant="destructive" className="gap-1">
                    <WifiOff className="w-3 h-3" />
                    Disconnected
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    Last update: {device.lastUpdate}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="link"
                    size="sm"
                    onClick={() => handleTestConnection(device.id)}
                    className="text-primary"
                  >
                    Test Connection
                  </Button>
                  <Button
                    variant="link"
                    size="sm"
                    onClick={() => handleRemoveDevice(device.id)}
                    className="text-destructive"
                  >
                    remove
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Model</Label>
                  <Select
                    value={device.model}
                    onValueChange={(value) =>
                      setDevices(devices.map((d) =>
                        d.id === device.id ? { ...d, model: value } : d
                      ))
                    }
                  >
                    <SelectTrigger className="bg-secondary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Powdrive">Powdrive</SelectItem>
                      <SelectItem value="Senergy">Senergy</SelectItem>
                      <SelectItem value="Growatt">Growatt</SelectItem>
                      <SelectItem value="Deye">Deye</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Connections</Label>
                  <Select
                    value={device.connection}
                    onValueChange={(value) =>
                      setDevices(devices.map((d) =>
                        d.id === device.id ? { ...d, connection: value } : d
                      ))
                    }
                  >
                    <SelectTrigger className="bg-secondary/50">
                      <SelectValue placeholder="Select port..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="serial1">Serial Port 1</SelectItem>
                      <SelectItem value="serial2">Serial Port 2</SelectItem>
                      <SelectItem value="tcp">TCP/IP</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Unit ID</Label>
                  <Input
                    value={device.unitId}
                    onChange={(e) =>
                      setDevices(devices.map((d) =>
                        d.id === device.id ? { ...d, unitId: e.target.value } : d
                      ))
                    }
                    className="bg-secondary/50"
                  />
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Battery Devices */}
        <div className="space-y-4">
          {batteryDevices.map((device, index) => (
            <motion.div
              key={device.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 + index * 0.05 }}
              className="glass-card p-4 space-y-4"
            >
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-medium text-foreground">{device.name}</span>
                <Badge variant="destructive" className="gap-1">
                  <WifiOff className="w-3 h-3" />
                  Disconnected
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Last update: {device.lastUpdate}
                </span>
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => handleTestConnection(device.id)}
                  className="text-primary ml-auto"
                >
                  Test Connection
                </Button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Battery</Label>
                  <Select
                    value={device.model}
                    onValueChange={(value) =>
                      setBatteryDevices(batteryDevices.map((d) =>
                        d.id === device.id ? { ...d, model: value } : d
                      ))
                    }
                  >
                    <SelectTrigger className="bg-secondary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="USB PYTES">USB PYTES</SelectItem>
                      <SelectItem value="Pylontech">Pylontech</SelectItem>
                      <SelectItem value="EVE">EVE</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Connections</Label>
                  <Select
                    value={device.connection}
                    onValueChange={(value) =>
                      setBatteryDevices(batteryDevices.map((d) =>
                        d.id === device.id ? { ...d, connection: value } : d
                      ))
                    }
                  >
                    <SelectTrigger className="bg-secondary/50">
                      <SelectValue placeholder="Select port..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="usb1">USB Port 1</SelectItem>
                      <SelectItem value="usb2">USB Port 2</SelectItem>
                      <SelectItem value="can">CAN Bus</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Batteries</Label>
                  <Input
                    value={device.unitId}
                    onChange={(e) =>
                      setBatteryDevices(batteryDevices.map((d) =>
                        d.id === device.id ? { ...d, unitId: e.target.value } : d
                      ))
                    }
                    className="bg-secondary/50"
                  />
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <Button onClick={handleSave} className="gap-2">
            Save Device Configuration
          </Button>
        </div>
      </div>
    </AppLayout>
  );
};

export default DeviceManagementPage;
