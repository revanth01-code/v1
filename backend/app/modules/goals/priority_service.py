# backend/app/modules/goals/priority_service.py
from datetime import date
from typing import Optional

from app.core.exceptions import AppError
from app.modules.profile.service import ProfileService
from app.modules.emergency_fund.repository import EmergencyFundRepository
from app.modules.goals.repository import GoalRepository
from app.modules.goals.service import _enrich_goal_out, _attach_recommended_funds
from app.modules.goals.schemas import GoalOut
from .priority_schemas import (
    PriorityRankIn,
    PriorityAnalysisOut,
    ConflictWarning,
    PrioritySuggestion,
    CapacitySummary,
)


class PriorityService:
    @staticmethod
    def set_priority_ranks(
        access_token: str,
        user_id: str,
        payload: PriorityRankIn,
    ) -> list[GoalOut]:
        """Validate and update priority ranks for the user's goals.

        Rules:
        - Allows partial ranking (goals not in payload keep/remain with NULL/existing).
        - Ranks must be positive integers without duplicates in the payload.
        - All goals in the payload must belong to the user.
        - Ranks are saved directly to the database.
        """
        # Fetch all user goals
        user_goals = GoalRepository.list_by_user(access_token, user_id, limit=100)
        user_goal_ids = {g["id"] for g in user_goals}

        # Check for duplicates in the payload
        ranks_in_payload = [item.priority_rank for item in payload.rankings]
        if len(ranks_in_payload) != len(set(ranks_in_payload)):
            raise AppError("Duplicate priority ranks are not allowed.", 422)

        # Validate that all goals in payload exist and belong to the user
        for item in payload.rankings:
            if item.goal_id not in user_goal_ids:
                raise AppError(f"Goal '{item.goal_id}' not found or access denied.", 404)

        # Update ranks in the database
        for item in payload.rankings:
            GoalRepository.update_priority_rank(
                access_token, user_id, item.goal_id, item.priority_rank
            )

        # Re-fetch goals to get the updated sorted list
        updated_rows = GoalRepository.list_by_user(access_token, user_id, limit=100)

        res = []
        for row in updated_rows:
            enriched = _enrich_goal_out(row)
            res.append(
                GoalOut(
                    **enriched,
                    recommended_funds=_attach_recommended_funds(row["fund_category_mix"]),
                )
            )
        return res

    @staticmethod
    def get_priority_analysis(
        access_token: str,
        user_id: str,
    ) -> PriorityAnalysisOut:
        """Run strategic conflict analysis and generate recommendations based on
        user goal prioritization, feasibility, deadlines, and financial capacity.
        """
        # 1. Fetch user goals
        goals_rows = GoalRepository.list_by_user(access_token, user_id, limit=100)

        # Map to GoalOut
        goals = []
        for row in goals_rows:
            enriched = _enrich_goal_out(row)
            goals.append(
                GoalOut(
                    **enriched,
                    recommended_funds=_attach_recommended_funds(row["fund_category_mix"]),
                )
            )

        # Sort goals: ranked goals first (by priority_rank ASC), unranked last (by target_date / created_at DESC)
        # Note: list_by_user already orders by priority_rank ASC NULLS LAST, created_at DESC.
        # But we ensure it here to guarantee consistent python sorting.
        def get_sort_key(g: GoalOut):
            rank = g.priority_rank if g.priority_rank is not None else float("inf")
            # We sort unranked by creation timestamp desc
            created_time = getattr(g, "created_at", None)
            created_ts = created_time.timestamp() if created_time else 0
            return (rank, -created_ts)

        goals.sort(key=get_sort_key)

        # 2. Try loading financial profile
        profile = None
        try:
            profile = ProfileService.get_profile(access_token, user_id)
        except Exception:
            pass

        # 3. Try loading emergency fund
        ef_plan = None
        try:
            ef_plan = EmergencyFundRepository.get_by_user_id(access_token, user_id)
        except Exception:
            pass

        # Prepare outputs
        warnings: list[ConflictWarning] = []
        suggestions: list[PrioritySuggestion] = []

        # ── Capacity Summary ──
        total_monthly_contributions = sum(
            g.monthly_contribution
            for g in goals
            if g.contribution_mode in ("sip", "both")
        )

        if profile is None:
            warnings.append(
                ConflictWarning(
                    code="PROFILE_CAPACITY_UNAVAILABLE",
                    severity="INFO",
                    message="We could not evaluate whether your total goal contributions fit within your available monthly financial capacity. Complete your financial profile for more personalized recommendations.",
                )
            )
            capacity_summary = CapacitySummary(
                total_monthly_contributions=total_monthly_contributions,
                is_overcommitted=False,
            )
        else:
            available_capacity = getattr(profile, "available_capacity", 0.0)
            surplus_shortfall = available_capacity - total_monthly_contributions
            is_overcommitted = surplus_shortfall < 0

            capacity_summary = CapacitySummary(
                monthly_income=getattr(profile, "monthly_income", 0.0),
                monthly_expenses=getattr(profile, "monthly_expenses", 0.0),
                essential_expenses=getattr(profile, "essential_expenses", 0.0),
                emi_obligations=getattr(profile, "emi_obligations", 0.0),
                mandatory_commitments=getattr(profile, "mandatory_commitments", 0.0),
                emergency_fund_contribution=getattr(profile, "emergency_fund_contribution", 0.0),
                available_capacity=available_capacity,
                total_monthly_contributions=total_monthly_contributions,
                surplus_shortfall=surplus_shortfall,
                is_overcommitted=is_overcommitted,
            )

            if is_overcommitted:
                warnings.append(
                    ConflictWarning(
                        code="OVER_COMMITTED_CAPACITY",
                        severity="WARNING",
                        message=f"Your total monthly goal contributions ({total_monthly_contributions:.2f}) exceed your available monthly financial capacity ({available_capacity:.2f}). Consider extending timelines or reducing targets.",
                        affected_goal_ids=[
                            g.id for g in goals if g.contribution_mode in ("sip", "both")
                        ],
                    )
                )

        # ── Emergency Fund Check (Rule 1) ──
        # Check if the emergency fund is building / incomplete.
        # If so, check if the user has highly prioritized discretionary goals.
        discretionary_types = {"vacation", "car", "wedding", "custom"}
        if ef_plan:
            current_amount = ef_plan.get("current_amount", 0.0)
            months_of_coverage = ef_plan.get("months_of_coverage", 3.0)
            monthly_expenses = getattr(profile, "monthly_expenses", 0.0) if profile else 0.0
            target_amount = monthly_expenses * months_of_coverage
            is_building = ef_plan.get("status") == "building" or current_amount < target_amount

            if is_building:
                # Find discretionary goals ranked high (e.g. rank <= 2)
                high_discretionary_goals = [
                    g
                    for g in goals
                    if g.goal_type in discretionary_types
                    and g.priority_rank is not None
                    and g.priority_rank <= 2
                ]

                if high_discretionary_goals:
                    affected_ids = [g.id for g in high_discretionary_goals]
                    discretionary_names = ", ".join(f"'{g.name}'" for g in high_discretionary_goals)
                    warnings.append(
                        ConflictWarning(
                            code="EMERGENCY_FUND_DEPRIORITIZED",
                            severity="WARNING",
                            message=f"Your emergency fund is still building, but you have prioritized discretionary goal(s) {discretionary_names} highly. We recommend securing your emergency fund first.",
                            affected_goal_ids=affected_ids,
                        )
                    )
                    # Generate a suggestion for discretionary goal re-ranking
                    for g in high_discretionary_goals:
                        suggestions.append(
                            PrioritySuggestion(
                                goal_id=g.id,
                                current_rank=g.priority_rank,
                                suggested_rank=(g.priority_rank + 1),
                                reason=f"Securing 3-6 months of expenses in an emergency fund is critical before funding discretionary items like '{g.name}'. Consider lowering its rank.",
                            )
                        )

        # ── Infeasible High-Priority Goals (Rule 3) ──
        # Check if goals ranked 1 or 2 are unlikely or at_risk.
        high_priority_goals = [g for g in goals if g.priority_rank in (1, 2)]
        for g in high_priority_goals:
            status_lower = g.feasibility_status.lower()
            if status_lower in ("unlikely", "at_risk"):
                warnings.append(
                    ConflictWarning(
                        code="INFEASIBLE_HIGH_PRIORITY",
                        severity="WARNING",
                        message=f"Your top priority goal '{g.name}' is currently rated as '{g.feasibility_status}'. You may need a higher monthly SIP or a longer time horizon to achieve it.",
                        affected_goal_ids=[g.id],
                    )
                )

                # Generate strategic suggestion using feasibility_details if available
                feas_details = g.feasibility_details or {}
                suggested_sip = feas_details.get("suggested_monthly_sip")
                suggested_months = feas_details.get("suggested_extended_months")

                reason = f"Your top priority goal '{g.name}' is not achievable under your current plan."
                if suggested_sip:
                    reason += f" Try raising the monthly SIP to {suggested_sip:.2f}."
                if suggested_months:
                    reason += f" Or extend the target date by {suggested_months} months."
                if not suggested_sip and not suggested_months:
                    reason += " Consider reducing the target amount or risk level."

                suggestions.append(
                    PrioritySuggestion(
                        goal_id=g.id,
                        current_rank=g.priority_rank,
                        suggested_rank=g.priority_rank,
                        reason=reason,
                    )
                )

        # ── Short-Deadline Deprioritized Goals (Rule 4) ──
        # Find short-term goals (deadline <= 12 months) that are ranked below long-term goals.
        # Let's count months between today and target date.
        short_term_goals = []
        long_term_goals = []
        for g in goals:
            target_date = g.target_date
            if isinstance(target_date, str):
                target_date = date.fromisoformat(target_date)
            months_left = (target_date.year - date.today().year) * 12 + (target_date.month - date.today().month)
            if months_left <= 12:
                short_term_goals.append((g, months_left))
            elif months_left > 36:
                long_term_goals.append(g)

        # Check if any short-term goal is ranked lower (higher rank number or None) than any long-term goal
        for stg, months_left in short_term_goals:
            stg_rank = stg.priority_rank if stg.priority_rank is not None else float("inf")
            # See if there's any long-term goal ranked higher (rank < stg_rank)
            higher_ltg = [
                ltg
                for ltg in long_term_goals
                if ltg.priority_rank is not None and ltg.priority_rank < stg_rank
            ]
            if higher_ltg:
                ltg_names = ", ".join(f"'{g.name}'" for g in higher_ltg)
                warnings.append(
                    ConflictWarning(
                        code="SHORT_DEADLINE_DEPRIORITIZED",
                        severity="INFO",
                        message=f"Short-term goal '{stg.name}' has an urgent deadline ({months_left} months left) but is ranked below long-term goal(s) {ltg_names}. Ensure you have allocated enough to meet the near-term target.",
                        affected_goal_ids=[stg.id] + [g.id for g in higher_ltg],
                    )
                )
                suggestions.append(
                    PrioritySuggestion(
                        goal_id=stg.id,
                        current_rank=stg.priority_rank,
                        suggested_rank=1,
                        reason=f"Since '{stg.name}' has an urgent short-term timeline of {months_left} months, raising its priority rank helps ensure it is fully funded in time.",
                    )
                )

        # ── Unranked Goals (Rule 5) ──
        unranked_goals = [g for g in goals if g.priority_rank is None]
        if unranked_goals:
            warnings.append(
                ConflictWarning(
                    code="UNRANKED_GOALS_EXIST",
                    severity="INFO",
                    message=f"You have {len(unranked_goals)} unranked goal(s). Assign them a priority rank to optimize your financial plan.",
                    affected_goal_ids=[g.id for g in unranked_goals],
                )
            )

        # ── Priority-Aware Strategic Reasoning ──
        strategic_reasoning: list[str] = []

        if not goals:
            strategic_reasoning.append("No active goals found. Set up some goals to generate a priority-aware financial strategy.")
        elif len(goals) == 1:
            g = goals[0]
            strategic_reasoning.append(f"Goal '{g.name}' is currently your single focus.")
            if profile:
                available_capacity = getattr(profile, "available_capacity", 0.0)
                if g.monthly_contribution > available_capacity:
                    strategic_reasoning.append(f"Your monthly contribution for '{g.name}' exceeds your available capacity. The plan is currently unrealistic.")
                else:
                    strategic_reasoning.append("Your current contribution plan is realistic and fits within your monthly capacity.")
        else:
            # Multiple goals exist -> priority-aware multi-goal logic
            primary_goal = goals[0]
            secondary_goal = goals[1]

            # 1. Primary and secondary focus
            if primary_goal.priority_rank is not None:
                strategic_reasoning.append(f"Goal '{primary_goal.name}' is your primary focus (Rank {primary_goal.priority_rank}) and receives highest priority for resource allocation.")
            else:
                strategic_reasoning.append(f"Goal '{primary_goal.name}' is treated as your primary focus based on creation order.")

            if secondary_goal.priority_rank is not None:
                strategic_reasoning.append(f"Goal '{secondary_goal.name}' is your secondary focus (Rank {secondary_goal.priority_rank}) and should be funded after securing your primary target.")
            else:
                strategic_reasoning.append(f"Goal '{secondary_goal.name}' is your secondary focus.")

            # 2. Plan realism & simultaneous pursuit
            if profile:
                available_capacity = getattr(profile, "available_capacity", 0.0)
                if total_monthly_contributions > available_capacity:
                    strategic_reasoning.append("Your total financial commitments are unrealistic under your current surplus capacity.")
                    # Suggest reduced allocation for lowest-priority goal
                    lowest_priority_goal = goals[-1]
                    strategic_reasoning.append(
                        f"Since your monthly financial capacity is limited, lower-priority goals like '{lowest_priority_goal.name}' "
                        "should receive reduced allocation or have their deadlines extended to protect your primary goals."
                    )
                else:
                    strategic_reasoning.append("Your current contribution plan is realistic. Your total monthly commitments fit within your surplus, allowing you to pursue these goals simultaneously.")
            else:
                strategic_reasoning.append("We cannot evaluate plan realism or capacity limits because your financial profile is not completed.")

            # 3. Emergency fund status check
            if ef_plan:
                current_amount = ef_plan.get("current_amount", 0.0)
                months_of_coverage = ef_plan.get("months_of_coverage", 3.0)
                monthly_expenses = getattr(profile, "monthly_expenses", 0.0) if profile else 0.0
                target_amount = monthly_expenses * months_of_coverage
                is_building = ef_plan.get("status") == "building" or current_amount < target_amount
                if is_building:
                    strategic_reasoning.append("Your emergency fund is not fully funded. Prioritize building your cash reserve before committing extra funds to secondary goals.")

            # 4. Feasibility checks on top goals
            top_infeasible = [g for g in goals[:2] if g.feasibility_status.lower() in ("unlikely", "at_risk")]
            if top_infeasible:
                names = ", ".join(f"'{g.name}'" for g in top_infeasible)
                strategic_reasoning.append(
                    f"Top priority goal(s) {names} are currently infeasible. Strategic focus should be directed here to resolve the shortfall before allocating budget to secondary goals."
                )

            # 5. Short deadline checks
            short_deadline_neglected = False
            for stg, months_left in short_term_goals:
                stg_rank = stg.priority_rank if stg.priority_rank is not None else float("inf")
                higher_ltg = [ltg for ltg in long_term_goals if ltg.priority_rank is not None and ltg.priority_rank < stg_rank]
                if higher_ltg:
                    short_deadline_neglected = True
                    break
            if short_deadline_neglected:
                strategic_reasoning.append("Some short-term goals with urgent deadlines are ranked below long-term goals. Ensure they receive adequate near-term allocations.")

        return PriorityAnalysisOut(
            goals=goals,
            warnings=warnings,
            suggestions=suggestions,
            capacity_summary=capacity_summary,
            strategic_reasoning=strategic_reasoning,
        )
