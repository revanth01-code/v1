# backend/app/modules/universe/sync_repository.py
from datetime import datetime, timezone
import logging
from typing import Optional
from app.core.supabase import supabase_admin

logger = logging.getLogger(__name__)

TABLE = "mf_sync_status"


class SyncStatusRepository:
    @staticmethod
    def start_sync(sync_type: str) -> Optional[str]:
        """Creates a new sync status log entry with status 'running' and started_at = now().
        
        Args:
            sync_type: 'latest_nav' or 'historical_backfill'
            
        Returns:
            The sync record UUID if created successfully, otherwise None.
        """
        try:
            res = (
                supabase_admin.table(TABLE)
                .insert({
                    "sync_type": sync_type,
                    "status": "running",
                    "started_at": datetime.now(timezone.utc).isoformat()
                })
                .execute()
            )
            if res.data and len(res.data) > 0:
                return res.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Failed to start sync log in db: {e}")
            return None

    @staticmethod
    def complete_sync_success(
        sync_id: str,
        records_processed: int,
        records_failed: int,
        duration_seconds: float,
        last_successful_sync: Optional[datetime] = None
    ) -> bool:
        """Marks an active sync run as successful.
        
        Args:
            sync_id: The UUID of the sync run.
            records_processed: Number of successfully ingested records.
            records_failed: Number of failed records.
            duration_seconds: Execution duration of the sync run.
            last_successful_sync: Optional timestamp for this success. Defaults to now().
            
        Returns:
            True if updated successfully, False otherwise.
        """
        now = datetime.now(timezone.utc)
        completed_at = now.isoformat()
        
        success_ts = last_successful_sync or now
        success_ts_str = success_ts.isoformat()
        
        try:
            res = (
                supabase_admin.table(TABLE)
                .update({
                    "status": "success",
                    "completed_at": completed_at,
                    "records_processed": records_processed,
                    "records_failed": records_failed,
                    "duration_seconds": duration_seconds,
                    "last_successful_sync": success_ts_str
                })
                .eq("id", sync_id)
                .execute()
            )
            return bool(res.data)
        except Exception as e:
            logger.error(f"Failed to update sync success log in db: {e}")
            return False

    @staticmethod
    def complete_sync_failure(
        sync_id: str,
        error_message: str,
        duration_seconds: float
    ) -> bool:
        """Marks an active sync run as failed.
        
        Args:
            sync_id: The UUID of the sync run.
            error_message: Error description.
            duration_seconds: Execution duration of the sync run.
            
        Returns:
            True if updated successfully, False otherwise.
        """
        completed_at = datetime.now(timezone.utc).isoformat()
        try:
            res = (
                supabase_admin.table(TABLE)
                .update({
                    "status": "failed",
                    "completed_at": completed_at,
                    "error_message": error_message[:500],  # Truncate to match table capacity safely
                    "duration_seconds": duration_seconds
                })
                .eq("id", sync_id)
                .execute()
            )
            return bool(res.data)
        except Exception as e:
            logger.error(f"Failed to update sync failure log in db: {e}")
            return False

    @staticmethod
    def get_last_successful_sync(sync_type: str) -> Optional[datetime]:
        """Retrieves the timestamp of the last successful sync run for a sync type.
        
        Args:
            sync_type: 'latest_nav' or 'historical_backfill'
            
        Returns:
            The last_successful_sync datetime if found, otherwise None.
        """
        try:
            res = (
                supabase_admin.table(TABLE)
                .select("last_successful_sync")
                .eq("sync_type", sync_type)
                .eq("status", "success")
                .order("completed_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data and len(res.data) > 0:
                raw_ts = res.data[0]["last_successful_sync"]
                if raw_ts:
                    return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve last successful sync from db: {e}")
            return None

    @staticmethod
    def get_latest_sync(sync_type: str) -> Optional[dict]:
        """Retrieves the full row representing the latest sync run for a sync type.
        
        Args:
            sync_type: 'latest_nav' or 'historical_backfill'
            
        Returns:
            A dictionary of the latest sync run, otherwise None.
        """
        try:
            res = (
                supabase_admin.table(TABLE)
                .select("*")
                .eq("sync_type", sync_type)
                .order("started_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve latest sync log from db: {e}")
            return None

    @staticmethod
    def try_start_sync(sync_type: str) -> Optional[str]:
        """Atomically acquires transaction lock, checks running sync state, and inserts sync start record.
        
        Args:
            sync_type: 'latest_nav' or 'historical_backfill'
            
        Returns:
            A string UUID representing the sync run ID if started successfully, otherwise None.
        """
        try:
            res = supabase_admin.rpc("try_start_sync", {"p_sync_type": sync_type}).execute()
            return res.data if res.data else None
        except Exception as e:
            logger.error(f"Failed to start sync run via try_start_sync RPC: {e}")
            return None
