"""
ESP32 Boot Script.

This runs before main.py. Keep it minimal for fast boot.
"""
import gc
import esp

# Disable debug output on UART0
esp.osdebug(None)

# Run garbage collection
gc.collect()

print("Boot complete, starting main...")

