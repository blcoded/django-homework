from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Household,
    HouseholdMember,
    JoinRequest,
    JoinRequestVote,
    LeaveRequest,
    LeaveRequestVote,
)
from .permissions import IsActiveHouseholdMember
from .serializers import (
    HouseholdCreateSerializer,
    HouseholdMemberSerializer,
    HouseholdSerializer,
    JoinHouseholdSerializer,
    JoinRequestSerializer,
    LeaveRequestSerializer,
    VoteActionSerializer,
)


class HouseholdViewSet(viewsets.ModelViewSet):
    """
    Endpoints for creating, joining, leaving, and managing households.
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
        if self.action in ["create", "list", "join"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsActiveHouseholdMember()]

    @action(detail=False, methods=["post"], url_path="join")
    def join(self, request):
        """
        Join a household using a valid invite code.
        If require_join_approval is enabled, creates a JoinRequest requiring unanimous consent.
        Otherwise enrolls the user immediately.
        """
        serializer = JoinHouseholdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["invite_code"].strip()

        household = Household.objects.filter(invite_code=code).first()
        if not household:
            return Response(
                {"detail": "Invalid invite code."},
                status=status.HTTP_404_NOT_FOUND,
            )

        existing_membership = HouseholdMember.objects.filter(
            household=household, user=request.user
        ).first()
        if existing_membership and existing_membership.status == HouseholdMember.STATUS_ACTIVE:
            return Response(
                {"detail": "You are already an active member of this household."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not household.require_join_approval:
            # Immediate join
            membership, _ = HouseholdMember.objects.update_or_create(
                household=household,
                user=request.user,
                defaults={"status": HouseholdMember.STATUS_ACTIVE},
            )
            return Response(
                {
                    "status": "joined",
                    "household": HouseholdSerializer(household).data,
                    "membership": HouseholdMemberSerializer(membership).data,
                },
                status=status.HTTP_200_OK,
            )

        # Requires household-wide unanimous approval
        join_req, created = JoinRequest.objects.get_or_create(
            household=household,
            user=request.user,
            status=JoinRequest.STATUS_PENDING,
        )
        return Response(
            {
                "status": "pending_approval",
                "join_request": JoinRequestSerializer(join_req).data,
                "household": HouseholdSerializer(household).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="join-requests")
    def join_requests(self, request, pk=None):
        """List all pending join requests for the household."""
        household = self.get_object()
        reqs = household.join_requests.filter(status=JoinRequest.STATUS_PENDING)
        serializer = JoinRequestSerializer(reqs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path="join-requests/(?P<request_id>[^/.]+)/vote",
    )
    def vote_join_request(self, request, pk=None, request_id=None):
        """Active members vote on a prospective roommate's join request."""
        household = self.get_object()
        join_req = household.join_requests.filter(
            id=request_id, status=JoinRequest.STATUS_PENDING
        ).first()
        if not join_req:
            return Response(
                {"detail": "Pending join request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VoteActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data["approved"]

        vote, _ = JoinRequestVote.objects.update_or_create(
            join_request=join_req,
            voter=request.user,
            defaults={"approved": approved},
        )

        join_req.evaluate_votes()
        return Response(JoinRequestSerializer(join_req).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="leave")
    def leave(self, request, pk=None):
        """
        Request to leave the household.
        Requires unanimous consent from all other active members.
        """
        household = self.get_object()
        membership = household.members.filter(
            user=request.user, status=HouseholdMember.STATUS_ACTIVE
        ).first()
        if not membership:
            return Response(
                {"detail": "You are not an active member of this household."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        other_members = household.get_active_members().exclude(id=membership.id)
        if other_members.count() == 0:
            # Solo member leaving immediately
            membership.status = HouseholdMember.STATUS_DEPARTED
            membership.save(update_fields=["status", "updated_at"])
            return Response(
                {"status": "departed", "message": "You have left the household."},
                status=status.HTTP_200_OK,
            )

        leave_req, created = LeaveRequest.objects.get_or_create(
            household=household,
            member=membership,
            status=LeaveRequest.STATUS_PENDING,
        )
        return Response(
            {
                "status": "pending_approval",
                "leave_request": LeaveRequestSerializer(leave_req).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="leave-requests")
    def leave_requests(self, request, pk=None):
        """List all pending departure requests for the household."""
        household = self.get_object()
        reqs = household.leave_requests.filter(status=LeaveRequest.STATUS_PENDING)
        serializer = LeaveRequestSerializer(reqs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path="leave-requests/(?P<request_id>[^/.]+)/vote",
    )
    def vote_leave_request(self, request, pk=None, request_id=None):
        """Other active members vote on a roommate's departure request."""
        household = self.get_object()
        leave_req = household.leave_requests.filter(
            id=request_id, status=LeaveRequest.STATUS_PENDING
        ).first()
        if not leave_req:
            return Response(
                {"detail": "Pending leave request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if leave_req.member.user == request.user:
            return Response(
                {"detail": "You cannot vote on your own leave request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = VoteActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data["approved"]

        LeaveRequestVote.objects.update_or_create(
            leave_request=leave_req,
            voter=request.user,
            defaults={"approved": approved},
        )

        leave_req.evaluate_votes()
        return Response(
            LeaveRequestSerializer(leave_req).data, status=status.HTTP_200_OK
        )

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
