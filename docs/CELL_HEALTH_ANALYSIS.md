# Cell Health — Candidate Cells for Inspection

**Purpose.** Surface individual battery cells that deviate from their siblings
in the same pack, so operators can investigate before a failure. This is a
diagnostic heuristic, **not** a warranty claim — the UI, API, and this doc use
the wording "candidate for inspection" throughout.

**Scope.** Phase 1 (snapshot-only) ships in System A's battery-bank endpoint.
Phase 2 (time-series) is designed but not implemented — see the roadmap at
the bottom.

---

## Data path

```
Battery adapter (poll)
       │
       ▼
System B collector ──▶ Redis blob: device:{serial}:telemetry
                          └── battery_bank.cells: [{unit, cell, voltage_v, ...}]
                          │
                          ▼
System A: GET /api/v1/devices/{id}/battery/bank
   1. reads Redis blob
   2. calls detect_snapshot(battery_bank.cells)
   3. injects `cell_health` block into the response
                          │
                          ▼
Frontend: BatteryCellGrid renders CellHealthPanel
```

The detector is a pure Python function in
`system_a/app/application/services/cell_health_service.py`. It has no
SQLAlchemy, FastAPI, Redis, or Pydantic runtime dependencies — safe to call
from the endpoint on every request (~sub-millisecond for 32 cells).

---

## Per-adapter applicability

Redis exposes per-cell arrays only for adapters that read them from the BMS:

| Adapter | Per-cell voltage | Per-cell temperature | Per-cell current | Vendor `*_st` flags | Phase 1 coverage |
|---|---|---|---|---|---|
| Pytes / Pylontech | yes | yes (real) | yes | yes | full — all four symptoms |
| JK BMS TCP/IP | yes | no | no | no | voltage outlier only |
| JK BMS BLE | yes | yes (derived) | no | no | voltage + temperature outlier |
| Senergy (any variant) | no | no | no | no | endpoint returns `available: false, reason: "pack_level_only"` |

"Derived temperature" on JK BMS BLE means the value came from a module-level
sensor and was fanned out per cell — treat those `temp_outlier` symptoms as
lower confidence than the same signal on Pytes.

---

## Symptoms

Four symptoms are computed per cell. Each symptom carries a `severity`
(`critical | warning | watch`) and a `source` (`vendor | computed`).

### `vendor_flag`  ·  source: vendor
The BMS reports a non-benign state on `basic_st`, `volt_st`, `curr_st`, or
`temp_st`. Benign vocabulary is the set:
`{"", Normal, Idle, Charge, Charging, Dischg, Discharge, Discharging, Balance, Balancing, Standby, Sleep, OK}`.
Anything else is surfaced. Severity is inferred from substrings:

| Substring hint | Severity |
|---|---|
| `alarm`, `fault`, `ovp`, `uvp`, `otp`, `utp`, `short` | critical |
| `warn`, `high`, `low`, `over`, `under` | warning |
| anything else non-benign | watch |

Vendor flags are the only high-confidence signal; the BMS is authoritative.
When a cell has a vendor flag, the candidate's confidence is `high` regardless
of what the statistical detectors say.

### `voltage_outlier`  ·  source: computed
Robust Z-score of the cell's `voltage_v` against the module's median, using
median absolute deviation (MAD) with the 1.4826 consistency constant so the
statistic is comparable to standard deviation under a normal distribution.

- Threshold: `robust_z ≥ 3.0` → warning, `≥ 4.5` → critical.
- Noise floor: skipped when the module's voltage spread is below **20 mV**
  (typical inter-cell noise; below this any Z-score is meaningless).
- Requires ≥ 4 voltages in the unit for the statistic to be computed.

### `temp_outlier`  ·  source: computed
Same robust Z-score, on `temperature`.

- Threshold: `robust_z ≥ 3.0` → warning, `≥ 4.5` → critical.
- Noise floor: skipped when the module's temperature spread is below **2 °C**.
- Requires ≥ 4 temperatures in the unit.
- **Caveat**: on JK BMS BLE this signal is derived from module sensors, not a
  per-cell measurement. Prefer to corroborate with vendor flags or repeated
  observation before acting.

### `current_mismatch`  ·  source: computed (Pytes only)
Cells in a series string should carry the same current at any given moment
(KCL). A deviation implies a bypass path, contact resistance issue, or
measurement fault.

- Threshold: `robust_z ≥ 3.0` → warning, `≥ 4.5` → critical.
- Minimum deviation guard: absolute deviation must exceed **0.5 A** to avoid
  measurement noise near idle.
- Requires ≥ 4 currents in the unit.

---

## Scoring & confidence

Each cell that trips any symptom becomes a candidate. Its score is the sum
of severity weights across its symptoms:

| Symptom | critical | warning | watch |
|---|---|---|---|
| `vendor_flag` | 5 | 3 | 2 |
| `voltage_outlier`, `temp_outlier`, `current_mismatch` | 4 | 2 | 1 |

Vendor flags are weighted higher because they are authoritative rather than
inferred.

Confidence is a coarse rollup:

- **high** — any `vendor_flag` present
- **medium** — two or more computed symptoms
- **low** — one computed symptom only

Candidates are sorted by score (desc) and **capped at 5 per unit** — a
diagnostic panel that lists everything trains operators to ignore it.

---

## API contract

Endpoint: `GET /api/v1/devices/{device_id}/battery/bank`

The response gains one new top-level field `cell_health`:

