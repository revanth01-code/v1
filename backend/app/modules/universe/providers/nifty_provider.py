"""Fetches historical index data from niftyindices.com (NSE Indices'
official domain). No documented public API, but this endpoint is the
same one used by widely-adopted community tools (nsepython etc.) — same
category of "official domain, undocumented endpoint" as our AMFI source.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.niftyindices.com"
HISTORICAL_URL = f"{BASE_URL}/Backpage.aspx/getHistoricaldatatabletoString"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


class NiftyIndexProvider:
    """One instance per fetch call — matches the simple, stateless style
    of AMFIMutualFundProvider."""

    def fetch_index_history(self, index_name: str, start_date: date, end_date: date) -> list[dict]:
        """Returns [{observation_date: 'YYYY-MM-DD', close_value: float}, ...],
        oldest first. Returns an empty list on any failure — callers must
        treat that as 'no data available', not raise.
        """
        payload = {
            "name": index_name,
            "startDate": start_date.strftime("%d-%b-%Y"),
            "endDate": end_date.strftime("%d-%b-%Y"),
        }

        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                # Prime cookies first — this endpoint requires a session
                # cookie from a prior GET, same pattern documented for
                # this niftyindices.com endpoint.
                client.get(BASE_URL, headers=HEADERS)
                resp = client.post(HISTORICAL_URL, json=payload, headers=HEADERS)
                resp.raise_for_status()
        except Exception as e:
            logger.error(f"Nifty index fetch failed for {index_name}: {e}")
            return []

        try:
            import json as _json
            outer = resp.json()
            # Response shape: {"d": "<json string of records>"}
            records = _json.loads(outer.get("d", "[]"))
        except Exception as e:
            logger.error(f"Failed to parse Nifty index response for {index_name}: {e}")
            return []

        results = []
        for row in records:
            try:
                # niftyindices.com uses 'EOD_CLOSE_INDEX_VAL' and 'EOD_TIMESTAMP' keys
                close_val = float(row.get("EOD_CLOSE_INDEX_VAL", row.get("Close", 0)))
                raw_date = row.get("EOD_TIMESTAMP", row.get("Date", ""))
                obs_date = date.fromisoformat(
                    _normalize_date(raw_date)
                )
                if close_val > 0:
                    results.append({
                        "observation_date": obs_date.isoformat(),
                        "close_value": close_val,
                    })
            except (ValueError, TypeError, KeyError):
                continue

        results.sort(key=lambda r: r["observation_date"])
        return results


def _normalize_date(raw: str) -> str:
    """niftyindices.com dates come as '01-Jan-2020' style strings —
    convert to ISO format."""
    from datetime import datetime
    return datetime.strptime(raw.strip(), "%d-%b-%Y").date().isoformat()