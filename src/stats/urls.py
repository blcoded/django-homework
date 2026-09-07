from django.urls import path
from stats.views import HouseholdStatsView, PersonalStatsView

urlpatterns = [
    path("personal/", PersonalStatsView.as_view(), name="personal-stats"),
    path("me/", PersonalStatsView.as_view(), name="my-stats"),
    path("household/", HouseholdStatsView.as_view(), name="household-stats"),
]
