# backend/app/modules/simulation/tests/test_simulation.py
import pytest
from datetime import date, timedelta
from app.modules.simulation.schemas import SimulationInput
from app.modules.simulation.service import SimulationService


def make_sim_input(**overrides):
    target_date = (date.today() + timedelta(days=365 * 10)).isoformat()  # 10 years
    defaults = dict(
        lumpsum_amount=100000.0,
        monthly_contribution=10000.0,
        target_amount=2000000.0,
        target_date=target_date,
        risk_level="mid",
        inflation_pct=6.0,
        stress_scenario="none"
    )
    defaults.update(overrides)
    return SimulationInput(**defaults)


class TestMonteCarloEngine:
    def test_conservative_strategy(self):
        payload = make_sim_input(risk_level="low")
        res = SimulationService.run_simulation(payload)
        
        assert res.median_corpus > 0
        assert res.mean_corpus > 0
        assert res.downside_percentile_10 < res.upside_percentile_90
        assert 0 <= res.prob_success <= 100
        assert res.adjusted_target > payload.target_amount

    def test_aggressive_strategy(self):
        payload = make_sim_input(risk_level="high")
        res = SimulationService.run_simulation(payload)
        
        assert res.median_corpus > 0
        # Aggressive expected returns are higher, so median corpus should typically exceed conservative
        cons_payload = make_sim_input(risk_level="low")
        cons_res = SimulationService.run_simulation(cons_payload)
        assert res.median_corpus > cons_res.median_corpus

    def test_sip_pause_reduces_corpus(self):
        baseline = make_sim_input(stress_scenario="none")
        paused = make_sim_input(stress_scenario="sip_pause")
        
        res_base = SimulationService.run_simulation(baseline)
        res_pause = SimulationService.run_simulation(paused)
        
        # Pausing SIP for first 12 months must result in a lower median corpus
        assert res_pause.median_corpus < res_base.median_corpus

    def test_high_inflation_increases_target(self):
        baseline = make_sim_input(stress_scenario="none")
        stressed = make_sim_input(stress_scenario="high_inflation")
        
        res_base = SimulationService.run_simulation(baseline)
        res_stress = SimulationService.run_simulation(stressed)
        
        # Target adjusted for high inflation scenario (6% + 3% = 9% p.a.) must be greater
        assert res_stress.adjusted_target > res_base.adjusted_target

    def test_short_term_vs_long_term(self):
        st_date = (date.today() + timedelta(days=365)).isoformat()  # 1 year
        st_payload = make_sim_input(target_date=st_date)
        lt_payload = make_sim_input()  # 10 years
        
        res_st = SimulationService.run_simulation(st_payload)
        res_lt = SimulationService.run_simulation(lt_payload)
        
        assert res_st.median_corpus < res_lt.median_corpus
