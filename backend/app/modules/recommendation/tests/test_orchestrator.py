# backend/app/modules/recommendation/tests/test_orchestrator.py
from datetime import date
import pytest
from unittest.mock import patch, MagicMock
from app.modules.recommendation.orchestrator import RecommendationOrchestrator
from app.modules.recommendation.models import RecommendationRequest, RecommendationRequestGoal, RecommendationRequestOptions
from app.modules.universe.recommendation.schemas import UserPreferences
from app.modules.tax.tax_service import TaxProfile
from app.modules.goals.feasibility.feasibility_models import GoalFeasibilityAlternative

MOCK_ORCHESTRATOR_FUNDS = [
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
                "metrics": {"returns": {"5y": 0.15}, "sharpe_ratio": 1.2, "volatility": 0.12}
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
                "metrics": {"returns": {"5y": 0.12}, "sharpe_ratio": 0.9, "volatility": 0.14}
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
                "metrics": {"returns": {"5y": 0.15}, "sharpe_ratio": 1.2, "volatility": 0.12}
            }
        ]
    }
]


@pytest.fixture
def mock_supabase_select():
    with patch("app.core.supabase.supabase_admin.table") as mock_table:
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=MOCK_ORCHESTRATOR_FUNDS)
        mock_table.return_value.select.return_value.eq.return_value.in_.return_value = mock_execute
        yield mock_table


def test_achievable_goal_recommendations_ready(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None,
        options=RecommendationRequestOptions(allow_stretched_goal=False)
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "RECOMMENDATIONS_READY"
    assert res["strategy"] is not None
    assert len(res["recommendations"]["funds"]) > 0


def test_stretched_goal_review_required(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Stretched",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=7500.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None,
        options=RecommendationRequestOptions(allow_stretched_goal=False)
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "FEASIBILITY_REVIEW_REQUIRED"
    assert res["recommendations"] is None


def test_stretched_goal_with_explicit_allow_flag(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Stretched Allowed",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=7500.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None,
        options=RecommendationRequestOptions(allow_stretched_goal=True)
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "RECOMMENDATIONS_READY"
    assert res["recommendations"] is not None


def test_difficult_goal_review_required(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Difficult",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=4000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "FEASIBILITY_REVIEW_REQUIRED"


def test_unrealistic_goal_review_required(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Unrealistic",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=1000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "FEASIBILITY_REVIEW_REQUIRED"


def test_missing_information_insufficient_info(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Missing Info",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=1000.0,
            horizon_months=None,
            target_date=None,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "INSUFFICIENT_INFORMATION"


def test_selected_alternative_revised_strategy(mock_supabase_select):
    original_goal = RecommendationRequestGoal(
        goal_name="Stretched",
        target_amount=100000.0,
        current_amount=0.0,
        monthly_investment=7500.0,
        horizon_months=12,
        risk_level="mid"
    )
    alt = GoalFeasibilityAlternative(
        type="increase_monthly_investment",
        recommended_monthly_investment=9000.0,
        description="Recommend increase monthly investment"
    )
    req = RecommendationRequest(
        goal=original_goal,
        preferences=None,
        tax_profile=None,
        options=RecommendationRequestOptions(allow_stretched_goal=False),
        selected_alternative=alt
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "RECOMMENDATIONS_READY"
    assert res["strategy"] is not None


def test_insufficient_confidence_fund_excluded(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    funds = res["recommendations"]["funds"]
    # Check that identifier "119779" (Insufficient Data Fund) is excluded
    identifiers = [f["identifier"] for f in funds]
    assert "119779" not in identifiers


def test_null_recommendation_score_excluded(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    funds = res["recommendations"]["funds"]
    # Check that identifier "119780" (No Score Fund) is excluded
    identifiers = [f["identifier"] for f in funds]
    assert "119780" not in identifiers


def test_funds_correctly_sorted(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    funds = res["recommendations"]["funds"]
    # Ranks should be sorted by:
    # 1. final_match_score DESC (here 70% of score + 30% of 100 compatibility since pref=None)
    # 2. recommendation_score DESC
    scores = [f["scores"]["final_match_score"] for f in funds]
    assert scores[0] >= scores[1]


def test_tie_breaking_deterministic(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    funds = res["recommendations"]["funds"]
    # Tie-breaker between score 92.5: "Equal Score B Fund" comes before "SBI Large Cap Fund"
    assert funds[0]["fund_name"] == "Equal Score B Fund"
    assert funds[1]["fund_name"] == "SBI Large Cap Fund"


def test_tax_section_remains_separate(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert "tax_summary" in res
    # Verify that tax summaries are separated from fund scoring fields
    for f in res["recommendations"]["funds"]:
        assert "tax" not in f["scores"]


def test_recommendation_scores_unchanged(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=UserPreferences(growth_vs_stability="stability"),
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    # recommendation_score remains 92.5 for SBI Large Cap Fund
    for f in res["recommendations"]["funds"]:
        if f["identifier"] == "119777":
            assert f["scores"]["recommendation_score"] == 92.5


def test_no_automatic_risk_escalation(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="low"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["strategy"]["risk_level"] == "low"


def test_explanations_only_use_real_metrics(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    for f in res["recommendations"]["funds"]:
        if f["identifier"] == "119777":
            assert any("risk-adjusted returns" in reason for reason in f["why_recommended"])


def test_same_input_always_produces_same_output(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res1 = RecommendationOrchestrator.get_recommendation_preview(req)
    res2 = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res1["workflow_state"] == res2["workflow_state"]
    assert res1["recommendations"]["funds"] == res2["recommendations"]["funds"]


def test_empty_eligible_fund_set_handled_safely():
    with patch("app.core.supabase.supabase_admin.table") as mock_table:
        mock_execute = MagicMock()
        mock_execute.execute.return_value = MagicMock(data=[])
        mock_table.return_value.select.return_value.eq.return_value.in_.return_value = mock_execute

        req = RecommendationRequest(
            goal=RecommendationRequestGoal(
                goal_name="Achievable",
                target_amount=100000.0,
                current_amount=0.0,
                monthly_investment=9000.0,
                horizon_months=12,
                risk_level="mid"
            ),
            preferences=None,
            tax_profile=None
        )
        res = RecommendationOrchestrator.get_recommendation_preview(req)
        assert res["workflow_state"] == "RECOMMENDATIONS_READY"
        assert len(res["recommendations"]["funds"]) == 0


def test_missing_preferences_handled_safely(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "RECOMMENDATIONS_READY"


def test_tax_profile_optional(mock_supabase_select):
    req = RecommendationRequest(
        goal=RecommendationRequestGoal(
            goal_name="Achievable",
            target_amount=100000.0,
            current_amount=0.0,
            monthly_investment=9000.0,
            horizon_months=12,
            risk_level="mid"
        ),
        preferences=None,
        tax_profile=None
    )
    res = RecommendationOrchestrator.get_recommendation_preview(req)
    assert res["workflow_state"] == "RECOMMENDATIONS_READY"
    assert res["tax_summary"] is not None
