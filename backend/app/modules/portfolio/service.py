# backend/app/modules/portfolio/service.py
"""Business logic for the Portfolio module (Part 3D-B).

Central flow for process_transaction():

    TransactionIn
        ↓
    Validate user + asset + transaction fields
        ↓
    Load current holding
        ↓
    Validate sell/redeem quantity <= owned quantity
        ↓
    Compute updated holding values (Decimal arithmetic)
        ↓
    Insert transaction ledger record
        ↓
    Upsert (or delete) holdings snapshot
        ↓
    Return (TransactionOut, HoldingOut)

Holdings arithmetic uses Python's decimal.Decimal to avoid float
rounding errors in financial calculations.  Values are only converted
back to float at the Pydantic schema boundary.

Atomicity note:
    PostgREST does not expose multi-statement transactions via the Python
    SDK.  To minimise inconsistency risk:
      1. All validation happens before any write.
      2. The transaction ledger insert happens FIRST.
      3. The holdings upsert/delete happens SECOND.
    If step 3 fails after step 2 succeeds, the inconsistency is logged
    with enough detail to allow manual reconciliation.  This is the
    safest practical approach without introducing a Postgres function
    or a queue-based saga — both of which are out of scope for Part 3D-B.

Full-sell behaviour:
    When a sell/redeem reduces quantity to exactly zero the holdings row
    is DELETED (not kept at zero).  The full transaction history is
    preserved in portfolio_transactions regardless.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.core.exceptions import AppError
from .repository import PortfolioRepository
from .schemas import (
    HoldingOut,
    HoldingUpsertIn,
    TransactionIn,
    TransactionOut,
    TransactionResponse,
)

logger = logging.getLogger(__name__)

# Transaction types that increase a holding
BUY_TYPES = {"buy", "sip"}
# Transaction types that decrease a holding
SELL_TYPES = {"sell", "redeem"}

# Decimal precision used for average_cost storage (6 dp gives sub-paisa accuracy)
COST_PRECISION = Decimal("0.000001")


# ---------------------------------------------------------------------------
# Private helpers (pure — unit-testable, no I/O)
# ---------------------------------------------------------------------------

def _to_d(value) -> Decimal:
    """Convert any numeric value to Decimal safely."""
    return Decimal(str(value))


def _compute_buy(
    current_qty: Decimal,
    current_invested: Decimal,
    buy_qty: Decimal,
    buy_amount: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (new_quantity, new_invested_amount, new_average_cost) after a buy/SIP.

    new_quantity       = current_qty + buy_qty
    new_invested_amount= current_invested + buy_amount
    new_average_cost   = new_invested_amount / new_quantity
    """
    new_qty = current_qty + buy_qty
    new_invested = current_invested + buy_amount
    new_avg = (new_invested / new_qty).quantize(COST_PRECISION, rounding=ROUND_HALF_UP)
    return new_qty, new_invested, new_avg


def _holdings_data_status(universe_status: str | None) -> str:
    """Translate asset_universe.data_status to a value allowed by the
    user_portfolio_holdings CHECK constraint.

    asset_universe uses operational freshness codes set by the ingestion
    and backfill pipelines:  'fresh', 'unavailable', etc.

    user_portfolio_holdings only allows:
        'verified' | 'unverified' | 'inactive' | 'unavailable'

    Mapping:
      'fresh'       -> 'verified'    (asset has current, confirmed data)
      'unavailable' -> 'unavailable' (same meaning; in both constraint lists)
      anything else -> 'unverified'  (safe default for unknown/null values)
    """
    if universe_status == "fresh":
        return "verified"
    if universe_status == "unavailable":
        return "unavailable"
    return "unverified"


