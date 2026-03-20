"""
Minimal log stub — passes print() through to UART console only.

The full circular buffer (log_buffer_full.py) is not loaded because it
keeps 80 log strings in RAM (~4 KB) which is better spent on the JK BMS
receive buffer.  Logs are visible on the serial console instead.
"""
try:
    import builtins as _builtins

    def log_print(*args, **kwargs):
        _builtins.print(*args, **kwargs)

except ImportError:
    def log_print(*args, **kwargs):
        print(*args, **kwargs)


def get_log_buffer():
    """No in-memory log buffer — returns None."""
    return None
