# backend/app/modules/universe/tests/test_sync_status.py
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest

from app.modules.universe.sync_repository import SyncStatusRepository
from app.modules.universe.ingestion_service import UniverseIngestionService
from app.modules.universe.providers.amfi_provider import ProviderAsset

class TestSyncStatusRepository:
    @patch("app.core.supabase.supabase_admin.table")
    def test_start_sync_success(self, mock_table):
        # Setup mocks
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=[{"id": "sync-123"}])
        mock_table.return_value.insert.return_value = mock_execute

        sync_id = SyncStatusRepository.start_sync("latest_nav")
        assert sync_id == "sync-123"
        mock_table.assert_called_once_with("mf_sync_status")
        mock_table.return_value.insert.assert_called_once()
        insert_args = mock_table.return_value.insert.call_args[0][0]
        assert insert_args["sync_type"] == "latest_nav"
        assert insert_args["status"] == "running"

    @patch("app.core.supabase.supabase_admin.table")
    def test_start_sync_failure(self, mock_table):
        mock_table.side_effect = Exception("Supabase connection failed")
        
        # Ingestion/logging failure must be caught and return None rather than raising
        sync_id = SyncStatusRepository.start_sync("latest_nav")
        assert sync_id is None

    @patch("app.core.supabase.supabase_admin.table")
    def test_complete_sync_success(self, mock_table):
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=[{"id": "sync-123", "status": "success"}])
        mock_table.return_value.update.return_value.eq.return_value = mock_execute

        success = SyncStatusRepository.complete_sync_success(
            sync_id="sync-123",
            records_processed=10,
            records_failed=1,
            duration_seconds=5.4
        )
        assert success is True
        mock_table.assert_called_once_with("mf_sync_status")
        update_args = mock_table.return_value.update.call_args[0][0]
        assert update_args["status"] == "success"
        assert update_args["records_processed"] == 10
        assert update_args["records_failed"] == 1
        assert update_args["duration_seconds"] == 5.4
        assert "last_successful_sync" in update_args

    @patch("app.core.supabase.supabase_admin.table")
    def test_complete_sync_failure(self, mock_table):
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=[{"id": "sync-123", "status": "failed"}])
        mock_table.return_value.update.return_value.eq.return_value = mock_execute

        success = SyncStatusRepository.complete_sync_failure(
            sync_id="sync-123",
            error_message="AMFI Timeout occurred",
            duration_seconds=2.1
        )
        assert success is True
        update_args = mock_table.return_value.update.call_args[0][0]
        assert update_args["status"] == "failed"
        assert update_args["error_message"] == "AMFI Timeout occurred"
        assert update_args["duration_seconds"] == 2.1

    @patch("app.core.supabase.supabase_admin.table")
    def test_get_last_successful_sync_found(self, mock_table):
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(
            data=[{"last_successful_sync": "2026-08-29T18:00:00+00:00"}]
        )
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value = mock_execute

        ts = SyncStatusRepository.get_last_successful_sync("latest_nav")
        assert ts is not None
        assert ts.year == 2026
        assert ts.month == 8
        assert ts.day == 29

    @patch("app.core.supabase.supabase_admin.table")
    def test_get_last_successful_sync_not_found(self, mock_table):
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=[])
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value = mock_execute

        ts = SyncStatusRepository.get_last_successful_sync("latest_nav")
        assert ts is None


