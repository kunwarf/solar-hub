/**
 * Enhanced Telemetry Types
 *
 * Extended telemetry data structures for real-time device monitoring
 */

/**
 * MPPT (Maximum Power Point Tracking) Channel Data
 * Represents individual solar array/string connected to inverter
 */
export interface MPPTChannel {
  channel_id: number;
  name: string;
  power_w: number;
  voltage_v: number;
  current_a: number;
  status: 'optimal' | 'shaded' | 'offline' | 'low';
  panel_count?: number;
  efficiency_pct?: number;
}

/**
 * Extended Inverter Metrics
 * Detailed electrical and performance metrics
 */
export interface ExtendedInverterMetrics {
  // DC Side
  dc_voltage_v: number;
  dc_current_a?: number;
  dc_power_w?: number;

  // AC Side
  ac_voltage_v: number;
  ac_current_a?: number;
  ac_power_w?: number;
  ac_frequency_hz: number;

  // Performance
  efficiency_pct: number;
  power_factor?: number;

  // Environmental
  temperature_c: number;
  temperature_heatsink_c?: number;

  // Battery (if applicable)
  battery_voltage_v?: number;
  battery_current_a?: number;
  battery_soc_pct?: number;

  // Status
  timestamp: string;
  online: boolean;
}

/**
 * Historical Power Data Point
 * Time-series data for charts
 */
export interface HistoricalPowerPoint {
  timestamp: string;
  solar_power_kw: number;
  battery_power_kw: number;
  load_power_kw: number;
  grid_power_kw: number;
  efficiency_pct?: number;
  temperature_c?: number;
}

/**
 * Telemetry Response Wrapper
 */
export interface DeviceTelemetryResponse {
  device_id: string;
  serial_number: string;
  mppt_channels?: MPPTChannel[];
  metrics?: ExtendedInverterMetrics;
  historical_data?: HistoricalPowerPoint[];
  last_updated: string;
}
