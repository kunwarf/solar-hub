import { useState } from "react";
import { motion } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Battery, Settings2, Plug, Info } from "lucide-react";

interface BatteryConfig {
  id: string;
  name: string;
  array_id: string;
  adapter: {
    type: string;
    transport: string;
    // RTU fields
    serial_port: string;
    baudrate: number;
    parity: string;
    stopbits: number;
    bytesize: number;
    // TCP fields
    host: string;
    port: number;
    // Battery-specific
    batteries: number;
    cells_per_battery: number;
    dev_name: string;
    manufacturer: string;
    model: string;
  };
}

interface BatteryConfigPageProps {
  deviceId?: string;
  deviceName?: string;
}

// Mock available USB serial ports
const availableSerialPorts = [
  { value: "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9U593Y5-if00-port0", label: "FTDI FT232R USB UART (A9U593Y5)" },
  { value: "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_CVCLe12CJ06-if00-port0", label: "Prolific USB-Serial (CVCLe12CJ06)" },
  { value: "/dev/ttyUSB0", label: "/dev/ttyUSB0" },
  { value: "/dev/ttyUSB1", label: "/dev/ttyUSB1" },
  { value: "COM1", label: "COM1 (Windows)" },
  { value: "COM3", label: "COM3 (Windows)" },
];

