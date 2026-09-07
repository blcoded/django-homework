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

        occurrence = ChoreOccurrence.objects.create(
            chore=chore,
            status=initial_status,
            scheduled_start=scheduled_start,
            due_date=due_date,
        )

        from .assignment import FairAssignmentEngine
        FairAssignmentEngine.assign_occurrence(occurrence, current_time=now)

        return occurrence


    @staticmethod
    def activate_upcoming_occurrences(current_time=None) -> list[ChoreOccurrence]:
        """
        Transition upcoming chore occurrences to active once their scheduled start arrives.
        Freezes activation for households currently in paused status.
        """
        now = current_time or timezone.now()
        upcoming = ChoreOccurrence.objects.filter(
            chore__household__is_paused=False,
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start__lte=now,
        )
        activated = []
        for occ in upcoming:
            occ.activate()
            activated.append(occ)
        return activated

    @staticmethod
    def detect_and_transition_missed_occurrences(current_time=None) -> list[ChoreOccurrence]:
        """
        Transition past-due active occurrences to Missed while keeping them
        assigned to the responsible roommate(s) and recording missed statistics.
        Freezes missed penalties for households currently in paused status.
        """
        now = current_time or timezone.now()
        past_due = ChoreOccurrence.objects.filter(
            chore__household__is_paused=False,
            status=ChoreOccurrence.STATUS_ACTIVE,
            due_date__isnull=False,
            due_date__lt=now,
        )
        missed = []
        for occ in past_due:
            occ.mark_missed(missed_time=now)
            missed.append(occ)
        return missed

    @staticmethod
    def get_missed_statistics(user, household_id=None) -> dict:
        """
        Compute missed chore statistics for user and household.
        Strictly records missed events and tracks late completions.
        """
        user_assignments = ChoreAssignment.objects.filter(user=user)
        if household_id:
            user_assignments = user_assignments.filter(
                occurrence__chore__household_id=household_id
            )

        user_total_missed = user_assignments.filter(was_missed=True).count()
        user_currently_missed = user_assignments.filter(
            occurrence__status=ChoreOccurrence.STATUS_MISSED
        ).count()
        user_completed_late = user_assignments.filter(
            occurrence__status=ChoreOccurrence.STATUS_COMPLETED_LATE,
            completed=True,
        ).count()

        recovery_rate = (
            round((user_completed_late / user_total_missed) * 100.0, 1)
            if user_total_missed > 0
            else 100.0
        )

        household_occurrences = ChoreOccurrence.objects.all()
        if household_id:
            household_occurrences = household_occurrences.filter(
                chore__household_id=household_id
            )

        household_total_missed = household_occurrences.filter(was_missed=True).count()
        household_currently_missed = household_occurrences.filter(
            status=ChoreOccurrence.STATUS_MISSED
        ).count()
        household_completed_late = household_occurrences.filter(
            status=ChoreOccurrence.STATUS_COMPLETED_LATE
        ).count()

        return {
            "user_total_missed": user_total_missed,
            "user_currently_missed": user_currently_missed,
            "user_completed_late": user_completed_late,
            "user_late_recovery_rate": recovery_rate,
            "household_total_missed": household_total_missed,
            "household_currently_missed": household_currently_missed,
            "household_completed_late": household_completed_late,
        }

    @staticmethod
    def complete_occurrence(
        occurrence: ChoreOccurrence,
        user,
        notes: str = "",
        proof_image=None,
        completed_time=None,
    ) -> ChoreOccurrence:
        """
        Record completion by an assigned roommate.
        Supports optional notes and validated photo proof upload.
        Enforces completion gating for multi-person chores such that the occurrence
        only completes once every assigned roommate submits their completion.
        """
        from django.core.exceptions import PermissionDenied

        now = completed_time or timezone.now()
        if occurrence.pk:
            occurrence.refresh_from_db(fields=["status", "was_missed", "missed_at"])

        chore = occurrence.chore

        # Multi-assignee check: if assignments already exist, user must be one of the assignees
        existing_assignments = occurrence.assignments.all()
        if existing_assignments.exists():
            assignment = existing_assignments.filter(user=user).first()
            if not assignment:
                raise PermissionDenied(
                    "You are not an assigned roommate for this chore occurrence."
                )
        else:
            assignment = ChoreAssignment.objects.create(
                occurrence=occurrence, user=user
            )

        assignment.completed = True
        assignment.completed_at = now
        if notes:
            assignment.notes = notes
        if proof_image:
            assignment.proof_image = proof_image
        assignment.save()

        # Enforce completion gating: all required assignees must independently complete
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
