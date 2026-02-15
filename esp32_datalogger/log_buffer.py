"""
Circular log buffer for capturing console output.

Stores recent log messages in memory for display on web interface.
"""
import time


class LogBuffer:
    """Thread-safe circular buffer for log messages."""

    def __init__(self, max_size=200):
        """
        Initialize log buffer.

        Args:
            max_size: Maximum number of log entries to keep
        """
        self.buffer = []
        self.max_size = max_size
        self.index = 0
        self._start_time = time.time()

    def add(self, message):
        """Add a log message to the buffer."""
        timestamp = self._get_timestamp()
        entry = {
            "id": self.index,
            "time": timestamp,
            "msg": str(message)
        }

        if len(self.buffer) >= self.max_size:
            self.buffer.pop(0)  # Remove oldest

        self.buffer.append(entry)
        self.index += 1

    def get_recent(self, count=50, since_id=None):
        """
        Get recent log entries.

        Args:
            count: Number of entries to return
            since_id: Only return entries after this ID

        Returns:
            List of log entries
        """
        if since_id is not None:
            # Return only new entries
            return [e for e in self.buffer if e["id"] > since_id][-count:]
        else:
            # Return last N entries
            return self.buffer[-count:]

    def get_last_id(self):
        """Get the ID of the most recent log entry."""
        return self.buffer[-1]["id"] if self.buffer else 0

    def clear(self):
        """Clear all log entries."""
        self.buffer = []
        self.index = 0

    def _get_timestamp(self):
        """Get current timestamp as string."""
        try:
            elapsed = time.time() - self._start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = elapsed % 60
            return "{:02d}:{:02d}:{:05.2f}".format(hours, minutes, seconds)
        except:
            return "00:00:00.00"


# Global log buffer instance
_log_buffer = LogBuffer(max_size=200)


def get_log_buffer():
    """Get the global log buffer instance."""
    return _log_buffer


def log_print(*args, **kwargs):
    """
    Replacement for print() that also logs to buffer.

    Use this in your code instead of print():
        from log_buffer import log_print as print
    """
    # Convert args to string
    message = " ".join(str(arg) for arg in args)

    # Add to buffer
    _log_buffer.add(message)

    # Also print to console
    import builtins
    builtins.print(message)
