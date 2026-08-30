# backend/app/modules/recommendation/explanation_builder.py

def build_explanations(fund: dict, category_funds: list[dict]) -> list[str]:
    """Generates deterministic selection reasons based on actual performance metrics and category comparisons.

    Avoids vague statements or future return predictions.
    """
    reasons = []
    
    score = fund.get("recommendation_score")
    confidence = fund.get("data_confidence")
    metrics = fund.get("metrics") or {}
    
    # Calculate category averages dynamically from the candidate pool
    valid_scores = [f.get("recommendation_score") for f in category_funds if f.get("recommendation_score") is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 50.0
    
    valid_vols = [
        f.get("metrics", {}).get("volatility")
        for f in category_funds
        if f.get("metrics", {}).get("volatility") is not None
    ]
    avg_vol = sum(valid_vols) / len(valid_vols) if valid_vols else None
    
    # 1. Ranks highly or above average explanation
    if score is not None:
        if score >= 80.0:
            reasons.append("This fund ranks highly within its category because it has strong risk-adjusted returns compared with its peers.")
        elif score > avg_score:
            reasons.append("This fund performs above the category average based on peer-relative evaluation.")
            
    # 2. Sharpe ratio indicator
    sharpe = metrics.get("sharpe_ratio")
    if sharpe is not None and sharpe > 1.0:
        reasons.append("Strong Sharpe ratio indicates superior risk-adjusted performance.")
        
    # 3. Volatility comparison
    vol = metrics.get("volatility")
    if vol is not None and avg_vol is not None and vol < avg_vol:
        reasons.append("Lower relative volatility compared to the category average indicates better stability.")
        
    # 4. Data confidence indicator
    if confidence == "HIGH":
        reasons.append("This recommendation has HIGH data confidence based on sufficient historical observations and recent data.")
        
    return reasons
