// Mock data for the solar monitoring application

// ============= HIERARCHY STRUCTURE =============
// Home > System > [Inverter Arrays, Battery Arrays, Meters]
// A Home can have multiple Systems (electrical circuits)
// Meters can exist at both Home level and System level
// Inverter Arrays and Battery Arrays are siblings under System

export interface BatteryBank {
  id: string;
  name: string;
  model: string;
  serialNumber: string;
  status: "online" | "offline" | "warning";
  metrics: {
    soc: number;
    power: number; // positive = charging, negative = discharging
    voltage: number;
    temperature: number;
  };
}

export interface BatteryArray {
  id: string;
  name: string;
  batteries: BatteryBank[];
}

export interface Inverter {
  id: string;
  name: string;
  model: string;
  serialNumber: string;
  status: "online" | "offline" | "warning";
  metrics: {
    solarPower: number;
    gridPower: number;
    loadPower: number;
    batteryPower: number;
    efficiency: number;
    dcVoltage: number;
    temperature: number;
  };
}

export interface InverterArray {
  id: string;
  name: string;
  inverters: Inverter[];
}

export interface Meter {
  id: string;
  name: string;
  model: string;
  serialNumber: string;
  status: "online" | "offline" | "warning";
  metrics: {
    power: number;
    importKwh: number;
    exportKwh: number;
    frequency: number;
    powerFactor: number;
  };
}

export interface System {
  id: string;
  name: string;
  inverterArrays: InverterArray[];
  batteryArrays: BatteryArray[];
  meters: Meter[];
}

export interface HomeHierarchy {
  id: string;
  name: string;
  systems: System[];
  meters: Meter[]; // Home-level meters (e.g., main grid meter)
}

