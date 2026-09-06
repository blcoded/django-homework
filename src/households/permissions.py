from rest_framework.permissions import BasePermission
from .models import HouseholdMember


class IsActiveHouseholdMember(BasePermission):
    """
    Enforces the equal permissions model:
    Any active member of the household has full access to household operations.
    Non-members and non-active members are denied access.
    """

    def has_object_permission(self, request, view, obj):
        household = obj if hasattr(obj, "invite_code") else getattr(obj, "household", None)
        if not household:
            return False

        return HouseholdMember.objects.filter(
            household=household,
            user=request.user,
            status=HouseholdMember.STATUS_ACTIVE,
        ).exists()
