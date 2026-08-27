# backend/app/modules/goals/tests/test_priority.py
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.exceptions import AppError
from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut
from app.modules.goals.priority_service import PriorityService
from app.modules.goals.priority_schemas import PriorityRankIn, GoalRankItem
from app.modules.goals.schemas import GoalOut
from app.modules.profile.schemas import ProfileOut

client = TestClient(app)
FAKE_USER = UserOut(id="user-123", email="test@example.com")


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_access_token] = lambda: "fake-token"
    yield
    app.dependency_overrides.clear()


def make_fake_goal(id: str, name: str, subcategory: str, contribution: float = 1000.0, rank: int = None, type: str = "custom", status: str = "feasible", target_date: date = None) -> dict:
    if target_date is None:
        target_date = date.today() + timedelta(days=365 * 2)  # 2 years
    return {
        "id": id,
        "user_id": "user-123",
        "name": name,
        "target_amount": 100000.0,
        "target_date": target_date.isoformat(),
        "term_type": "long_term" if (target_date - date.today()).days > 365 * 3 else "short_term",
        "contribution_mode": "sip",
        "monthly_contribution": contribution,
        "lumpsum_amount": 0.0,
        "risk_level": "mid",
        "fund_category_mix": {"largecap": 40, "flexicap": 40, "debt": 20},
        "expected_return_pct": 10.0,
        "inflation_adjusted_target": 110000.0,
        "feasibility_status": status,
        "feasibility_details": {
            "status": status,
            "suggested_monthly_sip": 1500.0,
            "suggested_extended_months": 6
        },
        "status": "active",
        "created_at": "2026-08-09T00:00:00Z",
        "updated_at": "2026-08-09T00:00:00Z",
        "goal_type": type,
        "priority": "medium",
        "deadline_flexibility": "flexible",
        "importance": "important",
        "inflation_scenario": "expected",
        "inflation_rate_pct": 6.0,
        "inflation_rate_override": None,
        "strategies": None,
        "priority_rank": rank
    }


class TestPriorityRankingService:
    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.goals.repository.GoalRepository.update_priority_rank")
    def test_set_priority_ranks_success(self, mock_update, mock_list):
        # 1. Setup mock goals
        goal1 = make_fake_goal("g1", "House", "flexi_cap", rank=None)
        goal2 = make_fake_goal("g2", "Phone", "large_cap", rank=None)
        mock_list.side_effect = [
            [goal1, goal2],  # First call inside set_priority_ranks to get list of user goal ids
            [
                {**goal1, "priority_rank": 1},
                {**goal2, "priority_rank": 2}
            ]  # Second call to return updated/ranked goals
        ]

        payload = PriorityRankIn(rankings=[
            GoalRankItem(goal_id="g1", priority_rank=1),
            GoalRankItem(goal_id="g2", priority_rank=2)
        ])

        res = PriorityService.set_priority_ranks("fake-token", "user-123", payload)

        assert len(res) == 2
        assert res[0].priority_rank == 1
        assert res[1].priority_rank == 2
        assert mock_update.call_count == 2

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    def test_set_priority_ranks_duplicates_rejected(self, mock_list):
        goal1 = make_fake_goal("g1", "House", "flexi_cap")
        goal2 = make_fake_goal("g2", "Phone", "large_cap")
        mock_list.return_value = [goal1, goal2]

        payload = PriorityRankIn(rankings=[
            GoalRankItem(goal_id="g1", priority_rank=1),
            GoalRankItem(goal_id="g2", priority_rank=1)  # Duplicate rank
        ])

        with pytest.raises(AppError) as exc:
            PriorityService.set_priority_ranks("fake-token", "user-123", payload)
        assert exc.value.status_code == 422
        assert "Duplicate priority ranks" in exc.value.message

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    def test_set_priority_ranks_unknown_goal_rejected(self, mock_list):
        goal1 = make_fake_goal("g1", "House", "flexi_cap")
        mock_list.return_value = [goal1]

        payload = PriorityRankIn(rankings=[
            GoalRankItem(goal_id="unknown_id", priority_rank=1)
        ])

        with pytest.raises(AppError) as exc:
            PriorityService.set_priority_ranks("fake-token", "user-123", payload)
        assert exc.value.status_code == 404
        assert "not found or access denied" in exc.value.message


