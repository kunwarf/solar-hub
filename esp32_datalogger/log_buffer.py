"""
Circular log buffer for capturing console output.

Pre-allocated fixed-size buffer — no dynamic list growth, no pop(0).
Messages are stored as plain strings; timestamps are generated only
on read (infrequent web UI access), keeping the hot add() path cheap.
"""
import time


class LogBuffer:
    """Pre-allocated circular buffer for log messages."""

    def __init__(self, max_size=50):
        # Pre-allocate the full list upfront — no realloc ever
        self._buf = [None] * max_size
        self._size = max_size
        self._head = 0      # next slot to write into
        self._count = 0     # number of valid entries (<= _size)
        self._base_id = 0   # global ID of the oldest entry in buffer
        self._start_time = time.time()

    def add(self, message):
        """Add a log message to the buffer (O(1), no allocation)."""
        self._buf[self._head] = str(message)
        self._head = (self._head + 1) % self._size
        if self._count < self._size:
            self._count += 1
        else:
            # Buffer full — oldest slot overwritten, advance base_id
            self._base_id += 1

    def _entry_at(self, slot_index):
        """Build a dict for one slot (called only on read)."""
        # slot_index is 0 = oldest, 1 = next, ... count-1 = newest
        slot = (self._head - self._count + slot_index) % self._size
        global_id = self._base_id + slot_index
        return {
            "id": global_id,
            "time": self._timestamp(),
            "msg": self._buf[slot],
        }

    def get_recent(self, count=50, since_id=None):
        """
        Return recent log entries as list of dicts.

        Args:
            count: Maximum number of entries to return.
            since_id: If set, only return entries with id > since_id.
        """
        if self._count == 0:
            return []

        oldest_id = self._base_id
        newest_id = self._base_id + self._count - 1

        if since_id is not None:
            start_id = since_id + 1
        else:
            start_id = max(oldest_id, newest_id - count + 1)

        if start_id > newest_id:
            return []

        start_id = max(start_id, oldest_id)
        result = []
        for global_id in range(start_id, newest_id + 1):
            slot_index = global_id - oldest_id
            slot = (self._head - self._count + slot_index) % self._size
            result.append({
                "id": global_id,
                "time": self._timestamp(),
                "msg": self._buf[slot],
            })
            if len(result) >= count:
                break
        return result

    def get_last_id(self):
        """Return the global ID of the most recent entry."""
        if self._count == 0:
            return 0
        return self._base_id + self._count - 1

    def clear(self):
        """Clear all entries."""
        self._head = 0
        self._count = 0
        self._base_id = 0
        # Leave _buf contents; they will be overwritten on next add()

    def _timestamp(self):
        """Format elapsed time as HH:MM:SS.ss (generated only on read)."""
        try:
            elapsed = time.time() - self._start_time
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = elapsed % 60
            return "{:02d}:{:02d}:{:05.2f}".format(h, m, s)
        except Exception:
            return "00:00:00.00"


# Global instance — small buffer to keep heap usage low
_log_buffer = LogBuffer(max_size=80)


def get_log_buffer():
    """Return the global log buffer instance."""
    return _log_buffer


def log_print(*args, **kwargs):
    """
    Drop-in replacement for print() that also buffers to the web UI.

    Usage:
        from log_buffer import log_print as print
    """
    message = " ".join(str(a) for a in args)
    _log_buffer.add(message)
    import builtins
    builtins.print(message)