class TestUniverseIngestionSyncIntegration:
    @patch("app.modules.universe.providers.amfi_provider.AMFIMutualFundProvider.fetch_assets")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.try_start_sync")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.complete_sync_success")
    @patch("app.core.supabase.supabase_admin.table")
    def test_ingest_lifecycle_success_calls_tracking(
        self, mock_table, mock_success, mock_try_start, mock_fetch
    ):
        mock_try_start.return_value = "sync-123"
        
        # Setup mock assets
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

        # Setup mock db query responses
        mock_prices_execute = MagicMock()
        mock_prices_execute.execute.return_value = MagicMock(data=[])
        mock_upsert_execute = MagicMock()
        mock_upsert_execute.execute.return_value = MagicMock(data=[{"identifier": "119777"}])
        
        mock_table.return_value.select.return_value.execute = mock_prices_execute.execute
        mock_table.return_value.upsert.return_value.execute = mock_upsert_execute.execute

        # Run ingestion
        count = UniverseIngestionService.ingest_universe_discovery()
        
        assert count == 1
        mock_try_start.assert_called_once_with("latest_nav")
        mock_success.assert_called_once()
        args, kwargs = mock_success.call_args
        assert args[0] == "sync-123"
        assert kwargs["records_processed"] == 1
        assert kwargs["records_failed"] == 0
        assert kwargs["duration_seconds"] >= 0

    @patch("app.modules.universe.providers.amfi_provider.AMFIMutualFundProvider.fetch_assets")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.try_start_sync")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.complete_sync_failure")
    def test_ingest_lifecycle_failure_calls_tracking(
        self, mock_failure, mock_try_start, mock_fetch
    ):
        mock_try_start.return_value = "sync-123"
        mock_fetch.side_effect = Exception("AMFI Network down")

        # Run ingestion (should degrade gracefully and return 0, according to original app specification)
        count = UniverseIngestionService.ingest_universe_discovery()
        
        assert count == 0
        mock_try_start.assert_called_once_with("latest_nav")
        mock_failure.assert_called_once()
        args, kwargs = mock_failure.call_args
        assert args[0] == "sync-123"
        assert "AMFI Network down" in kwargs["error_message"]
        assert kwargs["duration_seconds"] >= 0

    @patch("app.modules.universe.providers.amfi_provider.AMFIMutualFundProvider.fetch_assets")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.try_start_sync")
    def test_ingest_works_when_sync_logging_fails(
        self, mock_try_start, mock_fetch
    ):
        # Database logger throws exception
        mock_try_start.side_effect = Exception("Supabase is down")
        
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

        # Setup mock db query response for ingestion
        with patch("app.core.supabase.supabase_admin.table") as mock_table:
            mock_prices_execute = MagicMock()
            mock_prices_execute.execute.return_value = MagicMock(data=[])
            mock_upsert_execute = MagicMock()
            mock_upsert_execute.execute.return_value = MagicMock(data=[{"identifier": "119777"}])
            mock_table.return_value.select.return_value.execute = mock_prices_execute.execute
            mock_table.return_value.upsert.return_value.execute = mock_upsert_execute.execute
            
            # Run ingestion (must not fail, should succeed and return count)
            count = UniverseIngestionService.ingest_universe_discovery()
            
            assert count == 1

    @patch("app.modules.universe.providers.amfi_provider.AMFIMutualFundProvider.fetch_assets")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.try_start_sync")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.complete_sync_failure")
    def test_ingest_failure_hides_no_original_exceptions(
        self, mock_failure, mock_try_start, mock_fetch
    ):
        mock_try_start.return_value = "sync-123"
        mock_fetch.side_effect = Exception("AMFI Network down")
        
        # complete_sync_failure itself raises a database logging error
        mock_failure.side_effect = Exception("Logging database connection failed")

        # Run ingestion (original provider failure should be logged and return 0, not log error)
        count = UniverseIngestionService.ingest_universe_discovery()
        assert count == 0
        mock_failure.assert_called_once()

    @patch("app.modules.universe.providers.amfi_provider.AMFIMutualFundProvider.fetch_assets")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.try_start_sync")
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.complete_sync_failure")
    @patch("app.core.supabase.supabase_admin.table")
    def test_ingest_unexpected_python_failure_re_raises(
        self, mock_table, mock_failure, mock_try_start, mock_fetch
    ):
        mock_try_start.return_value = "sync-123"
        
        # Simulating None in assets which triggers AttributeError in loop (unexpected error)
        mock_fetch.return_value = [None]
        
        # Setup mock table to return empty list
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=[])
        mock_table.return_value.select.return_value.execute = mock_execute.execute

        # Ingestion must re-raise this AttributeError (unexpected behavior preserved)
        with pytest.raises(AttributeError) as exc_info:
            UniverseIngestionService.ingest_universe_discovery()
            
        assert "'NoneType' object has no attribute 'latest_price'" in str(exc_info.value)
        # Verify sync was logged as failed
        mock_failure.assert_called_once()
        args, kwargs = mock_failure.call_args
        assert args[0] == "sync-123"
        assert "'NoneType' object has no attribute 'latest_price'" in kwargs["error_message"]

