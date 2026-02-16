"""
Test different register addresses to find where inverter responds.
"""
from modbus_rtu import ModbusRTU
from config import get_config
import time

print("\n" + "="*50)
print("Testing Common Inverter Registers")
print("="*50 + "\n")

config = get_config()
rtu = ModbusRTU(config["rtu"])
unit_id = config["rtu"]["unit_id"]

# Common register addresses used by different inverter brands
test_registers = [
    (0, 1, "Register 0 (device ID)"),
    (1, 1, "Register 1"),
    (10, 1, "Register 10"),
    (100, 2, "Register 100-101 (AC voltage)"),
    (256, 2, "Register 256-257"),
    (1000, 2, "Register 1000-1001"),
    (3000, 2, "Register 3000-3001"),
    (30000, 2, "Register 30000 (holding)"),
    (40000, 2, "Register 40000 (input)"),
]

print("Testing {} register locations...\n".format(len(test_registers)))

for addr, count, desc in test_registers:
    print("[Test] {} (address {}, count {})".format(desc, addr, count))

    # Try as holding register (0x03)
    result = rtu.read_holding_registers(addr, count, unit_id=unit_id, quiet=True)

    if result:
        print("  ✓✓✓ SUCCESS! ✓✓✓")
        print("  Function: 0x03 (Read Holding Registers)")
        print("  Address: {}".format(addr))
        print("  Data: {}".format([hex(x) for x in result]))
        print("\n" + "="*50)
        print("INVERTER IS RESPONDING!")
        print("="*50)
        import sys
        sys.exit(0)

    time.sleep(0.3)
    print("  ✗ No response\n")

print("="*50)
print("Still no response - check hardware:")
print("1. Swap RS485 A/B wires")
print("2. Check inverter is ON")
print("3. Verify inverter Modbus settings")
print("="*50)
