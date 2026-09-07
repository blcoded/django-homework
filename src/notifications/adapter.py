import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailDispatchAdapter:
    """
    Adapter responsible for formatting and delivering notification emails.
    Supports development console logging (or test locmem) and production delivery.
    """

    DEFAULT_FROM_EMAIL = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@chores.local")

    @classmethod
    def format_email_content(cls, notification) -> tuple[str, str]:
        """
        Format the email subject and body for a notification.
        """
        user_name = getattr(notification.user, "display_name", "") or notification.user.email
        chore_title = notification.occurrence.chore.title if notification.occurrence else "Chore"
        due_str = (
            f"Due: {notification.occurrence.due_date}"
            if notification.occurrence and notification.occurrence.due_date
            else "No strict deadline"
        )

        if notification.notification_type == notification.TYPE_YOURE_NEXT:
            subject = f"You're next: {chore_title}"
            body = (
                f"Hi {user_name},\n\n"
                f"Heads up! You are scheduled next for '{chore_title}' in your household.\n"
                f"{notification.message}\n"
                f"{due_str}\n\n"
                f"Happy chore sharing!\n"
            )
        elif notification.notification_type == notification.TYPE_YOUR_TURN:
            subject = f"It's your turn: {chore_title}"
            body = (
                f"Hi {user_name},\n\n"
                f"It's your turn! The action window for '{chore_title}' is now open.\n"
                f"{notification.message}\n"
                f"{due_str}\n\n"
                f"Please mark it complete when done!\n"
            )
        else:
            subject = notification.title
            body = f"Hi {user_name},\n\n{notification.message}\n"

        return subject, body

    @classmethod
    def dispatch(cls, notification) -> bool:
        """
        Deliver the email for the given notification.
        Updates notification.email_sent and email_sent_at upon success.
        """
        subject, body = cls.format_email_content(notification)
        recipient_list = [notification.user.email]

        try:
            logger.info(
                f"[EmailDispatchAdapter] Dispatching '{subject}' to {recipient_list}..."
            )
            send_mail(
                subject=subject,
                message=body,
                from_email=cls.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                fail_silently=False,
            )
            notification.email_sent = True
            notification.email_sent_at = timezone.now()
            notification.save(update_fields=["email_sent", "email_sent_at", "updated_at"])
            return True
        except Exception as e:
            logger.error(f"[EmailDispatchAdapter] Failed to deliver email: {e}")
            return False
