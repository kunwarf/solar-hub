"""
Unit tests for dependency injection providers.

Tests the new get_telemetry_sync_service() provider.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from system_a.app.application.services.telemetry_sync_service import TelemetrySyncService
from system_a.app.infrastructure.database.repositories.telemetry_repository import (
    SQLAlchemyTelemetryRepository,
)


class TestGetTelemetrySyncService:
    """Tests for get_telemetry_sync_service dependency provider."""

    def test_creates_sync_service_with_correct_dependencies(self):
        """get_telemetry_sync_service should create service with all required deps."""
        mock_session = MagicMock()
        mock_uow = MagicMock()
        mock_uow._session = mock_session
        mock_uow.sites = MagicMock()
        mock_uow.devices = MagicMock()

        mock_client = MagicMock()

        from system_a.app.api.dependencies import get_telemetry_sync_service

        # Call the DI provider directly (without FastAPI's Depends resolution)
        # This tests the wiring logic
        with patch(
            "system_a.app.api.dependencies.SQLAlchemyTelemetryRepository"
        ) as MockRepo:
            mock_repo_instance = MagicMock(spec=SQLAlchemyTelemetryRepository)
            MockRepo.return_value = mock_repo_instance

            service = get_telemetry_sync_service(
                uow=mock_uow,
                system_b_client=mock_client,
            )

            assert isinstance(service, TelemetrySyncService)
            MockRepo.assert_called_once_with(mock_session)

    def test_sync_service_uses_uow_session(self):
        """Sync service should use the UoW's session for the telemetry repo."""
        mock_session = MagicMock()
        mock_uow = MagicMock()
        mock_uow._session = mock_session
        mock_uow.sites = MagicMock()
        mock_uow.devices = MagicMock()

        mock_client = MagicMock()

        from system_a.app.api.dependencies import get_telemetry_sync_service

        with patch(
            "system_a.app.api.dependencies.SQLAlchemyTelemetryRepository"
        ) as MockRepo:
            service = get_telemetry_sync_service(
                uow=mock_uow,
                system_b_client=mock_client,
            )

            # Verify the session passed to repo is from the UoW
            MockRepo.assert_called_once_with(mock_session)
            # Verify the service received the correct repos
            assert service._site_repo is mock_uow.sites
            assert service._device_repo is mock_uow.devices
