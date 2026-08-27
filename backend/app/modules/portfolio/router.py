# backend/app/modules/portfolio/router.py
"""FastAPI router for the Portfolio module (Part 3D-B).

Endpoints:
  GET  /api/v1/portfolio/holdings       — list the user's current holdings
  POST /api/v1/portfolio/holdings       — direct snapshot upsert (no transaction history)
  POST /api/v1/portfolio/transactions   — process a buy/sell/SIP/redeem transaction

All endpoints require a valid authenticated user session (Bearer token).
Users can only access their own holdings and transactions (enforced both
by RLS on Supabase and by scoping queries to user.id in the service layer).
"""
from fastapi import APIRouter, Depends, status

from app.middleware.auth import get_current_user, get_access_token
from app.modules.auth.schemas import UserOut

from .schemas import HoldingOut, HoldingUpsertIn, TransactionIn, TransactionResponse
from .service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get(
    "/holdings",
    response_model=list[HoldingOut],
    status_code=status.HTTP_200_OK,
    summary="List the authenticated user's portfolio holdings",
)
def list_holdings(
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    """Return all holdings belonging to the authenticated user.

    Current value reflects whatever is stored in the snapshot; the backend
    does not fabricate live prices.
    """
    return PortfolioService.list_holdings(token, user.id)


@router.post(
    "/holdings",
    response_model=HoldingOut,
    status_code=status.HTTP_200_OK,
    summary="Directly upsert a portfolio holding snapshot",
)
def upsert_holding(
    payload: HoldingUpsertIn,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    """Create or update a holding snapshot without creating a transaction record.

    Intended for users who import holdings directly from broker statements
    and do not want to enter the full historical transaction history.

    - Identifier is validated against asset_universe.
    - Asset name, class, and subcategory are always sourced from asset_universe.
    - average_cost is computed from invested_amount / quantity.
    - Does NOT create historical transaction records.
    """
    return PortfolioService.upsert_holding_direct(token, user.id, payload)


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a portfolio transaction and update holdings",
)
def create_transaction(
    payload: TransactionIn,
    user: UserOut = Depends(get_current_user),
    token: str = Depends(get_access_token),
):
    """Process a portfolio transaction (buy / sell / SIP / redeem).

    The backend:
    1. Validates the identifier against asset_universe.
    2. Validates sell/redeem quantity does not exceed the current holding.
    3. Computes updated holding values using Decimal arithmetic.
    4. Inserts a ledger record in portfolio_transactions.
    5. Upserts (or deletes on full sell) the holdings snapshot.
    6. Returns both the transaction record and the updated holding.

    **Full-sell behaviour**: when a sell/redeem reduces quantity to zero,
    the holding row is deleted.  The response holding will show
    quantity=0 and an empty id.
    """
    return PortfolioService.process_transaction(token, user.id, payload)
