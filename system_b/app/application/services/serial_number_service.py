"""
Serial Number Generation and Validation Service.

Generates and validates 16-character alphanumeric serial numbers
with a 2-character check digit for data integrity verification.

Serial Number Format: MMHH-TTNN-NNNN-NNCC (16 chars, dashes optional)
- MM: Manufacturer code (2 chars) - "SH" for SolarHub
- HH: Hardware revision (2 chars) - e.g., "01", "02"
- TT: Device type code (2 chars) - "IN"=inverter, "BT"=battery, "MT"=meter, "GW"=gateway
- NNNNNNNN: Random alphanumeric (8 chars)
- CC: Check digits (2 chars) - calculated from first 14 chars

Check Digit Algorithm:
Uses a modified Luhn algorithm adapted for alphanumeric (base 36):
1. Convert chars to values: 0-9=0-9, A-Z=10-35
2. Process from right to left, doubling every second digit
3. If doubled value >= 36, subtract 36
4. Sum all values
5. Calculate check digits: (36 - (sum mod 36)) mod 36
"""

import secrets
import string
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

# Character set: 0-9, A-Z (uppercase only, no ambiguous chars O/0, I/1)
CHARSET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 chars, unambiguous
BASE = len(CHARSET)  # 32

# Alternative full alphanumeric for validation of legacy serials
FULL_CHARSET = string.digits + string.ascii_uppercase  # 36 chars


class DeviceTypeCode(str, Enum):
    """Device type codes for serial numbers."""
    INVERTER = "IN"
    BATTERY = "BT"
    METER = "MT"
    GATEWAY = "GW"
    SENSOR = "SR"
    WEATHER = "WS"
    OTHER = "XX"


# Mapping from DeviceType enum to code
DEVICE_TYPE_TO_CODE = {
    "inverter": DeviceTypeCode.INVERTER,
    "battery": DeviceTypeCode.BATTERY,
    "meter": DeviceTypeCode.METER,
    "gateway": DeviceTypeCode.GATEWAY,
    "sensor": DeviceTypeCode.SENSOR,
    "weather_station": DeviceTypeCode.WEATHER,
    "other": DeviceTypeCode.OTHER,
}

CODE_TO_DEVICE_TYPE = {v.value: k for k, v in DEVICE_TYPE_TO_CODE.items()}


@dataclass
class SerialNumberInfo:
    """Parsed serial number information."""
    serial_number: str
    manufacturer_code: str
    hardware_revision: str
    device_type_code: str
    device_type: str
    random_part: str
    check_digits: str
    is_valid: bool


