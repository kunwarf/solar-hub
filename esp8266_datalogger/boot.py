"""
ESP8266 Boot Script.

This runs before main.py. Keep it minimal for fast boot.
"""
import gc
import esp

# Disable debug output on UART0
esp.osdebug(None)

# Run garbage collection
gc.collect()
print("Free:", gc.mem_free())
print("Alloc:", gc.mem_alloc())
print("Boot complete, starting main...")
