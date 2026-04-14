"""
Unit tests for system_b/device_server/settings_schema.py

Verifies that:
1. Every known protocol has a schema.
2. Every schema has the required top-level keys.
3. Every field in every group has at minimum: key, label, type.
4. Enum fields have an 'options' dict.
5. Number fields have min and max defined.
6. Destructive fields are correctly flagged.
7. get_schema() returns None for unknown protocols.
8. powdrive and deye map to the same groups.
"""

import pytest
from system_b.device_server.settings_schema import (
    get_schema,
    SCHEMAS_BY_PROTOCOL,
    POWDRIVE_SCHEMA,
    SENERGY_SCHEMA,
    VOLTRONIC_SCHEMA,
)


KNOWN_PROTOCOLS = [
    "powdrive",
    "deye",
    "senergy",
    "voltronic_pi30",
    "voltronic_pi18",
    "voltronic_pi16",
    "voltronic_pi17",
    "voltronic_pi34",
]


class TestGetSchema:
    def test_returns_none_for_unknown_protocol(self):
        assert get_schema("unknown_xyz") is None

    def test_returns_none_for_empty_string(self):
        assert get_schema("") is None

    @pytest.mark.parametrize("protocol", KNOWN_PROTOCOLS)
    def test_returns_schema_for_known_protocols(self, protocol):
        schema = get_schema(protocol)
        assert schema is not None

    def test_case_insensitive_lookup(self):
        assert get_schema("POWDRIVE") is not None
        assert get_schema("Senergy") is not None

    def test_powdrive_and_deye_share_same_groups(self):
        pd = get_schema("powdrive")
        dy = get_schema("deye")
        # Same group IDs
        assert [g["id"] for g in pd["groups"]] == [g["id"] for g in dy["groups"]]


class TestSchemaStructure:
    @pytest.mark.parametrize("protocol", KNOWN_PROTOCOLS)
    def test_top_level_keys(self, protocol):
        schema = get_schema(protocol)
        assert "version" in schema
        assert "family" in schema
        assert "groups" in schema
        assert isinstance(schema["groups"], list)
        assert len(schema["groups"]) > 0

    @pytest.mark.parametrize("protocol", KNOWN_PROTOCOLS)
    def test_groups_have_required_keys(self, protocol):
        schema = get_schema(protocol)
        for group in schema["groups"]:
            assert "id" in group, f"Group missing 'id' in {protocol}"
            assert "label" in group, f"Group missing 'label' in {protocol}"
            assert "fields" in group, f"Group missing 'fields' in {protocol}"
            assert isinstance(group["fields"], list)

    @pytest.mark.parametrize("protocol", KNOWN_PROTOCOLS)
    def test_fields_have_required_keys(self, protocol):
        schema = get_schema(protocol)
        for group in schema["groups"]:
            for field in group["fields"]:
                assert "key" in field, f"Field missing 'key' in group {group['id']} ({protocol})"
                assert "label" in field, f"Field missing 'label' in group {group['id']} ({protocol})"
                assert "type" in field, f"Field missing 'type' in group {group['id']} ({protocol})"
                assert field["type"] in ("number", "enum", "bool"), \
                    f"Unknown type '{field['type']}' in field {field['key']} ({protocol})"

    @pytest.mark.parametrize("protocol", KNOWN_PROTOCOLS)
    def test_enum_fields_have_options(self, protocol):
        schema = get_schema(protocol)
        for group in schema["groups"]:
            for field in group["fields"]:
                if field["type"] == "enum":
                    assert "options" in field, \
                        f"Enum field '{field['key']}' missing 'options' in {protocol}"
                    assert isinstance(field["options"], dict)
                    assert len(field["options"]) > 0

    @pytest.mark.parametrize("protocol", KNOWN_PROTOCOLS)
    def test_number_fields_have_min_max(self, protocol):
        schema = get_schema(protocol)
        for group in schema["groups"]:
            for field in group["fields"]:
                if field["type"] == "number" and field.get("writable", True):
                    assert "min" in field, \
                        f"Number field '{field['key']}' missing 'min' in {protocol}"
                    assert "max" in field, \
                        f"Number field '{field['key']}' missing 'max' in {protocol}"
                    assert field["min"] <= field["max"], \
                        f"min > max for '{field['key']}' in {protocol}"

    def test_destructive_fields_are_flagged(self):
        """Known destructive fields must have destructive=True."""
        destructive_keys = {
            "powdrive": ["battery_mode_source", "lithium_battery_type", "grid_standard"],
            "senergy": ["battery_type", "grid_standard"],
            "voltronic_pi30": ["restore_factory_defaults"],
        }
        for protocol, keys in destructive_keys.items():
            schema = get_schema(protocol)
            all_fields = {
                f["key"]: f
                for group in schema["groups"]
                for f in group["fields"]
            }
            for key in keys:
                assert key in all_fields, f"Expected field '{key}' in {protocol}"
                assert all_fields[key].get("destructive") is True, \
                    f"Field '{key}' in {protocol} should be marked destructive"


class TestPowdriveSchema:
    def test_has_battery_group(self):
        ids = [g["id"] for g in POWDRIVE_SCHEMA]
        assert "battery" in ids

    def test_has_schedule_group(self):
        ids = [g["id"] for g in POWDRIVE_SCHEMA]
        assert "schedule" in ids

    def test_schedule_group_has_six_programs(self):
        schedule = next(g for g in POWDRIVE_SCHEMA if g["id"] == "schedule")
        prog_time_keys = [f["key"] for f in schedule["fields"] if f["key"].endswith("_time")]
        assert len(prog_time_keys) == 6


class TestSenergySchema:
    def test_battery_group_has_sign_note(self):
        battery = next(g for g in SENERGY_SCHEMA if g["id"] == "battery")
        assert "sign_note" in battery
        assert "discharging" in battery["sign_note"].lower()

    def test_has_work_mode_group(self):
        ids = [g["id"] for g in SENERGY_SCHEMA]
        assert "work_mode" in ids

    def test_voltage_fields_have_scale_01(self):
        """Senergy voltage registers are stored as tenths of a volt."""
        battery = next(g for g in SENERGY_SCHEMA if g["id"] == "battery")
        voltage_fields = [f for f in battery["fields"] if f.get("unit") == "V"]
        # At least bulk and float voltages should have scale=0.1
        scaled = [f for f in voltage_fields if f.get("scale") == 0.1]
        assert len(scaled) >= 2, "Expected at least 2 Senergy voltage fields with scale=0.1"


class TestVoltronicSchema:
    def test_has_output_tab(self):
        ids = [g["id"] for g in VOLTRONIC_SCHEMA]
        assert "output" in ids

    def test_has_system_tab(self):
        ids = [g["id"] for g in VOLTRONIC_SCHEMA]
        assert "system" in ids

    def test_restore_factory_defaults_is_destructive(self):
        system_group = next(g for g in VOLTRONIC_SCHEMA if g["id"] == "system")
        factory = next(
            (f for f in system_group["fields"] if "factory" in f["key"].lower()), None
        )
        assert factory is not None
        assert factory.get("destructive") is True
