"""
Minimal log stub — passes print() through to UART console only.

Kept minimal on ESP8266 to preserve the limited ~80 KB heap.
Logs are visible on the serial console (UART0, GPIO1/GPIO3).
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
