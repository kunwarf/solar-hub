"""Unit tests for Serial Number Service."""

import pytest

from system_b.app.application.services.serial_number_service import (
    SerialNumberService,
    DeviceTypeCode,
    DEVICE_TYPE_TO_CODE,
    CODE_TO_DEVICE_TYPE,
)


class TestSerialNumberService:
    """Tests for SerialNumberService."""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return SerialNumberService()

    # =========================================================================
    # Generation Tests
    # =========================================================================

    def test_generate_single_serial(self, service):
        """Test generating a single serial number."""
        serials = service.generate(device_type="inverter", count=1)

        assert len(serials) == 1
        assert len(serials[0]) == 16
        assert serials[0].startswith("SH01IN")  # SH=manufacturer, 01=hw rev, IN=inverter

    def test_generate_multiple_serials(self, service):
        """Test generating multiple serial numbers."""
        serials = service.generate(device_type="battery", count=5)

        assert len(serials) == 5
        assert len(set(serials)) == 5  # All unique

        for serial in serials:
            assert len(serial) == 16
            assert serial.startswith("SH01BT")

    def test_generate_all_device_types(self, service):
        """Test generating serials for all device types."""
        expected_codes = {
            "inverter": "IN",
            "battery": "BT",
            "meter": "MT",
            "gateway": "GW",
            "sensor": "SR",
            "weather_station": "WS",
            "other": "XX",
        }

        for device_type, code in expected_codes.items():
            serials = service.generate(device_type=device_type, count=1)
            assert serials[0][4:6] == code, f"Failed for {device_type}"

    def test_generate_with_custom_hardware_revision(self, service):
        """Test generating with custom hardware revision."""
        serials = service.generate(device_type="inverter", hardware_revision="02", count=1)

        assert serials[0][2:4] == "02"

    def test_generate_unknown_device_type_uses_other(self, service):
        """Test that unknown device types default to 'other' (XX)."""
        serials = service.generate(device_type="unknown_type", count=1)

        assert serials[0][4:6] == "XX"

    # =========================================================================
    # Validation Tests
    # =========================================================================

    def test_validate_generated_serial(self, service):
        """Test that generated serials are valid."""
        serials = service.generate(device_type="inverter", count=10)

        for serial in serials:
            is_valid, error = service.validate(serial)
            assert is_valid, f"Serial {serial} should be valid but got error: {error}"

    def test_validate_with_dashes(self, service):
        """Test validation works with formatted serials (with dashes)."""
        serials = service.generate(device_type="inverter", count=1)
        formatted = service.format_display(serials[0])

        is_valid, error = service.validate(formatted)
        assert is_valid

    def test_validate_invalid_length(self, service):
        """Test validation fails for wrong length."""
        is_valid, error = service.validate("TOOSHORT")

        assert not is_valid
        assert "Invalid length" in error

    def test_validate_invalid_characters(self, service):
        """Test validation fails for invalid characters."""
        is_valid, error = service.validate("SH01IN12345$7890")

        assert not is_valid
        assert "Invalid character" in error

    def test_validate_invalid_check_digits(self, service):
        """Test validation fails for wrong check digits."""
        # Generate a valid serial and change the check digits
        serials = service.generate(device_type="inverter", count=1)
        tampered = serials[0][:14] + "XX"

        is_valid, error = service.validate(tampered)

        assert not is_valid
        assert "Invalid check digits" in error

    def test_validate_invalid_device_type_code(self, service):
        """Test validation fails for unknown device type code."""
        # Create a serial with invalid device type code
        is_valid, error = service.validate("SH01ZZ12345678AB")

        assert not is_valid
        assert "Invalid" in error

    # =========================================================================
    # Parse Tests
    # =========================================================================

    def test_parse_valid_serial(self, service):
        """Test parsing a valid serial number."""
        serials = service.generate(device_type="inverter", hardware_revision="01", count=1)
        info = service.parse(serials[0])

        assert info.is_valid
        assert info.manufacturer_code == "SH"
        assert info.hardware_revision == "01"
        assert info.device_type_code == "IN"
        assert info.device_type == "inverter"
        assert len(info.random_part) == 8
        assert len(info.check_digits) == 2

    def test_parse_invalid_serial(self, service):
        """Test parsing an invalid serial number."""
        info = service.parse("INVALID123456789")

        assert not info.is_valid

    # =========================================================================
    # Format Display Tests
    # =========================================================================

    def test_format_display(self, service):
        """Test formatting serial for display."""
        serials = service.generate(device_type="inverter", count=1)
        formatted = service.format_display(serials[0])

        assert len(formatted) == 19  # 16 chars + 3 dashes
        assert formatted.count("-") == 3
        assert formatted[4] == "-"
        assert formatted[9] == "-"
        assert formatted[14] == "-"

    def test_format_display_removes_existing_dashes(self, service):
        """Test that format_display normalizes input."""
        # Add some dashes/spaces
        serial_with_extras = "SH-01-IN-12-34-56-78-AB"
        formatted = service.format_display(serial_with_extras)

        # Should have exactly 3 dashes at correct positions
        assert formatted.count("-") == 3

    # =========================================================================
    # Check Digit Algorithm Tests
    # =========================================================================

    def test_check_digits_change_on_modification(self, service):
        """Test that any modification invalidates check digits."""
        serials = service.generate(device_type="inverter", count=1)
        original = serials[0]

        # Modify one character in the random part
        modified = original[:10] + ("A" if original[10] != "A" else "B") + original[11:]

        is_valid, _ = service.validate(modified)
        assert not is_valid

    def test_check_digits_deterministic(self, service):
        """Test that check digits are deterministic."""
        base = "SH01IN12345678"

        check1 = service._calculate_check_digits(base)
        check2 = service._calculate_check_digits(base)

        assert check1 == check2

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_case_insensitive_validation(self, service):
        """Test that validation is case insensitive."""
        serials = service.generate(device_type="inverter", count=1)

        is_valid_upper, _ = service.validate(serials[0].upper())
        is_valid_lower, _ = service.validate(serials[0].lower())

        assert is_valid_upper
        assert is_valid_lower

    def test_specific_serial_validation(self, service):
        """Test validation of the specific serial embedded in ESP32 config."""
        # This is the serial we embedded in the ESP32 datalogger config
        test_serial = "SH01IN9A423V4CU0"

        is_valid, error = service.validate(test_serial)

        assert is_valid, f"Test serial should be valid but got: {error}"

        info = service.parse(test_serial)
        assert info.manufacturer_code == "SH"
        assert info.hardware_revision == "01"
        assert info.device_type_code == "IN"
        assert info.device_type == "inverter"
