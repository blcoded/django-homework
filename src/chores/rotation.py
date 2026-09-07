"""
Hidden Rotation Service and Next-Up Visibility Enforcer.

Rule / Goal:
Expose only the immediate next upcoming chore assignee while keeping future rotation secret.
Prevent the database or endpoints from generating or leaking multi-week future schedules to
preserve the element of surprise and maintain dynamic fair workload calculations.
"""

from typing import Any, Optional
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from households.models import Household, HouseholdMember
from .models import Chore, ChoreOccurrence

User = get_user_model()


class HiddenRotationViolationError(PermissionDenied):
    """Raised when an action or query attempts to expose or generate future rotation schedules."""

    pass


class HiddenRotationService:
    """
    Authoritative service ensuring clients only see the single next upcoming occurrence
    and its assigned roommate(s). Strictly prevents leakage or multi-week projection
    of future chore rotations.
    """

    FORBIDDEN_LEAK_KEYS = {
        "future_rotation",
        "rotation_order",
        "future_assignees",
        "rotation_queue",
        "upcoming_queue",
        "multi_week_schedule",
        "future_schedule",
        "subsequent_assignees",
    }

    @classmethod
    def get_next_up_occurrence(cls, chore: Chore) -> Optional[ChoreOccurrence]:
        """
        Retrieve the single immediate next upcoming occurrence for a chore.
        By architecture and database constraint, at most one upcoming occurrence exists.
        """
        return (
            chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING)
            .order_by("scheduled_start")
            .first()
        )

    @classmethod
    def get_next_assignees(cls, chore: Chore) -> list[Any]:
        """
        Retrieve the assigned roommate(s) for the next upcoming occurrence.
        Returns empty list if no upcoming occurrence or no assignees yet.
        """
        occ = cls.get_next_up_occurrence(chore)
        if not occ:
            return []
        return [a.user for a in occ.assignments.select_related("user").all()]

    @classmethod
    def get_next_up_data(cls, chore: Chore) -> Optional[dict[str, Any]]:
        """
        Serialize the immediate next upcoming occurrence and its assigned roommate(s).
        Returns None if no upcoming occurrence exists.
        """
        occ = cls.get_next_up_occurrence(chore)
        if not occ:
            return None

        assignees_list = [
            {
                "id": a.user.id,
                "email": a.user.email,
                "display_name": a.user.display_name,
            }
            for a in occ.assignments.select_related("user").all()
        ]

        primary_assignee = assignees_list[0] if assignees_list else None

        data = {
            "id": occ.id,
            "occurrence_id": occ.id,
            "chore_id": chore.id,
            "chore_title": chore.title,
            "status": occ.status,
            "scheduled_start": occ.scheduled_start,
            "due_date": occ.due_date,
            "assignees": assignees_list,
            "assigned_roommate": primary_assignee,
        }

        return data

    @classmethod
    def get_household_next_up_data(
        cls, user: Any, household_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Return the single immediate next-up occurrence for each active chore in the household(s).
        Only accessible to active members of the household.
        """
        active_households_qs = HouseholdMember.objects.filter(
            user=user, status=HouseholdMember.STATUS_ACTIVE
        )
        if household_id:
            active_households_qs = active_households_qs.filter(household_id=household_id)

        household_ids = list(active_households_qs.values_list("household_id", flat=True))

        active_chores = (
            Chore.objects.filter(household_id__in=household_ids, is_archived=False)
            .prefetch_related("occurrences__assignments__user")
            .order_by("title")
        )

        results = []
        for chore in active_chores:
            next_data = cls.get_next_up_data(chore)
            if next_data:
                results.append(next_data)

        return results

    @classmethod
    def request_future_rotation(cls, chore: Chore, weeks: int = 2) -> None:
        """
        Strictly disallow querying or predicting future rotation beyond the next-up.
        """
        raise HiddenRotationViolationError(
            "Future rotation order is hidden to preserve fairness and the element of surprise. "
            "Only the immediate next upcoming assignee is disclosed."
        )

    @classmethod
    def prevent_multi_week_generation(cls, chore: Chore) -> None:
        """
        Enforce that no more than 1 upcoming occurrence can ever be generated for a chore.
        Raises HiddenRotationViolationError if an upcoming occurrence already exists.
        """
        if chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).exists():
            raise HiddenRotationViolationError(
                f"Chore '{chore.title}' already has an upcoming occurrence. Multi-week schedule generation is strictly prohibited."
            )

    @classmethod
    def assert_no_rotation_leakage(cls, payload: Any) -> None:
        """
        Utility to assert that a given API response or dictionary structure
        contains no forbidden rotation leakage keys.
        """
        if isinstance(payload, dict):
            for key, val in payload.items():
                if key.lower() in cls.FORBIDDEN_LEAK_KEYS:
                    raise AssertionError(f"Leaked forbidden rotation key: '{key}'")
                cls.assert_no_rotation_leakage(val)
        elif isinstance(payload, list):
            for item in payload:
                cls.assert_no_rotation_leakage(item)