// ============= HIERARCHICAL DATA =============
export const homeHierarchy: HomeHierarchy = {
  id: "home-001",
  name: "Home Solar System",
  systems: [
    {
      id: "sys-001",
      name: "Main Circuit",
      inverterArrays: [
        {
          id: "inv-array-1",
          name: "Rooftop Array - East",
          inverters: [
            {
              id: "inv-001",
              name: "Inverter 1A",
              model: "SolarMax 10K",
              serialNumber: "SM-2024-INV-001",
              status: "online",
              metrics: {
                solarPower: 4.2,
                gridPower: 0.5,
                loadPower: 2.1,
                batteryPower: 1.6,
                efficiency: 97.2,
                dcVoltage: 580,
                temperature: 42,
              },
            },
            {
              id: "inv-002",
              name: "Inverter 1B",
              model: "SolarMax 10K",
              serialNumber: "SM-2024-INV-002",
              status: "online",
              metrics: {
                solarPower: 4.5,
                gridPower: 0.3,
                loadPower: 2.3,
                batteryPower: 1.9,
                efficiency: 96.8,
                dcVoltage: 575,
                temperature: 44,
              },
            },
          ],
        },
        {
          id: "inv-array-2",
          name: "Rooftop Array - West",
          inverters: [
            {
              id: "inv-003",
              name: "Inverter 2A",
              model: "SolarMax 10K",
              serialNumber: "SM-2024-INV-003",
              status: "online",
              metrics: {
                solarPower: 3.8,
                gridPower: 0.2,
                loadPower: 1.8,
                batteryPower: 1.8,
                efficiency: 97.5,
                dcVoltage: 582,
                temperature: 40,
              },
            },
          ],
        },
      ],
      batteryArrays: [
        {
          id: "bat-array-1",
          name: "Battery Bank - East",
          batteries: [
            {
              id: "bat-001",
              name: "Battery 1A",
              model: "PowerStore 15kWh",
              serialNumber: "PS-2024-BAT-001",
              status: "online",
              metrics: {
                soc: 78,
                power: 2.1,
                voltage: 52.4,
                temperature: 28,
              },
            },
            {
              id: "bat-002",
              name: "Battery 1B",
              model: "PowerStore 15kWh",
              serialNumber: "PS-2024-BAT-002",
              status: "online",
              metrics: {
                soc: 82,
                power: 1.4,
                voltage: 52.8,
                temperature: 27,
              },
            },
          ],
        },
      ],
      meters: [
        {
          id: "mtr-002",
          name: "System 1 Meter",
          model: "GridSense Lite",
          serialNumber: "GS-2024-MTR-002",
          status: "online",
          metrics: {
            power: -0.8,
            importKwh: 1.2,
            exportKwh: 5.4,
            frequency: 50.01,
            powerFactor: 0.97,
          },
        },
      ],
    },
    {
      id: "sys-002",
      name: "Ground Mount Circuit",
      inverterArrays: [
        {
          id: "inv-array-3",
          name: "Ground Array",
          inverters: [
            {
              id: "inv-004",
              name: "Inverter 3A",
              model: "SolarMax 15K",
              serialNumber: "SM-2024-INV-004",
              status: "online",
              metrics: {
                solarPower: 5.2,
                gridPower: 0.1,
                loadPower: 2.5,
                batteryPower: 2.6,
                efficiency: 98.1,
                dcVoltage: 590,
                temperature: 38,
              },
            },
            {
              id: "inv-005",
              name: "Inverter 3B",
              model: "SolarMax 15K",
              serialNumber: "SM-2024-INV-005",
              status: "warning",
              metrics: {
                solarPower: 4.8,
                gridPower: 0.0,
                loadPower: 2.2,
                batteryPower: 2.6,
                efficiency: 95.5,
                dcVoltage: 585,
                temperature: 48,
              },
            },
          ],
        },
      ],
      batteryArrays: [
        {
          id: "bat-array-2",
          name: "Battery Bank - Ground",
          batteries: [
            {
              id: "bat-003",
              name: "Battery 2A",
              model: "PowerStore 10kWh",
              serialNumber: "PS-2024-BAT-003",
              status: "warning",
              metrics: {
                soc: 45,
                power: -1.2,
                voltage: 51.2,
                temperature: 32,
              },
            },
          ],
        },
      ],
      meters: [],
    },
  ],
  meters: [
    {
      id: "mtr-001",
      name: "Main Grid Meter",
      model: "GridSense Pro",
      serialNumber: "GS-2024-MTR-001",
      status: "online",
      metrics: {
        power: -1.1,
        importKwh: 2.5,
        exportKwh: 8.2,
        frequency: 50.02,
        powerFactor: 0.98,
      },
    },
  ],
};

// ============= AGGREGATION HELPERS =============
export function getInverterArrayAggregates(array: InverterArray) {
  return array.inverters.reduce(
    (acc, inv) => ({
      solarPower: acc.solarPower + inv.metrics.solarPower,
      gridPower: acc.gridPower + inv.metrics.gridPower,
      loadPower: acc.loadPower + inv.metrics.loadPower,
      batteryPower: acc.batteryPower + inv.metrics.batteryPower,
      inverterCount: acc.inverterCount + 1,
      onlineCount: acc.onlineCount + (inv.status === "online" ? 1 : 0),
      warningCount: acc.warningCount + (inv.status === "warning" ? 1 : 0),
    }),
    { solarPower: 0, gridPower: 0, loadPower: 0, batteryPower: 0, inverterCount: 0, onlineCount: 0, warningCount: 0 }
  );
}

export function getBatteryArrayAggregates(array: BatteryArray) {
  const totals = array.batteries.reduce(
    (acc, bat) => ({
      totalPower: acc.totalPower + bat.metrics.power,
      totalSoc: acc.totalSoc + bat.metrics.soc,
      batteryCount: acc.batteryCount + 1,
      onlineCount: acc.onlineCount + (bat.status === "online" ? 1 : 0),
      warningCount: acc.warningCount + (bat.status === "warning" ? 1 : 0),
    }),
    { totalPower: 0, totalSoc: 0, batteryCount: 0, onlineCount: 0, warningCount: 0 }
  );
  return {
    ...totals,
    avgSoc: totals.batteryCount > 0 ? totals.totalSoc / totals.batteryCount : 0,
  };
}

