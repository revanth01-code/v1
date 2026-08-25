from app.integrations.amfi import normalize_category, parse_navall, _is_direct_growth_plan

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