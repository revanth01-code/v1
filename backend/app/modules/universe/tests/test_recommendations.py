# backend/app/modules/universe/tests/test_recommendations.py
import pytest
from app.modules.universe.recommendation.scoring_engine import RecommendationScoringEngine


def test_higher_cagr_produces_better_score_when_others_similar():
    # Two eligible funds with identical metrics except cagr
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.15},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.15
        }
    }
    fund2 = {
        "identifier": "fund2",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.10},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.15
        }
    }
    res = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    score1 = next(x["recommendation_score"] for x in res if x["identifier"] == "fund1")
    score2 = next(x["recommendation_score"] for x in res if x["identifier"] == "fund2")
    assert score1 > score2


def test_better_sharpe_produces_better_score():
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 1.5,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.15
        }
    }
    fund2 = {
        "identifier": "fund2",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 0.8,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.15
        }
    }
    res = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    score1 = next(x["recommendation_score"] for x in res if x["identifier"] == "fund1")
    score2 = next(x["recommendation_score"] for x in res if x["identifier"] == "fund2")
    assert score1 > score2


def test_lower_volatility_produces_better_score():
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.08,  # Lower (better)
            "max_drawdown": -0.15
        }
    }
    fund2 = {
        "identifier": "fund2",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.18,  # Higher
            "max_drawdown": -0.15
        }
    }
    res = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    score1 = next(x["recommendation_score"] for x in res if x["identifier"] == "fund1")
    score2 = next(x["recommendation_score"] for x in res if x["identifier"] == "fund2")
    assert score1 > score2


def test_smaller_drawdown_produces_better_score():
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.05  # Smaller drawdown (better)
        }
    }
    fund2 = {
        "identifier": "fund2",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.25  # Larger drawdown
        }
    }
    res = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    score1 = next(x["recommendation_score"] for x in res if x["identifier"] == "fund1")
    score2 = next(x["recommendation_score"] for x in res if x["identifier"] == "fund2")
    assert score1 > score2


def test_insufficient_confidence_receives_null_score():
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "INSUFFICIENT",
        "metrics": {
            "returns": {"5y": 0.15},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.15
        }
    }
    res = RecommendationScoringEngine.calculate_scores([fund1])
    assert res[0]["recommendation_score"] is None


def test_fewer_than_three_usable_metrics_receives_null_score():
    # Only 2 metrics: 5y returns and sharpe
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 1.2
        }
    }
    fund2 = {
        "identifier": "fund2",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.10},
            "sharpe_ratio": 1.0
        }
    }
    res = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    assert res[0]["recommendation_score"] is None
    assert res[1]["recommendation_score"] is None


def test_funds_compared_only_against_peers_in_same_subcategory():
    # Note: calculate_scores expects the caller to group the peers first.
    # But if we pass multiple items, they are evaluated relative to the group passed in.
    # To test that grouping holds correct calculations, we can show that passing different 
    # peer sets alters the percentile and therefore the score.
    fund = {
        "identifier": "target",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 1.0,
            "sortino_ratio": 1.0,
            "volatility": 0.10,
            "max_drawdown": -0.10
        }
    }
    # Peer set A: very high performers (target will have low percentiles)
    peers_a = [
        fund,
        {
            "identifier": "peer_a1",
            "subcategory": "large_cap",
            "data_confidence": "HIGH",
            "metrics": {
                "returns": {"5y": 0.20},
                "sharpe_ratio": 2.0,
                "sortino_ratio": 2.0,
                "volatility": 0.05,
                "max_drawdown": -0.02
            }
        }
    ]
    # Peer set B: very low performers (target will have high percentiles)
    peers_b = [
        fund,
        {
            "identifier": "peer_b1",
            "subcategory": "large_cap",
            "data_confidence": "HIGH",
            "metrics": {
                "returns": {"5y": 0.05},
                "sharpe_ratio": 0.2,
                "sortino_ratio": 0.2,
                "volatility": 0.25,
                "max_drawdown": -0.30
            }
        }
    ]
    
    score_a = next(x["recommendation_score"] for x in RecommendationScoringEngine.calculate_scores(peers_a) if x["identifier"] == "target")
    score_b = next(x["recommendation_score"] for x in RecommendationScoringEngine.calculate_scores(peers_b) if x["identifier"] == "target")
    
    # Score in set B (poor peers) should be much higher than in set A (top peers)
    assert score_b > score_a


def test_scores_stay_between_zero_and_hundred():
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.15},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.15
        }
    }
    fund2 = {
        "identifier": "fund2",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.10},
            "sharpe_ratio": 0.8,
            "sortino_ratio": 1.0,
            "volatility": 0.18,
            "max_drawdown": -0.25
        }
    }
    res = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    for f in res:
        score = f["recommendation_score"]
        if score is not None:
            assert 0.0 <= score <= 100.0


def test_missing_metric_renormalizes_weights():
    # fund1 is missing volatility but has the other 4 metrics
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.12},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "max_drawdown": -0.15
            # Missing volatility
        }
    }
    fund2 = {
        "identifier": "fund2",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.10},
            "sharpe_ratio": 0.8,
            "sortino_ratio": 1.0,
            "max_drawdown": -0.25
            # Missing volatility
        }
    }
    res = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    score = res[0]["recommendation_score"]
    assert score is not None
    assert 0.0 <= score <= 100.0


def test_same_input_always_produces_same_score():
    fund1 = {
        "identifier": "fund1",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.15},
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "volatility": 0.12,
            "max_drawdown": -0.15
        }
    }
    fund2 = {
        "identifier": "fund2",
        "subcategory": "large_cap",
        "data_confidence": "HIGH",
        "metrics": {
            "returns": {"5y": 0.10},
            "sharpe_ratio": 0.8,
            "sortino_ratio": 1.0,
            "volatility": 0.18,
            "max_drawdown": -0.25
        }
    }
    
    res1 = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    res2 = RecommendationScoringEngine.calculate_scores([fund1, fund2])
    
    assert res1[0]["recommendation_score"] == res2[0]["recommendation_score"]
    assert res1[1]["recommendation_score"] == res2[1]["recommendation_score"]