def _compute_sell(
    current_qty: Decimal,
    current_invested: Decimal,
    current_avg_cost: Decimal,
    sell_qty: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return (new_quantity, new_invested_amount, new_average_cost, cost_basis)
    after a sell/redeem.

    new_quantity       = current_qty - sell_qty
    cost_basis         = current_avg_cost × sell_qty  (for tax ledger)
    new_invested_amount= current_invested - cost_basis
    new_average_cost   = unchanged (FIFO-like; preserved for remaining units)
    """
    cost_basis = (current_avg_cost * sell_qty).quantize(
        COST_PRECISION, rounding=ROUND_HALF_UP
    )
    new_qty = current_qty - sell_qty
    new_invested = current_invested - cost_basis
    # Clamp to zero to avoid float artifacts on full sell
    if new_invested < Decimal("0"):
        new_invested = Decimal("0")
    # average_cost is unchanged for remaining units
    new_avg = current_avg_cost
    return new_qty, new_invested, new_avg, cost_basis


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class PortfolioService:

    # -----------------------------------------------------------------------
    # Direct holdings snapshot endpoint (POST /portfolio/holdings)
    # -----------------------------------------------------------------------

    @staticmethod
    def upsert_holding_direct(
        access_token: str,
        user_id: str,
        payload: HoldingUpsertIn,
    ) -> HoldingOut:
        """Create or update a holding snapshot directly (no transaction history).

        The client supplies financial numbers; server enforces asset metadata
        from asset_universe.  average_cost is computed from the supplied
        invested_amount / quantity.
        """
        # 1. Validate asset exists in universe
        asset = PortfolioRepository.get_asset(payload.identifier)
        if not asset:
            raise AppError(
                f"Asset identifier '{payload.identifier}' not found in asset_universe.",
                404,
            )

        qty = _to_d(payload.quantity)
        invested = _to_d(payload.invested_amount)

        # Compute average_cost from caller-supplied values
        avg_cost = Decimal("0")
        if qty > Decimal("0") and invested > Decimal("0"):
            avg_cost = (invested / qty).quantize(COST_PRECISION, rounding=ROUND_HALF_UP)

        row = {
            "user_id": user_id,
            "identifier": asset["identifier"],
            "asset_name": asset["asset_name"],
            "asset_class": asset["asset_class"],
            "subcategory": asset["subcategory"],
            "data_status": _holdings_data_status(asset.get("data_status")),
            "quantity": float(qty),
            "invested_amount": float(invested),
            "current_value": payload.current_value,
            "average_cost": float(avg_cost),
            "purchase_date": (
                payload.purchase_date.isoformat() if payload.purchase_date else None
            ),
        }

        try:
            result = PortfolioRepository.upsert_holding(access_token, row)
        except Exception as e:
            logger.error(
                f"upsert_holding_direct failed for user={user_id}, "
                f"identifier={payload.identifier}: {e}"
            )
            raise AppError("Failed to save holding. Please try again.", 500)

        return _row_to_holding_out(result)

    # -----------------------------------------------------------------------
    # GET holdings
    # -----------------------------------------------------------------------

    @staticmethod
    def list_holdings(access_token: str, user_id: str) -> list[HoldingOut]:
        """Return all holdings for the authenticated user."""
        rows = PortfolioRepository.list_holdings(access_token, user_id)
        return [_row_to_holding_out(r) for r in rows]

    # -----------------------------------------------------------------------
    # Transaction processing (POST /portfolio/transactions)
    # -----------------------------------------------------------------------

    @staticmethod
    def process_transaction(
        access_token: str,
        user_id: str,
        payload: TransactionIn,
    ) -> TransactionResponse:
        """Validate, record, and apply a portfolio transaction.

        Steps:
          1. Validate asset exists.
          2. Load current holding.
          3. Validate sell/redeem quantity.
          4. Compute new holding values (Decimal arithmetic).
          5. Insert transaction ledger record.
          6. Upsert (or delete) holdings snapshot.
          7. Return TransactionResponse.

        See module-level docstring for atomicity details.
        """
        # ── Step 1: Asset validation ────────────────────────────────────────
        asset = PortfolioRepository.get_asset(payload.identifier)
        if not asset:
            raise AppError(
                f"Asset identifier '{payload.identifier}' not found in asset_universe.",
                404,
            )

        tx_type = payload.transaction_type  # already validated by Pydantic literal

        # ── Step 2: Load current holding ───────────────────────────────────
        current_holding = PortfolioRepository.get_holding(
            access_token, user_id, payload.identifier
        )

        # Convert current holding values to Decimal (default to zero for new holdings)
        if current_holding:
            cur_qty = _to_d(current_holding["quantity"])
            cur_invested = _to_d(current_holding["invested_amount"])
            cur_avg_cost = _to_d(current_holding["average_cost"])
            cur_current_value = _to_d(current_holding["current_value"])
            purchase_date = current_holding.get("purchase_date")
        else:
            cur_qty = Decimal("0")
            cur_invested = Decimal("0")
            cur_avg_cost = Decimal("0")
            cur_current_value = Decimal("0")
            purchase_date = None

        tx_qty = _to_d(payload.quantity)
        tx_price = _to_d(payload.price)
        tx_amount = _to_d(payload.amount)

        # ── Step 3: Sell/redeem quantity validation ─────────────────────────
        if tx_type in SELL_TYPES:
            if cur_qty == Decimal("0") and current_holding is None:
                raise AppError(
                    f"No holding found for '{payload.identifier}'. "
                    "Cannot sell/redeem an asset you do not hold.",
                    422,
                )
            if tx_qty > cur_qty:
                raise AppError(
                    f"Sell quantity ({float(tx_qty)}) exceeds current holding "
                    f"({float(cur_qty)}) for '{payload.identifier}'.",
                    422,
                )

        # ── Step 4: Compute new holding values ──────────────────────────────
        cost_basis: Optional[Decimal] = None
        full_sell = False

        if tx_type in BUY_TYPES:
            new_qty, new_invested, new_avg = _compute_buy(
                cur_qty, cur_invested, tx_qty, tx_amount
            )
            # For the first purchase, record the transaction date as purchase_date
            if purchase_date is None:
                purchase_date = payload.transaction_date.isoformat()

        else:  # SELL_TYPES
            new_qty, new_invested, new_avg, cost_basis = _compute_sell(
                cur_qty, cur_invested, cur_avg_cost, tx_qty
            )
            if new_qty == Decimal("0"):
                full_sell = True

        # ── Step 5: Insert transaction ledger record ────────────────────────
        tx_row = {
            "user_id": user_id,
            "identifier": payload.identifier,
            "transaction_type": tx_type,
            "quantity": float(tx_qty),
            "price": float(tx_price),
            "amount": float(tx_amount),
            "cost_basis": float(cost_basis) if cost_basis is not None else None,
            "transaction_date": payload.transaction_date.isoformat(),
            "metadata": payload.metadata or {},
        }

        try:
            tx_result = PortfolioRepository.insert_transaction(access_token, tx_row)
        except Exception as e:
            logger.error(
                f"Transaction insert failed for user={user_id}, "
                f"identifier={payload.identifier}: {e}"
            )
            raise AppError("Failed to record transaction. No changes were applied.", 500)

        # ── Step 6: Upsert / delete holding snapshot ────────────────────────
        if full_sell:
            # Full sell: remove the holding row entirely.
            # The transaction record already exists at this point, so a
            # failure here would leave an orphaned transaction.  Log clearly.
            try:
                PortfolioRepository.delete_holding(access_token, user_id, payload.identifier)
            except Exception as e:
                logger.error(
                    f"INCONSISTENCY RISK: transaction {tx_result.get('id')} was recorded "
                    f"but holding delete failed for user={user_id}, "
                    f"identifier={payload.identifier}: {e}"
                )
                raise AppError(
                    "Transaction was recorded but the holding snapshot could not be "
                    "updated. Please contact support with reference: "
                    f"txn={tx_result.get('id')}",
                    500,
                )
            # Return a synthetic zero-holding for the response (row is gone)
            synthetic_holding = _build_synthetic_zero_holding(
                tx_result, asset, user_id, cur_avg_cost
            )
            return TransactionResponse(
                transaction=_row_to_tx_out(tx_result),
                holding=synthetic_holding,
            )

        else:
            # Partial sell or buy: upsert the holding snapshot
            holding_row = {
                "user_id": user_id,
                "identifier": asset["identifier"],
                "asset_name": asset["asset_name"],
                "asset_class": asset["asset_class"],
                "subcategory": asset["subcategory"],
                "data_status": _holdings_data_status(asset.get("data_status")),
                "quantity": float(new_qty),
                "invested_amount": float(new_invested),
                # current_value: preserve existing value; don't fabricate live prices
                "current_value": float(cur_current_value),
                "average_cost": float(new_avg),
                "purchase_date": purchase_date,
            }

            try:
                holding_result = PortfolioRepository.upsert_holding(
                    access_token, holding_row
                )
            except Exception as e:
                logger.error(
                    f"INCONSISTENCY RISK: transaction {tx_result.get('id')} was recorded "
                    f"but holding upsert failed for user={user_id}, "
                    f"identifier={payload.identifier}: {e}"
                )
                raise AppError(
                    "Transaction was recorded but the holding snapshot could not be "
                    "updated. Please contact support with reference: "
                    f"txn={tx_result.get('id')}",
                    500,
                )

            return TransactionResponse(
                transaction=_row_to_tx_out(tx_result),
                holding=_row_to_holding_out(holding_result),
            )


# ---------------------------------------------------------------------------
# Private row → schema converters
# ---------------------------------------------------------------------------

def _row_to_holding_out(row: dict) -> HoldingOut:
    return HoldingOut(
        id=row["id"],
        user_id=row["user_id"],
        asset_name=row["asset_name"],
        identifier=row["identifier"],
        asset_class=row["asset_class"],
        subcategory=row["subcategory"],
        quantity=float(row["quantity"]),
        invested_amount=float(row["invested_amount"]),
        current_value=float(row["current_value"]),
        average_cost=float(row["average_cost"]),
        purchase_date=row.get("purchase_date"),
        data_status=row["data_status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_tx_out(row: dict) -> TransactionOut:
    return TransactionOut(
        id=row["id"],
        user_id=row["user_id"],
        identifier=row["identifier"],
        transaction_type=row["transaction_type"],
        quantity=float(row["quantity"]),
        price=float(row["price"]),
        amount=float(row["amount"]),
        cost_basis=float(row["cost_basis"]) if row.get("cost_basis") is not None else None,
        transaction_date=row["transaction_date"],
        metadata=row.get("metadata", {}),
        created_at=row["created_at"],
    )


def _build_synthetic_zero_holding(
    tx_result: dict,
    asset: dict,
    user_id: str,
    cur_avg_cost: Decimal,
) -> HoldingOut:
    """Build a synthetic HoldingOut for a full-sell response.

    After a full sell the DB row is deleted.  We return a synthetic
    snapshot so the caller always gets a consistent TransactionResponse
    shape without having to query for a row that no longer exists.
    """
    now = datetime.now(timezone.utc).isoformat()
    return HoldingOut(
        id="",          # no DB row
        user_id=user_id,
        asset_name=asset["asset_name"],
        identifier=asset["identifier"],
        asset_class=asset["asset_class"],
        subcategory=asset["subcategory"],
        quantity=0.0,
        invested_amount=0.0,
        current_value=0.0,
        average_cost=float(cur_avg_cost),
        purchase_date=None,
        data_status=asset.get("data_status", "unverified"),
        created_at=now,
        updated_at=now,
    )
