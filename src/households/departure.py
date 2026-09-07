from django.utils import timezone
from chores.models import ChoreAssignment, ChoreOccurrence
from chores.assignment import FairAssignmentEngine
from households.models import HouseholdAlert, HouseholdMember


class DepartureRebalanceService:
    """
    Service to reassign pending chores when a member's departure is approved,
    or mark them Unassigned and generate HouseholdAlerts if no eligible roommates exist.
    """

    @classmethod
    def rebalance_departing_member_chores(
        cls, member: HouseholdMember
    ) -> list[ChoreAssignment]:
        """
        Reassign active and upcoming chores assigned to the departing member.
        If no eligible active roommates are available, mark the occurrence as Unassigned
        and generate a HouseholdAlert.
        """
        pending_assignments = (
            ChoreAssignment.objects.filter(
                user=member.user,
                completed=False,
                occurrence__chore__household=member.household,
                occurrence__status__in=[
                    ChoreOccurrence.STATUS_UPCOMING,
                    ChoreOccurrence.STATUS_ACTIVE,
                ],
            )
            .select_related("occurrence__chore")
            .order_by("occurrence__scheduled_start")
        )

        reassigned = []
        for assignment in pending_assignments:
            occurrence = assignment.occurrence
            chore = occurrence.chore

            # Current assignees excluding departing member
            current_assigned_ids = set(
                occurrence.assignments.exclude(id=assignment.id).values_list(
                    "user_id", flat=True
                )
            )

            candidates = FairAssignmentEngine.select_assignees(
                chore=chore,
                current_time=timezone.now(),
                exclude_user_ids=current_assigned_ids,
            )

            if candidates:
                replacement_user = candidates[0]
                assignment.user = replacement_user
                assignment.original_user = None
                assignment.is_swapped = False
                assignment.save(update_fields=["user", "original_user", "is_swapped"])
                reassigned.append(assignment)
            else:
                # Zero eligible roommates available -> Mark occurrence as Unassigned
                occurrence.status = ChoreOccurrence.STATUS_UNASSIGNED
                occurrence.save(update_fields=["status", "updated_at"])
                assignment.delete()

                HouseholdAlert.objects.create(
                    household=member.household,
                    occurrence=occurrence,
                    chore=chore,
                    alert_type=HouseholdAlert.ALERT_UNASSIGNED,
                    message=f"Chore '{chore.title}' is unassigned because no eligible roommates are available following member departure.",
                )

        return reassigned
