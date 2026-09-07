from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from households.models import Household, HouseholdMember
from households.permissions import IsActiveHouseholdMember
from stats.serializers import HouseholdStatsSerializer, PersonalStatsSerializer
from stats.services import StatsService


class PersonalStatsView(APIView):
    """
    Retrieve personal chore performance metrics, on-time streak counts,
    and unlocked milestone achievement badges.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        household_id = request.query_params.get("household")
        if household_id:
            is_member = HouseholdMember.objects.filter(
                household_id=household_id,
                user=request.user,
                status__in=[HouseholdMember.STATUS_ACTIVE, HouseholdMember.STATUS_PAUSED],
            ).exists()
            if not is_member:
                return Response(
                    {"detail": "You are not an active member of this household."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        data = StatsService.get_personal_stats(
            user=request.user, household_id=household_id
        )
        serializer = PersonalStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class HouseholdStatsView(APIView):
    """
    Retrieve non-competitive aggregate household chore statistics and member summaries.
    Strictly avoids competitive leaderboards.
    """

    permission_classes = [IsAuthenticated, IsActiveHouseholdMember]

    def get(self, request):
        household_id = request.query_params.get("household")
        if not household_id:
            membership = HouseholdMember.objects.filter(
                user=request.user, status=HouseholdMember.STATUS_ACTIVE
            ).first()
            if not membership:
                return Response(
                    {"detail": "User does not belong to any active household."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            household = membership.household
        else:
            household = Household.objects.filter(id=household_id).first()
            if not household:
                return Response(
                    {"detail": "Household not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        is_member = HouseholdMember.objects.filter(
            household=household,
            user=request.user,
            status=HouseholdMember.STATUS_ACTIVE,
        ).exists()
        if not is_member:
            return Response(
                {"detail": "You are not an active member of this household."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = StatsService.get_household_stats(
            household=household, requesting_user=request.user
        )
        serializer = HouseholdStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
