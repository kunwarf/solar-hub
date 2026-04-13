# Today's Peak Metrics on Inverter Telemetry Page — Design Document

**Status:** Implemented  
**Date:** 2026-04-13  
**Author:** Engineering

---

## Overview

The Inverter Telemetry page shows live instantaneous power but gives no quick answer to "what was the best solar output today?" or "what was the peak load?". This feature adds four read-only **Today's Peaks** tiles:

| Tile | Metric | Source column | Sign rule |
|---|---|---|---|
| Max Solar | Peak `pv_power_w` | `pv_power_w` | Always positive |
| Max Load | Peak `load_power_w` | `load_power_w` | Always positive |
| Max Export | Peak export power | `grid_power_w < 0` → `-grid_power_w` | Negative = export |
| Max Import | Peak import power | `grid_power_w > 0` | Positive = import |

Each tile also shows **when** the peak occurred (HH:mm in the site's local timezone).

---

## Data Flow

```
frontend (Telemetry.tsx)
  → dashboardService.getStats(siteId)            [polls every 30 s]
    → GET /api/v1/widgets/stats?site_id=...       (System A)
      → system_b_client.get_site_daily_peaks(site_id, start_utc, end_utc)
        → GET /api/v1/telemetry/daily-peaks/{site_id}?start_time=&end_time=  (System B)
          → Single SQL query on telemetry_raw with MAX FILTER clauses
            → TimescaleDB
      → Redis cache key daily_peaks:{site_id}:{local_date}  (TTL 60 s)
```

---

## SQL Query (System B)

```sql
SELECT
    MAX(metric_value) FILTER (WHERE metric_name = 'pv_power_w')              AS max_pv_w,
    MAX(time)         FILTER (WHERE metric_name = 'pv_power_w'
                              AND metric_value = MAX(metric_value) FILTER (WHERE metric_name = 'pv_power_w'))
                                                                              AS max_pv_at,
    MAX(metric_value) FILTER (WHERE metric_name = 'load_power_w')             AS max_load_w,
    MAX(-metric_value) FILTER (WHERE metric_name = 'grid_power_w'
                               AND metric_value < 0)                          AS max_export_w,
    MAX(metric_value)  FILTER (WHERE metric_name = 'grid_power_w'
                               AND metric_value > 0)                          AS max_import_w
FROM telemetry_raw
WHERE site_id = :site_id
  AND time >= :start_time
  AND time < :end_time;
```

Because `MAX` with a scalar subquery inside a `FILTER` is not valid SQL, we use a two-step CTE:

```sql
WITH raw_peaks AS (
    SELECT
        MAX(metric_value)  FILTER (WHERE metric_name = 'pv_power_w')         AS max_pv_w,
        MAX(metric_value)  FILTER (WHERE metric_name = 'load_power_w')        AS max_load_w,
        MAX(-metric_value) FILTER (WHERE metric_name = 'grid_power_w'
                                   AND metric_value < 0)                      AS max_export_w,
        MAX(metric_value)  FILTER (WHERE metric_name = 'grid_power_w'
                                   AND metric_value > 0)                      AS max_import_w
    FROM telemetry_raw
    WHERE site_id = :site_id AND time >= :start_time AND time < :end_time
),
peak_times AS (
    SELECT DISTINCT ON (metric_name)
        metric_name,
        time,
        metric_value
    FROM telemetry_raw
    WHERE site_id = :site_id AND time >= :start_time AND time < :end_time
      AND metric_name IN ('pv_power_w', 'load_power_w', 'grid_power_w')
    ORDER BY metric_name, metric_value DESC
)
SELECT
    r.max_pv_w,
    (SELECT time FROM peak_times WHERE metric_name = 'pv_power_w' LIMIT 1)    AS max_pv_at,
    r.max_load_w,
    (SELECT time FROM peak_times WHERE metric_name = 'load_power_w' LIMIT 1)  AS max_load_at,
    r.max_export_w,
    (SELECT time FROM peak_times
     WHERE metric_name = 'grid_power_w' AND metric_value < 0
     ORDER BY metric_value ASC LIMIT 1)                                        AS max_export_at,
    r.max_import_w,
    (SELECT time FROM peak_times
     WHERE metric_name = 'grid_power_w' AND metric_value > 0
     ORDER BY metric_value DESC LIMIT 1)                                       AS max_import_at
FROM raw_peaks r;
```

---

## Example API Request / Response

### Request (System B)
```
GET /api/v1/telemetry/daily-peaks/{site_id}?start_time=2026-04-13T19:00:00Z&end_time=2026-04-14T18:59:59Z
```

### Response (System B)
```json
{
  "site_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "start_time": "2026-04-13T19:00:00Z",
  "end_time": "2026-04-14T18:59:59Z",
  "peaks": {
    "pv":     { "value_w": 4850.0, "occurred_at": "2026-04-14T08:23:00Z" },
    "load":   { "value_w": 3200.0, "occurred_at": "2026-04-14T13:05:00Z" },
    "export": { "value_w": 2400.0, "occurred_at": "2026-04-14T09:10:00Z" },
    "import": { "value_w": 1500.0, "occurred_at": "2026-04-14T19:45:00Z" }
  }
}
```

Null values are returned when no data exists in the window:
```json
{ "value_w": null, "occurred_at": null }
```

### Response (System A — appended to existing /widgets/stats)
```json
{
  "energy_today_kwh": 18.3,
  "peak_power_kw": 4.3,
  "...": "...",
  "max_pv_today":     { "value_kw": 4.850, "occurred_at": "2026-04-14T08:23:00Z" },
  "max_load_today":   { "value_kw": 3.200, "occurred_at": "2026-04-14T13:05:00Z" },
  "max_export_today": { "value_kw": 2.400, "occurred_at": "2026-04-14T09:10:00Z" },
  "max_import_today": { "value_kw": 1.500, "occurred_at": "2026-04-14T19:45:00Z" }
}
```

---

## Timezone Handling

1. System A receives `site_id`; loads the site entity to get `site.timezone` (e.g. `"Asia/Karachi"`).
2. Uses `TimezoneUtils.get_local_date_range(today_local, site_timezone)` to derive UTC bounds for "today".
3. Falls back to `"UTC"` if `site.timezone` is NULL, logging a warning.
4. Passes UTC `start_time`/`end_time` to System B.
5. Frontend receives `occurred_at` in UTC; converts to site timezone using `Intl.DateTimeFormat` or `date-fns-tz` for "Peak at HH:mm" label.

---

## Cache Strategy

- Redis key: `daily_peaks:{site_id}:{local_date}`  (e.g., `daily_peaks:abc123:2026-04-13`)
- TTL: 60 seconds (peaks update at most every minute; telemetry page polls every 30 s)
- Cache is populated in `get_stats` handler alongside the existing stats call.
- Key rolls over at local midnight automatically (date changes → new key, old key expires naturally within 60 s).

---

## Rollback Procedure

1. Frontend: remove `TodaysPeaks` block from `InverterTelemetry.tsx`; `StatsData` optional fields are ignored — no errors.
2. System A: remove 4 fields from `StatsResponse` and the `get_site_daily_peaks` call in `get_stats` — additive, non-breaking.
3. System B: remove the `/daily-peaks/{site_id}` endpoint — System A handles `SystemBClientError` silently.
4. No DB migration needed in any direction.

---

## Files Created / Modified

| File | Change |
|---|---|
| `system_b/app/api/v1/telemetry.py` | New `GET /telemetry/daily-peaks/{site_id}` endpoint |
| `system_a/app/infrastructure/external/system_b_client.py` | New `get_site_daily_peaks()` method |
| `system_a/app/api/v1/dashboard_widgets.py` | Extend `StatsResponse` + `get_stats` |
| `frontend/src/api/services/dashboard.service.ts` | Extend `StatsData` type |
| `frontend/src/components/telemetry/InverterTelemetry.tsx` | New "Today's Peaks" card row |
| `system_b/tests/unit/test_daily_peaks.py` | New — pytest coverage |
| `system_a/tests/unit/test_daily_peaks_stats.py` | New — pytest coverage |
| `frontend/src/components/telemetry/InverterTelemetry.test.tsx` | Extended |

---

## Running Tests

```bash
# Backend
pytest system_b/tests/unit/test_daily_peaks.py -v
pytest system_a/tests/unit/test_daily_peaks_stats.py -v

# Frontend
cd frontend && npm run test -- InverterTelemetry
```
