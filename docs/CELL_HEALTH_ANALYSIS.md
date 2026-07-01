# Cell Health — Candidate Cells for Inspection

**Purpose.** Surface individual battery cells that deviate from their siblings
in the same pack, so operators can investigate before a failure. This is a
diagnostic heuristic, **not** a warranty claim — the UI, API, and this doc use
the wording "candidate for inspection" throughout.

**Scope.** Phase 1 (snapshot-only) ships in System A's battery-bank endpoint.
Phase 2 (time-series) is now shipped — see "Phase 2" below for the algorithm,
API, and storage details.

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

## Phase 2 — time-series detector

Detects "quick full / quick empty" — cells whose voltage climbs or drops
materially faster than siblings during charge/discharge phases. Complements
the Phase 1 snapshot detector; both symptoms surface in the same battery
detail page but from separate API endpoints and separate UI sections.

### Storage

New hypertable + continuous aggregate provisioned by Alembic migration
`20260701_0012_add_battery_cell_hypertable.py`:

- `battery_cell_samples` — `(time, device_id, unit, cell)` PK.
  `voltage_v`, `current_a`, `temperature`, `soc_pct` nullable. 1-day chunks,
  compressed after 2 days segmented by `(device_id, unit, cell)`, retention
  drop at 7 days. Matches the `telemetry_raw` policy family.
- `battery_cell_hourly` — continuous aggregate with `FIRST(voltage_v, time)`
  and `LAST(voltage_v, time)` per bucket — the two values `dV/dt` needs.
  Refresh every hour with a 3-hour window. Retention drop at 90 days.

Both created with the standard `USE_TIMESCALEDB` guard so local Postgres
dev environments still boot.

### Ingestion

`CellSamplesWriter` (`system_b/device_server/storage/cell_samples_writer.py`)
runs alongside `TimescaleWriter` in the `_on_telemetry` callback. It owns its
own asyncpg pool and batch buffer — a failure here does not block Redis or
the main telemetry write. It reads `telemetry.get("battery_cells")`, handles
both `unit` (JK BMS) and `module` (Pylontech) grouping keys, and inserts with
`ON CONFLICT DO NOTHING` on the composite PK. `site_id` is resolved per-flush
via a single batched `device_registry` lookup, mirroring
`TimescaleWriter._flush_batch`.

### Detection algorithm

`detect_timeseries(cell_hourly, bank_current_by_bucket, window_hours)` in
`system_a/app/application/services/cell_health_service.py`:

1. Group `cell_hourly` rows by bucket.
2. For each bucket, look up bank current from `bank_current_by_bucket`.
   Classify as **charge** if `≥ +3 A`, **discharge** if `≤ -3 A`, else skip.
3. Per active bucket, compute `dV = last_v - first_v` per cell. Skip cells
   with `sample_count < 6` or `|dV| < 5 mV`.
4. Rank within the bucket:
   - Charge: top-2 highest dV (fastest climbers → reach cutoff first).
   - Discharge: top-2 most-negative dV (fastest fallers → empty first).
5. Hysteresis: a cell must appear in the top-2 in **≥ 3 phases** before it
   surfaces as a candidate. Kills BMS-balancing noise, which flips rankings
   sporadically.
6. Two symptoms: `fast_full` (charge) and `fast_empty` (discharge).
   Severity by ratio (`flagged / phases_in_direction`):
   `≥ 0.8` critical · `≥ 0.5` warning · else `watch`.

### API

`GET /api/v1/devices/{device_id}/battery/cell-health/timeseries?window_hours=168`

Response wraps a `cell_health_timeseries` block:

```jsonc
{
  "device_id": "…", "serial_number": "…",
  "cell_health_timeseries": {
    "algorithm": "timeseries_v1",
    "generated_at": "…+00:00",
    "available": true,
    "reason": null,
    "window_hours": 168,
    "phases_analysed": {"charge": 42, "discharge": 38},
    "total_candidates": 1,
    "units": [
      {
        "unit_index": 1,
        "candidates": [
          {
            "cell_index": 7,
            "score": 2.4,
            "confidence": "high",
            "symptoms": [
              {"type": "fast_full", "severity": "critical", "source": "computed",
               "evidence": {"flagged_phases": 38, "charge_phases": 42, "ratio": 0.90}}
            ],
            "phase_history": [{"symptom": "fast_full", "dv_v": 0.032}, ...]
          }
        ]
      }
    ]
  }
}
```

Unavailable states:

| Case | `available` | `reason` |
|---|---|---|
| No rows in `battery_cell_hourly` for the window | `false` | `"no_history"` |
| Rows exist but bank was idle every bucket | `false` | `"no_active_phases"` |
| Device serial not registered in System B | `false` | `"device_not_registered"` |

### Frontend

`CellHealthTimeseriesPanel.tsx` mounts inside `BatteryCellGrid` right after
the snapshot `CellHealthPanel`. Fetches via `useQuery` with a 5-minute
refetch interval (the CAgg only refreshes hourly on the backend — no point
polling faster). Each candidate row shows: unit, cell, symptom badges,
score, confidence, and a small recharts sparkline of `|dV|` (mV) across
the flagged phases in the analysis window.

### Storage budget (verified)

10 banks × 16 cells × 60 s poll = 230 K rows/day raw. After the 2-day
compression window (~10× ratio) and 7-day retention: ~30 MB steady state
per bank. Hourly aggregate: ~4 K rows/day × 90 days ≈ 360 K rows across
the fleet — negligible.

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