export function getSystemAggregates(system: System) {
  let solarPower = 0;
  let gridPower = 0;
  let loadPower = 0;
  let batteryPower = 0;
  let totalSoc = 0;
  let batteryCount = 0;
  let inverterCount = 0;
  let onlineInverters = 0;
  let warningInverters = 0;
  let onlineBatteries = 0;
  let warningBatteries = 0;

  system.inverterArrays.forEach((invArray) => {
    const invAgg = getInverterArrayAggregates(invArray);
    solarPower += invAgg.solarPower;
    gridPower += invAgg.gridPower;
    loadPower += invAgg.loadPower;
    batteryPower += invAgg.batteryPower;
    inverterCount += invAgg.inverterCount;
    onlineInverters += invAgg.onlineCount;
    warningInverters += invAgg.warningCount;
  });

  system.batteryArrays.forEach((batArray) => {
    const batAgg = getBatteryArrayAggregates(batArray);
    totalSoc += batAgg.totalSoc;
    batteryCount += batAgg.batteryCount;
    onlineBatteries += batAgg.onlineCount;
    warningBatteries += batAgg.warningCount;
  });

  const avgBatterySoc = batteryCount > 0 ? totalSoc / batteryCount : 0;

  return {
    solarPower,
    gridPower,
    loadPower,
    batteryPower,
    avgBatterySoc,
    batteryCount,
    inverterCount,
    onlineInverters,
    warningInverters,
    onlineBatteries,
    warningBatteries,
  };
}

export function getHomeAggregates(home: HomeHierarchy) {
  let solarPower = 0;
  let gridPower = 0;
  let loadPower = 0;
  let batteryPower = 0;
  let totalSoc = 0;
  let batteryCount = 0;
  let inverterCount = 0;

  home.systems.forEach((system) => {
    const sysAgg = getSystemAggregates(system);
    solarPower += sysAgg.solarPower;
    gridPower += sysAgg.gridPower;
    loadPower += sysAgg.loadPower;
    batteryPower += sysAgg.batteryPower;
    totalSoc += sysAgg.avgBatterySoc * sysAgg.batteryCount;
    batteryCount += sysAgg.batteryCount;
    inverterCount += sysAgg.inverterCount;
  });

  const avgBatterySoc = batteryCount > 0 ? totalSoc / batteryCount : 0;

  return {
    solarPower,
    gridPower,
    loadPower,
    batteryPower,
    avgBatterySoc,
    batteryCount,
    inverterCount,
    isGridExporting: gridPower < 0 || (home.meters[0]?.metrics.power ?? 0) < 0,
  };
}

// ============= HOME-LEVEL AGGREGATED STATS =============
const homeAgg = getHomeAggregates(homeHierarchy);

export const energyStats = {
  solarPower: parseFloat(homeAgg.solarPower.toFixed(1)),
  batteryPower: parseFloat(Math.abs(homeAgg.batteryPower).toFixed(1)),
  batteryLevel: Math.round(homeAgg.avgBatterySoc),
  consumption: parseFloat(homeAgg.loadPower.toFixed(1)),
  gridPower: parseFloat(Math.abs(homeHierarchy.meters[0]?.metrics.power ?? homeAgg.gridPower).toFixed(1)),
  isGridExporting: homeAgg.isGridExporting,
  dailyProduction: 42.6,
  dailyConsumption: 38.2,
  selfConsumption: 89,
  gridExported: 4.4,
  co2Saved: 18.7,
  moneySaved: 12.45,
  monthlyBillAmount: 48.20,
  dailyPrediction: 45.0,
  avgKwPerKwp: 4.26,
  installedCapacity: 10,
};

