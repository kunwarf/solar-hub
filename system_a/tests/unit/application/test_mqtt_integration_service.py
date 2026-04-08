"""
Unit tests for MqttIntegrationService.

All external dependencies (UoW, MosquittoAdminClient) are mocked so
these tests run without a database or MQTT broker.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.application.services.mqtt_integration_service import (
    MqttIntegrationService,
    MqttIntegrationResult,
    PasswordRotationResult,
)
from app.domain.entities.mqtt_integration import (
    MqttIntegration,
    MqttIntegrationDevice,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mosquitto_client():
    client = AsyncMock()
    client.create_user = AsyncMock()
    client.delete_user = AsyncMock()
    client.update_password = AsyncMock()
    return client


@pytest.fixture
def password_hasher():
    hasher = MagicMock()
    hasher.hash = lambda pw: f"bcrypt::{pw}"
    return hasher


@pytest.fixture
def service(mosquitto_client, password_hasher):
    return MqttIntegrationService(
        mosquitto_client=mosquitto_client,
        password_hasher=password_hasher,
        broker_public_host="mqtt.example.com",
        broker_public_port=8883,
    )


def make_uow(*, existing_integration=None, add_returns=None):
    """Build a mock UoW with common defaults."""
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.close = AsyncMock()

    uow.mqtt_integrations = AsyncMock()
    uow.mqtt_integrations.get_by_user_id = AsyncMock(return_value=existing_integration)
    if add_returns is None:
        add_returns = existing_integration
    uow.mqtt_integrations.add = AsyncMock(return_value=add_returns)
    uow.mqtt_integrations.update = AsyncMock(side_effect=lambda e: e)
    uow.mqtt_integrations.delete = AsyncMock(return_value=True)

    uow.mqtt_integration_devices = AsyncMock()
    uow.mqtt_integration_devices.get_by_integration_id = AsyncMock(return_value=[])
    uow.mqtt_integration_devices.get_by_integration_and_device = AsyncMock(return_value=None)
    uow.mqtt_integration_devices.add = AsyncMock(side_effect=lambda e: e)

    uow.users = AsyncMock()
    uow.organizations = AsyncMock()
    uow.organizations.get_by_member_id = AsyncMock(return_value=[])
    uow.sites = AsyncMock()
    uow.devices = AsyncMock()

    return uow


# ---------------------------------------------------------------------------
# TestCreateIntegration
# ---------------------------------------------------------------------------

class TestCreateIntegration:
    @pytest.mark.asyncio
    async def test_creates_integration_successfully(self, service, mosquitto_client):
        user_id = uuid4()
        saved = MqttIntegration(
            user_id=user_id, ha_username="sh_abc123", password_hash="bcrypt::pw"
        )
        uow = make_uow(existing_integration=None, add_returns=saved)

        result = await service.create_integration(user_id, uow)

        assert isinstance(result, MqttIntegrationResult)
        assert result.ha_username.startswith("sh_")
        assert len(result.ha_username) == 15  # "sh_" + 12 hex chars (token_hex(6) = 6 bytes = 12 hex digits)
        assert result.broker_host == "mqtt.example.com"
        assert result.broker_port == 8883

    @pytest.mark.asyncio
    async def test_password_is_not_hash(self, service, mosquitto_client):
        user_id = uuid4()
        saved = MqttIntegration(
            user_id=user_id, ha_username="sh_abc123", password_hash="bcrypt::pw"
        )
        uow = make_uow(existing_integration=None, add_returns=saved)

        result = await service.create_integration(user_id, uow)

        assert not result.password.startswith("bcrypt::")
        assert len(result.password) > 16

    @pytest.mark.asyncio
    async def test_mosquitto_called_before_db(self, service, mosquitto_client):
        user_id = uuid4()
        call_order = []

        async def mock_create_user(username, password):
            call_order.append("mosquitto")

        async def mock_add(entity):
            call_order.append("db")
            return entity

        mosquitto_client.create_user = mock_create_user
        saved = MqttIntegration(
            user_id=user_id, ha_username="sh_abc123", password_hash="bcrypt::pw"
        )
        uow = make_uow(existing_integration=None, add_returns=saved)
        uow.mqtt_integrations.add = mock_add

        await service.create_integration(user_id, uow)

        assert call_order == ["mosquitto", "db"]

    @pytest.mark.asyncio
    async def test_raises_if_integration_exists(self, service):
        user_id = uuid4()
        existing = MqttIntegration(
            user_id=user_id, ha_username="sh_existing", password_hash="hash"
        )
        uow = make_uow(existing_integration=existing)

        with pytest.raises(ValueError, match="already has an MQTT integration"):
            await service.create_integration(user_id, uow)

    @pytest.mark.asyncio
    async def test_db_not_written_on_broker_failure(self, service, mosquitto_client):
        user_id = uuid4()
        mosquitto_client.create_user.side_effect = ConnectionError("broker down")
        uow = make_uow(existing_integration=None)

        with pytest.raises(ConnectionError):
            await service.create_integration(user_id, uow)

        uow.mqtt_integrations.add.assert_not_called()
        uow.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_username_format(self, service, mosquitto_client):
        user_id = uuid4()
        usernames = set()
        for _ in range(10):
            saved = MqttIntegration(
                user_id=user_id, ha_username="sh_abc123", password_hash="hash"
            )
            uow = make_uow(existing_integration=None, add_returns=saved)
            mosquitto_client.create_user.reset_mock()

            result = await service.create_integration(user_id, uow)
            # The username passed to Mosquitto
            call_args = mosquitto_client.create_user.call_args
            username = call_args[0][0]
            assert username.startswith("sh_")
            usernames.add(username)

        # Should generate different usernames each time
        assert len(usernames) > 1


# ---------------------------------------------------------------------------
# TestRotatePassword
# ---------------------------------------------------------------------------

class TestRotatePassword:
    @pytest.mark.asyncio
    async def test_rotates_password(self, service, mosquitto_client):
        user_id = uuid4()
        integration = MqttIntegration(
            user_id=user_id, ha_username="sh_abc123", password_hash="old_hash"
        )
        uow = make_uow(existing_integration=integration)

        result = await service.rotate_password(user_id, uow)

        assert isinstance(result, PasswordRotationResult)
        assert result.ha_username == "sh_abc123"
        assert len(result.password) > 16
        mosquitto_client.update_password.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_if_no_integration(self, service):
        uow = make_uow(existing_integration=None)
        with pytest.raises(ValueError, match="no MQTT integration"):
            await service.rotate_password(uuid4(), uow)

    @pytest.mark.asyncio
    async def test_db_not_updated_on_broker_failure(self, service, mosquitto_client):
        user_id = uuid4()
        integration = MqttIntegration(
            user_id=user_id, ha_username="sh_abc123", password_hash="old_hash"
        )
        uow = make_uow(existing_integration=integration)
        mosquitto_client.update_password.side_effect = ConnectionError("broker down")

        with pytest.raises(ConnectionError):
            await service.rotate_password(user_id, uow)

        uow.mqtt_integrations.update.assert_not_called()


# ---------------------------------------------------------------------------
# TestDeleteIntegration
# ---------------------------------------------------------------------------

class TestDeleteIntegration:
    @pytest.mark.asyncio
    async def test_deletes_integration(self, service, mosquitto_client):
        user_id = uuid4()
        integration = MqttIntegration(
            user_id=user_id, ha_username="sh_abc123", password_hash="hash"
        )
        uow = make_uow(existing_integration=integration)

        await service.delete_integration(user_id, uow)

        mosquitto_client.delete_user.assert_called_once_with("sh_abc123")
        uow.mqtt_integrations.delete.assert_called_once_with(integration.id)
        uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_if_no_integration(self, service):
        uow = make_uow(existing_integration=None)
        with pytest.raises(ValueError, match="no MQTT integration"):
            await service.delete_integration(uuid4(), uow)


# ---------------------------------------------------------------------------
# TestAddDevice
# ---------------------------------------------------------------------------

class TestAddDevice:
    @pytest.mark.asyncio
    async def test_enrolls_device(self, service):
        user_id = uuid4()
        device_id = uuid4()
        site_id = uuid4()
        integration = MqttIntegration(
            user_id=user_id, ha_username="sh_abc123", password_hash="hash"
        )

        device = MagicMock()
        device.id = device_id
        device.site_id = site_id

        site = MagicMock()
        site.id = site_id

        uow = make_uow(existing_integration=integration)
        uow.devices.get_by_id = AsyncMock(return_value=device)
        uow.sites.get_by_id = AsyncMock(return_value=site)

        enrollment = await service.enroll_device(user_id, device_id, uow)

        assert enrollment.device_id == device_id
        assert enrollment.integration_id == integration.id
        uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_if_no_integration(self, service):
        uow = make_uow(existing_integration=None)
        with pytest.raises(ValueError, match="no MQTT integration"):
            await service.enroll_device(uuid4(), uuid4(), uow)

    @pytest.mark.asyncio
    async def test_raises_if_device_not_found(self, service):
        user_id = uuid4()
        integration = MqttIntegration(
            user_id=user_id, ha_username="sh_abc123", password_hash="hash"
        )
        uow = make_uow(existing_integration=integration)
        uow.devices.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await service.enroll_device(user_id, uuid4(), uow)
