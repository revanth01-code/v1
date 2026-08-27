# backend/app/modules/portfolio/schemas.py
"""Pydantic schemas for the Portfolio module (Part 3D-B).

Input schemas: what the client sends.
Output schemas: what the API returns.

Financial values use float throughout (Decimal arithmetic is kept
inside PortfolioService; we convert back to float at the boundary).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Shared / domain literals
# ---------------------------------------------------------------------------

TransactionType = Literal["buy", "sell", "sip", "redeem"]

DataStatus = Literal["verified", "unverified", "inactive", "unavailable"]


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------

class HoldingUpsertIn(BaseModel):
    """Client payload for POST /portfolio/holdings (direct snapshot upsert).

    The client supplies financial values from their broker statement.
    Server-side asset metadata (name, class, subcategory) is always
    fetched from asset_universe and never trusted from the client.
    """
    identifier: str = Field(
        min_length=1,
        max_length=50,
        description="Scheme code / asset identifier (must exist in asset_universe).",
    )
    quantity: float = Field(
        gt=0,
        description="Number of units held. Must be positive.",
    )
    invested_amount: float = Field(
        ge=0,
        description="Total amount invested in this holding (cost basis). Must be >= 0.",
    )
    current_value: float = Field(
        ge=0,
        default=0.0,
        description=(
            "Current market value of the holding. "
            "Defaults to 0 when unknown — backend does NOT fabricate a price."
        ),
    )
    purchase_date: Optional[date] = Field(
        default=None,
        description="Date of first/earliest purchase for this holding (optional).",
    )

    @model_validator(mode="after")
    def validate_financial_consistency(self) -> "HoldingUpsertIn":
        # invested_amount >= 0 is already enforced by Field(ge=0).
        # Additional cross-field checks can go here if needed.
        return self


class HoldingOut(BaseModel):
    """Full holding record returned to the client."""
    id: str
    user_id: str
    asset_name: str
    identifier: str
    asset_class: str
    subcategory: str
    quantity: float
    invested_amount: float
    current_value: float
    average_cost: float
    purchase_date: Optional[date] = None
    data_status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TransactionIn(BaseModel):
    """Client payload for POST /portfolio/transactions."""
    identifier: str = Field(
        min_length=1,
        max_length=50,
        description="Scheme code (must exist in asset_universe).",
    )
    transaction_type: TransactionType = Field(
        description="buy | sell | sip | redeem",
    )
    quantity: float = Field(
        gt=0,
        description="Number of units transacted. Must be strictly positive.",
    )
    price: float = Field(
        ge=0,
        description="NAV / price per unit at transaction time. Must be >= 0.",
    )
    amount: float = Field(
        ge=0,
        description=(
            "Total transaction amount (quantity × price, or declared amount for SIP). "
            "Must be >= 0."
        ),
    )
    transaction_date: date = Field(
        description="Date on which the transaction occurred.",
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Optional free-form metadata (folio number, etc.).",
    )


class TransactionOut(BaseModel):
    """Transaction ledger record returned to the client."""
    id: str
    user_id: str
    identifier: str
    transaction_type: str
    quantity: float
    price: float
    amount: float
    cost_basis: Optional[float] = None
    transaction_date: date
    metadata: dict
    created_at: datetime


class TransactionResponse(BaseModel):
    """Full response for POST /portfolio/transactions — includes both the
    created transaction record and the updated holdings snapshot."""
    transaction: TransactionOut
    holding: HoldingOut
