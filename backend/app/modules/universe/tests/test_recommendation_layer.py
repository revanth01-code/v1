# backend/app/modules/universe/tests/test_recommendation_layer.py
import pytest
from unittest.mock import patch, MagicMock
from app.modules.universe.recommendation.schemas import UserPreferences
from app.modules.universe.recommendation.recommendation_service import RecommendationService
from app.modules.universe.recommendation.compatibility import calculate_preference_match
from app.modules.universe.recommendation.explanation_service import generate_reasons
from app.modules.tax.tax_service import TaxProfile

# Mock data simulating Supabase query response
MOCK_SUPABASE_FUNDS = [
    {
        "identifier": "119777",
        "asset_name": "SBI Large Cap Fund",
        "subcategory": "large_cap",
        "instrument_type": "mutual_fund",
        "asset_class": "equity",
        "asset_metrics": [
            {
                "data_confidence": "HIGH",
                "recommendation_score": 92.5,
                "peer_reliability": "HIGH",
                "metrics": {"returns": {"5y": 0.15}}
            }
        ]
    },
    {
        "identifier": "119778",
        "asset_name": "HDFC Large Cap Fund",
        "subcategory": "large_cap",
        "instrument_type": "mutual_fund",
        "asset_class": "equity",
        "asset_metrics": [
            {
                "data_confidence": "MEDIUM",
                "recommendation_score": 85.0,
                "peer_reliability": "LOW",
                "metrics": {"returns": {"5y": 0.12}}
            }
        ]
    },
    {
        "identifier": "119779",
        "asset_name": "Insufficient Data Fund",
        "subcategory": "large_cap",
        "instrument_type": "mutual_fund",
        "asset_class": "equity",
        "asset_metrics": [
            {
                "data_confidence": "INSUFFICIENT",
                "recommendation_score": 95.0,
                "peer_reliability": "HIGH",
                "metrics": {}
            }
        ]
    },
    {
        "identifier": "119780",
        "asset_name": "No Score Fund",
        "subcategory": "large_cap",
        "instrument_type": "mutual_fund",
        "asset_class": "equity",
        "asset_metrics": [
            {
                "data_confidence": "HIGH",
                "recommendation_score": None,
                "peer_reliability": "HIGH",
                "metrics": {}
            }
        ]
    },
    {
        "identifier": "119781",
        "asset_name": "Low Confidence Fund",
        "subcategory": "large_cap",
        "instrument_type": "mutual_fund",
        "asset_class": "equity",
        "asset_metrics": [
            {
                "data_confidence": "LOW",
                "recommendation_score": 75.0,
                "peer_reliability": "HIGH",
                "metrics": {}
            }
        ]
    },
    {
        "identifier": "119782",
        "asset_name": "Axis ELSS Tax Saver Fund",
        "subcategory": "elss",
        "instrument_type": "mutual_fund",
        "asset_class": "equity",
        "asset_metrics": [
            {
                "data_confidence": "HIGH",
                "recommendation_score": 88.0,
                "peer_reliability": "HIGH",
                "metrics": {}
            }
        ]
    },
    {
        "identifier": "119783",
        "asset_name": "Equal Score B Fund",
        "subcategory": "large_cap",
        "instrument_type": "mutual_fund",
        "asset_class": "equity",
        "asset_metrics": [
            {
                "data_confidence": "HIGH",
                "recommendation_score": 92.5,
                "peer_reliability": "HIGH",
                "metrics": {}
            }
        ]
    }
]


@pytest.fixture
def mock_supabase_select():
    with patch("app.core.supabase.supabase_admin.table") as mock_table:
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=MOCK_SUPABASE_FUNDS)
        mock_table.return_value.select.return_value.eq.return_value.in_.return_value = mock_execute
        yield mock_table


def test_no_preferences_still_returns_recommendations(mock_supabase_select):
    mix = {"largecap": 100}
    res = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=None)
    assert len(res) == 1
    assert res[0]["category"] == "largecap"
    assert len(res[0]["funds"]) > 0
    # Every preference match score defaults to 100
    for f in res[0]["funds"]:
        assert f["preference_match_score"] == 100.0


def test_insufficient_confidence_funds_are_excluded(mock_supabase_select):
    mix = {"largecap": 100}
    res = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=None)
    funds = res[0]["funds"]
    # Check that "Insufficient Data Fund" (identifier 119779) is not included
    identifiers = [f["identifier"] for f in funds]
    assert "119779" not in identifiers


def test_null_recommendation_score_funds_are_excluded(mock_supabase_select):
    mix = {"largecap": 100}
    res = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=None)
    funds = res[0]["funds"]
    # Check that "No Score Fund" (identifier 119780) is not included
    identifiers = [f["identifier"] for f in funds]
    assert "119780" not in identifiers


def test_recommendation_ordering_is_deterministic(mock_supabase_select):
    mix = {"largecap": 100}
    res = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=None, limit=5)
    funds = res[0]["funds"]
    
    # Ranks should be sorted by:
    # 1. recommendation_score DESC
    # 2. data_confidence DESC (HIGH > MEDIUM > LOW)
    # 3. peer_reliability DESC (HIGH > LOW > INSUFFICIENT)
    # 4. asset_name ASC
    scores = [f["recommendation_score"] for f in funds]
    assert scores[0] >= scores[1]
    
    # Check tie-breaker between 92.5 score funds: "Equal Score B Fund" vs "SBI Large Cap Fund"
    # "Equal Score B Fund" (alphabetical first) should come before "SBI Large Cap Fund"
    assert funds[0]["asset_name"] == "Equal Score B Fund"
    assert funds[1]["asset_name"] == "SBI Large Cap Fund"