class TestPriorityConflictAnalysis:
    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_analysis_overcommitted_capacity(self, mock_ef, mock_profile, mock_list):
        # 1. Setup mock goals
        goal1 = make_fake_goal("g1", "House", "flexi_cap", contribution=25000.0, rank=1)
        mock_list.return_value = [goal1]

        # 2. Setup mock profile (available capacity = 20000, monthly contributions = 25000)
        profile_out = ProfileOut(
            id="p1",
            user_id="user-123",
            monthly_income=50000.0,
            monthly_expenses=30000.0,
            existing_savings=10000.0,
            existing_investments=5000.0,
            dependents=2,
            essential_expenses=20000.0,
            emi_obligations=5000.0,
            mandatory_commitments=5000.0,
            emergency_fund_contribution=0.0,
            available_capacity=20000.0,
            monthly_surplus=20000.0,
            created_at="2026-08-09T00:00:00Z",
            updated_at="2026-08-09T00:00:00Z"
        )
        mock_profile.return_value = profile_out
        mock_ef.return_value = None

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")

        # 3. Verify overcommitted capacity trigger
        assert analysis.capacity_summary.is_overcommitted is True
        assert analysis.capacity_summary.total_monthly_contributions == 25000.0
        assert analysis.capacity_summary.available_capacity == 20000.0
        assert len(analysis.warnings) == 1
        assert analysis.warnings[0].code == "OVER_COMMITTED_CAPACITY"
        assert analysis.warnings[0].severity == "WARNING"

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_analysis_emergency_fund_deprioritized(self, mock_ef, mock_profile, mock_list):
        # 1. Setup mock goals (discretionary goal prioritized highly)
        goal1 = make_fake_goal("g1", "Vacation Trip", "flexi_cap", contribution=2000.0, rank=1, type="vacation")
        mock_list.return_value = [goal1]

        # 2. Setup mock profile
        profile_out = ProfileOut(
            id="p1",
            user_id="user-123",
            monthly_income=50000.0,
            monthly_expenses=30000.0,
            existing_savings=10000.0,
            existing_investments=5000.0,
            dependents=2,
            essential_expenses=20000.0,
            emi_obligations=5000.0,
            mandatory_commitments=5000.0,
            emergency_fund_contribution=0.0,
            available_capacity=20000.0,
            monthly_surplus=20000.0,
            created_at="2026-08-09T00:00:00Z",
            updated_at="2026-08-09T00:00:00Z"
        )
        mock_profile.return_value = profile_out

        # 3. Setup mock emergency fund as "building"
        mock_ef.return_value = {
            "id": "ef1",
            "user_id": "user-123",
            "months_of_coverage": 3.0,
            "current_amount": 5000.0,  # target is 30000 * 3 = 90000
            "monthly_contribution": 1000.0,
            "status": "building"
        }

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")

        # 4. Verify emergency fund warnings & suggestions
        ef_warnings = [w for w in analysis.warnings if w.code == "EMERGENCY_FUND_DEPRIORITIZED"]
        assert len(ef_warnings) == 1
        assert ef_warnings[0].severity == "WARNING"
        assert "securing your emergency fund first" in ef_warnings[0].message
        assert "g1" in ef_warnings[0].affected_goal_ids

        assert len(analysis.suggestions) == 1
        assert analysis.suggestions[0].goal_id == "g1"
        assert "emergency fund is critical" in analysis.suggestions[0].reason

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_analysis_infeasible_high_priority(self, mock_ef, mock_profile, mock_list):
        # 1. Setup mock goals (infeasible top priority goal)
        goal1 = make_fake_goal("g1", "House", "flexi_cap", contribution=2000.0, rank=1, status="at_risk")
        mock_list.return_value = [goal1]

        mock_profile.return_value = None
        mock_ef.return_value = None

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")

        # 2. Verify infeasible priority warnings
        inf_warnings = [w for w in analysis.warnings if w.code == "INFEASIBLE_HIGH_PRIORITY"]
        assert len(inf_warnings) == 1
        assert inf_warnings[0].severity == "WARNING"
        assert "g1" in inf_warnings[0].affected_goal_ids

        assert len(analysis.suggestions) == 1
        assert analysis.suggestions[0].goal_id == "g1"
        assert "raising the monthly SIP to 1500.00" in analysis.suggestions[0].reason

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_analysis_short_deadline_deprioritized(self, mock_ef, mock_profile, mock_list):
        # 1. Setup mock goals (short deadline ranked lower than long term)
        stg = make_fake_goal(
            "stg", "Laptop", "large_cap", rank=2,
            target_date=date.today() + timedelta(days=180)  # 6 months left
        )
        ltg = make_fake_goal(
            "ltg", "Retirement", "flexi_cap", rank=1,
            target_date=date.today() + timedelta(days=365 * 10)  # 10 years left
        )
        mock_list.return_value = [stg, ltg]

        mock_profile.return_value = None
        mock_ef.return_value = None

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")

        # 2. Verify warnings & suggestions
        sd_warnings = [w for w in analysis.warnings if w.code == "SHORT_DEADLINE_DEPRIORITIZED"]
        assert len(sd_warnings) == 1
        assert sd_warnings[0].severity == "INFO"
        assert "stg" in sd_warnings[0].affected_goal_ids

        sd_suggestions = [s for s in analysis.suggestions if s.goal_id == "stg"]
        assert len(sd_suggestions) == 1
        assert sd_suggestions[0].suggested_rank == 1

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_analysis_profile_missing_graceful_degrade(self, mock_ef, mock_profile, mock_list):
        mock_list.return_value = []
        # Simulate ProfileRepository/Service raising AppError
        mock_profile.side_effect = AppError("Profile not found", 404)
        mock_ef.return_value = None

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")

        # Verify profile capacity warning is INFO and analysis succeeds
        unavail_warnings = [w for w in analysis.warnings if w.code == "PROFILE_CAPACITY_UNAVAILABLE"]
        assert len(unavail_warnings) == 1
        assert unavail_warnings[0].severity == "INFO"


