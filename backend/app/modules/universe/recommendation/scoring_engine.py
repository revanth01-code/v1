# backend/app/modules/universe/recommendation/scoring_engine.py
import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Centralized scoring weights for mutual fund metrics
DEFAULT_WEIGHTS = {
    "cagr_5y": 0.30,
    "sharpe": 0.25,
    "sortino": 0.20,
    "max_drawdown": 0.15,
    "volatility": 0.10,
}


def _compute_percentile_rank(value: float, all_values: list[float], reverse: bool = False) -> float:
    """Computes the percentile rank of a value in a collection of values (0.0 to 1.0).

    Handles ties symmetrically using fractional ranking.
    
    Args:
        value: The value to rank.
        all_values: The list of peer values.
        reverse: If True, lower is better (e.g. volatility). 
                 If False, higher is better (e.g. CAGR, Sharpe).
    """
    clean_values = [v for v in all_values if v is not None]
    n = len(clean_values)
    if n == 0:
        return 0.0
    if n == 1:
        return 1.0

    if not reverse:
        better_count = sum(1 for v in clean_values if v < value)
    else:
        better_count = sum(1 for v in clean_values if v > value)

    equal_count = sum(1 for v in clean_values if v == value)

    # Fractional rank formula: (better + 0.5 * (equal - 1)) / (n - 1)
    percentile = (better_count + 0.5 * (equal_count - 1)) / (n - 1)
    return percentile


class RecommendationScoringEngine:
    @staticmethod
    def calculate_scores(funds: list[dict], weights: Optional[dict] = None) -> list[dict]:
        """Calculates a deterministic recommendation score (0-100) for eligible funds.

        Expects a collection of peer funds belonging to the same subcategory.

        Args:
            funds: List of dicts, each representing a fund:
                   {
                       "identifier": str,
                       "subcategory": str,
                       "metrics": dict,
                       "data_confidence": str
                   }
            weights: Optional custom weights dict to override DEFAULT_WEIGHTS.
        
        Returns:
            List of dicts with updated 'recommendation_score' keys (float or None).
        """
        if not funds:
            return []

        active_weights = weights or DEFAULT_WEIGHTS

        # Filter eligible funds (data_confidence != 'INSUFFICIENT')
        eligible_funds = [f for f in funds if f.get("data_confidence") != "INSUFFICIENT"]

        # Collect metrics across all eligible funds in this peer group to compute percentiles
        cagr_5y_vals = []
        sharpe_vals = []
        sortino_vals = []
        drawdown_vals = []
        volatility_vals = []

        for f in eligible_funds:
            m = f.get("metrics") or {}
            
            # Extract 5y CAGR
            cagr = m.get("returns", {}).get("5y") if isinstance(m.get("returns"), dict) else None
            if cagr is not None:
                cagr_5y_vals.append(float(cagr))

            # Extract Sharpe
            sharpe = m.get("sharpe_ratio")
            if sharpe is not None:
                sharpe_vals.append(float(sharpe))

            # Extract Sortino
            sortino = m.get("sortino_ratio")
            if sortino is not None:
                sortino_vals.append(float(sortino))

            # Extract Max Drawdown (normalize to negative value: -0.10 is better than -0.40)
            dd = m.get("max_drawdown")
            if dd is not None:
                dd_val = float(dd)
                drawdown_vals.append(dd_val if dd_val <= 0 else -dd_val)

            # Extract Volatility
            vol = m.get("volatility")
            if vol is not None:
                volatility_vals.append(float(vol))

        # Calculate scores for all funds
        result = []
        for f in funds:
            # Copy fund structure
            fund_res = dict(f)
            
            # INSUFFICIENT data confidence always gets None/NULL score
            if f.get("data_confidence") == "INSUFFICIENT":
                fund_res["recommendation_score"] = None
                result.append(fund_res)
                continue

            m = f.get("metrics") or {}
            cagr = m.get("returns", {}).get("5y") if isinstance(m.get("returns"), dict) else None
            sharpe = m.get("sharpe_ratio")
            sortino = m.get("sortino_ratio")
            dd = m.get("max_drawdown")
            vol = m.get("volatility")

            fund_percentiles = {}
            
            if cagr is not None:
                fund_percentiles["cagr_5y"] = _compute_percentile_rank(float(cagr), cagr_5y_vals, reverse=False)
            if sharpe is not None:
                fund_percentiles["sharpe"] = _compute_percentile_rank(float(sharpe), sharpe_vals, reverse=False)
            if sortino is not None:
                fund_percentiles["sortino"] = _compute_percentile_rank(float(sortino), sortino_vals, reverse=False)
            if dd is not None:
                dd_val = float(dd)
                fund_percentiles["max_drawdown"] = _compute_percentile_rank(
                    dd_val if dd_val <= 0 else -dd_val, drawdown_vals, reverse=False
                )
            if vol is not None:
                fund_percentiles["volatility"] = _compute_percentile_rank(float(vol), volatility_vals, reverse=True)

            # Require at least 3 usable metrics for score eligibility
            if len(fund_percentiles) < 3:
                fund_res["recommendation_score"] = None
                result.append(fund_res)
                continue

            # Re-normalize weights among available metrics
            available_weight_sum = sum(active_weights[k] for k in fund_percentiles.keys())
            if available_weight_sum <= 0:
                fund_res["recommendation_score"] = None
                result.append(fund_res)
                continue

            weighted_sum = 0.0
            for k, pct in fund_percentiles.items():
                norm_weight = active_weights[k] / available_weight_sum
                weighted_sum += norm_weight * pct

            # Scale to 0-100 range and round to 1 decimal place
            fund_res["recommendation_score"] = round(weighted_sum * 100, 1)
            result.append(fund_res)

        return result
