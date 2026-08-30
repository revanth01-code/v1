# backend/app/modules/universe/providers/amfi_provider.py
import logging
from app.integrations import amfi
from .base import AssetUniverseProvider, ProviderAsset

logger = logging.getLogger(__name__)


class AMFIMutualFundProvider(AssetUniverseProvider):
    def fetch_assets(self) -> list[ProviderAsset]:
        results = []
        try:
            # Call centralized, robust fetching with retries, timeout and backoff
            raw_text = amfi.fetch_navall_raw()
        except Exception as e:
            logger.error(f"AMFI Provider network error: {e}")
            raise RuntimeError(f"AMFI NAV feed currently unreachable: {e}")

        # Parse using centralized parsing logic (allowing all categories)
        try:
            parsed_records = amfi.parse_navall(raw_text, filter_legacy_categories=False)
        except Exception as e:
            logger.error(f"AMFI Provider parsing error: {e}")
            raise RuntimeError(f"Failed to parse AMFI feed: {e}")

        for rec in parsed_records:
            nav = rec["latest_nav"]
            results.append(ProviderAsset(
                asset_name=rec["scheme_name"],
                asset_class=rec["asset_class"],
                subcategory=rec["subcategory"],
                instrument_type=rec["instrument_type"],
                identifier=rec["scheme_code"],
                data_source="amfi",
                liquidity="high",
                tax_classification=rec["tax_classification"],
                tax_rule_key=rec["tax_rule_key"],
                tax_metadata={},
                latest_price=nav,
                data_status="fresh" if nav is not None else "unavailable"
            ))

        return results
