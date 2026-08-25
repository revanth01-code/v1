from app.core.constants import SHORT_TERM_MONTHS_THRESHOLD
from .schemas import GuardrailResult


def derive_term_type(months: int) -> str:
    return "short_term" if months < SHORT_TERM_MONTHS_THRESHOLD else "long_term"


def validate_risk_for_term(months: int, risk_level: str) -> GuardrailResult:
    """Guardrail: goals under 3 years shouldn't be Mid/High risk — equity
    volatility could shrink capital right when the user needs it."""
    if months < SHORT_TERM_MONTHS_THRESHOLD and risk_level in ("mid", "high"):
        return GuardrailResult(
            allowed=False,
            warning=(
                "Goals under 3 years shouldn't be in equity-heavy funds — market "
                "volatility could shrink your capital right when you need it. "
                "Consider 'Low' risk for this goal."
            ),
        )
    return GuardrailResult(allowed=True)