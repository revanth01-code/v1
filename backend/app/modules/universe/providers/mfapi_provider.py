# backend/app/modules/universe/providers/mfapi_provider.py
from datetime import datetime
import logging
import os
import time
import httpx
from app.core.constants import MFAPI_BASE_URL

logger = logging.getLogger(__name__)

# Configurable throttling interval in milliseconds (defaults to 200ms)
THROTTLE_MS = float(os.getenv("MFAPI_THROTTLE_MS", "200"))
THROTTLE_SEC = THROTTLE_MS / 1000.0


class MFAPIHistoryProvider:
    @staticmethod
    def fetch_history(scheme_code: str) -> list[dict]:
        """Fetches historical daily NAV records from api.mfapi.in.

        Supports exponential backoff retries on transient network
        timeouts.
        """
        # Rate limiting sleep call
        time.sleep(THROTTLE_SEC)

        url = f"{MFAPI_BASE_URL}/{scheme_code}"
        max_retries = 3
        raw_data = []
        
        for attempt in range(max_retries):
            try:
                # 15-second response timeout
                resp = httpx.get(url, timeout=15.0)
                resp.raise_for_status()
                body = resp.json()
                raw_data = body.get("data", [])
                break # Success!
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt == max_retries - 1:
                    logger.error(f"MFAPI history fetch failed after {max_retries} attempts for scheme {scheme_code}: {e}")
                    return []
                # Exponential backoff delay: 2s, 4s, 8s...
                sleep_duration = 1.0 * (2 ** attempt)
                logger.warning(f"MFAPI attempt {attempt + 1} failed for {scheme_code}. Retrying in {sleep_duration}s...")
                time.sleep(sleep_duration)
            except Exception as e:
                logger.error(f"Unexpected parser failure for {scheme_code}: {e}")
                return []

        results = []
        for row in raw_data:
            date_str = row.get("date")
            nav_str = row.get("nav")
            if not date_str or not nav_str:
                continue

            try:
                # Convert "DD-MM-YYYY" to ISO format "YYYY-MM-DD"
                dt = datetime.strptime(date_str.strip(), "%d-%m-%Y")
                iso_date = dt.strftime("%Y-%m-%d")
                price = float(nav_str.strip())
                results.append({
                    "observation_date": iso_date,
                    "price_or_nav": price
                })
            except Exception as ex:
                logger.debug(f"Skipping malformed historical NAV point: {ex}")
                continue

        # Sort observations oldest to newest
        results.sort(key=lambda x: x["observation_date"])
        return results
