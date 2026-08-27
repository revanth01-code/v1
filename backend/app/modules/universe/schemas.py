from typing import Any, Optional
from pydantic import BaseModel


class AssetOut(BaseModel):
    id: str
    asset_name: str
    asset_class: str
    subcategory: str
    instrument_type: str
    identifier: str
    data_source: str
    liquidity: str
    tax_classification: str
    tax_rule_key: Optional[str] = None
    tax_metadata: Optional[dict[str, Any]] = None
    latest_price: Optional[float] = None
    data_status: str = "unavailable"
    last_fetched: Optional[str] = None
    last_updated: str
