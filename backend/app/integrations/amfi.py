# backend/app/integrations/amfi.py
import logging
import time
from typing import Optional

import httpx
from app.core.config import settings
from app.core.constants import AMFI_NAV_URL

logger = logging.getLogger(__name__)

# Custom exceptions for robust error handling and caller differentiation
class AMFIProviderError(Exception):
    """Base exception for all AMFI provider errors."""
    pass

class AMFINetworkError(AMFIProviderError):
    """Raised when a network failure occurs (DNS issues, connection refused, etc.)."""
    pass

class AMFITimeoutError(AMFIProviderError):
    """Raised when the HTTP request times out."""
    pass

class AMFIInvalidResponseError(AMFIProviderError):
    """Raised when AMFI returns an invalid response (non-200 status, empty response)."""
    pass

class AMFIParsingError(AMFIProviderError):
    """Raised when there is a critical failure parsing the AMFI document."""
    pass


# AMFI's raw category text -> our simplified 4-bucket system. Match order
# matters: check more specific terms (e.g. "flexi cap") before generic ones.
CATEGORY_KEYWORD_MAP = [
    (["large cap"], "largecap"),
    (["flexi cap", "multi cap"], "flexicap"),
    (["mid cap", "small cap"], "midcap"),
    (
        ["debt", "liquid", "overnight", "gilt", "money market", "ultra short",
         "short duration", "corporate bond", "banking and psu"],
        "debt",
    ),
]

CATEGORY_MAP_UNIVERSE = {
    "large cap fund": ("equity", "large_cap", "mutual_fund", "equity", "in_equity_standard_v1"),
    "flexi cap fund": ("equity", "flexi_cap", "mutual_fund", "equity", "in_equity_standard_v1"),
    "mid cap fund": ("equity", "mid_cap", "mutual_fund", "equity", "in_equity_standard_v1"),
    "small cap fund": ("equity", "small_cap", "mutual_fund", "equity", "in_equity_standard_v1"),
    "elss": ("equity", "elss", "mutual_fund", "equity", "in_equity_standard_v1"),
    "index funds": ("equity", "index_fund", "mutual_fund", "equity", "in_equity_standard_v1"),
    "liquid fund": ("debt", "liquid", "mutual_fund", "debt", "in_debt_standard_v1"),
    "overnight fund": ("debt", "overnight", "mutual_fund", "debt", "in_debt_standard_v1"),
    "ultra short duration fund": ("debt", "ultra_short", "mutual_fund", "debt", "in_debt_standard_v1"),
    "money market fund": ("debt", "money_market", "mutual_fund", "debt", "in_debt_standard_v1"),
    "short duration fund": ("debt", "short_duration", "mutual_fund", "debt", "in_debt_standard_v1"),
    "gold etf": ("diversifier", "gold_etf", "etf", "gold", "in_gold_standard_v1"),
}


def normalize_category(category_raw: str) -> str | None:
    """Maps AMFI's raw section-header text to one of our 4 legacy fund categories.
    Returns None for categories we don't support in v1 (sectoral, hybrid,
    ELSS, index funds, etc.) — those are simply excluded from the cache."""
    text = category_raw.lower()
    for keywords, bucket in CATEGORY_KEYWORD_MAP:
        if any(kw in text for kw in keywords):
            return bucket
    return None


def resolve_universe_category(category_header: str, scheme_name: str) -> Optional[tuple[str, str, str, str, Optional[str]]]:
    """Maps category header and scheme name to universe metadata tuple:
    (asset_class, subcategory, instrument_type, tax_classification, tax_rule_key)
    
    Returns None if the category is unsupported or unmapped.
    """
    header_lower = category_header.lower()

    # Check for direct maps in headers first
    for amfi_name, mapped in CATEGORY_MAP_UNIVERSE.items():
        if amfi_name in header_lower:
            return mapped

    # Check other ETFs header
    if "other etfs" in header_lower:
        if "gold" in scheme_name.lower():
            return ("diversifier", "gold_etf", "etf", "gold", "in_gold_standard_v1")
        return ("equity", "etf", "etf", "equity", "in_equity_standard_v1")

    # Log unmapped category headers for operational transparency
    logger.debug(f"AMFI Category header unmapped/unsupported: {category_header}")
    return None


