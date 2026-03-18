/**
 * Settings Mapper
 *
 * Converts flat API settings (from device registers) to structured component config
 */

export interface InverterConfig {
  id: string;
  name: string;
  array_id: string;
  adapter: {
    type: string;
    transport: string;
    unit_id: number;
    serial_port: string;
    baudrate: number;
    parity: string;
    stopbits: number;
    bytesize: number;
    register_map_file: string;
    host: string;
    port: number;
  };
  safety: {
    max_batt_voltage_v: number;
    max_charge_a: number;
    max_discharge_a: number;
  };
  solar: Array<{
    pv_dc_kw: number;
    tilt_deg: number;
    azimuth_deg: number;
    perf_ratio: number;
    albedo: number;
  }>;
  specification: {
    driver: string;
    serialNumber: string;
    protocolVersion: number;
    maxAcOutputPower: number;
    mpptConnections: number;
    parallelMode: boolean;
    modbusNumber: number;
  };
  gridSettings: {
    voltageHigh: number;
    voltageLow: number;
    frequency: number;
    frequencyHigh: number;
    frequencyLow: number;
    peakShavingEnabled: boolean;
  };
  batteryConfig: {
    type: string;
    capacity: number;
    operation: string;
    maxDischargeCurrent: number;
    maxChargeCurrent: number;
    maxGridChargeCurrent: number;
    maxGeneratorChargeCurrent: number;
    maxGridChargerPower: number;
    maxChargerPower: number;
    maxDischargerPower: number;
  };
  workMode: {
    remoteSwitch: boolean;
    gridCharge: boolean;
    generatorCharge: boolean;
    forceGeneratorOn: boolean;
    outputShutdownCapacity: number;
    stopBatteryDischargeCapacity: number;
    startBatteryDischargeCapacity: number;
    startGridChargeCapacity: number;
    offGridMode: boolean;
    offGridStartupBatteryCapacity: number;
  };
}

export interface TOUWindowData {
  gridCharge: boolean;  // prog_charge_mode: 0=disabled, 1=enabled
  startTime: string;
  endTime: string;
  power: number;
  targetSoc: number;
  enabled: boolean;
}

/**
 * Map API settings to InverterConfig structure
 */
export function mapApiSettingsToConfig(
  settings: Record<string, any>,
  deviceId?: string,
  deviceName?: string
): InverterConfig {
  // Convert HHMM integer (e.g. 1700 = 17:00) to HH:MM string
  const hhmmToTime = (hhmm: number): string => {
    const hours = Math.floor(hhmm / 100);
    const mins = hhmm % 100;
    return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
  };

  return {
    id: deviceId || 'device1',
    name: deviceName || 'Inverter',
    array_id: 'array1',

    // Adapter settings (these typically don't come from device registers)
    adapter: {
      type: 'powdrive',
      transport: 'rtu',
      unit_id: 1,
      serial_port: '/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0',
      baudrate: 9600,
      parity: 'N',
      stopbits: 1,
      bytesize: 8,
      register_map_file: 'register_maps/powdrive_registers.json',
      host: '192.168.1.100',
      port: 502,
    },

    // Safety limits
    safety: {
      max_batt_voltage_v: settings.battery_floating_voltage_v ?? 52,
      max_charge_a: settings.battery_max_charge_current_a ?? 100,
      max_discharge_a: settings.battery_max_discharge_current_a ?? 100,
    },

    // Solar array (placeholder - not in device settings)
    solar: [
      { pv_dc_kw: 15.4, tilt_deg: 28, azimuth_deg: 180, perf_ratio: 0.82, albedo: 0.2 },
    ],

    // Specification (placeholder - not all in device settings)
    specification: {
      driver: 'powdrive',
      serialNumber: '2406130030',
      protocolVersion: 260,
      maxAcOutputPower: settings.max_export_power_w ?? 13000,
      mpptConnections: 3,
      parallelMode: false,
      modbusNumber: 1,
    },

    // Grid settings
    gridSettings: {
      voltageHigh: settings.grid_voltage_upper_limit_v ?? 26.5,
      voltageLow: settings.grid_voltage_lower_limit_v ?? 0,
      frequency: settings.grid_frequency_hz ?? 50,
      frequencyHigh: settings.grid_frequency_upper_limit_hz ?? 0.52,
      frequencyLow: settings.grid_frequency_lower_limit_hz ?? 0.48,
      peakShavingEnabled: settings.limit_control_function === 1,
    },

    // Battery configuration
    batteryConfig: {
      type: settings.lithium_battery_type === 65535 ? 'Lithium Battery' : 'Lead Acid',
      capacity: settings.battery_capacity_ah ?? 450,
      operation: 'State of Charge',
      maxDischargeCurrent: settings.battery_max_discharge_current_a ?? 100,
      maxChargeCurrent: settings.battery_max_charge_current_a ?? 75,
      maxGridChargeCurrent: settings.grid_charge_battery_current_a ?? 20,
      maxGeneratorChargeCurrent: settings.generator_charge_battery_current_a ?? 0,
      maxGridChargerPower: settings.grid_peak_shaving_power_w ?? 8000,
      maxChargerPower: settings.max_charge_power_w ?? 8000,
      maxDischargerPower: settings.max_export_power_w ?? 13000,
    },

    // Work mode
    workMode: {
      remoteSwitch: true,
      gridCharge: settings.ac_charge_battery === 1,
      generatorCharge: settings.generator_charge_enabled === 1,
      forceGeneratorOn: false,
      outputShutdownCapacity: settings.battery_shutdown_capacity_pct ?? 10,
      stopBatteryDischargeCapacity: settings.battery_low_capacity_pct ?? 30,
      startBatteryDischargeCapacity: settings.battery_restart_capacity_pct ?? 40,
      startGridChargeCapacity: settings.grid_charging_start_capacity_pct ?? 30,
      offGridMode: settings.grid_type_setting === 0,
      offGridStartupBatteryCapacity: settings.battery_restart_capacity_pct ?? 40,
    },
  };
}

