from .repository import NotificationRepository
from .schemas import SIPReminderItem, SIPRemindersResponse


class NotificationService:
    @staticmethod
    def get_sip_reminders() -> SIPRemindersResponse:
        """Collect all SIP-enabled goals and resolve each goal's user email.
        Returns a narrow payload intended solely for n8n SIP reminder delivery.
        No financial calculations are performed here.
        """
        goals = NotificationRepository.list_sip_goals()

        # Build a per-user email cache to avoid redundant Auth API calls
        email_cache: dict[str, str | None] = {}

        reminders: list[SIPReminderItem] = []
        for goal in goals:
            user_id = goal["user_id"]
            if user_id not in email_cache:
                email_cache[user_id] = NotificationRepository.get_user_email(user_id)

            reminders.append(SIPReminderItem(
                user_id=user_id,
                email=email_cache[user_id],
                goal_id=goal["id"],
                goal_name=goal["name"],
                monthly_contribution=goal["monthly_contribution"],
                sip_day=goal["sip_day"],
            ))

        return SIPRemindersResponse(reminders=reminders)
