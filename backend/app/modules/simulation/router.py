# backend/app/modules/simulation/router.py
from fastapi import APIRouter
from .schemas import SimulationInput, SimulationResult, WhatIfComparisonResponse
from .service import SimulationService

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run", response_model=SimulationResult)
def run_simulation(payload: SimulationInput):
    """Runs a stochastic Monte Carlo simulation using current plan parameters
    and optional stress scenarios.
    """
    return SimulationService.run_simulation(payload)


@router.post("/what-if", response_model=WhatIfComparisonResponse)
def compare_what_if(payload: dict):
    """Runs Monte Carlo simulations for both the current plan and a modified
    what-if plan parameters, returning a side-by-side comparison.
    """
    current_input = SimulationInput(**payload["current_plan"])
    what_if_input = SimulationInput(**payload["what_if_plan"])
    
    current_res = SimulationService.run_simulation(current_input)
    what_if_res = SimulationService.run_simulation(what_if_input)
    
    return WhatIfComparisonResponse(
        current_plan=current_res,
        what_if_plan=what_if_res
    )
