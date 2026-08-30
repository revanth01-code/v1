# backend/app/modules/universe/recommendation/recommendation_service.py
import logging
from typing import Optional, Any
from datetime import datetime, timezone

from app.core.supabase import supabase_admin
from app.core.constants import LEGACY_TO_UNIVERSE_SUBCAT_MAP
from .schemas import UserPreferences
from .compatibility import calculate_preference_match
from .explanation_service import generate_reasons

logger = logging.getLogger(__name__)

CONFIDENCE_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
RELIABILITY_ORDER = {"HIGH": 3, "LOW": 2, "INSUFFICIENT": 1}


class RecommendationService:
    @staticmethod
    def get_recommendations(
        fund_category_mix: dict,
        investment_horizon_years: float,
        risk_level: str,
        preferences: Optional[UserPreferences] = None,
        tax_profile: Optional[Any] = None,
        limit: int = 2
    ) -> list[dict]:
        """Fetches and ranks eligible mutual funds based on peer score, preferences compatibility, and explanations.

        Args:
            fund_category_mix: dict representing the target category allocation percentage.
            investment_horizon_years: float representing goal duration.
            risk_level: str (low/mid/high).
            preferences: Optional UserPreferences payload.
            tax_profile: Optional TaxProfile payload.
            limit: int, max funds to return per category.
        """
        # 1. Map legacy categories to subcategories
        # Expand target subcategories
        all_subcategories = []
        for cat in fund_category_mix.keys():
            if cat == "elss":
                all_subcategories.append("elss")
            else:
                all_subcategories.extend(LEGACY_TO_UNIVERSE_SUBCAT_MAP.get(cat, []))

        if not all_subcategories:
            return []

        # 2. Query asset_universe joined with asset_metrics
        try:
            res = (
                supabase_admin.table("asset_universe")
                .select("*, asset_metrics(*)")
                .eq("instrument_type", "mutual_fund")
                .in_("subcategory", all_subcategories)
                .execute()
            )
            rows = res.data or []
        except Exception as e:
            logger.error(f"Failed to fetch funds for recommendation: {e}")
            rows = []

        # 3. Parse joined rows and filter eligibility
        eligible_funds = []
        for row in rows:
            metrics_list = row.get("asset_metrics") or []
            if not metrics_list:
                continue
            
            # PostgREST may return metrics_list as a dict or a list containing a dict
            if isinstance(metrics_list, list):
                metrics_record = metrics_list[0] if len(metrics_list) > 0 else {}
            else:
                metrics_record = metrics_list

            data_confidence = metrics_record.get("data_confidence")
            recommendation_score = metrics_record.get("recommendation_score")
            peer_reliability = metrics_record.get("peer_reliability")

            # Exclude INSUFFICIENT confidence or NULL recommendation_score
            if data_confidence == "INSUFFICIENT" or recommendation_score is None:
                continue

            fund_data = {
                "identifier": row.get("identifier"),
                "asset_name": row.get("asset_name"),
                "subcategory": row.get("subcategory"),
                "asset_class": row.get("asset_class"),
                "data_confidence": data_confidence,
                "peer_reliability": peer_reliability,
                "recommendation_score": float(recommendation_score),
                "metrics": metrics_record.get("metrics") or {},
            }
            eligible_funds.append(fund_data)

        # 4. Score compatibility and final match
        for fund in eligible_funds:
            pref_score = calculate_preference_match(
                fund["subcategory"],
                fund["asset_class"],
                preferences
            )
            # final_match_score = 70% recommendation_score + 30% preference_match_score
            final_score = round(0.70 * fund["recommendation_score"] + 0.30 * pref_score, 2)
            
            fund["preference_match_score"] = pref_score
            fund["final_match_score"] = final_score
            fund["selection_reasons"] = generate_reasons(
                fund["subcategory"],
                fund["asset_name"],
                fund["recommendation_score"],
                fund["data_confidence"],
                preferences
            )

        # 5. Group and select best matches per category in the mix
        recommendations = []
        for category, alloc_pct in fund_category_mix.items():
            category_subcats = ["elss"] if category == "elss" else LEGACY_TO_UNIVERSE_SUBCAT_MAP.get(category, [])
            
            # Filter funds matching the subcategories of this category
            cat_funds = [f for f in eligible_funds if f["subcategory"] in category_subcats]

            # Sort: recommendation_score DESC, data_confidence DESC, peer_reliability DESC, asset_name ASC
            def sort_key(f):
                score = f["recommendation_score"]
                conf_val = CONFIDENCE_ORDER.get(f["data_confidence"], 0)
                rel_val = RELIABILITY_ORDER.get(f["peer_reliability"], 0)
                name = f["asset_name"] or ""
                return (-score, -conf_val, -rel_val, name)

            sorted_funds = sorted(cat_funds, key=sort_key)

            # Limit candidates
            selected_funds = sorted_funds[:limit]

            # Format the output matching the Pydantic schema
            formatted_funds = []
            for f in selected_funds:
                formatted_funds.append({
                    "identifier": f["identifier"],
                    "asset_name": f["asset_name"],
                    "recommendation_score": f["recommendation_score"],
                    "preference_match_score": f["preference_match_score"],
                    "final_match_score": f["final_match_score"],
                    "data_confidence": f["data_confidence"],
                    "peer_reliability": f["peer_reliability"],
                    "metrics": f["metrics"],
                    "selection_reasons": f["selection_reasons"]
                })

            recommendations.append({
                "category": category,
                "allocation_percent": alloc_pct,
                "funds": formatted_funds
            })

        return recommendations