export function BatteryConfigPage({ deviceId, deviceName }: BatteryConfigPageProps) {
  const [config, setConfig] = useState<BatteryConfig>({
    id: deviceId || "battery1",
    name: deviceName || "Pylontech Battery Bank",
    array_id: "array1",
    adapter: {
      type: "pytes",
      transport: "rtu",
      serial_port: "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9U593Y5-if00-port0",
      baudrate: 115200,
      parity: "N",
      stopbits: 1,
      bytesize: 8,
      host: "192.168.1.100",
      port: 502,
      batteries: 4,
      cells_per_battery: 15,
      dev_name: "pytes",
      manufacturer: "PYTES Energy Co.Ltd",
      model: "USP5000",
    },
  });

  const updateAdapter = (key: keyof BatteryConfig["adapter"], value: string | number) => {
    setConfig(prev => ({
      ...prev,
      adapter: { ...prev.adapter, [key]: value },
    }));
  };

  return (
    <Tabs defaultValue="general" className="w-full">
      <TabsList className="grid w-full grid-cols-3 mb-4">
        <TabsTrigger value="general" className="gap-2">
          <Settings2 className="w-4 h-4 hidden sm:inline" />
          General
        </TabsTrigger>
        <TabsTrigger value="adapter" className="gap-2">
          <Plug className="w-4 h-4 hidden sm:inline" />
          Adapter
        </TabsTrigger>
        <TabsTrigger value="battery" className="gap-2">
          <Battery className="w-4 h-4 hidden sm:inline" />
          Battery Bank
        </TabsTrigger>
      </TabsList>

      {/* General Tab */}
      <TabsContent value="general" className="space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 space-y-4"
        >
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Battery className="w-4 h-4 text-battery" />
            Device Identity
          </h3>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Device ID</Label>
              <Input
                value={config.id}
                onChange={(e) => setConfig(prev => ({ ...prev, id: e.target.value }))}
                className="bg-secondary/50 font-mono"
                placeholder="battery1"
              />
              <p className="text-xs text-muted-foreground">Unique identifier for this device</p>
            </div>
            <div className="space-y-2">
              <Label>Device Name</Label>
              <Input
                value={config.name}
                onChange={(e) => setConfig(prev => ({ ...prev, name: e.target.value }))}
                className="bg-secondary/50"
                placeholder="Pylontech Battery Bank"
              />
              <p className="text-xs text-muted-foreground">Display name for the device</p>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Array Assignment</Label>
            <Select
              value={config.array_id}
              onValueChange={(v) => setConfig(prev => ({ ...prev, array_id: v }))}
            >
              <SelectTrigger className="bg-secondary/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="array1">Array 1</SelectItem>
                <SelectItem value="array2">Array 2</SelectItem>
                <SelectItem value="battery_array1">Battery Array 1</SelectItem>
                <SelectItem value="battery_array2">Battery Array 2</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">Assign this battery to a battery array</p>
          </div>

          <div className="p-3 rounded-lg bg-battery/10 border border-battery/20">
            <div className="flex items-start gap-2">
              <Info className="w-4 h-4 text-battery mt-0.5" />
              <div className="text-xs text-muted-foreground">
                <p className="font-medium text-foreground mb-1">Battery Bank Configuration</p>
                <p>This device communicates with your battery management system (BMS) to monitor state of charge, cell voltages, temperatures, and more.</p>
              </div>
            </div>
          </div>
        </motion.div>
      </TabsContent>

      {/* Adapter Tab */}
      <TabsContent value="adapter" className="space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 space-y-4"
        >
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Plug className="w-4 h-4 text-primary" />
            Communication Settings
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Adapter Type</Label>
              <Select
                value={config.adapter.type}
                onValueChange={(v) => updateAdapter("type", v)}
              >
                <SelectTrigger className="bg-secondary/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pytes">Pytes/Pylontech</SelectItem>
                  <SelectItem value="byd">BYD</SelectItem>
                  <SelectItem value="pylontech">Pylontech (Legacy)</SelectItem>
                  <SelectItem value="seplos">Seplos</SelectItem>
                  <SelectItem value="jbd">JBD BMS</SelectItem>
                  <SelectItem value="daly">Daly BMS</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Transport Protocol</Label>
              <Select
                value={config.adapter.transport}
                onValueChange={(v) => updateAdapter("transport", v)}
              >
                <SelectTrigger className="bg-secondary/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rtu">RTU (Serial)</SelectItem>
                  <SelectItem value="tcp">TCP (Modbus TCP)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Device Name</Label>
            <Input
              value={config.adapter.dev_name}
              onChange={(e) => updateAdapter("dev_name", e.target.value)}
              className="bg-secondary/50"
              placeholder="pytes"
            />
          </div>

          {/* Conditional fields based on transport */}
          {config.adapter.transport === "rtu" ? (
            <>
              <div className="space-y-2">
                <Label>Serial Port</Label>
                <Select
                  value={config.adapter.serial_port}
                  onValueChange={(v) => updateAdapter("serial_port", v)}
                >
                  <SelectTrigger className="bg-secondary/50 font-mono text-xs">
                    <SelectValue placeholder="Select serial port" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableSerialPorts.map((port) => (
                      <SelectItem key={port.value} value={port.value}>
                        {port.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">Select USB serial device for communication</p>
              </div>
            </>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Host IP Address</Label>
                <Input
                  value={config.adapter.host}
                  onChange={(e) => updateAdapter("host", e.target.value)}
                  className="bg-secondary/50 font-mono"
                  placeholder="192.168.1.100"
                />
                <p className="text-xs text-muted-foreground">IP address of the battery BMS</p>
              </div>
              <div className="space-y-2">
                <Label>Port</Label>
                <Input
                  type="number"
                  value={config.adapter.port}
                  onChange={(e) => updateAdapter("port", parseInt(e.target.value))}
                  className="bg-secondary/50"
                  min={1}
                  max={65535}
                />
                <p className="text-xs text-muted-foreground">Modbus TCP port (default: 502)</p>
              </div>
            </div>
          )}

          {/* Serial settings only shown for RTU */}
          {config.adapter.transport === "rtu" && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label>Baudrate</Label>
                <Select
                  value={config.adapter.baudrate.toString()}
                  onValueChange={(v) => updateAdapter("baudrate", parseInt(v))}
                >
                  <SelectTrigger className="bg-secondary/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="9600">9600</SelectItem>
                    <SelectItem value="19200">19200</SelectItem>
                    <SelectItem value="38400">38400</SelectItem>
                    <SelectItem value="57600">57600</SelectItem>
                    <SelectItem value="115200">115200</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Parity</Label>
                <Select
                  value={config.adapter.parity}
                  onValueChange={(v) => updateAdapter("parity", v)}
                >
                  <SelectTrigger className="bg-secondary/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="N">None (N)</SelectItem>
                    <SelectItem value="E">Even (E)</SelectItem>
                    <SelectItem value="O">Odd (O)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Stop Bits</Label>
                <Select
                  value={config.adapter.stopbits.toString()}
                  onValueChange={(v) => updateAdapter("stopbits", parseInt(v))}
                >
                  <SelectTrigger className="bg-secondary/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1</SelectItem>
                    <SelectItem value="2">2</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Byte Size</Label>
                <Select
                  value={config.adapter.bytesize.toString()}
                  onValueChange={(v) => updateAdapter("bytesize", parseInt(v))}
                >
                  <SelectTrigger className="bg-secondary/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="7">7</SelectItem>
                    <SelectItem value="8">8</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
        </motion.div>
      </TabsContent>

      {/* Battery Bank Tab */}
      <TabsContent value="battery" className="space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 space-y-4"
        >
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Battery className="w-4 h-4 text-battery" />
            Battery Bank Configuration
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Number of Batteries</Label>
              <Input
                type="number"
                value={config.adapter.batteries}
                onChange={(e) => updateAdapter("batteries", parseInt(e.target.value))}
                className="bg-secondary/50"
                min={1}
                max={16}
              />
              <p className="text-xs text-muted-foreground">Total batteries in the bank</p>
            </div>
            <div className="space-y-2">
              <Label>Cells per Battery</Label>
              <Input
                type="number"
                value={config.adapter.cells_per_battery}
                onChange={(e) => updateAdapter("cells_per_battery", parseInt(e.target.value))}
                className="bg-secondary/50"
                min={1}
                max={24}
              />
              <p className="text-xs text-muted-foreground">Number of cells in each battery module</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Manufacturer</Label>
              <Input
                value={config.adapter.manufacturer}
                onChange={(e) => updateAdapter("manufacturer", e.target.value)}
                className="bg-secondary/50"
                placeholder="PYTES Energy Co.Ltd"
              />
            </div>
            <div className="space-y-2">
              <Label>Model</Label>
              <Input
                value={config.adapter.model}
                onChange={(e) => updateAdapter("model", e.target.value)}
                className="bg-secondary/50"
                placeholder="USP5000"
              />
            </div>
          </div>

          {/* Summary */}
          <div className="p-4 rounded-lg bg-secondary/30 space-y-2">
            <h4 className="text-sm font-medium text-foreground">Bank Summary</h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Batteries:</span>
                <span className="font-mono text-foreground">{config.adapter.batteries}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Cells:</span>
                <span className="font-mono text-foreground">{config.adapter.batteries * config.adapter.cells_per_battery}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Manufacturer:</span>
                <span className="font-medium text-foreground">{config.adapter.manufacturer}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Model:</span>
                <span className="font-medium text-foreground">{config.adapter.model}</span>
              </div>
            </div>
          </div>
        </motion.div>
      </TabsContent>
    </Tabs>
  );
}
