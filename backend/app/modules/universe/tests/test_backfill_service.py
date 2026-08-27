"""
Tests for backfill_service.py — pure logic functions only.

No DB access, no network calls, no MFAPI, no Supabase.

Functions under test:
  - _is_fresh_enough(count, latest_date)
  - _determine_candidates(obs_summary, assets, limit)
"""
import pytest
from datetime import date, timedelta

from app.modules.universe.backfill_service import (
    _is_fresh_enough,
    _determine_candidates,
    SUFFICIENT_OBS_COUNT,
    FRESHNESS_THRESHOLD_DAYS,
    MAX_BATCH_LIMIT,
    DEFAULT_BATCH_LIMIT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _asset(identifier: str, subcategory: str = "flexi_cap") -> dict:
    return {
        "identifier": identifier,
        "asset_name": f"Fund {identifier}",
        "subcategory": subcategory,
    }


def _fresh_date() -> date:
    """A date within FRESHNESS_THRESHOLD_DAYS of today."""
    return date.today() - timedelta(days=FRESHNESS_THRESHOLD_DAYS - 1)


def _stale_date() -> date:
    """A date older than FRESHNESS_THRESHOLD_DAYS."""
    return date.today() - timedelta(days=FRESHNESS_THRESHOLD_DAYS + 1)


# ---------------------------------------------------------------------------
# _is_fresh_enough
# ---------------------------------------------------------------------------

class TestIsFreshEnough:
    def test_sufficient_count_and_fresh_date_returns_true(self):
        """An asset with enough recent obs should be skipped."""
        assert _is_fresh_enough(SUFFICIENT_OBS_COUNT, _fresh_date()) is True

    def test_more_than_sufficient_count_and_fresh_returns_true(self):
        assert _is_fresh_enough(SUFFICIENT_OBS_COUNT * 3, _fresh_date()) is True

    def test_exactly_on_freshness_boundary_returns_true(self):
        """Latest date exactly FRESHNESS_THRESHOLD_DAYS old should still count as fresh."""
        boundary = date.today() - timedelta(days=FRESHNESS_THRESHOLD_DAYS)
        assert _is_fresh_enough(SUFFICIENT_OBS_COUNT, boundary) is True

    def test_one_day_over_boundary_returns_false(self):
        """One day past the threshold should NOT be considered fresh."""
        stale = date.today() - timedelta(days=FRESHNESS_THRESHOLD_DAYS + 1)
        assert _is_fresh_enough(SUFFICIENT_OBS_COUNT, stale) is False

    def test_sufficient_count_but_stale_date_returns_false(self):
        """Enough obs but stale data → asset needs re-fetch."""
        assert _is_fresh_enough(SUFFICIENT_OBS_COUNT, _stale_date()) is False

    def test_fresh_date_but_insufficient_count_returns_false(self):
        """Fresh but not enough obs → still a candidate."""
        assert _is_fresh_enough(SUFFICIENT_OBS_COUNT - 1, _fresh_date()) is False

    def test_zero_count_returns_false(self):
        """No observations at all → definitely a candidate."""
        assert _is_fresh_enough(0, _fresh_date()) is False

    def test_none_latest_date_returns_false(self):
        """No known latest date → should be treated as a candidate."""
        assert _is_fresh_enough(SUFFICIENT_OBS_COUNT, None) is False

    def test_zero_count_none_date_returns_false(self):
        assert _is_fresh_enough(0, None) is False


# ---------------------------------------------------------------------------
# _determine_candidates
# ---------------------------------------------------------------------------

class TestDetermineCandidates:
    def test_empty_asset_list_returns_no_candidates(self):
        candidates, skipped = _determine_candidates({}, [], 10)
        assert candidates == []
        assert skipped == 0

    def test_all_fresh_assets_are_skipped(self):
        """All assets with sufficient fresh obs → no candidates."""
        assets = [_asset("A"), _asset("B"), _asset("C")]
        obs_summary = {
            "A": {"count": SUFFICIENT_OBS_COUNT, "latest": _fresh_date()},
            "B": {"count": SUFFICIENT_OBS_COUNT, "latest": _fresh_date()},
            "C": {"count": SUFFICIENT_OBS_COUNT, "latest": _fresh_date()},
        }
        candidates, skipped = _determine_candidates(obs_summary, assets, 10)
        assert candidates == []
        assert skipped == 3

    def test_all_new_assets_are_candidates(self):
        """Assets with no observations → all are candidates."""
        assets = [_asset("A"), _asset("B"), _asset("C")]
        obs_summary = {}  # no observations at all
        candidates, skipped = _determine_candidates(obs_summary, assets, 10)
        assert len(candidates) == 3
        assert skipped == 0

    def test_limit_caps_candidates(self):
        """Only `limit` candidates should be returned even if more are eligible."""
        assets = [_asset(str(i)) for i in range(20)]
        obs_summary = {}
        candidates, skipped = _determine_candidates(obs_summary, assets, limit=5)
        assert len(candidates) == 5
        assert skipped == 0

    def test_limit_of_one_returns_exactly_one(self):
        assets = [_asset("A"), _asset("B"), _asset("C")]
        obs_summary = {}
        candidates, skipped = _determine_candidates(obs_summary, assets, limit=1)
        assert len(candidates) == 1
        assert candidates[0]["identifier"] == "A"  # first in order

    def test_mixed_fresh_and_stale(self):
        """Some fresh (skipped), some stale/new (candidates)."""
        assets = [_asset("A"), _asset("B"), _asset("C"), _asset("D")]
        obs_summary = {
            "A": {"count": SUFFICIENT_OBS_COUNT, "latest": _fresh_date()},  # skip
            "B": {"count": SUFFICIENT_OBS_COUNT, "latest": _stale_date()},  # candidate
            "C": {"count": 0, "latest": None},                              # candidate
            "D": {"count": SUFFICIENT_OBS_COUNT, "latest": _fresh_date()},  # skip
        }
        candidates, skipped = _determine_candidates(obs_summary, assets, limit=10)
        assert skipped == 2
        assert len(candidates) == 2
        candidate_ids = {c["identifier"] for c in candidates}
        assert candidate_ids == {"B", "C"}

    def test_limit_applied_after_skipping(self):
        """Limit applies to candidates, not to total assets processed."""
        assets = [_asset(str(i)) for i in range(10)]
        # First 3 are fresh (skipped), rest are candidates
        obs_summary = {
            str(i): {"count": SUFFICIENT_OBS_COUNT, "latest": _fresh_date()}
            for i in range(3)
        }
        candidates, skipped = _determine_candidates(obs_summary, assets, limit=4)
        assert skipped == 3
        assert len(candidates) == 4  # limit from the 7 eligible

    def test_asset_not_in_obs_summary_is_candidate(self):
        """An identifier absent from obs_summary has 0 obs → candidate."""
        assets = [_asset("NEW")]
        obs_summary = {}  # NEW not present
        candidates, skipped = _determine_candidates(obs_summary, assets, limit=10)
        assert len(candidates) == 1
        assert candidates[0]["identifier"] == "NEW"

    def test_order_is_preserved(self):
        """Candidates appear in the same order as the input asset list."""
        assets = [_asset("Z"), _asset("M"), _asset("A")]
        obs_summary = {}
        candidates, _ = _determine_candidates(obs_summary, assets, limit=10)
        assert [c["identifier"] for c in candidates] == ["Z", "M", "A"]

    def test_insufficient_obs_count_but_fresh_date_is_candidate(self):
        """count < SUFFICIENT even with fresh date → candidate."""
        assets = [_asset("X")]
        obs_summary = {"X": {"count": SUFFICIENT_OBS_COUNT - 1, "latest": _fresh_date()}}
        candidates, skipped = _determine_candidates(obs_summary, assets, limit=10)
        assert len(candidates) == 1
        assert skipped == 0


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------

class TestConstants:
    def test_sufficient_obs_count_is_positive(self):
        assert SUFFICIENT_OBS_COUNT > 0

    def test_freshness_threshold_is_positive(self):
        assert FRESHNESS_THRESHOLD_DAYS > 0

    def test_max_batch_limit_greater_than_default(self):
        assert MAX_BATCH_LIMIT >= DEFAULT_BATCH_LIMIT

    def test_default_batch_limit_is_conservative(self):
        """Default limit should be small to prevent accidental bulk fetches."""
        assert DEFAULT_BATCH_LIMIT <= 20
