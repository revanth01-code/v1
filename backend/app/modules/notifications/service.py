from .repository import NotificationRepository
from .schemas import (
    SIPReminderItem,
    SIPRemindersResponse,
    GoalProgressReminderItem,
    GoalProgressRemindersResponse
)


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

    @staticmethod
    def get_goal_progress_reminders() -> GoalProgressRemindersResponse:
        """Calculate progress for active goals and return those that reached a milestone."""
        goals = NotificationRepository.list_active_goals_for_progress()
        email_cache: dict[str, str | None] = {}
        reminders: list[GoalProgressReminderItem] = []

        defined_milestones = [25, 50, 75, 100]

        for goal in goals:
            target_amount = goal["target_amount"]
            current_amount = goal.get("lumpsum_amount") or 0.0
            
            if target_amount <= 0:
                continue
                
            progress_ratio = current_amount / target_amount
            progress_percentage = round(progress_ratio * 100, 2)
            
            # Find reached milestones
            reached = [m for m in defined_milestones if progress_percentage >= m]
            
            if not reached:
                continue

            user_id = goal["user_id"]
            if user_id not in email_cache:
                email_cache[user_id] = NotificationRepository.get_user_email(user_id)

            reminders.append(GoalProgressReminderItem(
                user_id=user_id,
                email=email_cache[user_id],
                goal_id=goal["id"],
                goal_name=goal["name"],
                target_amount=target_amount,
                current_amount=current_amount,
                progress_percentage=progress_percentage,
                reached_milestones=reached,
            ))

        return GoalProgressRemindersResponse(reminders=reminders)
