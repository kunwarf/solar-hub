# Solar Hub Standalone Scheduler Service

## Overview

The standalone scheduler service (`solarhub-scheduler.service`) runs all APScheduler-based
background jobs independently from the System A API process. This enables:

- **Horizontal scaling** — multiple instances run in parallel; Redis distributed locks
  prevent duplicate job execution.
- **Resource isolation** — billing and outage-detection jobs no longer compete with API
  request handling for CPU and database connections.
- **Independent lifecycle** — the scheduler can be restarted without cycling System A,
  and vice versa.

System B's continuous background workers (AggregationWorker, CommandWorker,
TelemetryWorker, StorageWorker) are **unchanged** — they are asyncio loops, not
scheduled jobs, and belong to System B's device server.

---

## Architecture

```
┌──────────────────────────────────────┐     ┌───────────────────────────────┐
│  System A (solarhub-platform)        │     │  Scheduler (solarhub-         │
│  FastAPI, port 8000                  │     │  scheduler), port 8002 health │
│                                      │     │                               │
│  No scheduled jobs when              │     │  APScheduler (AsyncIO)        │
│  SCHEDULER_ENABLED=false             │◄────│  PostgreSQL job store         │
│                                      │     │  Redis distributed locks      │
│  /api/v1/scheduler/* proxies         │     │                               │
│  to http://127.0.0.1:8002            │     │  Jobs:                        │
└──────────────────────────────────────┘     │    daily_billing (00:30 KHI)  │
                                             │    cycle_settlement (15th)    │
                ┌────────────────────────┐   │    outage_detection (2 min)   │
                │  PostgreSQL            │◄──┤                               │
                │  apscheduler_jobs      │   │  Imports system_a.app.*       │
                └────────────────────────┘   │  directly (same virtualenv)   │
                                             └───────────────────────────────┘
```

---

## Scheduled Jobs

| Job ID | Schedule | Description |
|--------|----------|-------------|
| `daily_billing` | 00:30 Asia/Karachi daily | Compute billing snapshots for all sites |
| `cycle_settlement_check` | 15th of month, 01:00 | Safety net for billing cycle finalization |
| `outage_detection` | Every 2 minutes | Detect grid outages from Redis telemetry |

---

## Directory Structure

```
scheduler/
  __init__.py          Package init
  __main__.py          Entry point (python -m scheduler)
  config.py            Imports System A settings via PYTHONPATH
  lock.py              Redis SETNX distributed lock decorator
  health.py            aiohttp health + admin endpoints on port 8002
  jobs/
    __init__.py
    registry.py        Registers all jobs; wraps billing jobs with Redis locks
  tests/
    __init__.py
    test_lock.py        Unit tests for lock.py
    test_registry.py    Unit tests for registry.py
    test_health.py      Unit tests for health.py
    test_main.py        Unit tests for __main__.py lifecycle
```

---

## Key Design Decisions

### Direct Python Import (not REST API)
The scheduler imports `system_a.app` modules directly because:
- All job logic lives in `system_a/app/infrastructure/scheduler/billing_jobs.py` and `ai_jobs.py`
- Rewriting them as HTTP API calls would require 4+ new internal endpoints and add
  HTTP error surface on long-running billing jobs
- Both processes run on the same server in the same virtualenv; the `PYTHONPATH`
  environment variable in the systemd unit makes System A's package importable

### Redis Distributed Locking
Each billing job is wrapped with `scheduler/lock.py:with_redis_lock()`:
- `daily_billing` — lock TTL 23 hours
- `cycle_settlement_check` — lock TTL 28 days
- `outage_detection` — has its own internal lock (TTL 90s); not double-wrapped

Multiple scheduler instances attempt `SETNX scheduler:lock:{job_id}`. Only the first
acquires the lock and executes; others skip silently.

### Backward Compatibility
System A's `SCHEDULER_ENABLED` setting defaults to `true`. Until the operator sets it
to `false`, System A continues to run its own embedded scheduler exactly as before.
During an overlapping period when both are running, the Redis locks prevent duplicate
billing.

---

## Deployment

### Install the service

```bash
# Copy service file
sudo cp deployment/systemd/solarhub-scheduler.service /etc/systemd/system/

# Reload and enable
sudo systemctl daemon-reload
sudo systemctl enable solarhub-scheduler.service
sudo systemctl start solarhub-scheduler.service
```

### Switch System A to external mode

Add to `/opt/solarhub/app/.env`:
```
SCHEDULER_ENABLED=false
```

Then restart System A:
```bash
sudo systemctl restart solarhub-platform.service
```

### Verify

```bash
# Check scheduler is running
sudo systemctl status solarhub-scheduler.service

# Check health endpoint
curl http://127.0.0.1:8002/health | python3 -m json.tool

# Check System A proxies correctly
curl -H "Authorization: Bearer $TOKEN" \
     https://your-domain/api/v1/scheduler/status | python3 -m json.tool
```

### Logs

```bash
tail -f /opt/solarhub/logs/scheduler.log
tail -f /opt/solarhub/logs/scheduler-error.log
journalctl -u solarhub-scheduler.service -f
```

---

## Horizontal Scaling

To run two scheduler instances (active-passive, locks ensure only one executes per job):

```bash
# Create a second instance via systemd template or a copy of the service file
# No configuration changes needed — Redis locks handle the rest
sudo cp /etc/systemd/system/solarhub-scheduler.service \
        /etc/systemd/system/solarhub-scheduler-2.service
sudo systemctl start solarhub-scheduler-2.service
```

Each instance independently:
1. Starts APScheduler connected to the same PostgreSQL job store
2. Fires jobs at the scheduled time
3. Attempts to acquire the Redis lock — only the winner executes

---

## Adding New Jobs

1. Write the job function in `system_a/app/infrastructure/scheduler/` (keep it there for
   System A's own import chain)
2. Import it in `scheduler/jobs/registry.py` and call `scheduler.add_job()`
3. Wrap with `with_redis_lock()` if the job must not run concurrently across instances
4. Add a unit test in `scheduler/tests/test_registry.py`
