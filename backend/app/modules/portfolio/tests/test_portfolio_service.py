"""
Tests for portfolio/service.py — pure logic helpers only.

Covers _compute_buy, _compute_sell, _to_d, and the validation guard
logic that lives before any I/O.  No DB, no network, no Supabase.

Run from backend/:
    python -m pytest app/modules/portfolio/tests/test_portfolio_service.py -v
"""
from decimal import Decimal
import pytest

from app.modules.portfolio.service import (
    _to_d,
    _compute_buy,
    _compute_sell,
    _holdings_data_status,
    COST_PRECISION,
    BUY_TYPES,
    SELL_TYPES,
)


# ---------------------------------------------------------------------------
# _to_d
# ---------------------------------------------------------------------------

class TestToDecimal:
    def test_converts_int(self):
        assert _to_d(100) == Decimal("100")

    def test_converts_float(self):
        # float("106.666...") via str avoids float imprecision
        result = _to_d(106.6666)
        assert isinstance(result, Decimal)

    def test_converts_string(self):
        assert _to_d("3.14") == Decimal("3.14")

    def test_converts_zero(self):
        assert _to_d(0) == Decimal("0")


# ---------------------------------------------------------------------------
# _compute_buy
# ---------------------------------------------------------------------------

class TestComputeBuy:
    def test_first_purchase(self):
        """Buying into an empty holding."""
        new_qty, new_invested, new_avg = _compute_buy(
            current_qty=Decimal("0"),
            current_invested=Decimal("0"),
            buy_qty=Decimal("10"),
            buy_amount=Decimal("1000"),
        )
        assert new_qty == Decimal("10")
        assert new_invested == Decimal("1000")
        assert new_avg == Decimal("100")

    def test_second_purchase_increases_average(self):
        """Adding units at higher price increases average cost."""
        new_qty, new_invested, new_avg = _compute_buy(
            current_qty=Decimal("10"),
            current_invested=Decimal("1000"),
            buy_qty=Decimal("5"),
            buy_amount=Decimal("600"),
        )
        assert new_qty == Decimal("15")
        assert new_invested == Decimal("1600")
        # 1600 / 15 = 106.666... → quantized to 6dp with ROUND_HALF_UP = 106.666667
        expected_avg = (Decimal("1600") / Decimal("15")).quantize(COST_PRECISION)
        assert new_avg == expected_avg

    def test_buy_preserves_precision(self):
        """Average cost is quantized to COST_PRECISION decimal places."""
        _, _, new_avg = _compute_buy(
            current_qty=Decimal("3"),
            current_invested=Decimal("10"),
            buy_qty=Decimal("0"),   # zero qty added (edge — not a real call but tests rounding)
            buy_amount=Decimal("0"),
        )
        # 10/3 = 3.333333... → quantized
        assert new_avg.as_tuple().exponent >= -6  # at most 6 decimal places

    def test_sip_multiple_additions(self):
        """Simulate 3 SIP installments."""
        qty, inv, avg = Decimal("0"), Decimal("0"), Decimal("0")
        for amount in [Decimal("1000"), Decimal("1000"), Decimal("1000")]:
            qty, inv, avg = _compute_buy(qty, inv, Decimal("10"), amount)
        assert qty == Decimal("30")
        assert inv == Decimal("3000")
        assert avg == Decimal("100")

    def test_fractional_units(self):
        """Mutual funds allow fractional units (e.g., NAV-based allocation)."""
        new_qty, new_invested, new_avg = _compute_buy(
            current_qty=Decimal("2.5"),
            current_invested=Decimal("250"),
            buy_qty=Decimal("1.5"),
            buy_amount=Decimal("180"),
        )
        assert new_qty == Decimal("4.0")
        assert new_invested == Decimal("430")
        expected_avg = (Decimal("430") / Decimal("4.0")).quantize(
            COST_PRECISION
        )
        assert new_avg == expected_avg


# ---------------------------------------------------------------------------
# _compute_sell
# ---------------------------------------------------------------------------

