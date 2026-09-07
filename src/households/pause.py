from django.utils import timezone
from households.models import Household, HouseholdAlert


class HouseholdPauseService:
    """
    Service managing household-wide chore freezes and resumptions.
    Freezes all chore activity during pauses without missed penalties.
    """

    @classmethod
    def freeze_household(cls, household: Household) -> Household:
        """Freeze household chore activity."""
        household.pause_chores()
        HouseholdAlert.objects.create(
            household=household,
            alert_type=HouseholdAlert.ALERT_PAUSE,
            message=f"Household '{household.name}' chore activity has been paused. Missed penalties are suspended.",
        )
        return household

    @classmethod
    def resume_household(cls, household: Household) -> Household:
        """Resume household chore activity."""
        household.resume_chores()
        return household
