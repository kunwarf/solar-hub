/**
 * Register Field Mapping
 *
 * Maps frontend UI field names to backend register IDs from register maps.
 * Enables decoupling of UI from hardware-specific register addressing.
 */

// ============== INVERTER SETTINGS MAPPING ==============

export const INVERTER_SETTINGS_MAP: Record<string, string> = {
  // ===== Battery Configuration =====
  'batteryCapacity': 'battery_capacity_ah',  // Register 102
  'batteryMaxChargeCurrent': 'battery_max_charge_current_a',  // Register 108
  'batteryMaxDischargeCurrent': 'battery_max_discharge_current_a',  // Register 109
  'batteryShutdownCapacity': 'battery_shutdown_capacity_pct',  // Register 115
  'batteryRestartCapacity': 'battery_restart_capacity_pct',  // Register 116
  'batteryLowCapacity': 'battery_low_capacity_pct',  // Register 117
  'batteryShutdownVoltage': 'battery_shutdown_voltage_v',  // Register 118
  'batteryRestartVoltage': 'battery_restart_voltage_v',  // Register 119
  'batteryLowVoltage': 'battery_low_voltage_v',  // Register 120
  'batteryEqualizationVoltage': 'battery_equalization_voltage_v',  // Register 99
  'batteryFloatingVoltage': 'battery_floating_voltage_v',  // Register 101
  'batteryModeSource': 'battery_mode_source',  // Register 111 (0=Voltage, 1=Capacity, 2=No Battery)
  'batteryType': 'lithium_battery_type',  // Register 223

  // ===== Grid Settings =====
  'maxExportPower': 'max_export_power_w',  // Register 143
  'solarSellEnabled': 'solar_sell',  // Register 145 (0=disabled, 1=enabled)
  'solarPriority': 'solar_priority',  // Register 141 (0=Battery first, 1=Load first)
  'limitControlFunction': 'limit_control_function',  // Register 142
  'zeroExportPower': 'zero_export_power_w',  // Register 104
  'gridChargingStartVoltage': 'grid_charging_start_voltage_v',  // Register 126
  'gridChargingStartCapacity': 'grid_charging_start_capacity_pct',  // Register 127
  'gridChargeBatteryCurrent': 'grid_charge_battery_current_a',  // Register 128
  'acChargeBatteryEnabled': 'ac_charge_battery',  // Register 130 (0=Enabled, 1=Disabled)
  'gridPeakShavingPower': 'grid_peak_shaving_power_w',  // Register 191
  'gridPhaseSequence': 'grid_phase_sequence',  // Register 147
  'gridStandard': 'grid_standard',  // Register 182
  'gridTypemax_etting': 'grid_type_setting',  // Register 184

  // ===== TOU (Time of Use) Scheduling =====
  'touSelling': 'tou_selling',  // Register 146
  'prog1Time': 'prog1_time',  // Register 148
  'prog2Time': 'prog2_time',  // Register 149
  'prog3Time': 'prog3_time',  // Register 150
  'prog4Time': 'prog4_time',  // Register 151
  'prog5Time': 'prog5_time',  // Register 152
  'prog6Time': 'prog6_time',  // Register 153
  'prog1Power': 'prog1_power_w',  // Register 154
  'prog2Power': 'prog2_power_w',  // Register 155
  'prog3Power': 'prog3_power_w',  // Register 156
  'prog4Power': 'prog4_power_w',  // Register 157
  'prog5Power': 'prog5_power_w',  // Register 158
  'prog6Power': 'prog6_power_w',  // Register 159
  'prog1Voltage': 'prog1_voltage_v',  // Register 160
  'prog2Voltage': 'prog2_voltage_v',  // Register 161
  'prog3Voltage': 'prog3_voltage_v',  // Register 162
  'prog4Voltage': 'prog4_voltage_v',  // Register 163
  'prog5Voltage': 'prog5_voltage_v',  // Register 164
  'prog6Voltage': 'prog6_voltage_v',  // Register 165
  'prog1Capacity': 'prog1_capacity_pct',  // Register 166
  'prog2Capacity': 'prog2_capacity_pct',  // Register 167
  'prog3Capacity': 'prog3_capacity_pct',  // Register 168
  'prog4Capacity': 'prog4_capacity_pct',  // Register 169
  'prog5Capacity': 'prog5_capacity_pct',  // Register 170
  'prog6Capacity': 'prog6_capacity_pct',  // Register 171
  'prog1ChargeMode': 'prog1_charge_mode',  // Register 172
  'prog2ChargeMode': 'prog2_charge_mode',  // Register 173
  'prog3ChargeMode': 'prog3_charge_mode',  // Register 174
  'prog4ChargeMode': 'prog4_charge_mode',  // Register 175
  'prog5ChargeMode': 'prog5_charge_mode',  // Register 176
  'prog6ChargeMode': 'prog6_charge_mode',  // Register 177

  // ===== Generator/Auxiliary =====
  'generatorMaxRunTime': 'generator_max_run_time_h',  // Register 121
  'generatorDownTime': 'generator_down_time_h',  // Register 122
  'generatorChargingStartVoltage': 'generator_charging_start_voltage_v',  // Register 123
  'generatorChargingStartCapacity': 'generator_charging_start_capacity_pct',  // Register 124
  'generatorChargeBatteryCurrent': 'generator_charge_battery_current_a',  // Register 125
  'generatorChargeEnabled': 'generator_charge_enabled',  // Register 129
  'generatorPortUsage': 'generator_port_usage',  // Register 133
  'generatorConnectedToGridInput': 'generator_connected_to_grid_input',  // Register 189
  'genPeakShavingPower': 'gen_peak_shaving_power_w',  // Register 190
  'smartloadOffVoltage': 'smartload_off_voltage_v',  // Register 134
  'smartloadOffCapacity': 'smartload_off_capacity_pct',  // Register 135
  'smartloadOnVoltage': 'smartload_on_voltage_v',  // Register 136
  'smartloadOnCapacity': 'smartload_on_capacity_pct',  // Register 137

  // ===== Advanced =====
  'batteryEqualizationDayCycle': 'battery_equalization_day_cycle',  // Register 105
  'batteryEqualizationTime': 'battery_equalization_time',  // Register 106
  'maxSolarSellPower': 'max_solar_sell_power_w',  // Register 340
  'solarArcFaultMode': 'solar_arc_fault_mode',  // Register 181
  'externalCtDirection': 'external_ct_direction',  // Register 144
};

