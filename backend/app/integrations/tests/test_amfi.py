# backend/app/integrations/tests/test_amfi.py
from unittest.mock import patch, MagicMock
import httpx
import pytest
from app.integrations.amfi import (
    normalize_category,
    parse_navall,
    _is_direct_growth_plan,
    fetch_navall_raw,
    AMFITimeoutError,
    AMFINetworkError,
    AMFIInvalidResponseError,
    AMFIParsingError
)

SAMPLE_NAVALL = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

100001;INF000A01001;-;ABC Large Cap Fund - Direct Plan-Growth;150.25;09-Aug-2026
100002;INF000A01002;-;ABC Large Cap Fund - Regular Plan-Growth;140.10;09-Aug-2026
100003;INF000A01003;-;ABC Large Cap Fund - Direct Plan-IDCW;80.00;09-Aug-2026

Open Ended Schemes(Equity Scheme - Flexi Cap Fund)

100010;INF000B01001;-;XYZ Flexi Cap Fund - Direct Plan-Growth;220.75;09-Aug-2026

Open Ended Schemes(Debt Scheme - Liquid Fund)

100020;INF000C01001;-;PQR Liquid Fund - Direct Plan-Growth;1500.50;09-Aug-2026
"""

SAMPLE_8_COLUMNS = """Scheme Code;ISIN Growth;ISIN Div;Scheme Name;Plan;Option;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

120001;INF000D01001;-;ABC Large Cap Fund;Direct;Growth;165.50;10-Aug-2026
120002;INF000D01002;-;ABC Large Cap Fund;Regular;Growth;155.10;10-Aug-2026
120003;INF000D01003;-;ABC Large Cap Fund;Direct;IDCW;95.00;10-Aug-2026
"""


class TestNormalizeCategory:
    def test_large_cap(self):
        assert normalize_category("Open Ended Schemes(Equity Scheme - Large Cap Fund)") == "largecap"

    def test_flexi_cap(self):
        assert normalize_category("Equity Scheme - Flexi Cap Fund") == "flexicap"

    def test_mid_cap(self):
        assert normalize_category("Equity Scheme - Mid Cap Fund") == "midcap"

    def test_small_cap_also_maps_to_midcap_bucket(self):
        assert normalize_category("Equity Scheme - Small Cap Fund") == "midcap"

    def test_liquid_fund_maps_to_debt(self):
        assert normalize_category("Debt Scheme - Liquid Fund") == "debt"

    def test_unsupported_category_returns_none(self):
        assert normalize_category("Hybrid Scheme - Balanced Advantage Fund") is None


class TestIsDirectGrowthPlan:
    def test_accepts_direct_growth(self):
        assert _is_direct_growth_plan("ABC Fund - Direct Plan-Growth") is True

    def test_rejects_regular_growth(self):
        assert _is_direct_growth_plan("ABC Fund - Regular Plan-Growth") is False

    def test_rejects_direct_idcw(self):
        assert _is_direct_growth_plan("ABC Fund - Direct Plan-IDCW") is False


class TestParseNavall:
    def test_only_includes_direct_growth_plans(self):
        results = parse_navall(SAMPLE_NAVALL)
        scheme_codes = [r["scheme_code"] for r in results]
        assert "100001" in scheme_codes  # Direct Growth — included
        assert "100002" not in scheme_codes  # Regular Growth — excluded
        assert "100003" not in scheme_codes  # Direct IDCW — excluded

    def test_assigns_correct_category_per_section(self):
        results = parse_navall(SAMPLE_NAVALL)
        by_code = {r["scheme_code"]: r for r in results}
        assert by_code["100001"]["category"] == "largecap"
        assert by_code["100010"]["category"] == "flexicap"
        assert by_code["100020"]["category"] == "debt"

    def test_parses_nav_as_float(self):
        results = parse_navall(SAMPLE_NAVALL)
        by_code = {r["scheme_code"]: r for r in results}
        assert by_code["100001"]["latest_nav"] == 150.25

    def test_parses_8_columns_correctly(self):
        # Disable legacy filter to allow full parsing check
        results = parse_navall(SAMPLE_8_COLUMNS, filter_legacy_categories=False)
        scheme_codes = [r["scheme_code"] for r in results]
        assert "120001" in scheme_codes
        assert "120002" not in scheme_codes
        assert "120003" not in scheme_codes
        
        by_code = {r["scheme_code"]: r for r in results}
        assert by_code["120001"]["latest_nav"] == 165.50
        assert by_code["120001"]["plan"] == "Direct"
        assert by_code["120001"]["option"] == "Growth"

    def test_malformed_rows_skipped(self):
        malformed = SAMPLE_NAVALL + "\n100099;INF000;only_three_cols"
        results = parse_navall(malformed)
        scheme_codes = [r["scheme_code"] for r in results]
        assert "100099" not in scheme_codes

    def test_invalid_nav_skipped(self):
        invalid_nav = SAMPLE_NAVALL + "\n100099;INF000;-;XYZ Fund - Direct Plan-Growth;N/A;09-Aug-2026"
        results = parse_navall(invalid_nav)
        scheme_codes = [r["scheme_code"] for r in results]
        assert "100099" not in scheme_codes

    def test_empty_response_raises_parsing_error(self):
        with pytest.raises(AMFIParsingError):
            parse_navall("")

    def test_unsupported_universe_categories_skipped(self):
        # Balanced Advantage Fund is not in resolve_universe_category mapping
        unsupported = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
        
        Open Ended Schemes(Hybrid Scheme - Balanced Advantage Fund)
        
        100099;INF000A01001;-;XYZ Balanced Fund - Direct Plan-Growth;15.25;09-Aug-2026
        """
        results = parse_navall(unsupported, filter_legacy_categories=False)
        assert len(results) == 0


