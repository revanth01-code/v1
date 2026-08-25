import httpx
from app.core.constants import MFAPI_BASE_URL


def fetch_historical_nav(scheme_code: str) -> list[dict]:
    """Returns [{date, nav}, ...] for a single scheme, most recent first.
    Best-effort — MFAPI is a free/unofficial service with no SLA, so
    callers should handle failures gracefully rather than treat this as
    guaranteed to succeed."""
    resp = httpx.get(f"{MFAPI_BASE_URL}/{scheme_code}", timeout=15.0)
    resp.raise_for_status()
    body = resp.json()
    return [{"date": row["date"], "nav": float(row["nav"])} for row in body.get("data", [])]