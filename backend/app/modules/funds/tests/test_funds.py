from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

FAKE_CACHE_ROW = {
    "scheme_code": "100001",
    "scheme_name": "ABC Large Cap Fund - Direct Plan-Growth",
    "category": "largecap",
    "category_raw": "Equity Scheme - Large Cap Fund",
    "latest_nav": 150.25,
    "nav_date": "09-Aug-2026",
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


class TestListFunds:
    def test_rejects_invalid_category(self):
        res = client.get("/api/v1/funds", params={"category": "smallcap"})
        assert res.status_code == 422

    def test_returns_funds_for_valid_category_fresh_cache(self):
        with patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time",
                   return_value=datetime.now(timezone.utc)), \
             patch("app.modules.funds.repository.FundRepository.get_by_category",
                   return_value=[FAKE_CACHE_ROW]):
            res = client.get("/api/v1/funds", params={"category": "largecap"})
        assert res.status_code == 200
        assert res.json()[0]["scheme_code"] == "100001"

    def test_triggers_refresh_when_cache_is_stale(self):
        stale_time = datetime.now(timezone.utc) - timedelta(hours=48)
        with patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time",
                   return_value=stale_time), \
             patch("app.integrations.amfi.fetch_and_parse_funds", return_value=[FAKE_CACHE_ROW]) as mock_fetch, \
             patch("app.modules.funds.repository.FundRepository.upsert_many") as mock_upsert, \
             patch("app.modules.funds.repository.FundRepository.get_by_category", return_value=[FAKE_CACHE_ROW]):
            res = client.get("/api/v1/funds", params={"category": "largecap"})
        assert res.status_code == 200
        mock_fetch.assert_called_once()
        mock_upsert.assert_called_once()

    def test_falls_back_to_stale_cache_if_refresh_fails_but_data_exists(self):
        stale_time = datetime.now(timezone.utc) - timedelta(hours=48)
        with patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time",
                   return_value=stale_time), \
             patch("app.integrations.amfi.fetch_and_parse_funds", side_effect=Exception("AMFI down")), \
             patch("app.modules.funds.repository.FundRepository.get_by_category", return_value=[FAKE_CACHE_ROW]):
            res = client.get("/api/v1/funds", params={"category": "largecap"})
        assert res.status_code == 200  # degraded gracefully, not a hard failure

    def test_503_when_no_cache_exists_and_refresh_fails(self):
        with patch("app.modules.funds.repository.FundRepository.get_latest_refresh_time", return_value=None), \
             patch("app.integrations.amfi.fetch_and_parse_funds", side_effect=Exception("AMFI down")):
            res = client.get("/api/v1/funds", params={"category": "largecap"})
        assert res.status_code == 503


class TestGetFundDetail:
    def test_returns_404_when_not_in_cache(self):
        with patch("app.modules.funds.repository.FundRepository.get_by_scheme_code", return_value=None):
            res = client.get("/api/v1/funds/999999")
        assert res.status_code == 404

    def test_includes_historical_nav_when_mfapi_succeeds(self):
        with patch("app.modules.funds.repository.FundRepository.get_by_scheme_code", return_value=FAKE_CACHE_ROW), \
             patch("app.integrations.mfapi.fetch_historical_nav", return_value=[{"date": "01-01-2026", "nav": 145.0}]):
            res = client.get("/api/v1/funds/100001")
        assert res.status_code == 200
        assert res.json()["historical_nav_available"] is True
        assert len(res.json()["historical_nav"]) == 1

    def test_degrades_gracefully_when_mfapi_fails(self):
        with patch("app.modules.funds.repository.FundRepository.get_by_scheme_code", return_value=FAKE_CACHE_ROW), \
             patch("app.integrations.mfapi.fetch_historical_nav", side_effect=Exception("MFAPI down")):
            res = client.get("/api/v1/funds/100001")
        assert res.status_code == 200  # still returns the fund, just without history
        assert res.json()["historical_nav_available"] is False