class TestPriorityAPIEndpoints:
    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.goals.repository.GoalRepository.update_priority_rank")
    def test_api_put_priority_success(self, mock_update, mock_list):
        goal1 = make_fake_goal("g1", "House", "flexi_cap", rank=None)
        mock_list.side_effect = [
            [goal1],
            [{**goal1, "priority_rank": 1}]
        ]

        payload = {
            "rankings": [
                {"goal_id": "g1", "priority_rank": 1}
            ]
        }

        res = client.put("/api/v1/goals/priority", json=payload)
        assert res.status_code == 200
        assert res.json()[0]["priority_rank"] == 1

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_api_get_priority_analysis_success(self, mock_ef, mock_profile, mock_list):
        goal1 = make_fake_goal("g1", "House", "flexi_cap", rank=1)
        mock_list.return_value = [goal1]
        mock_profile.return_value = None
        mock_ef.return_value = None

        res = client.get("/api/v1/goals/priority-analysis")
        assert res.status_code == 200
        body = res.json()
        assert "goals" in body
        assert "warnings" in body
        assert "suggestions" in body
        assert "capacity_summary" in body


class TestPriorityStrategicReasoning:
    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_single_goal_backward_compatibility(self, mock_ef, mock_profile, mock_list):
        """Single-goal backward compatibility: works seamlessly and reports simple focus."""
        goal = make_fake_goal("g1", "Emergency Cash", "liquid", contribution=5000.0, rank=None)
        mock_list.return_value = [goal]
        
        # Profile capacity is 10000 -> fits
        profile_out = ProfileOut(
            id="p1", user_id="user-123", monthly_income=30000.0, monthly_expenses=15000.0,
            existing_savings=5000.0, existing_investments=0.0, dependents=1,
            essential_expenses=10000.0, emi_obligations=0.0, mandatory_commitments=0.0,
            emergency_fund_contribution=0.0, available_capacity=20000.0, monthly_surplus=15000.0,
            created_at="2026-08-09T00:00:00Z", updated_at="2026-08-09T00:00:00Z"
        )
        mock_profile.return_value = profile_out
        mock_ef.return_value = None

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")
        assert len(analysis.goals) == 1
        assert "g1" == analysis.goals[0].id
        
        # Verify reasoning strings
        reasoning = analysis.strategic_reasoning
        assert len(reasoning) >= 2
        assert "Goal 'Emergency Cash' is currently your single focus." in reasoning[0]
        assert "fits within your monthly capacity" in reasoning[1]

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_multi_goals_strategic_ordering_and_focus(self, mock_ef, mock_profile, mock_list):
        """User priority never overridden. Ranks correctly sort and generate clear focus advice."""
        # g1 is rank 2, g2 is rank 1 -> sorted list should place g2 first
        goal1 = make_fake_goal("g1", "New Laptop", "large_cap", contribution=2000.0, rank=2)
        goal2 = make_fake_goal("g2", "Retirement fund", "flexi_cap", contribution=10000.0, rank=1)
        mock_list.return_value = [goal1, goal2]

        profile_out = ProfileOut(
            id="p1", user_id="user-123", monthly_income=50000.0, monthly_expenses=25000.0,
            existing_savings=10000.0, existing_investments=0.0, dependents=1,
            essential_expenses=15000.0, emi_obligations=5000.0, mandatory_commitments=0.0,
            emergency_fund_contribution=0.0, available_capacity=30000.0, monthly_surplus=25000.0,
            created_at="2026-08-09T00:00:00Z", updated_at="2026-08-09T00:00:00Z"
        )
        mock_profile.return_value = profile_out
        mock_ef.return_value = None

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")
        
        # Verify user priority ordering is intact (g2 first, then g1)
        assert analysis.goals[0].id == "g2"
        assert analysis.goals[1].id == "g1"

        reasoning = analysis.strategic_reasoning
        # Confirm strategic focus reasoning
        assert any("Goal 'Retirement fund' is your primary focus (Rank 1)" in r for r in reasoning)
        assert any("Goal 'New Laptop' is your secondary focus (Rank 2)" in r for r in reasoning)
        assert any("allowing you to pursue these goals simultaneously" in r for r in reasoning)

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_multi_goals_with_unranked_fallback(self, mock_ef, mock_profile, mock_list):
        """Goals without priority_rank fall back to created_at and trigger warning."""
        # g1 has rank 1, g2 has no rank
        goal1 = make_fake_goal("g1", "House", "flexi_cap", contribution=15000.0, rank=1)
        goal2 = make_fake_goal("g2", "Vacation", "flexi_cap", contribution=5000.0, rank=None)
        mock_list.return_value = [goal1, goal2]

        mock_profile.return_value = None
        mock_ef.return_value = None

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")
        
        # Order is g1 (ranked 1) -> g2 (unranked)
        assert analysis.goals[0].id == "g1"
        assert analysis.goals[1].id == "g2"

        reasoning = analysis.strategic_reasoning
        assert any("Goal 'House' is your primary focus" in r for r in reasoning)
        assert any("Goal 'Vacation' is your secondary focus" in r for r in reasoning)
        
        # Check warnings
        unranked_warn = [w for w in analysis.warnings if w.code == "UNRANKED_GOALS_EXIST"]
        assert len(unranked_warn) == 1

    @patch("app.modules.goals.repository.GoalRepository.list_by_user")
    @patch("app.modules.profile.service.ProfileService.get_profile")
    @patch("app.modules.emergency_fund.repository.EmergencyFundRepository.get_by_user_id")
    def test_overcommitted_capacity_allocation_advice(self, mock_ef, mock_profile, mock_list):
        """Overcommitted capacity recommends reduced allocation for lowest-priority goals."""
        goal1 = make_fake_goal("g1", "Retirement", "flexi_cap", contribution=20000.0, rank=1)
        goal2 = make_fake_goal("g2", "Phone Buy", "large_cap", contribution=5000.0, rank=2)
        mock_list.return_value = [goal1, goal2]

        # Available capacity is 15000 -> commitments 25000 exceeds it
        profile_out = ProfileOut(
            id="p1", user_id="user-123", monthly_income=40000.0, monthly_expenses=25000.0,
            existing_savings=10000.0, existing_investments=0.0, dependents=1,
            essential_expenses=20000.0, emi_obligations=5000.0, mandatory_commitments=0.0,
            emergency_fund_contribution=0.0, available_capacity=15000.0, monthly_surplus=15000.0,
            created_at="2026-08-09T00:00:00Z", updated_at="2026-08-09T00:00:00Z"
        )
        mock_profile.return_value = profile_out
        mock_ef.return_value = None

        analysis = PriorityService.get_priority_analysis("fake-token", "user-123")
        reasoning = analysis.strategic_reasoning
        
        assert any("unrealistic under your current surplus capacity" in r for r in reasoning)
        assert any("lower-priority goals like 'Phone Buy' should receive reduced allocation" in r for r in reasoning)

