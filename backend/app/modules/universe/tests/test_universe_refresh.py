# backend/app/modules/universe/tests/test_universe_refresh.py
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.universe.ingestion_service import UniverseIngestionService, LockUnavailableError
from app.modules.universe.sync_repository import SyncStatusRepository
from app.modules.universe.providers.amfi_provider import ProviderAsset

client = TestClient(app)

# The stable advisory lock ID
LOCK_ID = 8877665544


class TestUniverseRefreshAPI:
    def test_missing_admin_key_header_unauthorized(self):
        response = client.post("/api/v1/universe/refresh")
        assert response.status_code in [401, 403]
        
    def test_invalid_admin_key_header_unauthorized(self):
        response = client.post(
            "/api/v1/universe/refresh",
            headers={"x-admin-key": "wrong-secret-key"}
        )
        assert response.status_code in [401, 403]

    @patch("app.modules.universe.ingestion_service.UniverseIngestionService.ingest_universe_discovery")
    def test_valid_admin_key_triggers_refresh_success(self, mock_ingest):
        mock_ingest.return_value = 150
        
        # We query the environment config to get the valid secret key dynamically
        from app.modules.universe.router import ADMIN_API_KEY
        
        response = client.post(
            "/api/v1/universe/refresh",
            headers={"x-admin-key": ADMIN_API_KEY}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["records_processed"] == 150
        assert data["records_failed"] == 0
        mock_ingest.assert_called_once()

    @patch("app.modules.universe.ingestion_service.UniverseIngestionService.ingest_universe_discovery")
    def test_valid_admin_key_already_running(self, mock_ingest):
        mock_ingest.side_effect = LockUnavailableError("Already running")
        
        from app.modules.universe.router import ADMIN_API_KEY
        
        response = client.post(
            "/api/v1/universe/refresh",
            headers={"x-admin-key": ADMIN_API_KEY}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_running"
        mock_ingest.assert_called_once()


class TestAdvisoryLockingAndIngestion:
    @patch("app.modules.universe.providers.amfi_provider.AMFIMutualFundProvider.fetch_assets")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.try_start_sync")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.complete_sync_success")
    @patch("app.core.supabase.supabase_admin.table")
    def test_successful_scheduled_refresh_with_lock(
        self, mock_table, mock_success, mock_try_start, mock_fetch
    ):
        mock_try_start.return_value = "sync-456"
        
        asset = ProviderAsset(
            asset_name="SBI Large Cap Fund",
            asset_class="equity",
            subcategory="large_cap",
            instrument_type="mutual_fund",
            identifier="119777",
            data_source="amfi",
            liquidity="high",
            tax_classification="equity_tax",
            tax_rule_key="in_equity_standard_v1",
            tax_metadata={},
            latest_price=105.5,
            data_status="fresh"
        )
        mock_fetch.return_value = [asset]
        
        mock_prices_execute = MagicMock()
        mock_prices_execute.execute.return_value = MagicMock(data=[])
        mock_upsert_execute = MagicMock()
        mock_upsert_execute.execute.return_value = MagicMock(data=[{"identifier": "119777"}])
        
        mock_table.return_value.select.return_value.execute = mock_prices_execute.execute
        mock_table.return_value.upsert.return_value.execute = mock_upsert_execute.execute

        count = UniverseIngestionService.ingest_universe_discovery()
        assert count == 1
        
        mock_try_start.assert_called_once_with("latest_nav")
        mock_success.assert_called_once()

    @patch("app.modules.universe.sync_repository.SyncStatusRepository.try_start_sync")
    def test_advisory_lock_unavailable_skips_ingestion(self, mock_try_start):
        mock_try_start.return_value = None # Lock held by another process or concurrent run in progress

        with pytest.raises(LockUnavailableError):
            UniverseIngestionService.ingest_universe_discovery()
            
        mock_try_start.assert_called_once_with("latest_nav")

    @patch("app.modules.universe.providers.amfi_provider.AMFIMutualFundProvider.fetch_assets")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.try_start_sync")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.complete_sync_failure")
    def test_provider_failure_marks_sync_failed(
        self, mock_failure, mock_try_start, mock_fetch
    ):
        mock_try_start.return_value = "sync-456"
        mock_fetch.side_effect = Exception("AMFI Network down")

        count = UniverseIngestionService.ingest_universe_discovery()
        assert count == 0
        
        mock_try_start.assert_called_once_with("latest_nav")
        mock_failure.assert_called_once()

