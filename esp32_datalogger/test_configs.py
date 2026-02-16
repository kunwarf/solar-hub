"""
Quick Modbus RTU configuration tester.
Tests multiple common configurations to find what works.
"""
from modbus_rtu import ModbusRTU
from config import get_config
import time

print("\n" + "="*50)
print("Modbus RTU Quick Test")
print("="*50 + "\n")

config = get_config()
rtu_config = config["rtu"]

print("Hardware Setup:")
print("  UART: 2")
print("  TX Pin: 17")
print("  RX Pin: 16")
print("  DE Pin:", rtu_config.get("de_pin", 0))
print()

# Test configurations - most common setups
tests = [
    # (unit_id, baudrate, description)
    (1, 9600, "Standard: UID=1, 9600 baud"),
    (247, 9600, "Broadcast: UID=247, 9600 baud"),
    (1, 19200, "Fast: UID=1, 19200 baud"),
    (247, 19200, "Broadcast: UID=247, 19200 baud"),
    (1, 4800, "Slow: UID=1, 4800 baud"),
]

print("Testing {} configurations...\n".format(len(tests)))
print("-" * 50)

current_baud = rtu_config["baudrate"]
rtu = ModbusRTU(rtu_config)

for i, (unit_id, baudrate, desc) in enumerate(tests, 1):
    print("\n[Test {}/{}] {}".format(i, len(tests), desc))

    # Reinitialize if baud rate changed
    if baudrate != current_baud:
        print("  Changing baud rate to {}...".format(baudrate))
        rtu_config["baudrate"] = baudrate
        rtu = ModbusRTU(rtu_config)
        current_baud = baudrate
        time.sleep(0.5)  # Let UART settle

    # Try reading a few common registers
    test_registers = [
        (0, "Register 0 (device info)"),
        (1, "Register 1"),
        (100, "Register 100 (common start)"),
    ]

    for reg_addr, reg_desc in test_registers:
        print("  Testing {}...".format(reg_desc))
        result = rtu.read_holding_registers(reg_addr, 1, unit_id=unit_id, quiet=True)

        if result:
            print("  ✓✓✓ SUCCESS! ✓✓✓")
            print("  Response:", [hex(x) for x in result])
            print("\n" + "="*50)
            print("FOUND WORKING CONFIGURATION!")
            print("="*50)
            print("Update your config.json:")
            print('  "unit_id": {},'.format(unit_id))
            print('  "baudrate": {}'.format(baudrate))
            print("="*50)
            import sys
            sys.exit(0)

        time.sleep(0.2)

    print("  ✗ No response")
    time.sleep(0.5)

print("\n" + "="*50)
print("TROUBLESHOOTING NEEDED")
print("="*50)
print("\nNo configuration worked. Try these:")
print("1. SWAP RS485 A and B wires (most common fix)")
print("2. Check inverter Modbus is enabled")
print("3. Try DE pin = 0 in config.json")
print("4. Verify inverter is powered on")
print("5. Check RS485 module has proper power (3.3V or 5V)")
print("\nIf you have inverter manual, check:")
print("- Modbus slave address (unit ID)")
print("- Baud rate setting")
print("- Register map (which registers are valid)")