class SerialNumberService:
    """
    Service for generating and validating device serial numbers.
    """

    MANUFACTURER_CODE = "SH"  # SolarHub
    DEFAULT_HARDWARE_REVISION = "01"

    def __init__(self, manufacturer_code: str = "SH"):
        """
        Initialize the service.

        Args:
            manufacturer_code: 2-char manufacturer code (default: "SH")
        """
        self.manufacturer_code = manufacturer_code.upper()[:2].ljust(2, "0")

    def generate(
        self,
        device_type: str = "inverter",
        hardware_revision: str = "01",
        count: int = 1,
    ) -> list[str]:
        """
        Generate serial numbers.

        Args:
            device_type: Device type (inverter, battery, meter, gateway, etc.)
            hardware_revision: 2-char hardware revision code
            count: Number of serial numbers to generate

        Returns:
            List of generated serial numbers
        """
        device_type_code = DEVICE_TYPE_TO_CODE.get(
            device_type.lower(),
            DeviceTypeCode.OTHER
        ).value

        hw_rev = hardware_revision.upper()[:2].ljust(2, "0")

        serials = []
        for _ in range(count):
            # Generate random part (8 chars)
            random_part = self._generate_random_string(8)

            # Build base serial (14 chars without check digits)
            base = f"{self.manufacturer_code}{hw_rev}{device_type_code}{random_part}"

            # Calculate check digits
            check_digits = self._calculate_check_digits(base)

            serial = base + check_digits
            serials.append(serial)

        return serials

    def validate(self, serial_number: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a serial number.

        Args:
            serial_number: Serial number to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Remove any dashes or spaces
        serial = serial_number.upper().replace("-", "").replace(" ", "")

        # Check length
        if len(serial) != 16:
            return False, f"Invalid length: expected 16, got {len(serial)}"

        # Check characters are valid
        for i, char in enumerate(serial):
            if char not in FULL_CHARSET:
                return False, f"Invalid character '{char}' at position {i+1}"

        # Extract parts
        base = serial[:14]
        provided_check = serial[14:16]

        # Calculate expected check digits
        expected_check = self._calculate_check_digits(base)

        if provided_check != expected_check:
            return False, "Invalid check digits"

        # Validate manufacturer code (optional strictness)
        manufacturer = serial[:2]
        if manufacturer != self.manufacturer_code:
            # Allow but warn - might be a different manufacturer
            pass

        # Validate device type code
        device_type_code = serial[4:6]
        if device_type_code not in [e.value for e in DeviceTypeCode]:
            return False, f"Invalid device type code: {device_type_code}"

        return True, None

    def parse(self, serial_number: str) -> SerialNumberInfo:
        """
        Parse a serial number and extract its components.

        Args:
            serial_number: Serial number to parse

        Returns:
            SerialNumberInfo with parsed components
        """
        serial = serial_number.upper().replace("-", "").replace(" ", "")

        is_valid, _ = self.validate(serial_number)

        manufacturer_code = serial[:2] if len(serial) >= 2 else ""
        hardware_revision = serial[2:4] if len(serial) >= 4 else ""
        device_type_code = serial[4:6] if len(serial) >= 6 else ""
        random_part = serial[6:14] if len(serial) >= 14 else ""
        check_digits = serial[14:16] if len(serial) >= 16 else ""

        device_type = CODE_TO_DEVICE_TYPE.get(device_type_code, "unknown")

        return SerialNumberInfo(
            serial_number=serial,
            manufacturer_code=manufacturer_code,
            hardware_revision=hardware_revision,
            device_type_code=device_type_code,
            device_type=device_type,
            random_part=random_part,
            check_digits=check_digits,
            is_valid=is_valid,
        )

    def format_display(self, serial_number: str) -> str:
        """
        Format serial number for display with dashes.

        Args:
            serial_number: Raw serial number

        Returns:
            Formatted serial: XXXX-XXXX-XXXX-XXXX
        """
        serial = serial_number.upper().replace("-", "").replace(" ", "")
        if len(serial) == 16:
            return f"{serial[:4]}-{serial[4:8]}-{serial[8:12]}-{serial[12:16]}"
        return serial

    def _generate_random_string(self, length: int) -> str:
        """Generate a random string from the character set."""
        return "".join(secrets.choice(CHARSET) for _ in range(length))

    def _calculate_check_digits(self, base: str) -> str:
        """
        Calculate 2-character check digits using modified Luhn algorithm.

        The algorithm:
        1. Convert each char to a value (0-9, A-Z=10-35)
        2. From right to left, double every second digit
        3. If doubled >= 36, subtract 36
        4. Sum all values
        5. First check digit: (36 - (sum mod 36)) mod 36
        6. Second check digit: (36 - ((sum + first_check) mod 36)) mod 36

        Args:
            base: 14-character base string

        Returns:
            2-character check digits
        """
        values = [self._char_to_value(c) for c in base.upper()]

        # Modified Luhn: double alternate digits from right
        total = 0
        for i, val in enumerate(reversed(values)):
            if i % 2 == 0:
                doubled = val * 2
                if doubled >= 36:
                    doubled -= 36
                total += doubled
            else:
                total += val

        # First check digit
        check1 = (36 - (total % 36)) % 36

        # Second check digit (include first check in calculation)
        total_with_check1 = total + check1
        check2 = (36 - (total_with_check1 % 36)) % 36

        return self._value_to_char(check1) + self._value_to_char(check2)

    def _char_to_value(self, char: str) -> int:
        """Convert character to numeric value (0-35)."""
        if char.isdigit():
            return int(char)
        return ord(char.upper()) - ord('A') + 10

    def _value_to_char(self, value: int) -> str:
        """Convert numeric value (0-35) to character."""
        if value < 10:
            return str(value)
        return chr(ord('A') + value - 10)


# Singleton instance
_serial_service: Optional[SerialNumberService] = None


def get_serial_number_service() -> SerialNumberService:
    """Get or create the serial number service singleton."""
    global _serial_service
    if _serial_service is None:
        _serial_service = SerialNumberService()
    return _serial_service
