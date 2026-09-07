from datetime import timedelta
from django.utils import timezone

from households.models import Household, HouseholdMember
from .models import Chore, ChoreAssignment, ChoreOccurrence


class FairAssignmentEngine:
    """
    Authoritative backend engine that assigns chores fairly among active roommates.
    Balances:
    1. Trailing 56-day (8-week) completed chore workload points (Small=1, Medium=2, Large=3).
       Strictly excludes missed/uncompleted chores.
    2. Chore variety penalty: penalizes assigning the same chore repeatedly to the same roommate.
    3. Deterministic tie-breaking among eligible active roommates.
    """

    LOOKBACK_DAYS = 56  # 8 weeks

    @classmethod
    def get_completed_workload_points(
        cls, user, household: Household, current_time=None
    ) -> int:
        """
        Calculate total completed chore points for user in household over trailing 56 days.
        Strictly excludes missed chores that were not completed.
        Completed late chores count toward credit.
        """
        now = current_time or timezone.now()
        since = now - timedelta(days=cls.LOOKBACK_DAYS)

        from django.db.models import Q

        completed_assignments = (
            ChoreAssignment.objects.filter(
                occurrence__chore__household=household,
                completed=True,
                completed_at__gte=since,
                occurrence__status__in=[
                    ChoreOccurrence.STATUS_COMPLETED,
                    ChoreOccurrence.STATUS_COMPLETED_LATE,
                    ChoreOccurrence.STATUS_DISPUTED,
                ],
            )
            .filter(
                Q(original_user=user)
                | (Q(original_user__isnull=True) & Q(user=user))
            )
            .select_related("occurrence__chore")
        )

        points = 0
        for assignment in completed_assignments:
            points += assignment.occurrence.chore.points

        return points

    @classmethod
    def get_chore_variety_penalty(cls, user, chore: Chore, current_time=None) -> float:
        """
        Compute variety penalty for assigning this specific chore to user.
        Roommates who did this specific chore more times recently receive a higher penalty.
        Also, if user did it within the last 7 or 14 days, extra penalty is applied.
        """
        now = current_time or timezone.now()
        since = now - timedelta(days=cls.LOOKBACK_DAYS)

        assignments = ChoreAssignment.objects.filter(
            user=user,
            occurrence__chore=chore,
            completed=True,
            completed_at__gte=since,
        ).order_by("-completed_at")

        count = assignments.count()
        penalty = count * 2.0  # 2 penalty points per previous completion in 8 weeks

        latest = assignments.first()
        if latest and latest.completed_at:
            days_ago = (now - latest.completed_at).total_seconds() / 86400.0
            if days_ago < 7:
                penalty += 3.0  # extra penalty for doing it within last week
            elif days_ago < 14:
                penalty += 1.5

        return penalty

    @classmethod
    def score_roommate(cls, user, chore: Chore, current_time=None) -> tuple[float, int, int]:
        """
        Compute total score for ranking:
        (total_composite_score, workload_points, user.id)
        Lower score = higher priority for receiving the assignment.
        """
        workload = cls.get_completed_workload_points(user, chore.household, current_time)
        variety_penalty = cls.get_chore_variety_penalty(user, chore, current_time)
        composite_score = float(workload) + variety_penalty
        return (composite_score, workload, user.id)

    @classmethod
    def select_assignees(
        cls, chore: Chore, current_time=None, exclude_user_ids=None
    ) -> list:
        """
        Select the optimal active roommate(s) for a chore occurrence.
        Returns a list of User instances (size matches required_assignees_count).
        """
        active_members = HouseholdMember.objects.filter(
            household=chore.household, status=HouseholdMember.STATUS_ACTIVE
        ).select_related("user")

        if exclude_user_ids:
            active_members = active_members.exclude(user_id__in=exclude_user_ids)

        if not active_members.exists():
            return []

        required_count = (
            chore.required_assignees_count if chore.is_multi_assignee else 1
        )

        ranked = []
        for member in active_members:
            score = cls.score_roommate(member.user, chore, current_time)
            ranked.append((score, member.user))

        # Sort ascending by composite score, then workload, then user.id (deterministic tie-breaker)
        ranked.sort(key=lambda x: x[0])

        selected = [item[1] for item in ranked[:required_count]]
        return selected

    @classmethod
    def assign_occurrence(
        cls, occurrence: ChoreOccurrence, current_time=None
    ) -> list[ChoreAssignment]:
        """
        Select and create ChoreAssignment records for an occurrence using the fair engine.
        Fallback logic: Marks occurrence as Unassigned and generates a household alert
        when zero eligible roommates are available for assignment.
        """
        selected_users = cls.select_assignees(occurrence.chore, current_time)
        if not selected_users:
            occurrence.status = ChoreOccurrence.STATUS_UNASSIGNED
            occurrence.save(update_fields=["status", "updated_at"])
            from households.models import HouseholdAlert

            HouseholdAlert.objects.create(
                household=occurrence.chore.household,
                occurrence=occurrence,
                chore=occurrence.chore,
                alert_type=HouseholdAlert.ALERT_UNASSIGNED,
                message=f"Chore '{occurrence.chore.title}' cannot be assigned because zero eligible roommates are available.",
            )
            return []

        assignments = []
        for user in selected_users:
            assignment, _ = ChoreAssignment.objects.get_or_create(
                occurrence=occurrence, user=user
            )
            assignments.append(assignment)

        try:
            from notifications.services import NotificationService

            if occurrence.status == ChoreOccurrence.STATUS_UPCOMING:
                NotificationService.dispatch_youre_next(occurrence, users=selected_users)
            elif occurrence.status == ChoreOccurrence.STATUS_ACTIVE:
                NotificationService.dispatch_your_turn(occurrence, users=selected_users)
        except Exception:
            pass

        return assignments
