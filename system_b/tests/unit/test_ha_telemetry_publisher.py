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
    return AsyncMock()


@pytest.fixture
def publisher(ha_settings, redis_client):
    return HATelemetryPublisher(
        ha_mqtt_settings=ha_settings,
        redis_client=redis_client,
        system_a_url="http://localhost:8000",
        system_a_api_key="test_key",
    )


SAMPLE_TELEMETRY = {
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

SAMPLE_ENROLLMENT = {
    "ha_username": "sh_abc123",
    "device_serial": "SH01GWAT9Q7YDV90",
    "device_name": "Solar Inverter",
    "manufacturer": "Senergy",
    "model": "SE5K",
    "publish_interval_seconds": 30,
}


# ---------------------------------------------------------------------------
# TestBuildStatePayload
# ---------------------------------------------------------------------------

class TestBuildStatePayload:
    def test_extracts_all_metrics(self, publisher):
        state = publisher._build_state_payload(SAMPLE_TELEMETRY)
        assert state["battery_soc_percent"] == 85.5
        assert state["pv_power_w"] == 3500.0
        assert state["grid_power_w"] == -200.0
        assert state["load_power_w"] == 3300.0
        assert state["battery_power_w"] == 0.0
        assert state["inverter_temp_c"] == 42.1
        assert state["grid_frequency_hz"] == 50.01

    def test_handles_missing_sections(self, publisher):
        state = publisher._build_state_payload({})
        assert state["battery_soc_percent"] is None
        assert state["pv_power_w"] is None

    def test_rounds_to_2_decimals(self, publisher):
        telemetry = {"power": {"pv_total_w": 3500.123456}}
        state = publisher._build_state_payload(telemetry)
        assert state["pv_power_w"] == 3500.12

    def test_returns_none_for_non_numeric(self, publisher):
        telemetry = {"battery": {"soc_pct": "bad_value"}}
        state = publisher._build_state_payload(telemetry)
        assert state["battery_soc_percent"] is None


# ---------------------------------------------------------------------------
# TestPublishDeviceState
# ---------------------------------------------------------------------------

class TestPublishDeviceState:
    @pytest.mark.asyncio
    async def test_publishes_state_when_data_available(self, publisher, redis_client):
        redis_client.get = AsyncMock(return_value=json.dumps(SAMPLE_TELEMETRY).encode())
        mqtt_client = AsyncMock()
        publisher._enrollments = [SAMPLE_ENROLLMENT]

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        # Should have published state
        calls = [str(call) for call in mqtt_client.publish.call_args_list]
        state_topic = build_state_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        avail_topic = build_availability_topic("sh_abc123", "SH01GWAT9Q7YDV90")

        published_topics = [
            call.args[0] if call.args else call.kwargs.get("topic", "")
            for call in mqtt_client.publish.call_args_list
        ]
        assert state_topic in published_topics
        assert avail_topic in published_topics

    @pytest.mark.asyncio
    async def test_publishes_offline_when_no_redis_data(self, publisher, redis_client):
        redis_client.get = AsyncMock(return_value=None)
        mqtt_client = AsyncMock()
        publisher._enrollments = [SAMPLE_ENROLLMENT]
        publisher._discovery_published.add("sh_abc123:SH01GWAT9Q7YDV90")

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        avail_topic = build_availability_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        mqtt_client.publish.assert_called_once_with(
            avail_topic, payload=b"offline", retain=False
        )

    @pytest.mark.asyncio
    async def test_publishes_offline_on_corrupt_json(self, publisher, redis_client):
        redis_client.get = AsyncMock(return_value=b"not_valid_json")
        mqtt_client = AsyncMock()
        publisher._discovery_published.add("sh_abc123:SH01GWAT9Q7YDV90")

        await publisher._publish_device(mqtt_client, SAMPLE_ENROLLMENT)

        avail_topic = build_availability_topic("sh_abc123", "SH01GWAT9Q7YDV90")
        published_args = [c[0][0] for c in mqtt_client.publish.call_args_list]
        assert avail_topic in published_args
        # Should publish offline
        for call in mqtt_client.publish.call_args_list:
            if call[0][0] == avail_topic:
                assert call[1]["payload"] == b"offline"

    @pytest.mark.asyncio
    async def test_device_errors_dont_stop_other_devices(self, publisher, redis_client):
        """An error publishing device A should not prevent device B from publishing."""
        redis_client.get = AsyncMock(return_value=json.dumps(SAMPLE_TELEMETRY).encode())
        mqtt_client = AsyncMock()
        mqtt_client.publish = AsyncMock(side_effect=[
            Exception("device A failed"),
            None, None  # device B succeeds
        ])

        enrollment_b = {**SAMPLE_ENROLLMENT, "device_serial": "SH01GWAT9Q7YDV91"}
        publisher._enrollments = [SAMPLE_ENROLLMENT, enrollment_b]
        publisher._discovery_published.update([
            "sh_abc123:SH01GWAT9Q7YDV90",
            "sh_abc123:SH01GWAT9Q7YDV91",
        ])

        # Should not raise
        await publisher._publish_cycle(mqtt_client)


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


# ---------------------------------------------------------------------------
# TestPublishLoop
# ---------------------------------------------------------------------------

class TestPublishLoop:
    @pytest.mark.asyncio
    async def test_discovery_published_only_once(self, publisher, redis_client):
        redis_client.get = AsyncMock(return_value=json.dumps(SAMPLE_TELEMETRY).encode())
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
