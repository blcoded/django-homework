from django.utils import timezone
from chores.models import ChoreAssignment, ChoreOccurrence
from chores.assignment import FairAssignmentEngine


class AbsenceRebalanceService:
    """
    Automated service managing member absence chore rebalancing and return to rotation.
    1. Pending chores assigned to a paused member are dynamically redistributed
       among available active roommates using the fair assignment engine.
    2. Returning members are reintegrated into future rotation without displacing
       active chores already assigned to other roommates.
    """

    @classmethod
    def rebalance_paused_member_chores(cls, member) -> list[ChoreAssignment]:
        """
        Automatically rebalance and reassign pending chores assigned to the paused member.
        Pending chores include uncompleted assignments on upcoming or active occurrences.
        """
        reassigned = []
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

        for assignment in pending_assignments:
            occurrence = assignment.occurrence
            chore = occurrence.chore

            # Existing assignees on this occurrence
            current_assigned_ids = set(
                occurrence.assignments.values_list("user_id", flat=True)
            )

            # Select replacement assignee from active roommates (excluding currently assigned)
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

        return reassigned

    @classmethod
    def check_and_complete_ended_absences(cls):
        """
        Scan for approved absences whose end_date has passed, and transition them
        to completed, restoring the member to active status without displacing active chores.
        """
        from households.models import AbsenceRequest

        today = timezone.localdate()
        ended_absences = AbsenceRequest.objects.filter(
            status=AbsenceRequest.STATUS_APPROVED,
            end_date__lt=today,
        )
        completed = []
        for req in ended_absences:
            req.end_absence()
            completed.append(req)
        return completed