class TestFetchNavallRaw:
    @patch("httpx.get")
    def test_fetch_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Scheme Code;Net Asset Value"
        mock_get.return_value = mock_response

        result = fetch_navall_raw()
        assert result == "Scheme Code;Net Asset Value"

    @patch("time.sleep")
    @patch("httpx.get")
    def test_fetch_timeout_retry_and_fail(self, mock_get, mock_sleep):
        mock_get.side_effect = httpx.TimeoutException("Timeout occurred")

        with pytest.raises(AMFITimeoutError):
            fetch_navall_raw()

        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    @patch("httpx.get")
    def test_fetch_network_error_retry_and_fail(self, mock_get, mock_sleep):
        mock_get.side_effect = httpx.NetworkError("Network down")

        with pytest.raises(AMFINetworkError):
            fetch_navall_raw()

        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    @patch("httpx.get")
    def test_fetch_429_retried_and_fails(self, mock_get, mock_sleep):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with pytest.raises(AMFIInvalidResponseError):
            fetch_navall_raw()

        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    @patch("httpx.get")
    def test_fetch_non_retryable_client_error_aborts(self, mock_get, mock_sleep):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        with pytest.raises(AMFIInvalidResponseError) as exc_info:
            fetch_navall_raw()

        assert "Non-retryable client error" in str(exc_info.value)
        # Should abort immediately without retry
        assert mock_get.call_count == 1
        assert mock_sleep.call_count == 0

    @patch("httpx.get")
    @patch("app.core.config.settings")
    def test_invalid_retry_config_uses_safe_minimum(self, mock_settings, mock_get):
        mock_settings.AMFI_MAX_RETRIES = 0  # Invalid configuration
        mock_settings.AMFI_TIMEOUT_SECONDS = 10.0
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Scheme Code;Net Asset Value"
        mock_get.return_value = mock_response

        # Should execute successfully with a minimum of 1 attempt
        result = fetch_navall_raw()
        assert result == "Scheme Code;Net Asset Value"
        assert mock_get.call_count == 1