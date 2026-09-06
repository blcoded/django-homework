from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Household, HouseholdMember
from .permissions import IsActiveHouseholdMember
from .serializers import (
    HouseholdCreateSerializer,
    HouseholdMemberSerializer,
    HouseholdSerializer,
)


class HouseholdViewSet(viewsets.ModelViewSet):
    """
    Endpoints for creating and managing households.
    All active members share equal permissions.
    """

    permission_classes = [IsAuthenticated, IsActiveHouseholdMember]

    def get_queryset(self):
        # Users only see households they actively belong to
        return Household.objects.filter(
            members__user=self.request.user,
            members__status=HouseholdMember.STATUS_ACTIVE,
        ).distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return HouseholdCreateSerializer
        return HouseholdSerializer

    def get_permissions(self):
        if self.action in ["create", "list"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsActiveHouseholdMember()]

    @action(detail=True, methods=["post"], url_path="regenerate-invite")
    def regenerate_invite(self, request, pk=None):
        """Any active member can regenerate the household invite code."""
        household = self.get_object()
        new_code = household.regenerate_invite_code()
        return Response(
            {
                "invite_code": new_code,
                "message": "Invite code regenerated successfully.",
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        """List all active members of the household."""
        household = self.get_object()
        members = household.members.filter(status=HouseholdMember.STATUS_ACTIVE)
        serializer = HouseholdMemberSerializer(members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="members/me")
    def my_membership(self, request, pk=None):
        """Retrieve the authenticated user's membership status in this household."""
        household = self.get_object()
        try:
            membership = household.members.get(user=request.user)
            serializer = HouseholdMemberSerializer(membership)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except HouseholdMember.DoesNotExist:
            return Response(
                {"detail": "Not a member of this household."},
                status=status.HTTP_404_NOT_FOUND,
            )
