# backend/app/modules/recommendation/orchestrator.py
import logging
from typing import Optional, Any
from datetime import datetime, date

from app.core.supabase import supabase_admin
from app.core.constants import LEGACY_TO_UNIVERSE_SUBCAT_MAP
from app.modules.goals.feasibility.feasibility_service import FeasibilityService
from app.modules.goals.feasibility.feasibility_models import GoalFeasibilityPreviewRequest, GoalFeasibilityApplyRequest
from app.modules.goals.service import GoalService
from app.modules.universe.recommendation.compatibility import calculate_preference_match
from .models import RecommendationRequest, RecommendationResponse
from .explanation_builder import build_explanations

logger = logging.getLogger(__name__)

CONFIDENCE_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "INSUFFICIENT": 0}
RELIABILITY_ORDER = {"HIGH": 2, "LOW": 1, "INSUFFICIENT": 0}


class RecommendationOrchestrator:
    @staticmethod
    def get_recommendation_preview(request: RecommendationRequest) -> dict:
        """Coordinates feasibility check, strategy selection, tax opportunity analysis, and fund ranking.

        Guarantees deterministic peer quality evaluation and decoupled preference matching.
        """
        # Step 1: Feasibility Evaluation
        goal_req = GoalFeasibilityPreviewRequest(
            target_amount=request.goal.target_amount,
            current_amount=request.goal.current_amount,
            monthly_investment=request.goal.monthly_investment,
            target_date=request.goal.target_date,
            horizon_months=request.goal.horizon_months,
            risk_level=request.goal.risk_level
        )

        # Apply selected alternative if supplied
        if request.selected_alternative:
            apply_req = GoalFeasibilityApplyRequest(
                original_goal=goal_req,
                selected_alternative=request.selected_alternative
            )
            apply_res = FeasibilityService.apply_alternative(apply_req)
            # Use revised values
            goal_req = apply_res.revised_goal
            feasibility_res = FeasibilityService.calculate_feasibility(goal_req)
        else:
            feasibility_res = FeasibilityService.calculate_feasibility(goal_req)

        # Step 2: Determine Workflow State
        status = feasibility_res.status
        allow_stretched = request.options.allow_stretched_goal if request.options else False

        if status == "INSUFFICIENT_INFORMATION":
            state = "INSUFFICIENT_INFORMATION"
        elif status in ["DIFFICULT", "UNREALISTIC"]:
            state = "FEASIBILITY_REVIEW_REQUIRED"
        elif status == "STRETCHED" and not allow_stretched:
            state = "FEASIBILITY_REVIEW_REQUIRED"
        else:
            state = "RECOMMENDATIONS_READY"

        feasibility_dict = feasibility_res.model_dump()

        # If review is required or information is insufficient, return early
        if state in ["INSUFFICIENT_INFORMATION", "FEASIBILITY_REVIEW_REQUIRED"]:
            return {
                "workflow_state": state,
                "feasibility": feasibility_dict,
                "strategy": None,
                "tax_summary": None,
                "recommendations": None,
                "disclaimers": [
                    "Mutual fund investments are subject to market risk.",
                    "Past performance does not guarantee future returns.",
                    "Recommendations are generated using historical and peer-relative metrics."
                ]
            }

        # Step 3: Strategy & Tax Generation (using revised target/horizon/risk)
        # Build payload matching GoalService expectations
        class PreviewPayload:
            def __init__(self, target_amount, target_date, horizon_months, risk_level, preferences, tax_profile):
                self.target_amount = target_amount
                # Target date must be resolved from target_date or horizon_months
                if target_date is not None:
                    self.target_date = target_date
                else:
                    from dateutil.relativedelta import relativedelta
                    self.target_date = date.today() + relativedelta(months=horizon_months or 12)
                self.risk_level = risk_level
                self.preferences = preferences
                self.tax_profile = tax_profile

        strategy_payload = PreviewPayload(
            target_amount=goal_req.target_amount,
            target_date=goal_req.target_date,
            horizon_months=goal_req.horizon_months,
            risk_level=goal_req.risk_level,
            preferences=request.preferences,
            tax_profile=request.tax_profile
        )

        finalize_res = GoalService.finalize_strategy(strategy_payload)
        strategy = finalize_res["strategy"]
        tax_summary = finalize_res["tax_summary"]

        # Step 4: Fetch Candidate Funds for Mix Categories
        mix_dict = {item["category"]: item["allocation_percent"] for item in strategy["fund_category_mix"]}
        
        all_subcategories = []
        for cat in mix_dict.keys():
            if cat == "elss":
                all_subcategories.append("elss")
            else:
                all_subcategories.extend(LEGACY_TO_UNIVERSE_SUBCAT_MAP.get(cat, []))

        all_candidates = []
        if all_subcategories:
            try:
                res = (
                    supabase_admin.table("asset_universe")
                    .select("*, asset_metrics(*)")
                    .eq("instrument_type", "mutual_fund")
                    .in_("subcategory", all_subcategories)
                    .execute()
                )
                all_candidates = res.data or []
            except Exception as e:
                logger.error(f"Failed to fetch candidates in orchestrator: {e}")

        # Step 5: Apply Eligibility Filtering and Count Exclusions
        total_candidates = len(all_candidates)
        eligible_funds = []
        
        insufficient_confidence_count = 0
        missing_score_count = 0
        invalid_data_count = 0

        for row in all_candidates:
            # Check required identifiers and basic fields
            if not row.get("identifier") or not row.get("asset_name"):
                invalid_data_count += 1
                continue

            metrics_list = row.get("asset_metrics") or []
            if not metrics_list:
                missing_score_count += 1
                continue
            
            if isinstance(metrics_list, list):
                metrics_record = metrics_list[0] if len(metrics_list) > 0 else {}
            else:
                metrics_record = metrics_list

            data_confidence = metrics_record.get("data_confidence")
            recommendation_score = metrics_record.get("recommendation_score")
            peer_reliability = metrics_record.get("peer_reliability")

            if data_confidence == "INSUFFICIENT":
                insufficient_confidence_count += 1
                continue

            if recommendation_score is None:
                missing_score_count += 1
                continue

            fund_data = {
                "identifier": row["identifier"],
                "asset_name": row["asset_name"],
                "subcategory": row.get("subcategory"),
                "asset_class": row.get("asset_class"),
                "data_confidence": data_confidence,
                "peer_reliability": peer_reliability or "INSUFFICIENT",
                "recommendation_score": float(recommendation_score),
                "metrics": metrics_record.get("metrics") or {}
            }
            eligible_funds.append(fund_data)

        filtered_summary = {
            "total_candidates": total_candidates,
            "eligible": len(eligible_funds),
            "excluded": {
                "insufficient_confidence": insufficient_confidence_count,
                "missing_score": missing_score_count,
                "invalid_data": invalid_data_count
            }
        }

        # Step 6: Apply Preference Matching and Final Match Score
        # final_match_score = 70% recommendation_score + 30% preference_match_score
        for fund in eligible_funds:
            pref_score = calculate_preference_match(
                fund["subcategory"],
                fund["asset_class"],
                request.preferences
            )
            final_score = round(0.70 * fund["recommendation_score"] + 0.30 * pref_score, 2)
            
            fund["preference_match_score"] = pref_score
            fund["final_match_score"] = final_score

        # Step 7: Deterministic Grouping & Sorting per Category
        max_funds = request.options.max_funds_per_category if request.options else 3
        recommended_funds_list = []

        for category, alloc_pct in mix_dict.items():
            category_subcats = ["elss"] if category == "elss" else LEGACY_TO_UNIVERSE_SUBCAT_MAP.get(category, [])
            cat_funds = [f for f in eligible_funds if f["subcategory"] in category_subcats]

            # Deterministic Sorting:
            # 1. final_match_score DESC
            # 2. recommendation_score DESC
            # 3. data_confidence (HIGH=3 > MEDIUM=2 > LOW=1) DESC
            # 4. peer_reliability (HIGH=2 > LOW=1 > INSUFFICIENT=0) DESC
            # 5. asset_name ASC
            def ranking_key(f):
                f_match = f["final_match_score"]
                rec_score = f["recommendation_score"]
                conf_val = CONFIDENCE_ORDER.get(f["data_confidence"], 0)
                rel_val = RELIABILITY_ORDER.get(f["peer_reliability"], 0)
                name = f["asset_name"] or ""
                return (-f_match, -rec_score, -conf_val, -rel_val, name)

            sorted_cat_funds = sorted(cat_funds, key=ranking_key)
            selected_cat_funds = sorted_cat_funds[:max_funds]

            # Generate explanations using actual metrics
            for f in selected_cat_funds:
                why_recs = build_explanations(f, cat_funds)
                
                # Format to final output schema
                recommended_funds_list.append({
                    "identifier": f["identifier"],
                    "fund_name": f["asset_name"],
                    "category": category,
                    "scores": {
                        "recommendation_score": f["recommendation_score"],
                        "preference_match_score": f["preference_match_score"],
                        "final_match_score": f["final_match_score"]
                    },
                    "confidence": {
                        "data_confidence": f["data_confidence"],
                        "peer_reliability": f["peer_reliability"]
                    },
                    "key_metrics": {
                        "cagr_1y": f["metrics"].get("returns", {}).get("1y"),
                        "cagr_3y": f["metrics"].get("returns", {}).get("3y"),
                        "cagr_5y": f["metrics"].get("returns", {}).get("5y"),
                        "volatility": f["metrics"].get("volatility"),
                        "max_drawdown": f["metrics"].get("max_drawdown"),
                        "sharpe_ratio": f["metrics"].get("sharpe_ratio"),
                        "sortino_ratio": f["metrics"].get("sortino_ratio")
                    },
                    "why_recommended": why_recs
                })

        recommendations = {
            "summary": {
                "categories": len(mix_dict),
                "eligible_funds": len(eligible_funds),
                "filtered_summary": filtered_summary
            },
            "funds": recommended_funds_list
        }

        return {
            "workflow_state": state,
            "feasibility": feasibility_dict,
            "strategy": strategy,
            "tax_summary": tax_summary,
            "recommendations": recommendations,
            "disclaimers": [
                "Mutual fund investments are subject to market risk.",
                "Past performance does not guarantee future returns.",
                "Recommendations are generated using historical and peer-relative metrics."
            ]
        }