def test_recommendation_score_remains_independent_of_preferences(mock_supabase_select):
    mix = {"largecap": 100}
    prefs_growth = UserPreferences(growth_vs_stability="growth")
    prefs_stability = UserPreferences(growth_vs_stability="stability")
    
    res_growth = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=prefs_growth)
    res_stability = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=prefs_stability)
    
    score_growth = {f["identifier"]: f["recommendation_score"] for f in res_growth[0]["funds"]}
    score_stability = {f["identifier"]: f["recommendation_score"] for f in res_stability[0]["funds"]}
    
    # recommendation_scores must be identical
    for ident in score_growth:
        assert score_growth[ident] == score_stability[ident]


def test_preference_match_score_changes_with_preferences(mock_supabase_select):
    mix = {"largecap": 100}
    prefs_growth = UserPreferences(growth_vs_stability="growth")
    prefs_stability = UserPreferences(growth_vs_stability="stability")
    
    res_growth = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=prefs_growth)
    res_stability = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=prefs_stability)
    
    # Large Cap is equity. Equity gets 100 compatibility for growth and 30 for stability.
    for f in res_growth[0]["funds"]:
        assert f["preference_match_score"] == 100.0
        
    for f in res_stability[0]["funds"]:
        assert f["preference_match_score"] == 30.0


def test_tax_preference_does_not_change_fund_quality_score(mock_supabase_select):
    mix = {"largecap": 100}
    prefs_tax = UserPreferences(tax_optimization_preference=True, accept_lock_in=True)
    res = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=prefs_tax)
    
    # recommendation_score remains unaltered
    for f in res[0]["funds"]:
        if f["identifier"] == "119777":
            assert f["recommendation_score"] == 92.5


def test_elss_is_only_considered_when_appropriate(mock_supabase_select):
    # Test adjustment mix utility directly:
    from app.modules.goals.service import adjust_mix_for_tax
    base_mix = {"largecap": 100}
    
    # Case A: wants tax optimization is false
    prefs_no_tax = UserPreferences(tax_optimization_preference=False, accept_lock_in=True)
    tax_profile = TaxProfile(tax_regime="old", existing_tax_saving_investments_range=0)
    mix_a = adjust_mix_for_tax(base_mix, prefs_no_tax, tax_profile)
    assert "elss" not in mix_a
    
    # Case B: accepts lock in is false
    prefs_no_lock = UserPreferences(tax_optimization_preference=True, accept_lock_in=False)
    mix_b = adjust_mix_for_tax(base_mix, prefs_no_lock, tax_profile)
    assert "elss" not in mix_b

    # Case C: new tax regime selected (no 80C capacity exists)
    prefs_ok = UserPreferences(tax_optimization_preference=True, accept_lock_in=True)
    tax_new_regime = TaxProfile(tax_regime="new")
    mix_c = adjust_mix_for_tax(base_mix, prefs_ok, tax_new_regime)
    assert "elss" not in mix_c

    # Case D: all conditions met
    mix_d = adjust_mix_for_tax(base_mix, prefs_ok, tax_profile)
    assert "elss" in mix_d
    assert mix_d["elss"] == 15.0


def test_lock_in_rejection_prevents_elss_preference_matching():
    # If lock-in is rejected (False) or not optimization, ELSS compatibility is 0.0
    prefs_no_lock = UserPreferences(tax_optimization_preference=True, accept_lock_in=False)
    score = calculate_preference_match("elss", "equity", prefs_no_lock)
    assert score == 0.0
    
    prefs_no_tax = UserPreferences(tax_optimization_preference=False, accept_lock_in=True)
    score_2 = calculate_preference_match("elss", "equity", prefs_no_tax)
    assert score_2 == 0.0


def test_alphabetical_ordering_is_only_a_final_tie_breaker(mock_supabase_select):
    mix = {"largecap": 100}
    res = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=None, limit=2)
    funds = res[0]["funds"]
    
    # Both "Equal Score B Fund" and "SBI Large Cap Fund" have score 92.5, HIGH confidence, HIGH reliability.
    # "Equal Score B Fund" must be ordered first because of alphabetical tie breaking.
    assert funds[0]["asset_name"] == "Equal Score B Fund"
    assert funds[1]["asset_name"] == "SBI Large Cap Fund"


def test_same_inputs_always_produce_identical_recommendations(mock_supabase_select):
    mix = {"largecap": 100}
    prefs = UserPreferences(growth_vs_stability="balanced")
    
    res1 = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=prefs)
    res2 = RecommendationService.get_recommendations(mix, 5.0, "mid", preferences=prefs)
    
    assert res1 == res2


def test_explanation_text_is_generated_from_actual_metrics():
    # Test high score, high confidence
    reasons = generate_reasons("flexi_cap", "Test Fund", 90.0, "HIGH", None)
    assert any("top group" in r for r in reasons)
    assert any("HIGH data confidence" in r for r in reasons)
    
    # Test elss with preferences
    prefs = UserPreferences(tax_optimization_preference=True, accept_lock_in=True)
    reasons_elss = generate_reasons("elss", "Axis ELSS", 88.0, "HIGH", prefs)
    assert any("3-year lock-in" in r for r in reasons_elss)
