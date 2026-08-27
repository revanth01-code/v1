# backend/app/modules/universe/providers/base.py
from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel


class ProviderAsset(BaseModel):
    asset_name: str
    asset_class: str
    subcategory: str
    instrument_type: str
    identifier: str
    data_source: str
    liquidity: str
    tax_classification: str
    tax_rule_key: Optional[str] = None
    tax_metadata: dict[str, Any] = {}
    latest_price: Optional[float] = None
    data_status: str = "unavailable"


class AssetUniverseProvider(ABC):
    @abstractmethod
    def fetch_assets(self) -> list[ProviderAsset]:
        """Fetch and normalize assets from the provider source."""
        pass