def is_direct_growth_plan(scheme_name: str, plan_str: str = "", option_str: str = "") -> bool:
    """Checks if a scheme is a Direct Growth plan.
    Supports checking both from a single scheme_name or from separate plan and option columns.
    """
    if plan_str or option_str:
        p = plan_str.lower()
        o = option_str.lower()
        return "direct" in p and "growth" in o

    name = scheme_name.lower()
    return "direct" in name and "growth" in name and "idcw" not in name and "dividend" not in name


# Compatibility alias for existing codebase callers
_is_direct_growth_plan = is_direct_growth_plan


def fetch_navall_raw() -> str:
    """Fetches raw NAVAll.txt from AMFI with retry and exponential backoff.
    
    Raises:
        AMFITimeoutError: If the request times out.
        AMFINetworkError: If a network/connection error occurs.
        AMFIInvalidResponseError: If the response is empty or status code is non-200.
    """
    url = AMFI_NAV_URL
    timeout = getattr(settings, "AMFI_TIMEOUT_SECONDS", 30.0)
    # Ensure at least 1 attempt is made
    max_retries = max(1, int(getattr(settings, "AMFI_MAX_RETRIES", 3)))
    backoff_factor = getattr(settings, "AMFI_RETRY_BACKOFF_FACTOR", 2.0)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching AMFI NAV data from {url} (attempt {attempt + 1}/{max_retries})")
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            
            if resp.status_code != 200:
                if resp.status_code == 429:
                    raise httpx.HTTPStatusError(
                        "Rate limited (status 429)",
                        request=resp.request,
                        response=resp
                    )
                elif 400 <= resp.status_code < 500:
                    # Non-transient client error; do not retry, raise immediately
                    raise AMFIInvalidResponseError(
                        f"Non-retryable client error (status {resp.status_code})"
                    )
                else:
                    raise httpx.HTTPStatusError(
                        f"Server error (status {resp.status_code})",
                        request=resp.request,
                        response=resp
                    )
                
            text = resp.text
            if not text or not text.strip():
                raise ValueError("AMFI returned an empty response body")
                
            return text
            
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout fetching AMFI data (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                raise AMFITimeoutError(f"AMFI request timed out after {max_retries} attempts: {e}") from e
                
        except (httpx.NetworkError, httpx.RequestError) as e:
            logger.warning(f"Network error fetching AMFI data (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                raise AMFINetworkError(f"AMFI network connection failed after {max_retries} attempts: {e}") from e
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"Transient HTTP error from AMFI (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                raise AMFIInvalidResponseError(f"AMFI returned HTTP error: {e}") from e
                
        except ValueError as e:
            # Empty response or other value errors do not merit retry
            raise AMFIInvalidResponseError(f"AMFI returned invalid/empty response: {e}") from e
        
        # Calculate backoff delay: e.g., 2s, 4s, 8s...
        sleep_duration = 1.0 * (backoff_factor ** attempt)
        logger.info(f"Retrying in {sleep_duration} seconds...")
        time.sleep(sleep_duration)

    raise AMFIProviderError("Unexpected failure in AMFI fetch retry loop")


def parse_navall(raw_text: str, filter_legacy_categories: bool = True) -> list[dict]:
    """Parses AMFI's NAVAll.txt format dynamically, detecting column indexes from the header.
    
    Falls back to count-based parsing if the column header is missing or incomplete.
    
    Args:
        raw_text: Raw text content from NAVAll.txt
        filter_legacy_categories: If True, filters out records with unsupported legacy categories.
        
    Returns:
        List of parsed records matching the structure:
        {
            "scheme_code": str,
            "scheme_name": str,
            "category": str | None,          # Legacy normalized category
            "category_raw": str,
            "latest_nav": float,
            "nav_date": str,
            "plan": str,
            "option": str,
            "asset_class": str,
            "subcategory": str,
            "instrument_type": str,
            "tax_classification": str,
            "tax_rule_key": str | None
        }
        
    Raises:
        AMFIParsingError: If parsing fails completely due to malformed header or structure.
    """
    if not raw_text or ";" not in raw_text:
        raise AMFIParsingError("Raw response is not in a valid semicolon-separated format")

    results = []
    current_category_raw = ""
    header_prefixes = ("open ended", "close ended", "closed ended", "interval")

    lines = raw_text.splitlines()
    if not lines:
        raise AMFIParsingError("Raw text contains no lines to parse")

    # Detect header layout dynamically
    header_map = None

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        # Detect column mapping from the header row
        if line.lower().startswith("scheme code"):
            headers = [h.strip().lower() for h in line.split(";")]
            header_map = {}
            for idx, h in enumerate(headers):
                if "scheme code" in h:
                    header_map["scheme_code"] = idx
                elif "scheme name" in h:
                    header_map["scheme_name"] = idx
                elif "net asset value" in h or h == "nav":
                    header_map["latest_nav"] = idx
                elif h == "date":
                    header_map["nav_date"] = idx
                elif h == "plan":
                    header_map["plan"] = idx
                elif h == "option":
                    header_map["option"] = idx
            continue

        if ";" not in line:
            if line.lower().startswith(header_prefixes):
                current_category_raw = line
            continue

        parts = line.split(";")
        
        # 1. Resolve columns using detected header_map if available
        if header_map is not None and all(k in header_map for k in ["scheme_code", "scheme_name", "latest_nav", "nav_date"]):
            max_idx = max(header_map.values())
            if len(parts) <= max_idx:
                logger.debug(f"Row {line_num} ignored: shorter than expected max header index {max_idx}")
                continue
                
            scheme_code = parts[header_map["scheme_code"]].strip()
            scheme_name = parts[header_map["scheme_name"]].strip()
            plan_str = parts[header_map["plan"]].strip() if "plan" in header_map else ""
            option_str = parts[header_map["option"]].strip() if "option" in header_map else ""
            nav_str = parts[header_map["latest_nav"]].strip()
            date_str = parts[header_map["nav_date"]].strip()
        
        # 2. Fall back to layout detection based on column count
        elif len(parts) >= 8:
            scheme_code = parts[0].strip()
            scheme_name = parts[3].strip()
            plan_str = parts[4].strip()
            option_str = parts[5].strip()
            nav_str = parts[6].strip()
            date_str = parts[7].strip()
        elif len(parts) >= 6:
            scheme_code = parts[0].strip()
            scheme_name = parts[3].strip()
            plan_str = ""
            option_str = ""
            nav_str = parts[4].strip()
            date_str = parts[5].strip()
        else:
            logger.debug(f"Row {line_num} ignored: insufficient columns (count={len(parts)})")
            continue

        # Filter Direct-Growth plans
        if plan_str or option_str:
            if not is_direct_growth_plan(scheme_name, plan_str, option_str):
                continue
        else:
            if not is_direct_growth_plan(scheme_name):
                continue

        # Legacy Category Normalization
        category_legacy = normalize_category(current_category_raw)
        if filter_legacy_categories and category_legacy is None:
            continue

        # Resolve Universe Categories (Returns None if unmapped/unsupported)
        universe_cat = resolve_universe_category(current_category_raw, scheme_name)
        if universe_cat is None:
            continue
            
        asset_class, subcategory, instrument_type, tax_class, tax_rule_key = universe_cat

        try:
            nav = float(nav_str.strip())
        except ValueError:
            logger.debug(f"Row {line_num} ignored: invalid NAV value '{nav_str}'")
            continue

        results.append({
            "scheme_code": scheme_code,
            "scheme_name": scheme_name,
            "category": category_legacy,
            "category_raw": current_category_raw,
            "latest_nav": nav,
            "nav_date": date_str,
            "plan": plan_str,
            "option": option_str,
            "asset_class": asset_class,
            "subcategory": subcategory,
            "instrument_type": instrument_type,
            "tax_classification": tax_class,
            "tax_rule_key": tax_rule_key
        })

    return results


def fetch_and_parse_funds() -> list[dict]:
    """Backward compatible entrypoint that fetches and parses funds using legacy categories."""
    return parse_navall(fetch_navall_raw(), filter_legacy_categories=True)