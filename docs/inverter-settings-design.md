# Inverter Settings Pages — Design Document

**Status:** Implemented  
**Date:** 2026-04-12  
**Author:** Engineering

---

## Overview

Solar Hub supports three inverter families, each with different settings mechanisms:

| Family | Protocol | Settings mechanism | RW fields |
|---|---|---|---|
| Powdrive / Deye | Modbus TCP | Register read/write | ~75 registers |
| Senergy | Modbus TCP | Register read/write | ~48 registers |
| Voltronic | Serial text commands (PI30/PI18/PI16/PI17/PI34) | Named command dispatch | 25 commands |

Previously, all three families shared two generic settings pages (`InverterSettingsPage`, `InverterConfigPage`). This caused:
- Missing family-specific validation (min/max/scale)
- Voltronic commands rendered as Modbus register edits
- Battery sign convention (positive=discharging) not surfaced for Senergy
- No destructive-write safety guards

This document describes the replacement: three purpose-built settings pages dispatched by `device.manufacturer` / `device.protocol`.

---

## Architecture

```
DeviceSettingsHybrid.tsx  (dispatcher)
  ├── PowdriveSettingsPage  ← powdrive | deye manufacturer
  ├── VoltronicSettingsPage  ← voltronic_* protocol
  ├── SenergySettingsPage  ← senergy manufacturer
  └── InverterConfigPage  ← fallback for unknown families
```

### Data flow

```
User edits field
  → SettingFieldCard (inline Apply)
  → onApply(changes)  [PowdrivePage / SenergyPage]
  or onSendCommand(cmd, value)  [VoltronicPage]
    → useDeviceSettings.updateDevice({ ...settings, ...changes })
      → deviceCommandsService.updateSettings(deviceId, changes)
        → POST /api/v1/devices/{id}/commands/update-settings
          → System A → System B command_executor.py
            → adapter_factory.write_register (Modbus)
            or adapter_factory.execute_voltronic_command (serial text)
```

### Settings schema flow

```
GET /api/v1/devices/settings-schema/{protocol}
  → System A device_commands.py
    → system_b_client.get_settings_schema(protocol)
      → GET /api/v1/settings/schema/{protocol} (System B)
        → settings_schema.py get_schema(protocol)
```

The schema is also embedded statically in each family page's `schema.ts` file to avoid a roundtrip when the page first renders.

---

## Per-Family Details

### Powdrive / Deye

**Accent colour:** `#10B981` (solar green)

**Groups:**
1. Battery — capacity, charge/discharge current, voltage thresholds, SOC limits, equalization, battery chemistry
2. Charger — AC charge enable, current, start SOC/voltage
3. Grid & Export — solar sell, export limits, grid standard (destructive), CT direction
4. Inverter / Output — solar priority, peak shaving
5. Generator — enable, port usage, run times, charge settings
6. TOU Schedule — 6 time-of-use programs (time, power, voltage, SOC, charge mode)
7. Protection — arc fault detection, smart load thresholds

**Layout:** Left sidebar navigation + right pane of SettingFieldCards in 2-column grid.

**Per-field Apply** — each field has its own Apply button that activates only when dirty. Global "Apply all (N)" accumulates pending writes for batch submit.

**Destructive fields:** `battery_mode_source`, `lithium_battery_type`, `grid_standard` — require ConfirmWriteDialog (serial number typing).

---

### Senergy

**Accent colour:** `#3B82F6` (blue)

**Groups:**
1. Battery — includes sign-convention banner ("positive = discharging, negative = charging")
2. Grid Code — includes restart warning banner; grid_standard is destructive
3. Charger — AC charge enable, current, SOC start/end
4. Work Mode — Self-Consumption / Backup / Feed-in / TOU; also surfaced as a quick-switcher in the top bar
5. Protection — overload/temp restart, backflow protection

**Key difference from Powdrive:** Voltage registers stored as tenths of volts (`scale = 0.1`). The SettingFieldCard multiplies by scale for display and divides for write.

**Layout:** Same as Powdrive. Always-visible Work Mode quick-switcher in the top bar so users can change the most-accessed setting without navigating to the Work Mode tab.

---

### Voltronic

**Accent colour:** `#A855F7` (purple)

**Tabs:**
1. Output — output source priority (POP), output mode (POPM)
2. Charger — charger priority (PCP), max charge current (MCHGC), max AC charge current (MUCHGC)
3. Battery — battery type (PBATCD, destructive), bulk voltage (PBCV), float voltage (PBDV), cutoff (PSDV), recharge trigger (PBCVV)
4. Grid — AC input voltage range (PGR), grid max charge current (MUCHGC)
5. System — buzzer, overload bypass, solar feed-to-grid, LCD backlight, factory defaults (PF, destructive)

**Key difference:** Each command is **atomic** — there is no batch Apply. Each Command Card has its own Apply button and shows inline ACK (green) or NAK (red) feedback.

