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
    AbsenceRequest,
    AbsenceRequestVote,
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
    AbsenceRequestSerializer,
    AbsenceRequestVoteSerializer,
    HouseholdAlertSerializer,
)


class HouseholdViewSet(viewsets.ModelViewSet):
    """
    Endpoints for creating, joining, leaving, and managing households.
    All active members share equal permissions.
    """

    permission_classes = [IsAuthenticated, IsActiveHouseholdMember]

    def get_queryset(self):
        # Users see households they belong to as active or paused member
        return Household.objects.filter(
            members__user=self.request.user,
            members__status__in=[
                HouseholdMember.STATUS_ACTIVE,
                HouseholdMember.STATUS_PAUSED,
            ],
        ).distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return HouseholdCreateSerializer
        return HouseholdSerializer

    def get_permissions(self):
        if self.action in ["create", "list", "join", "end_absence_request"]:
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
            from .departure import DepartureRebalanceService

            DepartureRebalanceService.rebalance_departing_member_chores(membership)
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

    @action(detail=True, methods=["get", "post"], url_path="absences")
    def absences(self, request, pk=None):
        """
        GET: List all absence requests for this household.
        POST: Active member submits an absence request with preset or custom dates.
        Requires unanimous approval from all other active roommates.
        """
        household = self.get_object()

        if request.method == "GET":
            reqs = household.absence_requests.all()
            status_filter = request.query_params.get("status")
            if status_filter:
                reqs = reqs.filter(status=status_filter)
            serializer = AbsenceRequestSerializer(reqs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        membership = household.members.filter(
            user=request.user, status=HouseholdMember.STATUS_ACTIVE
        ).first()
        if not membership:
            return Response(
                {"detail": "You are not an active member of this household."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AbsenceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        absence_req = AbsenceRequest.objects.create(
            household=household,
            member=membership,
            start_date=serializer.validated_data["start_date"],
            end_date=serializer.validated_data["end_date"],
            preset=serializer.validated_data.get("preset", ""),
            reason=serializer.validated_data.get("reason", ""),
            status=AbsenceRequest.STATUS_PENDING,
        )

        # Evaluate votes (auto-approves if solo member)
        absence_req.evaluate_votes()
        absence_req.refresh_from_db()

        return Response(
            {
                "status": absence_req.status,
                "absence_request": AbsenceRequestSerializer(absence_req).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="absences/(?P<request_id>[^/.]+)/vote",
    )
    def vote_absence_request(self, request, pk=None, request_id=None):
        """Other active members vote on a roommate's absence request."""
        household = self.get_object()
        absence_req = household.absence_requests.filter(
            id=request_id, status=AbsenceRequest.STATUS_PENDING
        ).first()
        if not absence_req:
            return Response(
                {"detail": "Pending absence request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if absence_req.member.user == request.user:
            return Response(
                {"detail": "You cannot vote on your own absence request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = VoteActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data["approved"]

        AbsenceRequestVote.objects.update_or_create(
            absence_request=absence_req,
            voter=request.user,
            defaults={"approved": approved},
        )

        absence_req.evaluate_votes()
        absence_req.refresh_from_db()

        return Response(
            AbsenceRequestSerializer(absence_req).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="absences/(?P<request_id>[^/.]+)/end",
    )
    def end_absence_request(self, request, pk=None, request_id=None):
        """
        End an approved absence, restoring the roommate to active rotation without displacing active chores.
        """
        household = self.get_object()
        absence_req = household.absence_requests.filter(
            id=request_id, status=AbsenceRequest.STATUS_APPROVED
        ).first()
        if not absence_req:
            return Response(
                {"detail": "Approved absence request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        absence_req.end_absence()
        absence_req.refresh_from_db()

        return Response(
            {
                "status": "completed",
                "message": "Absence ended. Member restored to active rotation without displacing active chores.",
                "absence_request": AbsenceRequestSerializer(absence_req).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="pause")
    def pause_household(self, request, pk=None):
        """Freeze all chore activity during a household-wide pause without missed penalties."""
        household = self.get_object()
        from .pause import HouseholdPauseService

        HouseholdPauseService.freeze_household(household)
        return Response(
            {
                "status": "paused",
                "message": "Household chore activity has been paused. Missed penalties and activations are suspended.",
                "household": HouseholdSerializer(household).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="resume")
    def resume_household(self, request, pk=None):
        """Resume chore activity for the household."""
        household = self.get_object()
        from .pause import HouseholdPauseService

        HouseholdPauseService.resume_household(household)
        return Response(
            {
                "status": "resumed",
                "message": "Household chore activity has been resumed.",
                "household": HouseholdSerializer(household).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="alerts")
    def alerts(self, request, pk=None):
        """List all alerts for this household."""
        household = self.get_object()
        alerts = household.alerts.all()
        serializer = HouseholdAlertSerializer(alerts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AbsenceRequestViewSet(viewsets.ModelViewSet):
    """
    Direct endpoint for absence requests: /api/households/absences/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = AbsenceRequestSerializer

    def get_queryset(self):
        user = self.request.user
        household_ids = HouseholdMember.objects.filter(
            user=user
        ).values_list("household_id", flat=True)
        return AbsenceRequest.objects.filter(household_id__in=household_ids)

    def create(self, request, *args, **kwargs):
        household_id = request.data.get("household")
        if not household_id:
            return Response(
                {"household": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = HouseholdMember.objects.filter(
            household_id=household_id, user=request.user, status=HouseholdMember.STATUS_ACTIVE
        ).first()
        if not membership:
            return Response(
                {"detail": "You are not an active member of this household."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        absence_req = AbsenceRequest.objects.create(
            household_id=household_id,
            member=membership,
            start_date=serializer.validated_data["start_date"],
            end_date=serializer.validated_data["end_date"],
            preset=serializer.validated_data.get("preset", ""),
            reason=serializer.validated_data.get("reason", ""),
            status=AbsenceRequest.STATUS_PENDING,
        )
        absence_req.evaluate_votes()
        absence_req.refresh_from_db()

        return Response(
            {
                "status": absence_req.status,
                "absence_request": AbsenceRequestSerializer(absence_req).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="vote")
    def vote(self, request, pk=None):
        absence_req = self.get_object()
        if absence_req.status != AbsenceRequest.STATUS_PENDING:
            return Response(
                {"detail": "Absence request is not pending."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if absence_req.member.user == request.user:
            return Response(
                {"detail": "You cannot vote on your own absence request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check voter is active member of the household
        is_active = HouseholdMember.objects.filter(
            household=absence_req.household,
            user=request.user,
            status=HouseholdMember.STATUS_ACTIVE,
        ).exists()
        if not is_active:
            return Response(
                {"detail": "You are not an active member of this household."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = VoteActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AbsenceRequestVote.objects.update_or_create(
            absence_request=absence_req,
            voter=request.user,
            defaults={"approved": serializer.validated_data["approved"]},
        )
        absence_req.evaluate_votes()
        absence_req.refresh_from_db()

        return Response(
            AbsenceRequestSerializer(absence_req).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="end")
    def end(self, request, pk=None):
        absence_req = self.get_object()
        if absence_req.status != AbsenceRequest.STATUS_APPROVED:
            return Response(
                {"detail": "Only approved absence requests can be ended."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        absence_req.end_absence()
        absence_req.refresh_from_db()

        return Response(
            {
                "status": "completed",
                "message": "Absence ended. Member restored to active rotation without displacing active chores.",
                "absence_request": AbsenceRequestSerializer(absence_req).data,
            },
            status=status.HTTP_200_OK,
        )
