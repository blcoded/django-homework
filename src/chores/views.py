from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from households.models import HouseholdMember
from households.permissions import IsActiveHouseholdMember
from households.serializers import VoteActionSerializer
from .heuristic import suggest_effort_level
from .models import Chore, ChoreSuggestion, ChoreSuggestionVote
from .serializers import (
    ChoreSerializer,
    ChoreSuggestionSerializer,
    EffortSuggestionSerializer,
)


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

    def perform_destroy(self, instance):
        """Soft delete: archive the chore instead of deleting from database."""
        instance.is_archived = True
        instance.save(update_fields=["is_archived", "updated_at"])

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
