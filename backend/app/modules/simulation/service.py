# backend/app/modules/simulation/service.py
from datetime import date
import random
import statistics
from app.lib.date_utils import months_between
from .schemas import SimulationInput, SimulationResult

# Core asset assumptions
EQUITY_RETURN = 14.0       # % p.a.
EQUITY_VOLATILITY = 18.0   # % p.a.
DEBT_RETURN = 6.0          # % p.a.
DEBT_VOLATILITY = 2.0      # % p.a.

RISK_ALLOCATION_MAP = {
    "low": {"equity": 20.0, "debt": 80.0},
    "mid": {"equity": 50.0, "debt": 50.0},
    "high": {"equity": 80.0, "debt": 20.0},
}


def get_allocated_metrics(equity_pct: float) -> tuple[float, float]:
    """Calculates expected return and volatility using linear interpolation."""
    eq_ratio = equity_pct / 100.0
    expected_return = eq_ratio * EQUITY_RETURN + (1.0 - eq_ratio) * DEBT_RETURN
    volatility = eq_ratio * EQUITY_VOLATILITY + (1.0 - eq_ratio) * DEBT_VOLATILITY
    return expected_return, volatility


class SimulationService:
    @staticmethod
    def run_simulation(payload: SimulationInput, seed: int = 42) -> SimulationResult:
        random.seed(seed)
        
        # Calculate goal horizon months
        target_dt = date.fromisoformat(payload.target_date)
        months = max(months_between(date.today(), target_dt), 1)
        years = months / 12.0
        
        # Resolve return & volatility based on inputs
        if payload.risk_level == "custom":
            equity = payload.equity_pct if payload.equity_pct is not None else 50.0
            expected_return, volatility = get_allocated_metrics(equity)
        else:
            alloc = RISK_ALLOCATION_MAP.get(payload.risk_level, {"equity": 50.0, "debt": 50.0})
            expected_return, volatility = get_allocated_metrics(alloc["equity"])
            
        # Target amounts & inflation
        inflation_rate = payload.inflation_pct
        target_amount = payload.target_amount
        lumpsum = payload.lumpsum_amount
        monthly_contrib = payload.monthly_contribution
        
        # Apply Stress Scenarios Modifications
        market_shock_month = 0
        market_shock_pct = 0.0
        low_return_duration = 0
        low_return_shock_pct = 0.0
        vol_multiplier = 1.0
        vol_multiplier_duration = 0
        
        sip_pause_start = payload.sip_pause_start
        sip_pause_duration = payload.sip_pause_duration
        sip_reduce_pct = payload.sip_reduce_pct
        sip_reduce_start = payload.sip_reduce_start
        sip_reduce_duration = payload.sip_reduce_duration
        
        if payload.stress_scenario == "market_downturn":
            # Shock 1: Immediate -20% drop in Month 1
            market_shock_month = 1
            market_shock_pct = -20.0
            # Shock 2: Volatility increases 1.5x for first 12 months
            vol_multiplier = 1.5
            vol_multiplier_duration = min(12, months)
        elif payload.stress_scenario == "high_inflation":
            # Add +3% to inflation
            inflation_rate += 3.0
        elif payload.stress_scenario == "low_return":
            # Return drops by 3% for the first 24 months
            low_return_duration = min(24, months)
            low_return_shock_pct = 3.0
        elif payload.stress_scenario == "sip_pause":
            # Pause SIP for the first 12 months
            sip_pause_start = 1
            sip_pause_duration = min(12, months)
        elif payload.stress_scenario == "reduced_income":
            # Reduce SIP by 50% for the first 12 months
            sip_reduce_start = 1
            sip_reduce_duration = min(12, months)
            sip_reduce_pct = 50.0
        elif payload.stress_scenario == "increased_cost":
            # Goal target increases by 20%
            target_amount *= 1.20

        # Run trials
        trials = 1000
        final_corpuses = []
        
        # Determine base monthly returns and standard deviations
        monthly_ret_base = expected_return / 12.0 / 100.0
        monthly_vol_base = volatility / (12.0 ** 0.5) / 100.0
        
        for _ in range(trials):
            corpus = lumpsum
            for m in range(1, months + 1):
                # Apply market shock
                if m == market_shock_month:
                    corpus *= (1.0 + market_shock_pct / 100.0)
                    
                # Adjust return if under stress
                m_ret = monthly_ret_base
                if m <= low_return_duration:
                    m_ret = (expected_return - low_return_shock_pct) / 12.0 / 100.0
                    
                # Adjust volatility if under stress
                m_vol = monthly_vol_base
                if m <= vol_multiplier_duration:
                    m_vol = (volatility * vol_multiplier) / (12.0 ** 0.5) / 100.0
                    
                # Compounding monthly return with random normal draw
                z = random.gauss(0.0, 1.0)
                r_t = m_ret + m_vol * z
                
                # Determine SIP contribution
                contrib = monthly_contrib
                if sip_pause_duration > 0 and sip_pause_start <= m < (sip_pause_start + sip_pause_duration):
                    contrib = 0.0
                elif sip_reduce_duration > 0 and sip_reduce_start <= m < (sip_reduce_start + sip_reduce_duration):
                    contrib = monthly_contrib * (1.0 - sip_reduce_pct / 100.0)
                    
                # Compounding (Annuity due)
                corpus = (corpus + contrib) * (1.0 + r_t)
                
            final_corpuses.append(max(corpus, 0.0))
            
        final_corpuses.sort()
        
        # Summary statistics
        mean_corpus = statistics.mean(final_corpuses)
        median_corpus = statistics.median(final_corpuses)
        
        p10 = final_corpuses[int(trials * 0.1)]
        p90 = final_corpuses[int(trials * 0.90) - 1]
        
        # Inflation adjusted target cost at timeline end
        adjusted_target = target_amount * ((1 + inflation_rate / 100.0) ** years)
        
        # Success and Shortfalls
        success_count = sum(1 for c in final_corpuses if c >= adjusted_target)
        prob_success = (success_count / trials) * 100.0
        prob_shortfall = 100.0 - prob_success
        
        shortfalls = [max(adjusted_target - c, 0.0) for c in final_corpuses if c < adjusted_target]
        if shortfalls:
            median_shortfall = statistics.median(shortfalls)
            expected_shortfall = statistics.mean(shortfalls)
        else:
            median_shortfall = 0.0
            expected_shortfall = 0.0
            
        # Inflation-adjusted purchasing power (in today's terms)
        purchasing_power_median = median_corpus / ((1.0 + inflation_rate / 100.0) ** years)
        
        # Dynamic, simple text explanation of outcomes
        if prob_success >= 85:
            message = (
                f"Your plan has an excellent success rate of {prob_success:.0f}%. "
                f"Even in a weak market, your downside projection is {formatINR(p10)}. "
                f"This plan is highly secure under current assumptions."
            )
        elif prob_success >= 60:
            message = (
                f"Your plan is moderately on track with a {prob_success:.0f}% success rate. "
                f"In case of a shortfall, the average gap is estimated around {formatINR(expected_shortfall)}. "
                f"A minor increase in monthly savings will improve reliability."
            )
        elif prob_success >= 30:
            message = (
                f"Your plan is At Risk (success rate is {prob_success:.0f}%). "
                f"There is a {prob_shortfall:.0f}% probability of shortfall, with an expected deficit of {formatINR(expected_shortfall)}. "
                f"Consider adjusting parameters."
            )
        else:
            message = (
                f"This goal is Unlikely to succeed (success probability is only {prob_success:.0f}%). "
                f"Your estimated median corpus is {formatINR(median_corpus)}, leaving a funding gap of {formatINR(median_shortfall)}. "
                f"Timeline extension or higher contributions are strongly advised."
            )
            
        return SimulationResult(
            median_corpus=round(median_corpus, 2),
            mean_corpus=round(mean_corpus, 2),
            downside_percentile_10=round(p10, 2),
            upside_percentile_90=round(p90, 2),
            prob_success=round(prob_success, 2),
            prob_shortfall=round(prob_shortfall, 2),
            median_shortfall=round(median_shortfall, 2),
            expected_shortfall=round(expected_shortfall, 2),
            purchasing_power_median=round(purchasing_power_median, 2),
            adjusted_target=round(adjusted_target, 2),
            message=message,
        )


def formatINR(number: float) -> str:
    """Helper to format numbers as Indian Rupee style string for messages."""
    return f"₹{number:,.2f}"
