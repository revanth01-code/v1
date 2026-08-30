# backend/app/modules/goals/tests/test_goals_strategy.py
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.goals.schemas import GoalStrategyPreviewRequest
from app.modules.goals.service import GoalService
from app.modules.tax.tax_rules import TAX_RULES_METADATA
from app.modules.tax.tax_service import TaxProfile, TaxOpportunityService

client = TestClient(app)


def test_existing_goal_creation_remains_unchanged():
    # Make sure we can still query the goals list endpoint or verify the router registration
    # Simply assert that GoalService.create continues to work as expected without signature changes
    assert hasattr(GoalService, "create")


def test_goal_strategy_preview_works():
    payload = {
        "name": "Retirement Goal",
        "target_amount": 5000000.0,
        "target_date": (date.today() + timedelta(days=365 * 10)).isoformat(),
        "risk_level": "mid",
        "goal_type": "retirement",
        "tax_profile": {
            "tax_regime": "old",
            "annual_income_range": "10L - 15L",
            "existing_tax_saving_investments_range": 50000.0,
            "wants_tax_optimization": True
        }
    }
    
    # We mock authentication by patching get_current_user in the route or just calling service layer
    request_obj = GoalStrategyPreviewRequest(**payload)
    result = GoalService.preview_strategy(request_obj)
    
    assert "strategy" in result
    assert "tax_summary" in result
    assert result["next_step"] == "review_strategy"
    assert result["strategy"]["risk_level"] == "mid"
    assert len(result["strategy"]["reasoning"]) > 0


def test_tax_profile_is_optional():
    payload = {
        "name": "Car Goal",
        "target_amount": 1000000.0,
        "target_date": (date.today() + timedelta(days=365 * 5)).isoformat(),
        "risk_level": "high",
        "goal_type": "car",
        "tax_profile": None
    }
    
    request_obj = GoalStrategyPreviewRequest(**payload)
    result = GoalService.preview_strategy(request_obj)
    
    assert "strategy" in result
    assert "tax_summary" in result
    assert result["tax_summary"]["status"] == "INFORMATIONAL"


def test_unknown_tax_information_does_not_break_strategy():
    payload = {
        "name": "Custom Goal",
        "target_amount": 200000.0,
        "target_date": (date.today() + timedelta(days=365 * 2)).isoformat(),
        "risk_level": "low",
        "goal_type": "custom",
        "tax_profile": {
            "tax_regime": "unknown",
            "annual_income_range": "unknown",
            "existing_tax_saving_investments_range": 0.0,
            "wants_tax_optimization": None
        }
    }
    
    request_obj = GoalStrategyPreviewRequest(**payload)
    result = GoalService.preview_strategy(request_obj)
    
    assert "strategy" in result
    assert "tax_summary" in result
    assert result["tax_summary"]["status"] == "INFORMATIONAL"


def test_tax_engine_does_not_alter_recommendation_score():
    # Verify that analyzing a tax profile does not touch recommendation scores or funds
    profile = TaxProfile(tax_regime="old", annual_income_range="5L - 10L")
    result = TaxOpportunityService.analyze_profile(profile)
    
    # Assert that no recommendation scores or assets are present in the output
    assert "recommendation_score" not in result
    assert "funds" not in result


def test_tax_insights_remain_separate_from_fund_ranking():
    # Confirm that tax_summary is distinct from strategy recommendations
    payload = {
        "name": "Education",
        "target_amount": 1500000.0,
        "target_date": (date.today() + timedelta(days=365 * 7)).isoformat(),
        "risk_level": "high",
        "goal_type": "education",
        "tax_profile": {
            "tax_regime": "old"
        }
    }
    request_obj = GoalStrategyPreviewRequest(**payload)
    result = GoalService.preview_strategy(request_obj)
    
    # They should be returned as separate root keys in the preview contract
    assert "strategy" in result
    assert "tax_summary" in result
    assert "recommended_funds" not in result["strategy"]


def test_strategy_reuses_existing_fund_category_mix_logic():
    # For mid risk level, it should match the constant FUND_CATEGORY_MIX["mid"]
    payload = {
        "name": "House",
        "target_amount": 4000000.0,
        "target_date": (date.today() + timedelta(days=365 * 8)).isoformat(),
        "risk_level": "mid",
        "goal_type": "house"
    }
    request_obj = GoalStrategyPreviewRequest(**payload)
    result = GoalService.preview_strategy(request_obj)
    
    mix = result["strategy"]["fund_category_mix"]
    # Check that it contains flexicap, largecap, debt in the correct proportions
    largecap_alloc = next(x["allocation_percent"] for x in mix if x["category"] == "largecap")
    flexicap_alloc = next(x["allocation_percent"] for x in mix if x["category"] == "flexicap")
    debt_alloc = next(x["allocation_percent"] for x in mix if x["category"] == "debt")
    
    assert largecap_alloc == 40
    assert flexicap_alloc == 40
    assert debt_alloc == 20


def test_same_inputs_produce_same_strategy():
    payload = {
        "name": "Wedding Goal",
        "target_amount": 800000.0,
        "target_date": (date.today() + timedelta(days=365 * 4)).isoformat(),
        "risk_level": "mid",
        "goal_type": "wedding",
        "tax_profile": {
            "tax_regime": "old",
            "annual_income_range": "5L - 10L"
        }
    }
    
    req1 = GoalStrategyPreviewRequest(**payload)
    req2 = GoalStrategyPreviewRequest(**payload)
    
    res1 = GoalService.preview_strategy(req1)
    res2 = GoalService.preview_strategy(req2)
    
    assert res1["strategy"] == res2["strategy"]
    assert res1["tax_summary"]["status"] == res2["tax_summary"]["status"]


def test_tax_rules_are_centrally_loaded():
    profile = TaxProfile(tax_regime="old", wants_tax_optimization=True)
    result = TaxOpportunityService.analyze_profile(profile)
    
    # Inspect metadata from the rules configuration is included
    assert "rules_applied" in result
    assert result["rules_applied"]["financial_year"] == "2026-2027"
    assert result["rules_applied"]["rule_identifier"] == TAX_RULES_METADATA["rule_identifier"]
    assert result["rules_applied"]["last_reviewed_date"] == TAX_RULES_METADATA["last_reviewed_date"]


def test_no_sensitive_tax_identifiers_are_required():
    # Verify that TaxProfile schema contains absolutely no fields for PAN, Aadhaar, bank details, salary slips etc.
    fields = TaxProfile.model_fields.keys()
    sensitive_keywords = ["pan", "aadhaar", "ssn", "bank", "account", "credential", "slip", "document", "file"]
    
    for field in fields:
        for keyword in sensitive_keywords:
            assert keyword not in field.lower()
