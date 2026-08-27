# backend/app/modules/portfolio/repository.py
"""Database access layer for the Portfolio module (Part 3D-B).

All reads/writes against user-owned tables (user_portfolio_holdings,
portfolio_transactions) use a RLS-scoped client so Supabase Row Level
Security enforces per-user isolation even at the DB level.

Asset validation reads go through supabase_admin because asset_universe
is a public, non-user table and the admin client avoids round-trip token
overhead for that lookup.

Design notes:
  - No SQL triggers drive holdings calculations; all arithmetic is in
    PortfolioService.
  - Full-sell strategy: DELETE the holding row when quantity reaches
    exactly zero after a sell/redeem.  This keeps the holdings table
    clean and avoids phantom zero-quantity rows.  The full transaction
    history is always preserved in portfolio_transactions regardless.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.supabase import supabase_admin, supabase_as_user

logger = logging.getLogger(__name__)

HOLDINGS_TABLE = "user_portfolio_holdings"
TRANSACTIONS_TABLE = "portfolio_transactions"
UNIVERSE_TABLE = "asset_universe"


class PortfolioRepository:
    # -----------------------------------------------------------------------
    # Asset universe validation (admin — public table)
    # -----------------------------------------------------------------------

    @staticmethod
    def get_asset(identifier: str) -> dict | None:
        """Return asset metadata from asset_universe, or None if not found.

        Uses supabase_admin because asset_universe has no RLS restriction
        and this avoids creating a user-scoped client just for a lookup.
        """
        try:
            res = (
                supabase_admin.table(UNIVERSE_TABLE)
                .select("identifier, asset_name, asset_class, subcategory, data_status")
                .eq("identifier", identifier)
                .maybe_single()
                .execute()
            )
            return res.data if res else None
        except Exception as e:
            logger.error(f"asset_universe lookup failed for '{identifier}': {e}")
            return None

    # -----------------------------------------------------------------------
    # Holdings (RLS-scoped)
    # -----------------------------------------------------------------------

    @staticmethod
    def get_holding(access_token: str, user_id: str, identifier: str) -> dict | None:
        """Fetch the current holding snapshot for (user_id, identifier), or None."""
        try:
            client = supabase_as_user(access_token)
            res = (
                client.table(HOLDINGS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("identifier", identifier)
                .maybe_single()
                .execute()
            )
            return res.data if res else None
        except Exception as e:
            logger.error(f"get_holding failed ({user_id}, {identifier}): {e}")
            return None

    @staticmethod
    def list_holdings(access_token: str, user_id: str) -> list[dict]:
        """Return all holdings for the authenticated user, ordered by asset_name."""
        try:
            client = supabase_as_user(access_token)
            res = (
                client.table(HOLDINGS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .order("asset_name")
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"list_holdings failed for user {user_id}: {e}")
            return []

    @staticmethod
    def upsert_holding(access_token: str, payload: dict) -> dict:
        """Create or update a holding snapshot.

        Conflict resolution: ON CONFLICT (user_id, identifier) UPDATE.
        Returns the resulting row.
        Raises on failure.
        """
        client = supabase_as_user(access_token)
        res = (
            client.table(HOLDINGS_TABLE)
            .upsert(payload, on_conflict="user_id,identifier")
            .execute()
        )
        return res.data[0]

    @staticmethod
    def delete_holding(access_token: str, user_id: str, identifier: str) -> None:
        """Delete a holding row (used when a full sell/redeem reduces quantity to zero).

        Design decision: full-sell removes the row rather than keeping a
        zero-quantity ghost.  Transaction history is preserved in
        portfolio_transactions regardless, so no data is lost.
        """
        try:
            client = supabase_as_user(access_token)
            (
                client.table(HOLDINGS_TABLE)
                .delete()
                .eq("user_id", user_id)
                .eq("identifier", identifier)
                .execute()
            )
        except Exception as e:
            logger.error(
                f"delete_holding failed ({user_id}, {identifier}): {e}"
            )
            raise

    # -----------------------------------------------------------------------
    # Transactions (RLS-scoped)
    # -----------------------------------------------------------------------

    @staticmethod
    def insert_transaction(access_token: str, payload: dict) -> dict:
        """Insert a new transaction ledger record.

        Returns the inserted row.
        Raises on failure.
        """
        client = supabase_as_user(access_token)
        res = client.table(TRANSACTIONS_TABLE).insert(payload).execute()
        return res.data[0]
