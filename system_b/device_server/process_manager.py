"""
Polling Process Manager — Phase 5 of the multi-process pipeline.

Spawns and supervises N independent Device Server worker processes.
Each process binds to port 8502 via SO_REUSEPORT; the Linux kernel
distributes incoming device connections across all of them.

Each worker runs a full Device Server:
  - TCP server (SO_REUSEPORT) → accepts ~1/N of device connections
  - Identification, polling, adapter management
  - Redis cache writes (real-time frontend data)
  - Redis Stream publishing → StorageWorker handles TimescaleDB

Result: N CPU cores fully utilised for device polling.

Managed by: solarhub-polling-manager.service
Log file:   /opt/solarhub/logs/polling-manager.log

Environment variables:
  POLLING_WORKERS=1           Number of worker processes (default: 1).
                              Raising this above 1 with SO_REUSEPORT causes
                              per-worker device-manager state divergence —
                              devices routed to worker A on one connection
                              cycle can end up on worker B the next, leaving
                              their prior state (claimed_data_loggers, poll
                              schedule) orphaned. Leave at 1 unless the
                              fleet grows large enough to bottleneck one
                              CPU core.
  STORAGE_WORKER_ENABLED=true Must also be set for workers to skip DB writes
"""
import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# How long to wait before restarting a crashed worker (seconds)
RESTART_DELAY = 5
# How often to log a health summary (seconds)
HEALTH_LOG_INTERVAL = 60


# ---------------------------------------------------------------------------
# Worker entry point (runs in child process)
# ---------------------------------------------------------------------------

def _run_worker(worker_id: int) -> None:
    """
    Entry point for each polling worker process.

    Runs a full Device Server instance. Called by multiprocessing.Process.
    """
    # Set worker identity in env so logs are distinguishable
    os.environ["POLLING_WORKER_ID"] = str(worker_id)

    # Reconfigure logging with worker prefix
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [polling-worker-{worker_id}] %(name)s %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    log = logging.getLogger(__name__)
    log.info("[POLLING_WORKER-%d] Starting", worker_id)

    try:
        from device_server.main import main as device_server_main
        asyncio.run(device_server_main())
    except KeyboardInterrupt:
        log.info("[POLLING_WORKER-%d] Interrupted", worker_id)
    except Exception:
        log.exception("[POLLING_WORKER-%d] Fatal error — process will exit", worker_id)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Process Manager
# ---------------------------------------------------------------------------

class ProcessManager:
    """
    Spawns and supervises N Device Server worker processes.

    Uses multiprocessing.Process so each worker gets its own OS process,
    its own Python interpreter, and its own CPU core.
    """

    def __init__(self, num_workers: int) -> None:
        self._num_workers = num_workers
        self._processes: Dict[int, multiprocessing.Process] = {}  # worker_id → process
        self._running = False
        self._start_time = time.monotonic()
        self._restart_counts: Dict[int, int] = {}

    def start(self) -> None:
        """Spawn all worker processes."""
        logger.info(
            "[POLLING_MGR] Starting %d polling workers (SO_REUSEPORT on port 8502)",
            self._num_workers,
        )
        self._running = True
        for worker_id in range(self._num_workers):
            self._spawn(worker_id)

    def _spawn(self, worker_id: int) -> None:
        """Start a single worker process."""
        p = multiprocessing.Process(
            target=_run_worker,
            args=(worker_id,),
            name=f"polling-worker-{worker_id}",
            daemon=False,
        )
        p.start()
        self._processes[worker_id] = p
        self._restart_counts.setdefault(worker_id, 0)
        logger.info(
            "[POLLING_MGR] Spawned polling-worker-%d (pid=%d)",
            worker_id,
            p.pid,
        )

    def stop(self) -> None:
        """Send SIGTERM to all workers and wait for them to exit."""
        self._running = False
        logger.info("[POLLING_MGR] Stopping all %d workers...", len(self._processes))
        for worker_id, p in self._processes.items():
            if p.is_alive():
                logger.info(
                    "[POLLING_MGR] Sending SIGTERM to polling-worker-%d (pid=%d)",
                    worker_id,
                    p.pid,
                )
                p.terminate()

        # Wait up to 15 s for graceful shutdown
        deadline = time.monotonic() + 15
        for worker_id, p in self._processes.items():
            remaining = max(0, deadline - time.monotonic())
            p.join(timeout=remaining)
            if p.is_alive():
                logger.warning(
                    "[POLLING_MGR] polling-worker-%d did not exit in time — killing",
                    worker_id,
                )
                p.kill()
                p.join(timeout=3)

        logger.info("[POLLING_MGR] All workers stopped")

    def monitor_loop(self) -> None:
        """
        Synchronous monitoring loop — blocks until stop() is called.

        Checks worker health every second. Restarts crashed workers after
        RESTART_DELAY seconds.
        """
        last_health_log = time.monotonic()

        while self._running:
            time.sleep(1)

            for worker_id in range(self._num_workers):
                p = self._processes.get(worker_id)
                if p is None or not p.is_alive():
                    exit_code = p.exitcode if p else None
                    logger.error(
                        "[POLLING_MGR] polling-worker-%d died (exit_code=%s) — "
                        "restarting in %ds",
                        worker_id,
                        exit_code,
                        RESTART_DELAY,
                    )
                    self._restart_counts[worker_id] = self._restart_counts.get(worker_id, 0) + 1
                    time.sleep(RESTART_DELAY)
                    if self._running:
                        self._spawn(worker_id)

            # Periodic health summary
            now = time.monotonic()
            if now - last_health_log >= HEALTH_LOG_INTERVAL:
                alive = sum(1 for p in self._processes.values() if p.is_alive())
                uptime = int(now - self._start_time)
                logger.info(
                    "[POLLING_MGR] Health: %d/%d workers alive | uptime=%ds | restarts=%s",
                    alive,
                    self._num_workers,
                    uptime,
                    dict(self._restart_counts),
                )
                last_health_log = now


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the polling process manager."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [polling-manager] %(name)s %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    num_workers = int(os.environ.get("POLLING_WORKERS", "1"))
    logger.info("[POLLING_MGR] Polling manager starting (workers=%d)", num_workers)

    manager = ProcessManager(num_workers=num_workers)

    # Handle SIGTERM / SIGINT for graceful shutdown
    def _shutdown(signum, frame):
        logger.info("[POLLING_MGR] Received signal %d — shutting down", signum)
        manager.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    manager.start()

    try:
        manager.monitor_loop()
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
