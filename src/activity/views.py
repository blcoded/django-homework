from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from activity.models import ActivityLog
from activity.serializers import ActivityLogSerializer
from chores.models import ChoreOccurrence
from chores.serializers import ChoreOccurrenceSerializer
from households.models import HouseholdMember
from households.permissions import IsActiveHouseholdMember


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Centralized activity log streaming all household chore events,
    including completions, misses, late recoveries, disputes, verifications,
    swaps, and member status changes.
    Scoped strictly to active members of the household.
    """

    permission_classes = [IsAuthenticated, IsActiveHouseholdMember]
    serializer_class = ActivityLogSerializer

    def get_queryset(self):
        user = self.request.user
        active_households = HouseholdMember.objects.filter(
            user=user, status=HouseholdMember.STATUS_ACTIVE
        ).values_list("household_id", flat=True)

        qs = ActivityLog.objects.filter(household_id__in=active_households)

        household_id = self.request.query_params.get("household")
        if household_id:
            qs = qs.filter(household_id=household_id)

        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        chore_id = self.request.query_params.get("chore")
        if chore_id:
            qs = qs.filter(chore_id=chore_id)

        actor_id = self.request.query_params.get("actor")
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        return qs.order_by("-created_at")

    @action(detail=False, methods=["get"], url_path="history")
    def history(self, request):
        """
        Filterable historical archive of past chore occurrences.
        Allows filtering by date range (start_date, end_date), specific chore,
        assignee, and status (completed, completed_late, missed, disputed).
        """
        user = request.user
        active_households = HouseholdMember.objects.filter(
            user=user, status=HouseholdMember.STATUS_ACTIVE
        ).values_list("household_id", flat=True)

        qs = ChoreOccurrence.objects.filter(
            chore__household_id__in=active_households
        )

        household_id = request.query_params.get("household")
        if household_id:
            qs = qs.filter(chore__household_id=household_id)

        chore_id = request.query_params.get("chore")
        if chore_id:
            qs = qs.filter(chore_id=chore_id)

        assignee_id = request.query_params.get("assignee")
        if assignee_id:
            qs = qs.filter(assignments__user_id=assignee_id)

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        start_date = request.query_params.get("start_date")
        if start_date:
            parsed_dt = parse_datetime(start_date)
            if parsed_dt:
                if timezone.is_naive(parsed_dt):
                    parsed_dt = timezone.make_aware(parsed_dt)
                qs = qs.filter(scheduled_start__gte=parsed_dt)
            else:
                parsed_d = parse_date(start_date)
                if parsed_d:
                    qs = qs.filter(scheduled_start__date__gte=parsed_d)

        end_date = request.query_params.get("end_date")
        if end_date:
            parsed_dt = parse_datetime(end_date)
            if parsed_dt:
                if timezone.is_naive(parsed_dt):
                    parsed_dt = timezone.make_aware(parsed_dt)
                qs = qs.filter(scheduled_start__lte=parsed_dt)
            else:
                parsed_d = parse_date(end_date)
                if parsed_d:
                    qs = qs.filter(scheduled_start__date__lte=parsed_d)

        qs = qs.distinct().order_by("-scheduled_start", "-created_at")
        serializer = ChoreOccurrenceSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
