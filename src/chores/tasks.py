import logging
from django.utils import timezone
from chores.models import ChoreOccurrence
from chores.services import OccurrenceService

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:  # pragma: no cover
    def shared_task(func=None, **kwargs):
        if func is not None:
            return func
        def decorator(f):
            return f
        return decorator


@shared_task
def check_and_activate_occurrences():
    """
    Periodic task to check and activate upcoming chore occurrences
    whose scheduled_start has arrived.
    """
    activated = OccurrenceService.activate_upcoming_occurrences()
    logger.info("Activated %d upcoming occurrences", len(activated))
    return [occ.id for occ in activated]


@shared_task
def check_and_transition_missed_occurrences():
    """
    Periodic task to transition past-due active occurrences to missed.
    """
    missed = OccurrenceService.detect_and_transition_missed_occurrences()
    logger.info("Transitioned %d occurrences to missed", len(missed))
    return [occ.id for occ in missed]


@shared_task
def dispatch_scheduled_reminders():
    """
    Periodic task to dispatch reminder notifications for active chores.
    Ensures active occurrences dispatch 'It's your turn' reminders if needed.
    """
    now = timezone.now()
    active_occurrences = ChoreOccurrence.objects.filter(
        chore__household__is_paused=False,
        status=ChoreOccurrence.STATUS_ACTIVE,
    )
    reminded = []
    for occ in active_occurrences:
        # Check if reminder or active notification already exists
        has_reminder = occ.notifications.filter(
            notification_type="your_turn"
        ).exists()
        if not has_reminder:
            try:
                from notifications.services import NotificationService
                NotificationService.dispatch_your_turn(occ)
                reminded.append(occ.id)
            except Exception as e:
                logger.warning("Failed to dispatch reminder for occurrence %s: %s", occ.id, e)
    return reminded


@shared_task
def run_all_periodic_tasks():
    """
    Execute all periodic background routines in a single pass.
    Useful for synchronous runners or unified beat schedules.
    """
    activated_ids = check_and_activate_occurrences()
    missed_ids = check_and_transition_missed_occurrences()
    reminder_ids = dispatch_scheduled_reminders()
    return {
        "activated": activated_ids,
        "missed": missed_ids,
        "reminders": reminder_ids,
    }
