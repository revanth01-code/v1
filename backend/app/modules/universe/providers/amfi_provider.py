# backend/app/modules/universe/providers/amfi_provider.py
import logging
from typing import Optional
import httpx
from app.core.constants import AMFI_NAV_URL
from .base import AssetUniverseProvider, ProviderAsset

logger = logging.getLogger(__name__)

# Map AMFI category headers to (asset_class, subcategory, instrument_type, tax_class, tax_rule_key)
CATEGORY_MAP = {
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


def _is_direct_growth_plan(plan: str, option: str) -> bool:
    p = plan.lower()
    o = option.lower()
    return "direct" in p and "growth" in o


def resolve_scheme_category(category_header: str, scheme_name: str) -> Optional[tuple[str, str, str, str, str]]:
    """Maps header and scheme name to category metadata tuple."""
    header_lower = category_header.lower()

    # Check for direct maps in headers first
    for amfi_name, mapped in CATEGORY_MAP.items():
        if amfi_name in header_lower:
            return mapped

    # Check other ETFs header
    if "other etfs" in header_lower:
        if "gold" in scheme_name.lower():
            return ("diversifier", "gold_etf", "etf", "gold", "in_gold_standard_v1")
        return ("equity", "etf", "etf", "equity", "in_equity_standard_v1")

    return None


class AMFIMutualFundProvider(AssetUniverseProvider):
    def fetch_assets(self) -> list[ProviderAsset]:
        results = []
        try:
            resp = httpx.get(AMFI_NAV_URL, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            raw_text = resp.text
        except Exception as e:
            logger.error(f"AMFI Provider network error: {e}")
            raise RuntimeError(f"AMFI NAV feed currently unreachable: {e}")

        current_category_raw = ""
        header_prefixes = ("open ended", "close ended", "closed ended", "interval")

        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("Scheme Code"):
                continue

            if ";" not in line:
                if line.lower().startswith(header_prefixes):
                    current_category_raw = line
                continue

            parts = line.split(";")
            if len(parts) < 8:
                continue

            scheme_code = parts[0].strip()
            scheme_name = parts[3].strip()
            plan_str = parts[4].strip()
            option_str = parts[5].strip()
            nav_str = parts[6].strip()
            date_str = parts[7].strip()

            if not _is_direct_growth_plan(plan_str, option_str):
                continue

            mapping = resolve_scheme_category(current_category_raw, scheme_name)
            if not mapping:
                asset_class, subcategory, instrument_type, tax_class, tax_rule_key = (
                    "unknown", "unclassified", "mutual_fund", "debt", None
                )
            else:
                asset_class, subcategory, instrument_type, tax_class, tax_rule_key = mapping

            try:
                nav = float(nav_str.strip())
            except ValueError:
                # If price fails to parse, leave latest_price as None (Data status remains unavailable)
                nav = None

            results.append(ProviderAsset(
                asset_name=scheme_name,
                asset_class=asset_class,
                subcategory=subcategory,
                instrument_type=instrument_type,
                identifier=scheme_code,
                data_source="amfi",
                liquidity="high",
                tax_classification=tax_class,
                tax_rule_key=tax_rule_key,
                tax_metadata={},
                latest_price=nav,
                data_status="fresh" if nav is not None else "unavailable"
            ))

        return results