```jsonc
{
  "device_id": "…", "serial_number": "…", "available": true,
  "bank": { … }, "units": [ … ], "cells": [ … ],
  "cell_health": {
    "algorithm": "snapshot_v1",
    "generated_at": "2026-07-01T12:00:00+00:00",
    "available": true,
    "reason": null,
    "total_candidates": 2,
    "units": [
      {
        "unit_index": 1,
        "cell_count": 16,
        "candidates": [
          {
            "cell_index": 7,
            "score": 9.0,
            "confidence": "high",
            "symptoms": [
              {
                "type": "vendor_flag", "severity": "critical", "source": "vendor",
                "evidence": { "volt_st": "UVP" }
              },
              {
                "type": "voltage_outlier", "severity": "critical", "source": "computed",
                "evidence": { "voltage_v": 3.02, "median_v": 3.321,
                              "mad_v": 0.001, "robust_z": 203.1,
                              "deviation_mv": -301.0 }
              }
            ]
          }
        ],
        "stats": { "voltage_median_v": 3.321, "voltage_mad_v": 0.001, "…": null }
      }
    ]
  }
}
```

Unavailable states are always explicit — no silent empty:

| Case | `available` | `reason` |
|---|---|---|
| Redis has no telemetry (offline/stale) | `false` | `"no_recent_data"` |
| Adapter emits pack-level only (e.g. Senergy) | `false` | `"pack_level_only"` |
| Cells present, healthy | `true` | `null` — `total_candidates: 0` |
| Cells present, some flagged | `true` | `null` |

---

## Frontend behaviour

`CellHealthPanel` mounts inside `BatteryCellGrid`, between the vendor-alarm
banner and the pack-status card. States rendered:

- **Pack-level-only**: muted single-line hint. No scary empty state.
- **No recent data**: nothing rendered (the bank card already indicates offline).
- **Healthy**: small green line "No candidate cells for inspection (N cells analysed)".
- **Candidates present**: panel with severity-tinted border, count summary,
  per-candidate table with symptom badges (hover for evidence), score,
  confidence.

Colouring never uses the word "faulty". Symptom tooltips show numeric
evidence (voltage, median, MAD, robust Z, deviation) so the operator can
sanity-check the flag.

---

## Known limitations

- **Snapshot only.** A single Redis reading can't detect "charges fast /
  discharges fast" behaviour — that needs multiple observations across a
  charge/discharge cycle. Persistence for time-series is Phase 2.
- **Vendor balancing looks like an outlier.** When the BMS is actively
  balancing a cell, its voltage will drift from the pack — that's the whole
  point of balancing. The current detector will flag it. Mitigation for Phase
  2: require persistence across multiple polls before flagging.
- **Median/MAD needs ≥ 4 samples.** Small packs (< 4 cells reporting a given
  field) fall back to vendor flags only.
- **Bimodal packs distort the statistic.** If half the cells are outliers,
  the median falls between the two modes; robust Z drops for everyone. In
  practice this only matters when a pack is already known to be compromised.
- **Temperature on JK BMS BLE is derived**, not per-cell measured. The
  detector marks these `source: computed`, but the underlying signal is
  weaker than on Pytes. Corroborate before acting.
- **Warranty language.** "Candidate for inspection", not "faulty" — do not
  reword in downstream integrations without reviewing the implications.

---

## Phase 2 roadmap (design, not implemented)

Time-series detection ("quick full / quick empty" — cells whose voltage
climbs or drops materially faster than siblings during charge/discharge)
requires historical per-cell voltage. Today, per-cell arrays only live in
Redis for 120 s — the narrow `telemetry_raw` hypertable in System B does not
decompose them into rows.

Proposed design:

1. New System B hypertable `battery_cell_samples (time, device_id, unit,
   cell, voltage_v, temperature_c, current_a)` — raw SQL migration,
   TimescaleDB `create_hypertable`, compression policy at 7 days, retention
   drop at 90 days. Analogous to `telemetry_raw`.
2. Continuous aggregate `battery_cell_hourly` — hourly `min/max/mean/first/
   last/delta` per (device, unit, cell). 5-year retention.
3. Extend `TelemetryService.ingest_telemetry` to insert into
   `battery_cell_samples` when `battery_bank.cells` is present.
4. Add `detect_timeseries(cell_id, window)` in `cell_health_service.py` —
   segment history into charge/discharge phases (pack current threshold),
   compute per-cell dV/dt per phase, rank against siblings, require
   persistence across ≥ 3 phases (hysteresis) before flagging.
5. Expose as `GET /api/v1/devices/{id}/battery/cell-health/timeseries?window=7d`.
6. Extend the frontend panel with a per-candidate mini-sparkline of charge-phase
   dV/dt across recent cycles.

Storage budget check (100 devices, 16 cells, 60 s cadence): ~2.3 M raw
rows/day, ~66 MB/day uncompressed. After 7-day compression window and 90-day
retention: ~500 MB steady-state. Well within existing operational envelopes.

Phase 2 requires an explicit go-ahead — the raw-SQL migration touches System
B's hot ingestion path and needs coordinated rollout with `TelemetryService`.

---

## Testing

Unit tests live at
`system_a/tests/unit/application/test_cell_health_service.py`. They cover:

- unavailable states (no Redis, empty cells)
- healthy pack produces zero candidates
- each symptom type, individually
- multi-symptom cells rank above single-symptom cells
- vendor-flag-only implies `confidence = high`
- top-5 per unit cap
- multi-unit grouping analysed independently
- `module` key falls back to `unit`
- voltage / temperature noise floors suppress spurious flags
- vendor state classification vocabulary (Normal, Balance, UVP, OVP, Alarm, High, unknown)
- report shape invariants and UTC timestamp
