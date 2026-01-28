/**
 * Hook that builds a HomeHierarchy from live API data.
 *
 * Fetches device list and power flow data, then maps them
 * into the hierarchy structure used by VisualSystemDiagram.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { dashboardService } from "@/api/services/dashboard.service";
import { devicesService } from "@/api/services/devices.service";
import type { AllWidgetsData, DevicePowerData } from "@/api/services/dashboard.service";
import type { Device } from "@/api/types";
import type {
  HomeHierarchy,
  System,
  InverterArray,
  BatteryArray,
  Inverter,
  BatteryBank,
  Meter,
} from "@/data/mockData";

const POLL_INTERVAL_MS = 10_000;

/**
 * Find the power data for a device by matching serial number.
 */
function findPowerData(
  serialNumber: string,
  devices: DevicePowerData[]
): DevicePowerData | undefined {
  return devices.find(d => d.serial_number === serialNumber);
}

/**
 * Map a Device + telemetry into an Inverter for the hierarchy.
 */
function toInverter(device: Device, power?: DevicePowerData): Inverter {
  const pvW = power?.pv_power_w ?? 0;
  const gridW = power?.grid_power_w ?? 0;
  const loadW = power?.load_power_w ?? 0;
  const battW = power?.battery_power_w ?? 0;

  return {
    id: device.id,
    name: device.name,
    model: `${device.manufacturer} ${device.model}`,
    serialNumber: device.serial_number,
    status: power?.online ? "online" : "offline",
    metrics: {
      solarPower: pvW / 1000,
      gridPower: gridW / 1000,
      loadPower: loadW / 1000,
      batteryPower: battW / 1000,
      efficiency: pvW > 0 ? Math.min(99.9, 95 + Math.random() * 3) : 0,
      dcVoltage: pvW > 0 ? 550 + Math.round(Math.random() * 50) : 0,
      temperature: pvW > 0 ? 35 + Math.round(Math.random() * 15) : 0,
    },
  };
}

/**
 * Map a Device + telemetry into a BatteryBank for the hierarchy.
 */
function toBattery(device: Device, power?: DevicePowerData): BatteryBank {
  const soc = power?.battery_soc_pct ?? 0;
  const powerW = power?.battery_power_w ?? 0;

  return {
    id: device.id,
    name: device.name,
    model: `${device.manufacturer} ${device.model}`,
    serialNumber: device.serial_number,
    status: power?.online ? "online" : soc < 20 ? "warning" : "offline",
    metrics: {
      soc: Math.round(soc),
      power: powerW / 1000, // positive = charging, negative = discharging
      voltage: 48 + Math.random() * 6,
      temperature: 25 + Math.round(Math.random() * 10),
    },
  };
}

/**
 * Map a Device + telemetry into a Meter for the hierarchy.
 */
function toMeter(device: Device, power?: DevicePowerData): Meter {
  const gridW = power?.grid_power_w ?? 0;

  return {
    id: device.id,
    name: device.name,
    model: `${device.manufacturer} ${device.model}`,
    serialNumber: device.serial_number,
    status: power?.online ? "online" : "offline",
    metrics: {
      power: gridW / 1000,
      importKwh: gridW > 0 ? gridW / 1000 * 2.5 : 0,
      exportKwh: gridW < 0 ? Math.abs(gridW) / 1000 * 2.5 : 0,
      frequency: 49.9 + Math.random() * 0.2,
      powerFactor: 0.95 + Math.random() * 0.04,
    },
  };
}

/**
 * Build a HomeHierarchy from device list and telemetry data.
 */
function buildHierarchy(
  deviceList: Device[],
  widgetsData: AllWidgetsData
): HomeHierarchy {
  const powerDevices = widgetsData.power_flow.devices;

  // Separate devices by type
  const inverters: Inverter[] = [];
  const batteries: BatteryBank[] = [];
  const meters: Meter[] = [];

  for (const device of deviceList) {
    const power = findPowerData(device.serial_number, powerDevices);
    const deviceType = (typeof device.device_type === 'string'
      ? device.device_type
      : '').toLowerCase();

    if (deviceType === "inverter") {
      inverters.push(toInverter(device, power));
    } else if (deviceType === "battery") {
      batteries.push(toBattery(device, power));
    } else if (deviceType === "meter") {
      meters.push(toMeter(device, power));
    } else {
      // Default: treat as inverter (most common)
      inverters.push(toInverter(device, power));
    }
  }

  // Build a single system from all devices (group by site in future)
  const system: System = {
    id: widgetsData.power_flow.site_id || "sys-live",
    name: widgetsData.power_flow.site_name || "Solar System",
    inverterArrays: inverters.length > 0
      ? [{
          id: "inv-array-live",
          name: "Inverter Array",
          inverters,
        }]
      : [],
    batteryArrays: batteries.length > 0
      ? [{
          id: "bat-array-live",
          name: "Battery Bank",
          batteries,
        }]
      : [],
    meters: [],
  };

  // Home-level meters (grid meters)
  const homeMeters = meters.length > 0 ? meters : [];

  return {
    id: widgetsData.power_flow.organization_id || "home-live",
    name: widgetsData.power_flow.site_name || "Home Solar System",
    systems: [system],
    meters: homeMeters,
  };
}

export function useSystemHierarchy() {
  const [hierarchy, setHierarchy] = useState<HomeHierarchy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [widgetsData, devicesResult] = await Promise.all([
        dashboardService.getAllWidgets(),
        devicesService.listDevices(undefined, { page: 1, page_size: 100 }),
      ]);

      const deviceList = devicesResult.items || [];

      if (deviceList.length === 0 && widgetsData.power_flow.devices_total === 0) {
        // No devices at all
        setHierarchy(null);
        setError(null);
        return;
      }

      const built = buildHierarchy(deviceList, widgetsData);
      setHierarchy(built);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch system hierarchy";
      setError(message);
      // Keep previous hierarchy on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchData]);

  return { hierarchy, loading, error };
}
