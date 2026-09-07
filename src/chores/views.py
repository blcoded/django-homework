from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from households.models import HouseholdMember
from households.permissions import IsActiveHouseholdMember
from .heuristic import suggest_effort_level
from .models import Chore
from .serializers import ChoreSerializer, EffortSuggestionSerializer


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