// ============== BATTERY SETTINGS MAPPING ==============

export const BATTERY_SETTINGS_MAP: Record<string, string> = {
  // TODO: Add battery-specific register mappings when available
  // Example for Pytes battery:
  // 'minSoc': 'min_soc_pct',
  // 'maxSoc': 'max_soc_pct',
  // 'maxChargeCurrent': 'max_charge_current_a',
  // 'maxDischargeCurrent': 'max_discharge_current_a',
};

// ============== METER SETTINGS MAPPING ==============

export const METER_SETTINGS_MAP: Record<string, string> = {
  // TODO: Add meter-specific register mappings when available
  // Example for IAMMeter:
  // 'ctRatio': 'ct_ratio',
  // 'vtRatio': 'vt_ratio',
  // 'phaseConfiguration': 'phase_config',
};

// ============== HELPER FUNCTIONS ==============

/**
 * Get register ID from UI field name
 */
export function getRegisterIdFromFieldName(
  deviceType: 'inverter' | 'battery' | 'meter',
  fieldName: string
): string | undefined {
  const mappings = {
    inverter: INVERTER_SETTINGS_MAP,
    battery: BATTERY_SETTINGS_MAP,
    meter: METER_SETTINGS_MAP,
  };
  return mappings[deviceType]?.[fieldName];
}

/**
 * Get UI field name from register ID
 */
export function getFieldNameFromRegisterId(
  deviceType: 'inverter' | 'battery' | 'meter',
  registerId: string
): string | undefined {
  const mappings = {
    inverter: INVERTER_SETTINGS_MAP,
    battery: BATTERY_SETTINGS_MAP,
    meter: METER_SETTINGS_MAP,
  };
  const mapping = mappings[deviceType];
  if (!mapping) return undefined;

  // Reverse lookup
  for (const [fieldName, regId] of Object.entries(mapping)) {
    if (regId === registerId) {
      return fieldName;
    }
  }
  return undefined;
}

/**
 * Convert UI settings object to register updates
 */
export function mapSettingsToRegisters(
  deviceType: 'inverter' | 'battery' | 'meter',
  settings: Record<string, any>
): Record<string, any> {
  const registerUpdates: Record<string, any> = {};

  for (const [fieldName, value] of Object.entries(settings)) {
    const registerId = getRegisterIdFromFieldName(deviceType, fieldName);
    if (registerId) {
      registerUpdates[registerId] = value;
    }
  }

  return registerUpdates;
}

/**
 * Convert register values to UI settings object
 */
export function mapRegistersToSettings(
  deviceType: 'inverter' | 'battery' | 'meter',
  registers: Record<string, any>
): Record<string, any> {
  const settings: Record<string, any> = {};

  for (const [registerId, value] of Object.entries(registers)) {
    const fieldName = getFieldNameFromRegisterId(deviceType, registerId);
    if (fieldName) {
      settings[fieldName] = value;
    }
  }

  return settings;
}

/**
 * Get all available field names for a device type
 */
export function getAvailableFields(
  deviceType: 'inverter' | 'battery' | 'meter'
): string[] {
  const mappings = {
    inverter: INVERTER_SETTINGS_MAP,
    battery: BATTERY_SETTINGS_MAP,
    meter: METER_SETTINGS_MAP,
  };
  return Object.keys(mappings[deviceType] || {});
}

/**
 * Check if a field is mapped for a device type
 */
export function isFieldMapped(
  deviceType: 'inverter' | 'battery' | 'meter',
  fieldName: string
): boolean {
  return getRegisterIdFromFieldName(deviceType, fieldName) !== undefined;
}
