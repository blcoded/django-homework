from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from households.models import HouseholdMember
from households.permissions import IsActiveHouseholdMember
from households.serializers import VoteActionSerializer
from .heuristic import suggest_effort_level
from .models import (
    Chore,
    ChoreAssignment,
    ChoreOccurrence,
    ChoreSuggestion,
    ChoreSuggestionVote,
    ChoreSwapRequest,
)
from .serializers import (
    ChoreCompletionSerializer,
    ChoreDisputeSerializer,
    ChoreOccurrenceSerializer,
    ChoreSerializer,
    ChoreSuggestionSerializer,
    ChoreSwapRequestSerializer,
    ChoreVerificationSerializer,
    EffortSuggestionSerializer,
)
from .rotation import HiddenRotationService
from .services import OccurrenceService



class ChoreViewSet(viewsets.ModelViewSet):
    """
    CRUD endpoints for managing household chores.
    Scoped strictly to households the authenticated user actively belongs to.
    """

    permission_classes = [IsAuthenticated, IsActiveHouseholdMember]
    serializer_class = ChoreSerializer

    def get_queryset(self):
        user = self.request.user
        # Only chores in households where user is an active member
        active_households = HouseholdMember.objects.filter(
            user=user, status=HouseholdMember.STATUS_ACTIVE
        ).values_list("household_id", flat=True)

        qs = Chore.objects.filter(household_id__in=active_households)

        household_id = self.request.query_params.get("household")
        if household_id:
            qs = qs.filter(household_id=household_id)

        include_archived = self.request.query_params.get(
            "include_archived", "false"
        ).lower() in ("true", "1")
        if not include_archived and self.action not in ["unarchive"]:
            qs = qs.filter(is_archived=False)

        return qs

    def perform_create(self, serializer):
        chore = serializer.save()
        OccurrenceService.generate_next_occurrence(chore)

    def perform_destroy(self, instance):
        """Soft delete: archive the chore instead of deleting from database."""
        instance.is_archived = True
        instance.save(update_fields=["is_archived", "updated_at"])

    @action(detail=True, methods=["get"], url_path="next-up")
    def next_up(self, request, pk=None):
        """Retrieve the single next upcoming occurrence and assigned roommate."""
        chore = self.get_object()
        data = HiddenRotationService.get_next_up_data(chore)
        if not data:
            return Response(
                {"detail": "No upcoming occurrence scheduled for this chore.", "next_up": None},
                status=status.HTTP_200_OK,
            )
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="next-up")
    def list_next_up(self, request):
        """List the single next upcoming occurrence for all active household chores."""
        household_id = request.query_params.get("household")
        data = HiddenRotationService.get_household_next_up_data(
            user=request.user, household_id=household_id
        )
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="rotation")
    def rotation(self, request, pk=None):
        """Disclose future rotation order - strictly prohibited to preserve surprise."""
        return Response(
            {
                "detail": "Future rotation order is hidden to preserve fairness and the element of surprise. Only the immediate next assignee is exposed."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=False, methods=["get"], url_path="rotation")
    def list_rotation(self, request):
        """Disclose future rotation schedules - strictly prohibited to preserve surprise."""
        return Response(
            {
                "detail": "Future rotation schedules are hidden to preserve fairness and the element of surprise. Only the immediate next assignee is exposed."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        """Explicitly archive a chore."""
        chore = self.get_object()
        chore.is_archived = True
        chore.save(update_fields=["is_archived", "updated_at"])
        return Response(
            {"message": f"Chore '{chore.title}' archived successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="unarchive")
    def unarchive(self, request, pk=None):
        """Restore an archived chore."""
        chore = self.get_object()
        chore.is_archived = False
        chore.save(update_fields=["is_archived", "updated_at"])
        return Response(
            {"message": f"Chore '{chore.title}' restored successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="suggest-effort")
    def suggest_effort(self, request):
        """Suggest Small, Medium, or Large effort level based on title and description."""
        serializer = EffortSuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data["title"]
        desc = serializer.validated_data.get("description", "")

        suggested = suggest_effort_level(title, desc)
        points = Chore.EFFORT_POINTS.get(suggested, 2)

        return Response(
            {
                "title": title,
                "suggested_effort": suggested,
                "points": points,
            },
            status=status.HTTP_200_OK,
        )


class ChoreSuggestionViewSet(viewsets.ModelViewSet):
    """
    Endpoints for anonymous chore suggestions and majority voting.
    The creator's identity is never exposed.
    """

    permission_classes = [IsAuthenticated, IsActiveHouseholdMember]
    serializer_class = ChoreSuggestionSerializer

    def get_queryset(self):
        user = self.request.user
        active_households = HouseholdMember.objects.filter(
            user=user, status=HouseholdMember.STATUS_ACTIVE
        ).values_list("household_id", flat=True)

        qs = ChoreSuggestion.objects.filter(household_id__in=active_households)

        # Check and update expirations
        for s in qs.filter(status=ChoreSuggestion.STATUS_PENDING):
            s.check_expiration()

        household_id = self.request.query_params.get("household")
        if household_id:
            qs = qs.filter(household_id=household_id)

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    @action(detail=True, methods=["post"], url_path="vote")
    def vote(self, request, pk=None):
        """Cast an approve/reject vote on an anonymous chore suggestion."""
        suggestion = self.get_object()
        suggestion.check_expiration()

        if suggestion.status != ChoreSuggestion.STATUS_PENDING:
            return Response(
                {
                    "detail": f"Cannot vote on suggestion with status '{suggestion.status}'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = VoteActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data["approved"]

        vote, _ = ChoreSuggestionVote.objects.update_or_create(
            suggestion=suggestion,
            voter=request.user,
            defaults={"approved": approved},
        )

        suggestion.evaluate_votes()
        serializer = self.get_serializer(suggestion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="check-expirations")
    def check_expirations(self, request):
        """Transition any overdue unreviewed suggestions to expired."""
        now = timezone.now()
        expired_count = 0
        pending = ChoreSuggestion.objects.filter(
            status=ChoreSuggestion.STATUS_PENDING, expires_at__lte=now
        )
        for s in pending:
            s.status = ChoreSuggestion.STATUS_EXPIRED
            s.save(update_fields=["status", "updated_at"])
            expired_count += 1

        return Response(
            {"expired_count": expired_count, "checked_at": now},
            status=status.HTTP_200_OK,
        )


class ChoreOccurrenceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoints for viewing and interacting with chore occurrences.
    Scoped to households where user is an active member.
    """

    permission_classes = [IsAuthenticated, IsActiveHouseholdMember]
    serializer_class = ChoreOccurrenceSerializer

    def get_queryset(self):
        user = self.request.user
        active_households = HouseholdMember.objects.filter(
            user=user, status=HouseholdMember.STATUS_ACTIVE
        ).values_list("household_id", flat=True)

        qs = ChoreOccurrence.objects.filter(chore__household_id__in=active_households)

        # Optional filters
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        chore_id = self.request.query_params.get("chore")
        if chore_id:
            qs = qs.filter(chore_id=chore_id)

        household_id = self.request.query_params.get("household")
        if household_id:
            qs = qs.filter(chore__household_id=household_id)

        return qs

    @action(detail=False, methods=["post"], url_path="activate-upcoming")
    def activate_upcoming(self, request):
        """Service trigger to activate any upcoming occurrences whose start window has opened."""
        activated = OccurrenceService.activate_upcoming_occurrences()
        return Response(
            {
                "activated_count": len(activated),
                "activated_ids": [occ.id for occ in activated],
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="complete",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def complete(self, request, pk=None):
        """
        Mark occurrence complete for the authenticated user.
        Supports single-tap completion (no payload), optional notes, and photo proof uploads.
        """
        occurrence = self.get_object()
        serializer = ChoreCompletionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = serializer.validated_data.get("notes", "")
        proof_image = serializer.validated_data.get("proof_image", None)

        try:
            updated = OccurrenceService.complete_occurrence(
                occurrence=occurrence,
                user=request.user,
                notes=notes,
                proof_image=proof_image,
            )
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        return Response(self.get_serializer(updated).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="next-up")
    def list_next_up(self, request):
        """List the single next upcoming occurrence for each chore."""
        qs = self.get_queryset().filter(status=ChoreOccurrence.STATUS_UPCOMING)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="future-schedule")
    def future_schedule(self, request):
        """Future rotation schedule request - strictly forbidden."""
        return Response(
            {
                "detail": "Future rotation schedules are hidden to preserve fairness and the element of surprise."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=False, methods=["post"], url_path="detect-missed")
    def detect_missed(self, request):
        """Service trigger to detect and transition past-due active occurrences to Missed."""
        missed = OccurrenceService.detect_and_transition_missed_occurrences()
        return Response(
            {
                "missed_count": len(missed),
                "missed_ids": [occ.id for occ in missed],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="missed-statistics")
    def missed_statistics(self, request):
        """Get missed chore statistics for user and household."""
        stats = OccurrenceService.get_missed_statistics(
            user=request.user,
            household_id=request.query_params.get("household"),
        )
        return Response(stats, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="history")
    def history(self, request):
        """
        Filterable historical archive of past chore occurrences.
        Allows filtering by date range (start_date, end_date), specific chore,
        assignee, and status (completed, completed_late, missed, disputed).
        """
        from django.utils.dateparse import parse_date, parse_datetime

        qs = self.get_queryset()

        assignee_id = request.query_params.get("assignee")
        if assignee_id:
            qs = qs.filter(assignments__user_id=assignee_id)

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
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        """
        Formally verify a completed chore occurrence.
        Only active household members can verify.
        In multi-member households, roommate cannot verify their own chore.
        """
        occurrence = self.get_object()
        if occurrence.status not in [
            ChoreOccurrence.STATUS_COMPLETED,
            ChoreOccurrence.STATUS_COMPLETED_LATE,
        ]:
            return Response(
                {
                    "detail": f"Cannot verify occurrence with status '{occurrence.status}'. It must be completed first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        household = occurrence.chore.household
        if (
            household.get_active_members().count() > 1
            and occurrence.assignments.filter(user=request.user, completed=True).exists()
        ):
            return Response(
                {
                    "detail": "You cannot verify your own chore completion; another roommate must verify."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ChoreVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = serializer.validated_data.get("notes", "")

        occurrence.verify(verified_by=request.user, notes=notes)
        return Response(self.get_serializer(occurrence).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="dispute")
    def dispute(self, request, pk=None):
        """
        Flag an occurrence as Disputed with an explanation note without erasing
        the underlying completion record, timestamps, or proof.
        """
        occurrence = self.get_object()
        if occurrence.status not in [
            ChoreOccurrence.STATUS_COMPLETED,
            ChoreOccurrence.STATUS_COMPLETED_LATE,
            ChoreOccurrence.STATUS_DISPUTED,
        ]:
            return Response(
                {
                    "detail": f"Cannot dispute occurrence with status '{occurrence.status}'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ChoreDisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        occurrence.dispute(disputed_by=request.user, reason=reason)
        return Response(self.get_serializer(occurrence).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="resolve-dispute")
    def resolve_dispute(self, request, pk=None):
        """Resolve a dispute, returning occurrence to completed while preserving dispute audit trail."""
        occurrence = self.get_object()
        if occurrence.status != ChoreOccurrence.STATUS_DISPUTED:
            return Response(
                {"detail": "Only occurrences in 'disputed' status can be resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        notes = request.data.get("notes", "")
        occurrence.resolve_dispute(resolved_by=request.user, resolution_notes=notes)
        return Response(self.get_serializer(occurrence).data, status=status.HTTP_200_OK)


class ChoreSwapRequestViewSet(viewsets.ModelViewSet):
    """
    Endpoints for proposing, viewing, accepting, declining, and cancelling chore swap requests.
    Enforces mutual acceptance before any swap takes effect.
    """

    permission_classes = [IsAuthenticated, IsActiveHouseholdMember]
    serializer_class = ChoreSwapRequestSerializer

    def get_queryset(self):
        user = self.request.user
        active_households = HouseholdMember.objects.filter(
            user=user, status=HouseholdMember.STATUS_ACTIVE
        ).values_list("household_id", flat=True)

        qs = ChoreSwapRequest.objects.filter(household_id__in=active_households)

        household_id = self.request.query_params.get("household")
        if household_id:
            qs = qs.filter(household_id=household_id)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        return qs

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        """Recipient explicitly accepts the chore swap request."""
        swap = self.get_object()
        if request.user != swap.recipient:
            return Response(
                {"detail": "Only the recipient can accept this swap request."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            swap.accept(user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(swap).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="decline")
    def decline(self, request, pk=None):
        """Recipient explicitly declines the chore swap request."""
        swap = self.get_object()
        if request.user != swap.recipient:
            return Response(
                {"detail": "Only the recipient can decline this swap request."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            swap.decline(user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(swap).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """Proposer cancels the pending swap request."""
        swap = self.get_object()
        if request.user != swap.proposer:
            return Response(
                {"detail": "Only the proposer can cancel this swap request."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            swap.cancel(user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(swap).data, status=status.HTTP_200_OK)

