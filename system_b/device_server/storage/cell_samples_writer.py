"""
Per-cell battery sample writer for TimescaleDB.

Phase 2 of the candidate-faulty-cell detector. The Pylontech and JK BMS
parsers already emit ``telemetry["battery_cells"]`` as a list of dicts;
this writer batches them into the ``battery_cell_samples`` hypertable
introduced in Alembic migration ``20260701_0012``.

The writer:

- Runs alongside ``TimescaleWriter`` and ``TelemetryCacheWriter`` from the
  ``_on_telemetry`` callback; a failure here does not block the other paths.
- Owns its own asyncpg pool (isolated from other writers).
- Buffers records and flushes on a configurable interval.
- Resolves ``site_id`` at flush time via a single batched ``device_registry``
  lookup, mirroring ``TimescaleWriter._flush_batch``.
- Deduplicates on ``(time, device_id, unit, cell)`` via ``ON CONFLICT DO NOTHING``.
- Silently no-ops when the telemetry payload has no ``battery_cells`` list
  (i.e. every non-battery device).

Cell dicts may carry either ``unit`` (JK BMS) or ``module`` (Pylontech) —
both are normalised to ``unit`` on insert.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

try:
    import asyncpg
except ImportError:  # pragma: no cover - env guard, matches TimescaleWriter
    asyncpg = None

from ..config import DeviceServerSettings, get_device_server_settings


logger = logging.getLogger(__name__)


# Buffered row shape: site_id is filled in at flush time, so it's absent here.
# (time, device_id, unit, cell, voltage_v, current_a, temperature, soc_pct)
_PendingRow = Tuple[
    datetime,
    UUID,
    int,
    int,
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[int],
]


class CellSamplesWriter:
    """Batches per-cell samples into ``battery_cell_samples``."""

    def __init__(
        self,
        settings: Optional[DeviceServerSettings] = None,
    ) -> None:
        self.settings = settings or get_device_server_settings()
        self._pool: Optional["asyncpg.Pool"] = None
        self._batch: List[_PendingRow] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None

    # ── lifecycle ───────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if asyncpg is None:
            logger.warning("asyncpg not installed, cell-samples writes disabled")
            return

        storage = self.settings.storage
        try:
            self._pool = await asyncpg.create_pool(
                host=storage.host,
                port=storage.port,
                database=storage.name,
                user=storage.user,
                password=storage.password,
                min_size=1,
                max_size=4,
            )
            logger.info(
                "CellSamplesWriter connected to TimescaleDB at %s:%s/%s",
                storage.host, storage.port, storage.name,
            )
            self._flush_task = asyncio.create_task(self._flush_loop())
        except Exception as exc:
            logger.error("CellSamplesWriter: connect failed: %s", exc)
            self._pool = None

    async def disconnect(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("CellSamplesWriter disconnected")

    # ── write path ──────────────────────────────────────────────────────────

    async def write(
        self,
        device_id: UUID,
        telemetry: Dict[str, Any],
    ) -> int:
        """Extract ``battery_cells`` from a telemetry dict and buffer rows.

        Returns the number of rows queued. Returns 0 (no error) when the
        payload has no per-cell data or no pool is connected.
        """
        if self._pool is None:
            return 0

        cells = telemetry.get("battery_cells")
        if not cells:
            return 0

        ts = self._resolve_timestamp(telemetry.get("_timestamp"))

        rows: List[_PendingRow] = []
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            unit = cell.get("unit", cell.get("module"))
            cell_index = cell.get("cell")
            if unit is None or cell_index is None:
                continue
            try:
                rows.append((
                    ts,
                    device_id,
                    int(unit),
                    int(cell_index),
                    _as_float(cell.get("voltage_v")),
                    _as_float(cell.get("current_a")),
                    _as_float(cell.get("temperature")),
                    _as_int(cell.get("soc")),
                ))
            except (TypeError, ValueError):
                # A malformed row shouldn't kill the batch.
                continue

        if not rows:
            return 0

        async with self._batch_lock:
            self._batch.extend(rows)
            if len(self._batch) >= self.settings.storage.batch_size:
                await self._flush_batch()
        return len(rows)

    async def flush(self) -> None:
        async with self._batch_lock:
            await self._flush_batch()

    # ── internals ───────────────────────────────────────────────────────────

    async def _flush_batch(self) -> None:
        if not self._batch or not self._pool:
            return
        batch = self._batch
        self._batch = []

        try:
            async with self._pool.acquire() as conn:
                # Resolve site_id for every distinct device in one query.
                device_ids = list({row[1] for row in batch})
                site_rows = await conn.fetch(
                    """
                    SELECT device_id, site_id
                    FROM device_registry
                    WHERE device_id = ANY($1::uuid[])
                    """,
                    device_ids,
                )
                site_map: Dict[UUID, UUID] = {
                    r["device_id"]: r["site_id"] for r in site_rows if r["site_id"]
                }

                # Assemble insert tuples in the column order of the INSERT.
                # (time, device_id, site_id, unit, cell, voltage_v,
                #  current_a, temperature, soc_pct)
                to_insert: List[Tuple[Any, ...]] = []
                skipped_no_site = 0
                for (ts, dev_id, unit, cell, v, c, t, soc) in batch:
                    site_id = site_map.get(dev_id)
                    if site_id is None:
                        skipped_no_site += 1
                        continue
                    to_insert.append(
                        (ts, dev_id, site_id, unit, cell, v, c, t, soc)
                    )

                if not to_insert:
                    if skipped_no_site:
                        logger.debug(
                            "CellSamplesWriter: dropped %d rows (no site_id)",
                            skipped_no_site,
                        )
                    return

                await conn.executemany(
                    """
                    INSERT INTO battery_cell_samples
                        (time, device_id, site_id, unit, cell,
                         voltage_v, current_a, temperature, soc_pct)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (time, device_id, unit, cell) DO NOTHING
                    """,
                    to_insert,
                )
            logger.debug(
                "CellSamplesWriter flushed %d rows (skipped %d for missing site_id)",
                len(to_insert), skipped_no_site,
            )
        except Exception as exc:
            logger.error("CellSamplesWriter: flush failed: %s", exc, exc_info=True)
            # Requeue so the next flush retries.
            self._batch.extend(batch)

    async def _flush_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.settings.storage.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("CellSamplesWriter flush loop error: %s", exc)

    @staticmethod
    def _resolve_timestamp(raw: Optional[str]) -> datetime:
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except Exception:
                pass
        return datetime.now(timezone.utc)


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