**Command log:** Collapsible panel at the bottom shows the last 20 sent commands with timestamps and ACK/NAK results.

**Boolean flags** (buzzer, bypass, etc.) map to `PE{flag}` (enable) / `PD{flag}` (disable) command pairs.

---

## Shared Primitives (`components/settings/shared/`)

| Component | Purpose |
|---|---|
| `SettingField.tsx` | Single field card with number/enum/bool control and inline Apply |
| `SettingsSection.tsx` | Group container with optional sign-convention note |
| `ConfirmWriteDialog.tsx` | Serial-typing confirmation for destructive fields |
| `types.ts` | `SettingField`, `SettingGroup`, `DirtyFields` TypeScript types |

---

## Backend Schema

**File:** `system_b/device_server/settings_schema.py`

Contains `POWDRIVE_SCHEMA`, `SENERGY_SCHEMA`, `VOLTRONIC_SCHEMA` and a `SCHEMAS_BY_PROTOCOL` registry. Each field descriptor has:

```python
{
  "key": "battery_capacity_ah",
  "label": "Battery Capacity",
  "type": "number",       # "number" | "enum" | "bool"
  "unit": "Ah",
  "min": 10,
  "max": 2000,
  "step": 1,
  "scale": 1.0,           # display = raw × scale
  "writable": True,
  "destructive": False,
}
```

**Endpoint:** `GET /api/v1/settings/schema/{protocol}` (System B)  
**Proxy:** `GET /api/v1/devices/settings-schema/{protocol}` (System A, authenticated)

---

## Dispatcher Logic (`DeviceSettingsHybrid.tsx`)

```typescript
const mfr = device.manufacturer.toLowerCase();
const proto = device.protocol.toLowerCase();

if (mfr.includes("powdrive") || mfr.includes("deye") || proto === "powdrive")
  → <PowdriveSettingsPage />

if (proto.startsWith("voltronic") || mfr.includes("voltronic"))
  → <VoltronicSettingsPage />

if (mfr.includes("senergy") || proto === "senergy")
  → <SenergySettingsPage />

// fallback
→ <InverterConfigPage />  (legacy, read-only for unknown families)
```

---

## Backward Compatibility

- All existing API routes and payloads unchanged (additive metadata only).
- `InverterConfigPage` retained as fallback; no broken URLs.
- No DB migration required.
- Gate new pages with `VITE_FEATURE_PER_FAMILY_SETTINGS` env var during rollout.

---

## Files Created / Modified

| File | Change |
|---|---|
| `system_b/device_server/settings_schema.py` | **New** — full metadata for all three families |
| `system_b/app/api/v1/settings.py` | **New** — GET /settings/schema/{protocol} endpoint |
| `system_b/app/api/v1/__init__.py` | Wired settings_router |
| `system_b/tests/unit/test_settings_schema.py` | **New** — pytest coverage for schema |
| `system_a/app/infrastructure/external/system_b_client.py` | Added `get_settings_schema()` |
| `system_a/app/api/v1/device_commands.py` | Added proxy endpoint + typed helpers |
| `system_a/tests/unit/test_settings_schema_endpoint.py` | **New** — pytest coverage |
| `frontend/src/components/settings/shared/types.ts` | **New** — shared TypeScript types |
| `frontend/src/components/settings/shared/ConfirmWriteDialog.tsx` | **New** |
| `frontend/src/components/settings/shared/SettingField.tsx` | **New** |
| `frontend/src/components/settings/shared/SettingsSection.tsx` | **New** |
| `frontend/src/components/settings/powdrive/schema.ts` | **New** |
| `frontend/src/components/settings/powdrive/PowdriveSettingsPage.tsx` | **New** |
| `frontend/src/components/settings/voltronic/VoltronicSettingsPage.tsx` | **New** |
| `frontend/src/components/settings/senergy/schema.ts` | **New** |
| `frontend/src/components/settings/senergy/SenergySettingsPage.tsx` | **New** |
| `frontend/src/pages/DeviceSettingsHybrid.tsx` | Updated dispatcher |
| `frontend/src/api/services/device-commands.service.ts` | Added schema types + `getSettingsSchema()` |
| `frontend/src/components/settings/shared/*.test.tsx` | **New** — Vitest suites |
| `frontend/src/components/settings/powdrive/*.test.tsx` | **New** |
| `frontend/src/components/settings/voltronic/*.test.tsx` | **New** |
| `frontend/src/components/settings/senergy/*.test.tsx` | **New** |

---

## Running Tests

```bash
# Frontend
cd frontend && npm run test

# Backend schema tests
pytest system_b/tests/unit/test_settings_schema.py -v
pytest system_a/tests/unit/test_settings_schema_endpoint.py -v

# All settings-related tests
pytest system_a/tests/unit system_b/tests/unit -k settings -v
```

---

## Lovable AI Design Prompts

See `docs/LOVABLE_PROMPTS.md` or the plan file for the three design prompts (Powdrive, Voltronic, Senergy).
