/**
 * Profile registry — maps a device protocol id (or manufacturer hint) to
 * a DeviceProfile.  SettingsScreen looks up by this map; adding a new
 * family = adding a profile file and one entry here.
 */
import type { DeviceProfile } from "./types";
import { senergyProfile } from "./senergy";
import { powdriveProfile } from "./powdrive";
import { voltronicProfile } from "./voltronic";

const PROFILES: Record<string, DeviceProfile> = {
  senergy: senergyProfile,
  // Powdrive and Deye share the same Modbus register layout — same profile
  powdrive: powdriveProfile,
  deye: powdriveProfile,
  // All Voltronic serial variants share the same command set
  voltronic_pi30: voltronicProfile,
  voltronic_pi18: voltronicProfile,
  voltronic_pi16: voltronicProfile,
  voltronic_pi17: voltronicProfile,
  voltronic_pi34: voltronicProfile,
};

/** Resolve a profile by device protocol string.  Falls back to null when
 *  the family isn't in the registry — caller renders a legacy page. */
export function resolveProfile(protocol: string | null | undefined): DeviceProfile | null {
  if (!protocol) return null;
  return PROFILES[protocol.toLowerCase()] ?? null;
}

export { senergyProfile, powdriveProfile, voltronicProfile };
export type { DeviceProfile };
