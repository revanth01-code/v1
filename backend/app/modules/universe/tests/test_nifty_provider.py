from unittest.mock import patch, MagicMock
from datetime import date
from app.modules.universe.providers.nifty_provider import NiftyIndexProvider, _normalize_date


class TestNormalizeDate:
    def test_converts_niftyindices_date_format(self):
        assert _normalize_date("01-Jan-2020") == "2020-01-01"

    def test_handles_whitespace(self):
        assert _normalize_date(" 15-Aug-2026 ") == "2026-08-15"


class TestFetchIndexHistory:
    def test_returns_empty_list_on_network_failure(self):
        provider = NiftyIndexProvider()
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.side_effect = Exception("network down")
            result = provider.fetch_index_history("NIFTY 100", date(2020, 1, 1), date(2026, 1, 1))
        assert result == []

    def test_parses_valid_response(self):
        provider = NiftyIndexProvider()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "d": '[{"EOD_TIMESTAMP": "01-Jan-2020", "EOD_CLOSE_INDEX_VAL": "12000.50"}, '
                 '{"EOD_TIMESTAMP": "02-Jan-2020", "EOD_CLOSE_INDEX_VAL": "12100.25"}]'
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_client

            result = provider.fetch_index_history("NIFTY 100", date(2020, 1, 1), date(2020, 1, 3))

        assert len(result) == 2
        assert result[0]["observation_date"] == "2020-01-01"
        assert result[0]["close_value"] == 12000.50

    def test_skips_malformed_records(self):
        provider = NiftyIndexProvider()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "d": '[{"EOD_TIMESTAMP": "bad-date", "EOD_CLOSE_INDEX_VAL": "100"}, '
                 '{"EOD_TIMESTAMP": "01-Jan-2020", "EOD_CLOSE_INDEX_VAL": "12000.50"}]'
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_client

            result = provider.fetch_index_history("NIFTY 100", date(2020, 1, 1), date(2020, 1, 3))

        assert len(result) == 1  # malformed row skipped, valid row kept