/**
 * Map API settings to TOU windows
 */
export function mapApiSettingsToTOUWindows(settings: Record<string, any>): TOUWindowData[] {
  const windows: TOUWindowData[] = [];

  // Convert HHMM integer (e.g. 1700 = 17:00) to HH:MM string
  const hhmmToTime = (hhmm: number): string => {
    const hours = Math.floor(hhmm / 100);
    const mins = hhmm % 100;
    return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
  };

  // prog_charge_mode: 0 = grid charge disabled, 1 = grid charge enabled
  const getGridCharge = (chargeMode: number): boolean => chargeMode === 1;

  // Extract TOU windows (prog1-6)
  for (let i = 1; i <= 6; i++) {
    const timeKey = `prog${i}_time`;
    const powerKey = `prog${i}_power_w`;
    const socKey = `prog${i}_capacity_pct`;
    const modeKey = `prog${i}_charge_mode`;

    if (settings[timeKey] !== undefined) {
      // Calculate end time (next window's start time, or midnight for last window)
      const startMinutes = settings[timeKey];
      const endMinutes = i < 6 ? settings[`prog${i + 1}_time`] : (i === 6 ? settings.prog1_time : 0);

      windows.push({
        gridCharge: getGridCharge(settings[modeKey] || 0),
        startTime: hhmmToTime(startMinutes),
        endTime: hhmmToTime(endMinutes),
        power: settings[powerKey] || 1000,
        targetSoc: settings[socKey] || 50,
        enabled: true,
      });
    }
  }

  return windows;
}

/**
 * Map component config back to API settings format
 */
export function mapConfigToApiSettings(
  config: InverterConfig,
  touWindows: TOUWindowData[]
): Record<string, any> {
  // Convert HH:MM string to HHMM integer (e.g. "17:00" → 1700)
  const timeToHhmm = (time: string): number => {
    const [hours, minutes] = time.split(':').map(Number);
    return hours * 100 + minutes;
  };

  const settings: Record<string, any> = {
    // Battery settings
    battery_capacity_ah: config.batteryConfig.capacity,
    battery_max_charge_current_a: config.batteryConfig.maxChargeCurrent,
    battery_max_discharge_current_a: config.batteryConfig.maxDischargeCurrent,
    battery_floating_voltage_v: config.safety.max_batt_voltage_v,
    grid_charge_battery_current_a: config.batteryConfig.maxGridChargeCurrent,
    generator_charge_battery_current_a: config.batteryConfig.maxGeneratorChargeCurrent,

    // Grid settings
    max_export_power_w: config.batteryConfig.maxDischargerPower,
    grid_peak_shaving_power_w: config.batteryConfig.maxGridChargerPower,
    limit_control_function: config.gridSettings.peakShavingEnabled ? 1 : 0,

    // Work mode
    ac_charge_battery: config.workMode.gridCharge ? 1 : 0,
    generator_charge_enabled: config.workMode.generatorCharge ? 1 : 0,
    battery_shutdown_capacity_pct: config.workMode.outputShutdownCapacity,
    battery_low_capacity_pct: config.workMode.stopBatteryDischargeCapacity,
    battery_restart_capacity_pct: config.workMode.startBatteryDischargeCapacity,
    grid_charging_start_capacity_pct: config.workMode.startGridChargeCapacity,
    grid_type_setting: config.workMode.offGridMode ? 0 : 1,
  };

  // Map TOU windows
  touWindows.forEach((window, i) => {
    const progNum = i + 1;
    if (progNum <= 6) {
      settings[`prog${progNum}_time`] = timeToHhmm(window.startTime);
      settings[`prog${progNum}_power_w`] = window.power;
      settings[`prog${progNum}_capacity_pct`] = window.targetSoc;
      settings[`prog${progNum}_charge_mode`] = window.gridCharge ? 1 : 0;
    }
  });

  return settings;
}
