import logging
from django.utils import timezone
from .adapter import EmailDispatchAdapter
from .models import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Core notification engine dispatching:
    1. Early 'You're next' warnings upon assignment to an upcoming chore.
    2. Active 'It's your turn' reminders upon window activation.
    """

    @classmethod
    def dispatch_youre_next(cls, occurrence, users=None) -> list[Notification]:
        """
        Moment 1: Early 'You're next' advance alert upon assignment.
        """
        if users is None:
            users = [a.user for a in occurrence.assignments.all()]

        chore = occurrence.chore
        household = chore.household
        created_notifications = []

        scheduled_str = occurrence.scheduled_start.strftime("%b %d, %Y") if occurrence.scheduled_start else "soon"

        for user in users:
            title = f"You're next: {chore.title}"
            message = (
                f"You have been assigned as next up for '{chore.title}' "
                f"scheduled for {scheduled_str} ({chore.get_effort_level_display()})."
            )
            notification = Notification.objects.create(
                user=user,
                household=household,
                occurrence=occurrence,
                notification_type=Notification.TYPE_YOURE_NEXT,
                title=title,
                message=message,
            )
            EmailDispatchAdapter.dispatch(notification)
            created_notifications.append(notification)

        return created_notifications

    @classmethod
    def dispatch_your_turn(cls, occurrence, users=None) -> list[Notification]:
        """
        Moment 2: Active 'It's your turn' reminder upon occurrence activation.
        """
        if users is None:
            users = [a.user for a in occurrence.assignments.all()]

        chore = occurrence.chore
        household = chore.household
        created_notifications = []

        due_str = f"due by {occurrence.due_date.strftime('%b %d, %Y %H:%M')}" if occurrence.due_date else "no strict deadline"

        for user in users:
            title = f"It's your turn: {chore.title}"
            message = (
                f"It is now your turn to complete '{chore.title}' ({due_str}). "
                f"Please complete and log your chore when finished!"
            )
            notification = Notification.objects.create(
                user=user,
                household=household,
                occurrence=occurrence,
                notification_type=Notification.TYPE_YOUR_TURN,
                title=title,
                message=message,
            )
            EmailDispatchAdapter.dispatch(notification)
            created_notifications.append(notification)

        return created_notifications
