from app.core.supabase import supabase_admin

GOALS_TABLE = "goals"


class NotificationRepository:
    """Admin-level (service-role) queries for notification data.
    Never used for user-facing routes — always called with the service-role
    client which bypasses RLS.  Returns only the minimal fields needed.
    """

    @staticmethod
    def list_sip_goals() -> list[dict]:
        """Return all active goals that have a non-null sip_day (1-28).
        Selects only the notification-relevant columns — no financial details
        beyond monthly_contribution.
        """
        res = (
            supabase_admin
            .table(GOALS_TABLE)
            .select("id, user_id, name, monthly_contribution, sip_day")
            .not_.is_("sip_day", "null")
            .gte("sip_day", 1)
            .lte("sip_day", 28)
            .execute()
        )
        return res.data or []

    @staticmethod
    def get_user_email(user_id: str) -> str | None:
        """Fetch a single user's email from Supabase Auth via admin API.
        Returns None if the user cannot be found.
        """
        try:
            res = supabase_admin.auth.admin.get_user_by_id(user_id)
            if res and res.user:
                return res.user.email
        except Exception:
            pass
        return None
