"""
Simple Modbus RTU diagnostic script for ESP32.

Tests different configurations to find what works with your inverter.
Upload this file and run it to test connectivity.
"""
from modbus_rtu import ModbusRTU
from config import get_config
import time

print("\n" + "="*50)
print("Modbus RTU Diagnostic Tool")
print("="*50 + "\n")

# Load config
config = get_config()
rtu_config = config["rtu"]

print("Current Configuration:")
print("  Baud Rate:", rtu_config["baudrate"])
print("  Unit ID:", rtu_config["unit_id"])
print("  TX Pin:", rtu_config["tx_pin"])
print("  RX Pin:", rtu_config["rx_pin"])
print("  DE Pin:", rtu_config.get("de_pin", 0))
print("  Timeout:", rtu_config["timeout_ms"], "ms")
print()

# Create RTU instance
rtu = ModbusRTU(rtu_config)

# Test configurations
test_configs = [
    {"unit_id": 1, "baudrate": 9600, "desc": "Unit 1, 9600 baud (default)"},
    {"unit_id": 247, "baudrate": 9600, "desc": "Unit 247, 9600 baud (single device)"},
    {"unit_id": 1, "baudrate": 19200, "desc": "Unit 1, 19200 baud"},
    {"unit_id": 1, "baudrate": 4800, "desc": "Unit 1, 4800 baud"},
]

print("Running diagnostic tests...")
print("-" * 50)

for i, test in enumerate(test_configs, 1):
    print(f"\n[Test {i}/4] {test['desc']}")

    # Update baud rate if different
    if test["baudrate"] != rtu_config["baudrate"]:
        print(f"  Changing baud rate to {test['baudrate']}...")
        rtu_config["baudrate"] = test["baudrate"]
        rtu = ModbusRTU(rtu_config)

    # Try reading register 0 (device type/identification)
    print(f"  Attempting to read register 0...")
    result = rtu.read_holding_registers(0, 1, unit_id=test["unit_id"], quiet=False)

    if result:
        print(f"  ✓ SUCCESS! Response: {result}")
        print(f"  >> This configuration works!")
        print(f"  >> Update your config.json:")
        print(f"     \"unit_id\": {test['unit_id']},")
        print(f"     \"baudrate\": {test['baudrate']}")
        break
    else:
        print(f"  ✗ No response (timeout)")

    time.sleep(1)

print("\n" + "="*50)
print("Diagnostic complete")
print("="*50)

# Additional tips
print("\nTroubleshooting Tips:")
print("1. Check RS485 wiring (try swapping A/B)")
print("2. Ensure inverter is powered on")
print("3. Check if inverter has 'Modbus Enable' setting")
print("4. Verify common ground connection")
print("5. Try disabling DE pin: set 'de_pin': 0 in config.json")
