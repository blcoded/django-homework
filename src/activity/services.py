import logging
from activity.models import ActivityLog

logger = logging.getLogger(__name__)


class ActivityService:
    """
    Centralized service for streaming and recording household activity events.
    Captures chore completions, misses, late recoveries, disputes, verifications,
    swaps, and member status changes.
    """

    @classmethod
    def log_event(
        cls,
        household,
        event_type: str,
        actor=None,
        chore=None,
        occurrence=None,
        title: str = "",
        description: str = "",
        metadata: dict = None,
    ) -> ActivityLog | None:
        if metadata is None:
            metadata = {}

        if not title:
            title = event_type.replace("_", " ").title()

        try:
            log = ActivityLog.objects.create(
                household=household,
                actor=actor,
                event_type=event_type,
                chore=chore,
                occurrence=occurrence,
                title=title,
                description=description,
                metadata=metadata,
            )
            return log
        except Exception as e:
            logger.error("Failed to record activity log: %s", e)
            return None