// ============= FLAT DEVICES LIST (for compatibility) =============
export const devices = [
  ...homeHierarchy.systems.flatMap((system) =>
    system.inverterArrays.flatMap((array) =>
      array.inverters.map((inv) => ({
        id: inv.id,
        name: inv.name,
        type: "inverter" as const,
        status: inv.status,
        model: inv.model,
        serialNumber: inv.serialNumber,
        value: inv.metrics.solarPower.toFixed(1),
        unit: "kW",
        metrics: [
          { label: "Power Output", value: inv.metrics.solarPower.toFixed(1), unit: "kW" },
          { label: "Efficiency", value: inv.metrics.efficiency.toFixed(1), unit: "%" },
          { label: "DC Voltage", value: inv.metrics.dcVoltage.toString(), unit: "V" },
          { label: "Temperature", value: inv.metrics.temperature.toString(), unit: "°C" },
        ],
      }))
    )
  ),
  ...homeHierarchy.systems.flatMap((system) =>
    system.batteryArrays.flatMap((array) =>
      array.batteries.map((bat) => ({
        id: bat.id,
        name: bat.name,
        type: "battery" as const,
        status: bat.status,
        model: bat.model,
        serialNumber: bat.serialNumber,
        value: bat.metrics.soc.toString(),
        unit: "%",
        metrics: [
          { label: "State of Charge", value: bat.metrics.soc.toString(), unit: "%" },
          { label: bat.metrics.power >= 0 ? "Charge Rate" : "Discharge Rate", value: Math.abs(bat.metrics.power).toFixed(1), unit: "kW" },
          { label: "Voltage", value: bat.metrics.voltage.toFixed(1), unit: "V" },
          { label: "Temperature", value: bat.metrics.temperature.toString(), unit: "°C" },
        ],
      }))
    )
  ),
  // System-level meters
  ...homeHierarchy.systems.flatMap((system) =>
    system.meters.map((meter) => ({
      id: meter.id,
      name: meter.name,
      type: "meter" as const,
      status: meter.status,
      model: meter.model,
      serialNumber: meter.serialNumber,
      value: Math.abs(meter.metrics.power).toFixed(1),
      unit: "kW",
      metrics: [
        { label: "Power", value: Math.abs(meter.metrics.power).toFixed(1), unit: "kW" },
        { label: meter.metrics.power >= 0 ? "Importing" : "Exporting", value: Math.abs(meter.metrics.power).toFixed(1), unit: "kW" },
        { label: "Frequency", value: meter.metrics.frequency.toFixed(2), unit: "Hz" },
        { label: "Power Factor", value: meter.metrics.powerFactor.toFixed(2), unit: "" },
      ],
    }))
  ),
  // Home-level meters
  ...homeHierarchy.meters.map((meter) => ({
    id: meter.id,
    name: meter.name,
    type: "meter" as const,
    status: meter.status,
    model: meter.model,
    serialNumber: meter.serialNumber,
    value: Math.abs(meter.metrics.power).toFixed(1),
    unit: "kW",
    metrics: [
      { label: "Power", value: Math.abs(meter.metrics.power).toFixed(1), unit: "kW" },
      { label: meter.metrics.power >= 0 ? "Importing" : "Exporting", value: Math.abs(meter.metrics.power).toFixed(1), unit: "kW" },
      { label: "Frequency", value: meter.metrics.frequency.toFixed(2), unit: "Hz" },
      { label: "Power Factor", value: meter.metrics.powerFactor.toFixed(2), unit: "" },
    ],
  })),
];

export const chartData = Array.from({ length: 24 }, (_, i) => {
  const hour = i;
  const sunIntensity = Math.max(0, Math.sin((hour - 6) * Math.PI / 12));
  return {
    time: `${hour.toString().padStart(2, "0")}:00`,
    solar: parseFloat((sunIntensity * 10 + Math.random() * 2).toFixed(1)),
    consumption: parseFloat((3 + Math.random() * 4 + (hour >= 18 && hour <= 22 ? 3 : 0)).toFixed(1)),
    battery: parseFloat((sunIntensity > 0.5 ? 2 + Math.random() : -1 - Math.random()).toFixed(1)),
    grid: parseFloat((Math.random() * 2 - 1).toFixed(1)),
  };
});

