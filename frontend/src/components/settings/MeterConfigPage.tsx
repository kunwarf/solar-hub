import { useState } from "react";
import { motion } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Gauge, Settings2, Plug, Network } from "lucide-react";

interface MeterConfig {
  id: string;
  name: string;
  array_id: string;
  adapter: {
    type: string;
    transport: string;
    host: string;
    port: number;
    unit_id: number;
    prefer_legacy_registers: boolean;
    // RTU-specific fields
    serial_port: string;
    baudrate: number;
    parity: string;
    stopbits: number;
    bytesize: number;
  };
}

interface MeterConfigPageProps {
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

export function MeterConfigPage({ deviceId, deviceName }: MeterConfigPageProps) {
  const [config, setConfig] = useState<MeterConfig>({
    id: deviceId || "grid_meter_1",
    name: deviceName || "IAMMeter",
    array_id: "home",
    adapter: {
      type: "iammeter",
      transport: "tcp",
      host: "192.168.88.23",
      port: 502,
      unit_id: 1,
      prefer_legacy_registers: true,
      serial_port: "/dev/ttyUSB0",
      baudrate: 9600,
      parity: "N",
      stopbits: 1,
      bytesize: 8,
    },
  });

  const updateAdapter = (key: keyof MeterConfig["adapter"], value: string | number | boolean) => {
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
        <TabsTrigger value="network" className="gap-2">
          <Network className="w-4 h-4 hidden sm:inline" />
          Connection
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
            <Gauge className="w-4 h-4 text-grid" />
            Device Identity
          </h3>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Device ID</Label>
              <Input
                value={config.id}
                onChange={(e) => setConfig(prev => ({ ...prev, id: e.target.value }))}
                className="bg-secondary/50 font-mono"
                placeholder="grid_meter_1"
              />
              <p className="text-xs text-muted-foreground">Unique identifier for this device</p>
            </div>
            <div className="space-y-2">
              <Label>Device Name</Label>
              <Input
                value={config.name}
                onChange={(e) => setConfig(prev => ({ ...prev, name: e.target.value }))}
                className="bg-secondary/50"
                placeholder="IAMMeter"
              />
              <p className="text-xs text-muted-foreground">Display name for the device</p>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Measurement Point</Label>
            <Select
              value={config.array_id}
              onValueChange={(v) => setConfig(prev => ({ ...prev, array_id: v }))}
            >
              <SelectTrigger className="bg-secondary/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="home">Home (Total Consumption)</SelectItem>
                <SelectItem value="array1">Array 1</SelectItem>
                <SelectItem value="array2">Array 2</SelectItem>
                <SelectItem value="grid">Grid Connection Point</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">Where this meter measures energy flow</p>
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
            Adapter Configuration
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Meter Type</Label>
              <Select
                value={config.adapter.type}
                onValueChange={(v) => updateAdapter("type", v)}
              >
                <SelectTrigger className="bg-secondary/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="iammeter">IAMMeter</SelectItem>
                  <SelectItem value="sdm120">Eastron SDM120</SelectItem>
                  <SelectItem value="sdm630">Eastron SDM630</SelectItem>
                  <SelectItem value="dds238">DDS238</SelectItem>
                  <SelectItem value="generic_modbus">Generic Modbus</SelectItem>
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
                  <SelectItem value="tcp">TCP (Modbus TCP)</SelectItem>
                  <SelectItem value="rtu">RTU (Serial)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Unit ID (Modbus Address)</Label>
            <Input
              type="number"
              value={config.adapter.unit_id}
              onChange={(e) => updateAdapter("unit_id", parseInt(e.target.value))}
              className="bg-secondary/50"
              min={1}
              max={247}
            />
            <p className="text-xs text-muted-foreground">Modbus slave address (1-247)</p>
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
            <div>
              <Label className="flex items-center gap-2">
                Prefer Legacy Registers
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                Use legacy register map for older firmware
              </p>
            </div>
            <Switch
              checked={config.adapter.prefer_legacy_registers}
              onCheckedChange={(v) => updateAdapter("prefer_legacy_registers", v)}
            />
          </div>
        </motion.div>
      </TabsContent>

      {/* Connection Tab */}
      <TabsContent value="network" className="space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 space-y-4"
        >
          {config.adapter.transport === "tcp" ? (
            <>
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Network className="w-4 h-4 text-grid" />
                TCP/IP Settings
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Host IP Address</Label>
                  <Input
                    value={config.adapter.host}
                    onChange={(e) => updateAdapter("host", e.target.value)}
                    className="bg-secondary/50 font-mono"
                    placeholder="192.168.1.100"
                  />
                  <p className="text-xs text-muted-foreground">IP address of the meter</p>
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
            </>
          ) : (
            <>
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Plug className="w-4 h-4 text-grid" />
                Serial Port Settings
              </h3>

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

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <Label>Baudrate</Label>
                  <Select
                    value={(config.adapter.baudrate || 9600).toString()}
                    onValueChange={(v) => updateAdapter("baudrate", parseInt(v))}
                  >
                    <SelectTrigger className="bg-secondary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="4800">4800</SelectItem>
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
                    value={config.adapter.parity || "N"}
                    onValueChange={(v) => updateAdapter("parity", v)}
                  >
                    <SelectTrigger className="bg-secondary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="N">None</SelectItem>
                      <SelectItem value="E">Even</SelectItem>
                      <SelectItem value="O">Odd</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Stop Bits</Label>
                  <Select
                    value={(config.adapter.stopbits || 1).toString()}
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
                    value={(config.adapter.bytesize || 8).toString()}
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
            </>
          )}
        </motion.div>
      </TabsContent>
    </Tabs>
  );
}
