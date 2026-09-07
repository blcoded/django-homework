from datetime import timedelta
from django.utils import timezone

from .models import Chore, ChoreAssignment, ChoreOccurrence

DAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


class OccurrenceService:
    """
    Service responsible for occurrence lifecycle transitions,
    activation of upcoming action windows, and single next-up generation.
    """

    @staticmethod
    def generate_next_occurrence(chore: Chore, from_time=None) -> ChoreOccurrence:
        """
        Generate the next single occurrence for a chore.
        Strict rule: Ensures only one upcoming occurrence exists per recurring chore.
        """
        # Strictly enforce: Only ONE upcoming occurrence can exist per recurring chore
        existing_upcoming = chore.occurrences.filter(
            status=ChoreOccurrence.STATUS_UPCOMING
        ).first()
        if existing_upcoming:
            return existing_upcoming

        # For one-off chores, do not create another occurrence if one already exists
        if not chore.is_recurring and chore.occurrences.exists():
            return chore.occurrences.first()

        now = timezone.now()
        base_time = from_time or now

        # Compute scheduled start time
        if chore.recurrence_type == Chore.RECURRENCE_INTERVAL:
            interval = int(chore.recurrence_rule.get("interval", 1))
            unit = chore.recurrence_rule.get("unit", "days").lower()
            if unit == "days":
                scheduled_start = base_time + timedelta(days=interval)
            elif unit == "weeks":
                scheduled_start = base_time + timedelta(weeks=interval)
            elif unit == "hours":
                scheduled_start = base_time + timedelta(hours=interval)
            else:
                scheduled_start = base_time + timedelta(days=interval)

        elif chore.recurrence_type == Chore.RECURRENCE_CALENDAR:
            days = [
                d.lower()[:3]
                for d in chore.recurrence_rule.get("days", [])
                if d.lower()[:3] in DAY_MAP
            ]
            target_weekdays = {DAY_MAP[d] for d in days}
            if not target_weekdays:
                scheduled_start = base_time + timedelta(days=1)
            else:
                cur = base_time + timedelta(days=1)
                while cur.weekday() not in target_weekdays:
                    cur += timedelta(days=1)
                scheduled_start = cur

        else:  # One-off
            scheduled_start = base_time

        due_date = chore.calculate_deadline(scheduled_start)
        initial_status = (
            ChoreOccurrence.STATUS_ACTIVE
            if scheduled_start <= now
            else ChoreOccurrence.STATUS_UPCOMING
        )

        return ChoreOccurrence.objects.create(
            chore=chore,
            status=initial_status,
            scheduled_start=scheduled_start,
            due_date=due_date,
        )

    @staticmethod
    def activate_upcoming_occurrences(current_time=None) -> list[ChoreOccurrence]:
        """
        Transition upcoming chore occurrences to active once their scheduled start arrives.
        """
        now = current_time or timezone.now()
        upcoming = ChoreOccurrence.objects.filter(
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start__lte=now,
        )
        activated = []
        for occ in upcoming:
            occ.activate()
            activated.append(occ)
        return activated

    @staticmethod
    def complete_occurrence(
        occurrence: ChoreOccurrence, user, notes: str = "", completed_time=None
    ) -> ChoreOccurrence:
        """
        Record completion by an assigned roommate.
        When all required assignments are satisfied, complete the occurrence and
        generate the next single occurrence for recurring chores.
        """
        now = completed_time or timezone.now()

        # Update or create user assignment completion
        assignment, _ = ChoreAssignment.objects.get_or_create(
            occurrence=occurrence,
            user=user,
        )
        assignment.completed = True
        assignment.completed_at = now
        if notes:
            assignment.notes = notes
        assignment.save(update_fields=["completed", "completed_at", "notes", "updated_at"])

        # Check if all required assignments are satisfied
        chore = occurrence.chore
        required_count = (
            chore.required_assignees_count if chore.is_multi_assignee else 1
        )
        completed_count = occurrence.assignments.filter(completed=True).count()

        if completed_count >= required_count:
            occurrence.complete(completed_time=now)
            # If recurring, generate the next single occurrence
            if chore.is_recurring:
                OccurrenceService.generate_next_occurrence(
                    chore=chore, from_time=occurrence.completed_at
                )

        return occurrence