class TestComputeSell:
    def test_partial_sell(self):
        """Selling some units reduces quantity and invested amount."""
        new_qty, new_invested, new_avg, cost_basis = _compute_sell(
            current_qty=Decimal("15"),
            current_invested=Decimal("1600"),
            current_avg_cost=Decimal("106.666667"),
            sell_qty=Decimal("5"),
        )
        assert new_qty == Decimal("10")
        # cost_basis = 106.666667 × 5 = 533.333335 (rounded)
        expected_cb = (Decimal("106.666667") * Decimal("5")).quantize(COST_PRECISION)
        assert cost_basis == expected_cb
        # new_invested = 1600 - cost_basis
        assert new_invested == Decimal("1600") - expected_cb
        # average_cost unchanged for remaining units
        assert new_avg == Decimal("106.666667")

    def test_full_sell_returns_zero_qty(self):
        """Selling everything produces zero quantity."""
        new_qty, new_invested, new_avg, cost_basis = _compute_sell(
            current_qty=Decimal("10"),
            current_invested=Decimal("1000"),
            current_avg_cost=Decimal("100"),
            sell_qty=Decimal("10"),
        )
        assert new_qty == Decimal("0")
        assert cost_basis == Decimal("1000")
        assert new_invested == Decimal("0")

    def test_full_sell_invested_clamps_to_zero(self):
        """Floating point artifacts should not produce negative invested amounts."""
        # Simulate a scenario where rounding might otherwise give -epsilon
        new_qty, new_invested, new_avg, cost_basis = _compute_sell(
            current_qty=Decimal("3"),
            current_invested=Decimal("300.000001"),
            current_avg_cost=Decimal("100"),
            sell_qty=Decimal("3"),
        )
        assert new_qty == Decimal("0")
        assert new_invested >= Decimal("0"), "invested_amount must never go negative"

    def test_cost_basis_stored_for_tax_engine(self):
        """cost_basis = avg_cost × sell_qty (for future tax engine)."""
        _, _, _, cost_basis = _compute_sell(
            current_qty=Decimal("20"),
            current_invested=Decimal("2000"),
            current_avg_cost=Decimal("100"),
            sell_qty=Decimal("7"),
        )
        assert cost_basis == Decimal("700")

    def test_average_cost_unchanged_after_partial_sell(self):
        """Remaining-unit average_cost must equal the pre-sell average_cost."""
        avg_before = Decimal("150.250000")
        _, _, new_avg, _ = _compute_sell(
            current_qty=Decimal("8"),
            current_invested=Decimal("1202"),
            current_avg_cost=avg_before,
            sell_qty=Decimal("3"),
        )
        assert new_avg == avg_before


# ---------------------------------------------------------------------------
# Transaction type sets (sanity)
# ---------------------------------------------------------------------------

class TestTransactionTypeSets:
    def test_buy_types_are_correct(self):
        assert BUY_TYPES == {"buy", "sip"}

    def test_sell_types_are_correct(self):
        assert SELL_TYPES == {"sell", "redeem"}

    def test_no_overlap(self):
        assert BUY_TYPES.isdisjoint(SELL_TYPES)


# ---------------------------------------------------------------------------
# _holdings_data_status  (universe status → holdings constraint-safe value)
# ---------------------------------------------------------------------------

class TestHoldingsDataStatus:
    """Verify that asset_universe.data_status values are correctly translated
    to values allowed by the user_portfolio_holdings CHECK constraint:
        ('verified', 'unverified', 'inactive', 'unavailable')
    """

    def test_fresh_maps_to_verified(self):
        """'fresh' is the pipeline status for assets with current data
        — it should map to 'verified' in the holdings table."""
        assert _holdings_data_status("fresh") == "verified"

    def test_unavailable_maps_to_unavailable(self):
        """'unavailable' is valid in both tables — should pass through unchanged."""
        assert _holdings_data_status("unavailable") == "unavailable"

    def test_none_maps_to_unverified(self):
        """None (missing field) should fall back to the safe default 'unverified'."""
        assert _holdings_data_status(None) == "unverified"

    def test_unknown_string_maps_to_unverified(self):
        """Any unrecognised string should fall back to 'unverified'."""
        assert _holdings_data_status("pending") == "unverified"
        assert _holdings_data_status("stale") == "unverified"
        assert _holdings_data_status("") == "unverified"

    def test_output_always_in_allowed_set(self):
        """Output must always be one of the four DB-allowed values."""
        allowed = {"verified", "unverified", "inactive", "unavailable"}
        for input_val in ["fresh", "unavailable", None, "unknown", "", "stale"]:
            result = _holdings_data_status(input_val)
            assert result in allowed, (
                f"_holdings_data_status({input_val!r}) returned {result!r}, "
                f"which is not in the DB CHECK constraint set."
            )