export const telemetryData = [
  { id: "1", timestamp: "14:32:15", parameter: "DC Voltage", value: "580.2", unit: "V", status: "normal" as const },
  { id: "2", timestamp: "14:32:15", parameter: "AC Current", value: "22.4", unit: "A", status: "normal" as const },
  { id: "3", timestamp: "14:32:15", parameter: "Power Output", value: "8.42", unit: "kW", status: "normal" as const },
  { id: "4", timestamp: "14:32:15", parameter: "Inverter Temp", value: "42.1", unit: "°C", status: "normal" as const },
  { id: "5", timestamp: "14:32:15", parameter: "Efficiency", value: "97.2", unit: "%", status: "normal" as const },
  { id: "6", timestamp: "14:32:15", parameter: "Battery SOC", value: "78", unit: "%", status: "normal" as const },
  { id: "7", timestamp: "14:32:15", parameter: "Battery Temp", value: "32.5", unit: "°C", status: "warning" as const },
  { id: "8", timestamp: "14:32:15", parameter: "Cell Voltage", value: "3.42", unit: "V", status: "normal" as const },
  { id: "9", timestamp: "14:32:15", parameter: "Grid Frequency", value: "50.02", unit: "Hz", status: "normal" as const },
  { id: "10", timestamp: "14:32:15", parameter: "Power Factor", value: "0.98", unit: "", status: "normal" as const },
];

export const billingData = {
  currentPeriod: {
    startDate: "2024-11-01",
    endDate: "2024-11-30",
    daysRemaining: 12,
  },
  energyProduced: 1284.6,
  energyConsumed: 892.4,
  energyExported: 392.2,
  energyImported: 124.8,
  feedInRate: 0.08,
  importRate: 0.24,
  earnings: 31.38,
  costs: 29.95,
  netBalance: 1.43,
  monthlyHistory: [
    { month: "Jun", produced: 1456, consumed: 780, exported: 676, imported: 98, earnings: 54.08, costs: 23.52, netBalance: 30.56, lastYearBill: 68.50, thisYearBill: 23.52 },
    { month: "Jul", produced: 1589, consumed: 820, exported: 769, imported: 112, earnings: 61.52, costs: 26.88, netBalance: 34.64, lastYearBill: 72.40, thisYearBill: 26.88 },
    { month: "Aug", produced: 1423, consumed: 856, exported: 567, imported: 134, earnings: 45.36, costs: 32.16, netBalance: 13.20, lastYearBill: 78.20, thisYearBill: 32.16 },
    { month: "Sep", produced: 1234, consumed: 890, exported: 344, imported: 156, earnings: 27.52, costs: 37.44, netBalance: -9.92, lastYearBill: 85.60, thisYearBill: 37.44 },
    { month: "Oct", produced: 1089, consumed: 912, exported: 177, imported: 189, earnings: 14.16, costs: 45.36, netBalance: -31.20, lastYearBill: 92.30, thisYearBill: 45.36 },
    { month: "Nov", produced: 1284, consumed: 892, exported: 392, imported: 125, earnings: 31.38, costs: 29.95, netBalance: 1.43, lastYearBill: 88.75, thisYearBill: 29.95 },
  ],
};

export const settingsData = {
  system: {
    name: "Home Solar System",
    location: "123 Solar Street, Sunnyvale",
    timezone: "UTC+5:00",
    currency: "USD",
  },
  notifications: {
    email: true,
    push: true,
    sms: false,
    alerts: {
      lowBattery: 20,
      highTemperature: 50,
      gridOutage: true,
      maintenanceReminder: true,
    },
  },
  gridExport: {
    enabled: true,
    maxExportPower: 10,
    feedInTariff: 0.08,
    peakHoursStart: "18:00",
    peakHoursEnd: "22:00",
  },
  battery: {
    minimumSoc: 10,
    maximumSoc: 95,
    chargePriority: "solar-first",
    dischargePriority: "peak-shaving",
  },
};
