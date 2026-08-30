# backend/app/modules/universe/recommendation/explanation_service.py
from typing import Optional
from .schemas import UserPreferences

def generate_reasons(
    subcategory: str,
    asset_name: str,
    recommendation_score: float,
    data_confidence: str,
    preferences: Optional[UserPreferences]
) -> list[str]:
    """Generates a list of deterministic explanation strings for a fund recommendation.

    Strictly uses actual metrics and preferences, avoiding vague or generic statements.
    """
    reasons = []
    subcat_title = subcategory.replace("_", " ").title()

    # 1. Performance Rank Explanation
    if recommendation_score is not None:
        if recommendation_score >= 80.0:
            reasons.append(f"This fund ranks in the top group of its {subcat_title} peers based on risk-adjusted performance.")
        elif recommendation_score >= 50.0:
            reasons.append(f"This fund ranks in the upper-middle tier of its {subcat_title} peers based on risk-adjusted performance.")
        else:
            reasons.append(f"Highest-ranked eligible fund within the selected category based on the current evaluation model.")

    # 2. Data Confidence Explanation
    if data_confidence == "HIGH":
        reasons.append("This recommendation has HIGH data confidence based on sufficient historical observations and recent data.")
    elif data_confidence == "MEDIUM":
        reasons.append("This recommendation has MEDIUM data confidence with acceptable historical observation coverage.")
    elif data_confidence == "LOW":
        reasons.append("This recommendation has LOW data confidence due to limited historical observation duration.")

    # 3. Preference Compatibility Explanation
    if preferences:
        # Growth vs Stability
        if preferences.growth_vs_stability == "growth" and subcategory in ["large_cap", "flexi_cap", "mid_cap", "small_cap"]:
            reasons.append("This fund matches your growth preference and long investment horizon.")
        elif preferences.growth_vs_stability == "stability" and subcategory in ["liquid", "overnight", "money_market"]:
            reasons.append("This fund matches your stability preference and capital preservation goal.")

        # ELSS / Tax Optimization Explanation
        if subcategory == "elss":
            if preferences.tax_optimization_preference is True and preferences.accept_lock_in is True:
                reasons.append("ELSS is being considered because you selected tax optimization and indicated that you can accept a 3-year lock-in.")

    # 4. Tax Isolation Statement
    reasons.append("Tax optimization was considered separately and did not influence the fund's quality score.")

    return reasons
