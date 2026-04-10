"""
Unit tests for the HA Telemetry Publisher.

All MQTT and Redis calls are mocked.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Any, Dict

from system_b.device_server.ha.publisher import HATelemetryPublisher
from system_b.device_server.ha.discovery import (
    build_state_topic,
    build_availability_topic,
    build_discovery_topic,
    build_discovery_payload,
    HA_METRICS,
    INVERTER_METRICS,
    BATTERY_METRICS,
    get_metrics_for_device_type,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ha_settings():
    settings = MagicMock()
    settings.broker_host = "localhost"
    settings.broker_port = 1884
    settings.publisher_username = "solarhub_publisher"
    settings.publisher_password = "test_pw"
    settings.publish_interval = 30
    settings.enrollment_refresh_interval = 300
    return settings


@pytest.fixture
def redis_client():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.incrbyfloat = AsyncMock(return_value=None)
    r.expire = AsyncMock(return_value=True)
    r.mget = AsyncMock(return_value=[b"0.0"] * 6)
    r.setex = AsyncMock(return_value=True)
    r.pipeline = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(execute=AsyncMock())),
        __aexit__=AsyncMock(return_value=False),
        setex=AsyncMock(),
        execute=AsyncMock(),
    ))
    return r


@pytest.fixture
def publisher(ha_settings, redis_client):
    return HATelemetryPublisher(
        ha_mqtt_settings=ha_settings,
        redis_client=redis_client,
        system_a_url="http://localhost:8000",
        system_a_api_key="test_key",
    )


SAMPLE_INVERTER_TELEMETRY = {
    "device_type": "inverter",
    "power": {
        "pv_total_w": 3500.0,
        "grid_w": -200.0,
        "load_w": 3300.0,
        "battery_w": 0.0,
    },
    "battery": {
        "soc_pct": 85.5,
        "voltage_v": 52.4,
    },
    "energy_today": {
        "pv_kwh": 12.3,
        "grid_import_kwh": 0.5,
        "load_kwh": 11.8,
    },
    "energy_total": {
        "pv_kwh": 9000.0,
        "grid_import_kwh": 500.0,
        "grid_export_kwh": 300.0,
        "battery_charge_kwh": 1000.0,
        "battery_discharge_kwh": 950.0,
        "load_kwh": 8500.0,
    },
    "temperatures": {
        "inverter_c": 42.1,
        "battery_c": 28.7,
    },
    "grid": {
        "frequency_hz": 50.01,
        "voltage_v": 229.8,
    },
    "raw": {},
}

SAMPLE_BATTERY_TELEMETRY = {
    "device_type": "battery",
    "battery": {
        "soc_pct": 90.0,
        "voltage_v": 54.0,
        "current_a": 10.0,
        "soh_pct": 98.0,
        "cycle_count": 50,
    },
    "power": {"battery_w": 540.0},
    "temperatures": {"battery_c": 30.0},
    "raw": {},
}

SAMPLE_ENROLLMENT = {
    "ha_username": "sh_abc123",
    "device_serial": "SH01GWAT9Q7YDV90",
    "device_name": "Solar Inverter",
    "manufacturer": "Senergy",
    "model": "SE5K",
    "publish_interval_seconds": 30,
}

BATTERY_ENROLLMENT = {
    "ha_username": "sh_abc123",
    "device_serial": "SH01BATT0001",
    "device_name": "JK BMS",
    "manufacturer": "JK",
    "model": "BMS-200A",
    "publish_interval_seconds": 30,
}


# ---------------------------------------------------------------------------
# TestBuildStatePayload
# ---------------------------------------------------------------------------

class TestBuildStatePayload:
    def test_extracts_all_power_metrics(self, publisher):
        state = publisher._build_state_payload(SAMPLE_INVERTER_TELEMETRY)
        assert state["battery_soc_percent"] == 85.5
        assert state["pv_power_w"] == 3500.0
        assert state["grid_power_w"] == -200.0
        assert state["load_power_w"] == 3300.0
        assert state["battery_power_w"] == 0.0
        assert state["inverter_temp_c"] == 42.1
        assert state["grid_frequency_hz"] == 50.01

    def test_extracts_energy_today(self, publisher):
        state = publisher._build_state_payload(SAMPLE_INVERTER_TELEMETRY)
        assert state["pv_energy_today_kwh"] == 12.3
        assert state["grid_import_today_kwh"] == 0.5
        assert state["load_energy_today_kwh"] == 11.8

    def test_extracts_energy_total(self, publisher):
        state = publisher._build_state_payload(SAMPLE_INVERTER_TELEMETRY)
        assert state["pv_energy_total_kwh"] == 9000.0
        assert state["grid_import_total_kwh"] == 500.0
        assert state["battery_charge_total_kwh"] == 1000.0

    def test_handles_missing_sections(self, publisher):
        state = publisher._build_state_payload({})
        assert state["battery_soc_percent"] is None
        assert state["pv_power_w"] is None
        assert state["pv_energy_total_kwh"] is None

    def test_rounds_to_2_decimals(self, publisher):
        telemetry = {"power": {"pv_total_w": 3500.123456}}
        state = publisher._build_state_payload(telemetry)
        assert state["pv_power_w"] == 3500.12

    def test_returns_none_for_non_numeric(self, publisher):
        telemetry = {"battery": {"soc_pct": "bad_value"}}
        state = publisher._build_state_payload(telemetry)
        assert state["battery_soc_percent"] is None

    def test_battery_current_and_soh_extracted(self, publisher):
        state = publisher._build_state_payload(SAMPLE_BATTERY_TELEMETRY)
        assert state["battery_current_a"] == 10.0
        assert state["battery_soh_percent"] == 98.0
        assert state["battery_cycle_count"] == 50


# ---------------------------------------------------------------------------
# TestPublishDeviceState
# ---------------------------------------------------------------------------

class TestPublishDeviceState:
    @pytest.mark.asyncio
    async def test_publishes_state_when_data_available(self, publisher, redis_client):
        redis_client.get = AsyncMock(
            return_value=json.dumps(SAMPLE_INVERTER_TELEMETRY).encode()
        )
        mqtt_client = AsyncMock()

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        state_topic = build_state_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        avail_topic = build_availability_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        published_topics = [
            call.args[0] if call.args else call.kwargs.get("topic", "")
            for call in mqtt_client.publish.call_args_list
        ]
        assert state_topic in published_topics
        assert avail_topic in published_topics

    @pytest.mark.asyncio
    async def test_publishes_offline_when_telemetry_is_stale(self, publisher, redis_client):
        """Telemetry older than 5 minutes should mark device offline even if Redis key exists."""
        stale_telemetry = {
            **SAMPLE_INVERTER_TELEMETRY,
            "timestamp": "2020-01-01T00:00:00+00:00",  # obviously old
        }
        redis_client.get = AsyncMock(return_value=json.dumps(stale_telemetry).encode())
        mqtt_client = AsyncMock()
        publisher._discovery_published["sh_abc123:SH01GWAT9Q7YDV90"] = "inverter"

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        avail_topic = build_availability_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        mqtt_client.publish.assert_called_once_with(
            avail_topic, payload=b"offline", retain=False
        )

    @pytest.mark.asyncio
    async def test_publishes_online_when_telemetry_is_fresh(self, publisher, redis_client):
        """Telemetry with a recent timestamp should publish normally."""
        from datetime import datetime, timezone
        fresh_telemetry = {
            **SAMPLE_INVERTER_TELEMETRY,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        redis_client.get = AsyncMock(return_value=json.dumps(fresh_telemetry).encode())
        mqtt_client = AsyncMock()
        publisher._discovery_published["sh_abc123:SH01GWAT9Q7YDV90"] = "inverter"

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        state_topic = build_state_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        published_topics = [c[0][0] for c in mqtt_client.publish.call_args_list]
        assert state_topic in published_topics

    @pytest.mark.asyncio
    async def test_publishes_offline_when_no_redis_data(self, publisher, redis_client):
        redis_client.get = AsyncMock(return_value=None)
        mqtt_client = AsyncMock()
        # Mark discovery as already published (dict-based)
        publisher._discovery_published["sh_abc123:SH01GWAT9Q7YDV90"] = "inverter"

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        avail_topic = build_availability_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        mqtt_client.publish.assert_called_once_with(
            avail_topic, payload=b"offline", retain=False
        )

    @pytest.mark.asyncio
    async def test_publishes_offline_on_corrupt_json(self, publisher, redis_client):
        redis_client.get = AsyncMock(return_value=b"not_valid_json")
        mqtt_client = AsyncMock()
        publisher._discovery_published["sh_abc123:SH01GWAT9Q7YDV90"] = "inverter"

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        avail_topic = build_availability_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        published_args = [c[0][0] for c in mqtt_client.publish.call_args_list]
        assert avail_topic in published_args
        for call in mqtt_client.publish.call_args_list:
            if call[0][0] == avail_topic:
                assert call[1]["payload"] == b"offline"

    @pytest.mark.asyncio
    async def test_device_errors_dont_stop_other_devices(self, publisher, redis_client):
        """An error publishing device A should not prevent device B from publishing."""
        redis_client.get = AsyncMock(
            return_value=json.dumps(SAMPLE_INVERTER_TELEMETRY).encode()
        )
        mqtt_client = AsyncMock()
        mqtt_client.publish = AsyncMock(side_effect=[
            Exception("device A failed"),
            None, None
        ])

        enrollment_b = {**SAMPLE_ENROLLMENT, "device_serial": "SH01GWAT9Q7YDV91"}
        publisher._enrollments = [SAMPLE_ENROLLMENT, enrollment_b]
        publisher._discovery_published["sh_abc123:SH01GWAT9Q7YDV90"] = "inverter"
        publisher._discovery_published["sh_abc123:SH01GWAT9Q7YDV91"] = "inverter"

        # Should not raise
        await publisher._publish_cycle(mqtt_client)


# ---------------------------------------------------------------------------
# TestDeviceTypeDiscovery
# ---------------------------------------------------------------------------

class TestDeviceTypeDiscovery:
    """Discovery is published with correct sensor set per device_type."""

    def test_inverter_metrics_count(self):
        metrics = get_metrics_for_device_type("inverter")
        assert len(metrics) == len(INVERTER_METRICS)

    def test_battery_metrics_count(self):
        metrics = get_metrics_for_device_type("battery")
        assert len(metrics) == len(BATTERY_METRICS)

    def test_inverter_has_pv_sensors(self):
        metrics = get_metrics_for_device_type("inverter")
        keys = {m["key"] for m in metrics}
        assert "pv_power_w" in keys
        assert "pv_energy_today_kwh" in keys
        assert "pv_energy_total_kwh" in keys

    def test_battery_has_current_and_soh(self):
        metrics = get_metrics_for_device_type("battery")
        keys = {m["key"] for m in metrics}
        assert "battery_current_a" in keys
        assert "battery_soh_percent" in keys
        assert "battery_cycle_count" in keys

    def test_battery_has_no_pv_sensors(self):
        metrics = get_metrics_for_device_type("battery")
        keys = {m["key"] for m in metrics}
        assert "pv_power_w" not in keys
        assert "pv_energy_today_kwh" not in keys

    def test_inverter_has_no_cycle_count(self):
        metrics = get_metrics_for_device_type("inverter")
        keys = {m["key"] for m in metrics}
        assert "battery_cycle_count" not in keys

    @pytest.mark.asyncio
    async def test_discovery_published_for_correct_device_type(self, publisher, redis_client):
        redis_client.get = AsyncMock(
            return_value=json.dumps(SAMPLE_INVERTER_TELEMETRY).encode()
        )
        mqtt_client = AsyncMock()

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        # Discovery includes active metrics + tombstone (empty retained) payloads for stale keys.
        # Check that all INVERTER_METRICS keys have a corresponding discovery publish.
        published_topics = [c[0][0] for c in mqtt_client.publish.call_args_list]
        discovery_topics = set(t for t in published_topics if t.startswith("homeassistant/sensor/"))
        for metric in INVERTER_METRICS:
            expected = build_discovery_topic("sh_abc123", "SH01GWAT9Q7YDV90", metric["key"])
            assert expected in discovery_topics, f"Missing discovery topic for {metric['key']}"

    @pytest.mark.asyncio
    async def test_battery_discovery_uses_battery_metrics(self, publisher, redis_client):
        redis_client.get = AsyncMock(
            return_value=json.dumps(SAMPLE_BATTERY_TELEMETRY).encode()
        )
        mqtt_client = AsyncMock()

        await publisher._publish_device(mqtt_client, BATTERY_ENROLLMENT)

        published_topics = [c[0][0] for c in mqtt_client.publish.call_args_list]
        discovery_topics = [t for t in published_topics if t.startswith("homeassistant/sensor/")]
        assert len(discovery_topics) > 0
        # Battery discovery should include battery_current_a
        current_topic = build_discovery_topic("sh_abc123", "SH01BATT0001", "battery_current_a")
        assert current_topic in discovery_topics

    @pytest.mark.asyncio
    async def test_discovery_republished_when_device_type_changes(self, publisher, redis_client):
        """If device_type changes from unknown→inverter, discovery should re-publish."""
        redis_client.get = AsyncMock(
            return_value=json.dumps(SAMPLE_INVERTER_TELEMETRY).encode()
        )
        mqtt_client = AsyncMock()

        # Simulate previously published as empty string (unknown type)
        publisher._discovery_published["sh_abc123:SH01GWAT9Q7YDV90"] = ""

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        # Should re-publish discovery since device_type changed from "" to "inverter"
        published_topics = [c[0][0] for c in mqtt_client.publish.call_args_list]
        discovery_topics = [t for t in published_topics if t.startswith("homeassistant/sensor/")]
        assert len(discovery_topics) > 0


# ---------------------------------------------------------------------------
# TestHADiscovery
# ---------------------------------------------------------------------------

class TestHADiscovery:
    def test_discovery_topic_format(self):
        topic = build_discovery_topic("sh_abc123", "SH01GWAT9Q7YDV90", "battery_soc_percent")
        assert topic.startswith("homeassistant/sensor/")
        assert "sh_abc123" in topic
        assert "SH01GWAT9Q7YDV90" in topic
        assert topic.endswith("/config")

    def test_discovery_payload_structure(self):
        metric = next(m for m in HA_METRICS if m["key"] == "battery_soc_percent")
        payload = build_discovery_payload(
            ha_username="sh_abc123",
            device_serial="SH01GWAT9Q7YDV90",
            device_name="Solar Inverter",
            manufacturer="Senergy",
            model="SE5K",
            metric=metric,
        )
        assert payload["state_topic"] == build_state_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        assert "battery_soc_percent" in payload["value_template"]
        assert payload["device"]["identifiers"] == ["solarhub_SH01GWAT9Q7YDV90"]
        assert payload["unique_id"] == "solarhub_sh_abc123_SH01GWAT9Q7YDV90_battery_soc_percent"

    def test_cycle_count_has_no_unit(self):
        """battery_cycle_count has unit=None and should not set unit_of_measurement."""
        metric = next(m for m in BATTERY_METRICS if m["key"] == "battery_cycle_count")
        payload = build_discovery_payload(
            ha_username="sh_abc123",
            device_serial="SH01BATT0001",
            device_name="JK BMS",
            manufacturer="JK",
            model="BMS-200A",
            metric=metric,
        )
        assert "unit_of_measurement" not in payload


# ---------------------------------------------------------------------------
# TestPublishLoop
# ---------------------------------------------------------------------------

class TestPublishLoop:
    @pytest.mark.asyncio
    async def test_discovery_published_only_once(self, publisher, redis_client):
        redis_client.get = AsyncMock(
            return_value=json.dumps(SAMPLE_INVERTER_TELEMETRY).encode()
        )
        mqtt_client = AsyncMock()
        publisher._enrollments = [SAMPLE_ENROLLMENT]

        # First cycle — should publish discovery
        await publisher._publish_cycle(mqtt_client)
        first_call_count = mqtt_client.publish.call_count

        mqtt_client.publish.reset_mock()

        # Second cycle — discovery should NOT be re-published
        await publisher._publish_cycle(mqtt_client)
        second_call_count = mqtt_client.publish.call_count

        # Second cycle has fewer publishes (no discovery payloads)
        assert second_call_count < first_call_count

    @pytest.mark.asyncio
    async def test_empty_enrollment_list_publishes_nothing(self, publisher, redis_client):
        mqtt_client = AsyncMock()
        publisher._enrollments = []

        await publisher._publish_cycle(mqtt_client)

        mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_inverter_energy_calculator_called_for_inverter(self, publisher, redis_client):
        """InverterEnergyCalculator.fill_missing_energy should be called for inverter devices."""
        redis_client.get = AsyncMock(
            return_value=json.dumps(SAMPLE_INVERTER_TELEMETRY).encode()
        )
        mqtt_client = AsyncMock()
        publisher._discovery_published["sh_abc123:SH01GWAT9Q7YDV90"] = "inverter"

        with patch.object(
            publisher._inv_energy_calc, "fill_missing_energy", new_callable=AsyncMock
        ) as mock_fill:
            await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        mock_fill.assert_called_once()
        # Check serial is passed correctly
        assert mock_fill.call_args[0][0] == "SH01GWAT9Q7YDV90"

    @pytest.mark.asyncio
    async def test_battery_energy_calculator_called_for_battery(self, publisher, redis_client):
        """BatteryEnergyCalculator.get_energy should be called for battery devices."""
        redis_client.get = AsyncMock(
            return_value=json.dumps(SAMPLE_BATTERY_TELEMETRY).encode()
        )
        mqtt_client = AsyncMock()
        publisher._discovery_published["sh_abc123:SH01BATT0001"] = "battery"

        with patch.object(
            publisher._energy_calc, "get_energy",
            new_callable=AsyncMock,
            return_value=(1.0, 0.5, 100.0, 95.0),
        ) as mock_get:
            await publisher._publish_device(mqtt_client, BATTERY_ENROLLMENT)

        mock_get.assert_called_once()
