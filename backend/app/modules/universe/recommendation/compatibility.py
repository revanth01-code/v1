# backend/app/modules/universe/recommendation/compatibility.py
from typing import Optional
from .schemas import UserPreferences

def calculate_preference_match(
    subcategory: str,
    asset_class: str,
    preferences: Optional[UserPreferences]
) -> float:
    """Calculates a compatibility match score (0-100) between a fund and user preferences.

    This calculation is deterministic and completely decoupled from recommendation_score.
    """
    if not preferences:
        return 100.0

    scores = []

    # 1. Growth vs Stability Preference
    # growth: prefers equity, dislikes debt
    # stability: prefers debt, dislikes equity
    # balanced: fits both reasonably
    g_vs_s = preferences.growth_vs_stability
    if g_vs_s:
        if g_vs_s == "growth":
            scores.append(100.0 if asset_class == "equity" else 30.0)
        elif g_vs_s == "stability":
            scores.append(100.0 if asset_class == "debt" else 30.0)
        elif g_vs_s == "balanced":
            scores.append(80.0)

    # 2. Liquidity Preference vs Lock-in Restrictions
    # ELSS funds have a mandatory 3-year lock-in period.
    liq = preferences.liquidity_preference
    if liq:
        if subcategory == "elss":
            if liq == "high":
                scores.append(10.0)
            elif liq == "medium":
                scores.append(50.0)
            elif liq == "low":
                scores.append(100.0)
        else:
            # Liquid or Overnight funds represent maximum liquidity
            if subcategory in ["liquid", "overnight"] and liq == "high":
                scores.append(100.0)
            else:
                scores.append(90.0)

    # 3. Tax Optimization & Lock-in Acceptance (ELSS rule)
    # ELSS is only appropriate if the user explicitly wants tax optimization
    # AND accepts the 3-year lock-in constraint.
    tax_opt = preferences.tax_optimization_preference
    lock_in = preferences.accept_lock_in
    
    if subcategory == "elss":
        if tax_opt is True and lock_in is True:
            scores.append(100.0)
        else:
            # ELSS gets 0 compatibility if they don't want tax optimization or reject lock-in
            scores.append(0.0)

    # 4. Investment Style
    # aggressive: high risk/reward (mid/small cap equity)
    # conservative: capital preservation (debt/large cap)
    # balanced: core growth and yield (large/flexi cap, moderate debt)
    style = preferences.investment_style
    if style:
        if style == "aggressive":
            if subcategory in ["mid_cap", "small_cap"]:
                scores.append(100.0)
            elif subcategory in ["large_cap", "flexi_cap"]:
                scores.append(70.0)
            else:
                scores.append(20.0)
        elif style == "conservative":
            if asset_class == "debt":
                scores.append(100.0)
            elif subcategory == "large_cap":
                scores.append(60.0)
            else:
                scores.append(10.0)
        elif style == "balanced":
            if subcategory in ["large_cap", "flexi_cap"]:
                scores.append(100.0)
            elif asset_class == "debt":
                scores.append(80.0)
            else:
                scores.append(50.0)

    if not scores:
        return 100.0

    return round(sum(scores) / len(scores), 2)
