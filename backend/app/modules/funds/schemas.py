from typing import Literal, Optional
from pydantic import BaseModel


class FundOut(BaseModel):
    scheme_code: str
    scheme_name: str
    category: str
    latest_nav: float
    nav_date: Optional[str] = None


class HistoricalNavPoint(BaseModel):
    date: str
    nav: float


class FundDetailOut(FundOut):
    historical_nav: list[HistoricalNavPoint] = []
    historical_nav_available: bool = True