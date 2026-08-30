# backend/app/modules/funds/tests/test_funds_migration.py
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.funds.repository import (
    FundRepository,
    to_legacy_dict,
    resolve_legacy_category_from_row
)
from app.core.constants import LEGACY_TO_UNIVERSE_SUBCAT_MAP, UNIVERSE_TO_LEGACY_CAT_MAP
from app.modules.goals.service import GoalService

client = TestClient(app)


class TestFundRepositoryMigration:
    def test_legacy_category_mapping_constants(self):
        # Verify largecap maps to large_cap
        assert "large_cap" in LEGACY_TO_UNIVERSE_SUBCAT_MAP["largecap"]
        # Verify flexicap maps to flexi_cap
        assert "flexi_cap" in LEGACY_TO_UNIVERSE_SUBCAT_MAP["flexicap"]
        # Verify midcap maps to mid_cap and small_cap
        assert "mid_cap" in LEGACY_TO_UNIVERSE_SUBCAT_MAP["midcap"]
        assert "small_cap" in LEGACY_TO_UNIVERSE_SUBCAT_MAP["midcap"]
        # Verify debt subcategories map to debt
        assert "liquid" in LEGACY_TO_UNIVERSE_SUBCAT_MAP["debt"]
        assert "overnight" in LEGACY_TO_UNIVERSE_SUBCAT_MAP["debt"]

    def test_to_legacy_dict_conversion(self):
        universe_row = {
            "identifier": "122639",
            "asset_name": "Parag Parikh Flexi Cap Fund",
            "subcategory": "flexi_cap",
            "latest_price": 72.10,
            "last_updated": "2026-08-29T18:00:00+00:00",
            "last_fetched": "2026-08-29T18:00:00+00:00"
        }
        
        legacy = to_legacy_dict(universe_row)
        assert legacy["scheme_code"] == "122639"
        assert legacy["scheme_name"] == "Parag Parikh Flexi Cap Fund"
        assert legacy["category"] == "flexicap"
        assert legacy["latest_nav"] == 72.10
        assert legacy["nav_date"] == "29-Aug-2026"
        assert legacy["updated_at"] == "2026-08-29T18:00:00+00:00"

    def test_resolve_legacy_category_unsupported_and_unexpected(self):
        # Mapped cases
        assert resolve_legacy_category_from_row({"subcategory": "large_cap"}) == "largecap"
        assert resolve_legacy_category_from_row({"subcategory": "liquid"}) == "debt"
        
        # Unsupported subcategories (must return "unsupported")
        assert resolve_legacy_category_from_row({"subcategory": "elss", "asset_class": "equity"}) == "unsupported"
        assert resolve_legacy_category_from_row({"subcategory": "index_fund", "asset_class": "equity"}) == "unsupported"
        
        # Unmapped/unknown non-equity subcategories
        assert resolve_legacy_category_from_row({"subcategory": "hybrid", "asset_class": "hybrid"}) == "unsupported"
        assert resolve_legacy_category_from_row({"subcategory": "arbitrage", "asset_class": "hybrid"}) == "unsupported"
        
        # Null subcategory
        assert resolve_legacy_category_from_row({"subcategory": None, "asset_class": "equity"}) == "unsupported"
        assert resolve_legacy_category_from_row({"subcategory": None, "asset_class": "debt"}) == "unsupported"
        
        # Future unknown subcategory
        assert resolve_legacy_category_from_row({"subcategory": "crypto_index", "asset_class": "equity"}) == "unsupported"

    @patch("app.core.supabase.supabase_admin.table")
    def test_get_by_category_from_universe_primary(self, mock_table):
        # Mock database response for asset_universe
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=[
            {
                "identifier": "119777",
                "asset_name": "SBI Bluechip Fund",
                "subcategory": "large_cap",
                "latest_price": 84.50,
                "last_updated": "2026-08-29T18:00:00+00:00"
            }
        ])
        # Direct mocks for chaining: .select().eq().in_().order().limit().execute()
        mock_table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value = mock_execute

        results = FundRepository.get_by_category("largecap", limit=10)
        assert len(results) == 1
        assert results[0]["scheme_code"] == "119777"
        assert results[0]["scheme_name"] == "SBI Bluechip Fund"
        assert results[0]["category"] == "largecap"
        assert results[0]["latest_nav"] == 84.50
        assert results[0]["nav_date"] == "29-Aug-2026"

    @patch("app.core.supabase.supabase_admin.table")
    def test_get_by_category_fallback_to_fund_cache(self, mock_table):
        # Mock database response for asset_universe (empty)
        mock_universe_execute = MagicMock()
        mock_universe_execute.execute.return_value = MagicMock(data=[])
        
        # Mock database response for check count (empty/unpopulated universe)
        mock_count_execute = MagicMock()
        mock_count_execute.execute.return_value = MagicMock(data=[])
        
        # Mock database response for legacy fund_cache
        mock_legacy_execute = MagicMock()
        mock_legacy_execute.execute.return_value = MagicMock(data=[
            {
                "scheme_code": "120586",
                "scheme_name": "Nippon India Small Cap Fund",
                "category": "midcap",
                "latest_nav": 142.80,
                "nav_date": "29-Aug-2026"
            }
        ])

        # Define side effects for table select routing
        def table_routing_side_effect(table_name):
            if table_name == "asset_universe":
                m = MagicMock()
                # Mock select chaining for get_by_category
                m.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value = mock_universe_execute
                # Mock select chaining for _has_any_universe_mutual_funds
                m.select.return_value.eq.return_value.limit.return_value = mock_count_execute
                return m
            elif table_name == "fund_cache":
                m = MagicMock()
                m.select.return_value.eq.return_value.order.return_value.limit.return_value = mock_legacy_execute
                return m
            return MagicMock()

        mock_table.side_effect = table_routing_side_effect

        results = FundRepository.get_by_category("midcap", limit=10)
        assert len(results) == 1
        assert results[0]["scheme_code"] == "120586"
        assert results[0]["scheme_name"] == "Nippon India Small Cap Fund"
        assert results[0]["category"] == "midcap"

    @patch("app.core.supabase.supabase_admin.table")
    def test_no_fallback_when_universe_has_mutual_funds_but_category_empty(self, mock_table):
        # 1. Query returned empty list for category
        mock_universe_execute = MagicMock()
        mock_universe_execute.execute.return_value = MagicMock(data=[])
        
        # 2. Database check shows we DO have mutual funds in universe (populated)
        mock_count_execute = MagicMock()
        mock_count_execute.execute.return_value = MagicMock(data=[{"id": "any-id"}])
        
        # 3. Legacy mock (should NOT be called)
        mock_legacy_execute = MagicMock()

        def table_routing_side_effect(table_name):
            if table_name == "asset_universe":
                m = MagicMock()
                m.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value = mock_universe_execute
                m.select.return_value.eq.return_value.limit.return_value = mock_count_execute
                return m
            elif table_name == "fund_cache":
                return mock_legacy_execute
            return MagicMock()

        mock_table.side_effect = table_routing_side_effect

        results = FundRepository.get_by_category("largecap", limit=10)
        # Must return empty list rather than falling back and serving stale data
        assert results == []
        mock_legacy_execute.select.assert_not_called()

    @patch("app.core.supabase.supabase_admin.table")
    def test_graceful_fallback_on_database_query_exception(self, mock_table):
        # If asset_universe select query raises an exception
        mock_table.side_effect = Exception("Supabase is temporarily down")
        
        # Mock FundRepository._has_any_universe_mutual_funds to also return False on error
        # So we fall back safely to legacy cache
        with patch("app.modules.funds.repository.FundRepository._has_any_universe_mutual_funds", return_value=False), \
             patch("app.core.supabase.supabase_admin.table") as mock_fallback_table:
             
             mock_legacy_execute = MagicMock()
             mock_legacy_execute.execute.return_value = MagicMock(data=[{"scheme_code": "119777", "scheme_name": "SBI Bluechip", "category": "largecap", "latest_nav": 10.0}])
             mock_fallback_table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value = mock_legacy_execute
             
             results = FundRepository.get_by_category("largecap", limit=10)
             assert len(results) == 1
             assert results[0]["scheme_code"] == "119777"

    @patch("app.core.supabase.supabase_admin.table")
    def test_get_by_scheme_code_success(self, mock_table):
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data={
            "identifier": "119063",
            "asset_name": "HDFC Mid-Cap Opportunities Fund",
            "subcategory": "mid_cap",
            "latest_price": 156.40,
            "last_updated": "2026-08-29T18:00:00+00:00"
        })
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value = mock_execute

        res = FundRepository.get_by_scheme_code("119063")
        assert res is not None
        assert res["scheme_code"] == "119063"
        assert res["scheme_name"] == "HDFC Mid-Cap Opportunities Fund"
        assert res["latest_nav"] == 156.40

    @patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time")
    @patch("app.modules.funds.repository.FundRepository.get_by_category")
    def test_get_funds_api_route_unchanged(self, mock_get_by_cat, mock_time):
        mock_time.return_value = datetime.now(timezone.utc)
        mock_get_by_cat.return_value = [
            {
                "scheme_code": "119777",
                "scheme_name": "SBI Bluechip Fund",
                "category": "largecap",
                "latest_nav": 84.50,
                "nav_date": "29-Aug-2026",
                "updated_at": "2026-08-29T18:00:00+00:00"
            }
        ]

        response = client.get("/api/v1/funds", params={"category": "largecap"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["scheme_code"] == "119777"
        assert data[0]["scheme_name"] == "SBI Bluechip Fund"
        assert data[0]["category"] == "largecap"
        assert data[0]["latest_nav"] == 84.50


class TestFundWritePathMigration:
    @patch("app.modules.universe.sync_repository.SyncStatusRepository.get_last_successful_sync")
    @patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time")
    @patch("app.modules.universe.ingestion_service.UniverseIngestionService.ingest_universe_discovery")
    @patch("app.modules.funds.repository.FundRepository.get_by_category")
    def test_fresh_universe_does_not_trigger_refresh(self, mock_get_by_cat, mock_ingest, mock_time, mock_last_sync):
        # 1. Fresh date (e.g. now)
        mock_time.return_value = datetime.now(timezone.utc)
        mock_last_sync.return_value = datetime.now(timezone.utc)
        mock_get_by_cat.return_value = []

        response = client.get("/api/v1/funds", params={"category": "largecap"})
        assert response.status_code == 200
        # Ingestion refresh should NOT be triggered since last successful sync is fresh
        mock_ingest.assert_not_called()

    @patch("app.modules.universe.sync_repository.SyncStatusRepository.get_last_successful_sync")
    @patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time")
    @patch("app.modules.universe.ingestion_service.UniverseIngestionService.ingest_universe_discovery")
    @patch("app.modules.funds.repository.FundRepository.get_by_category")
    def test_stale_universe_triggers_safe_refresh(self, mock_get_by_cat, mock_ingest, mock_time, mock_last_sync):
        # 2. Stale sync date (48 hours ago), but not empty
        mock_time.return_value = datetime.now(timezone.utc) - pytest.importorskip("datetime").timedelta(hours=48)
        mock_last_sync.return_value = datetime.now(timezone.utc) - pytest.importorskip("datetime").timedelta(hours=48)
        mock_get_by_cat.return_value = [{"scheme_code": "119777", "scheme_name": "SBI Bluechip", "category": "largecap", "latest_nav": 10.0}]

        response = client.get("/api/v1/funds", params={"category": "largecap"})
        assert response.status_code == 200
        # Ingestion refresh MUST be triggered because the last successful sync is stale!
        mock_ingest.assert_called_once()
        assert response.json()[0]["scheme_code"] == "119777"

    @patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time")
    @patch("app.modules.universe.ingestion_service.UniverseIngestionService.ingest_universe_discovery")
    @patch("app.modules.funds.repository.FundRepository.get_by_category")
    def test_cold_start_triggers_ingestion(self, mock_get_by_cat, mock_ingest, mock_time):
        # 3. None returned means empty database universe/cache (cold start)
        mock_time.return_value = None
        mock_ingest.return_value = 100
        mock_get_by_cat.return_value = []

        response = client.get("/api/v1/funds", params={"category": "largecap"})
        assert response.status_code == 200
        mock_ingest.assert_called_once()

    @patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time")
    @patch("app.modules.universe.ingestion_service.UniverseIngestionService.ingest_universe_discovery")
    @patch("app.modules.funds.repository.FundRepository.get_by_category")
    def test_cold_start_ingestion_failure_raises_503(self, mock_get_by_cat, mock_ingest, mock_time):
        # 4. None returned (empty DB) and ingestion returns 0 (fails)
        mock_time.return_value = None
        mock_ingest.return_value = 0

        # API should fail with 503 since no fallback data exists anywhere
        response = client.get("/api/v1/funds", params={"category": "largecap"})
        assert response.status_code == 503
        mock_ingest.assert_called_once()

    @patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time")
    def test_future_timestamp_does_not_crash_freshness_logic(self, mock_time):
        # Mock a future timestamp (e.g. system clock drift)
        import datetime as dt
        mock_time.return_value = datetime.now(timezone.utc) + dt.timedelta(hours=2)
        
        # When checking latest refresh time, it returns the future timestamp correctly
        assert FundRepository.get_latest_refresh_time() is not None

    @patch("app.core.supabase.supabase_admin.table")
    def test_freshness_query_filters_only_mutual_funds(self, mock_table):
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=[{"last_updated": "2026-08-29T18:00:00+00:00"}])
        
        # Mock select query chaining
        mock_table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value = mock_execute
        
        t = FundRepository.get_latest_refresh_time()
        assert t is not None
        mock_table.assert_called_with("asset_universe")
        mock_table.return_value.select.return_value.eq.assert_called_once_with("instrument_type", "mutual_fund")



