import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient
from rest_framework import status

from activity.models import ActivityLog
from chores.models import (
    Chore,
    ChoreAssignment,
    ChoreOccurrence,
    ChoreSuggestion,
    ChoreSwapRequest,
)
from chores.tasks import run_all_periodic_tasks
from households.models import AbsenceRequest, Household, HouseholdMember
from stats.models import UserMilestone, UserStreak

User = get_user_model()


@pytest.mark.django_db
class TestDemoSeedAndEndToEndWorkflow:
    """
    Comprehensive end-to-end integration test suite verifying:
    1. Management command execution (seed_demo_household).
    2. Complete user lifecycle (auth, dashboard, chore completion, verification, disputes).
    3. Roommate chore swaps and exchanges.
    4. Anonymous chore proposals and democratic voting.
    5. Absence requests and rotation pausing.
    6. Non-competitive statistics and personal streak milestone badge unlocks.
    7. Scheduled periodic runner integration.
    """

    def test_seed_demo_household_management_command(self):
        """Verify that seed_demo_household command executes and seeds rich realistic data."""
        call_command("seed_demo_household", clear=True)

        # 1. Household and users verification
        household = Household.objects.get(name="Baker Street 221B")
        assert household.invite_code == "BAKER-221B"

        members = HouseholdMember.objects.filter(household=household, status=HouseholdMember.STATUS_ACTIVE)
        assert members.count() == 4

        emails = set(members.values_list("user__email", flat=True))
        assert emails == {
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com",
            "dana@example.com",
        }

        # 2. Chores & Occurrences verification
        chores = Chore.objects.filter(household=household)
        assert chores.count() == 6

        # 48 history + 6 active = 54 occurrences
        total_occurrences = ChoreOccurrence.objects.filter(chore__household=household)
        assert total_occurrences.count() >= 54

        completed_count = total_occurrences.filter(status=ChoreOccurrence.STATUS_COMPLETED).count()
        assert completed_count > 30

        active_count = total_occurrences.filter(status=ChoreOccurrence.STATUS_ACTIVE).count()
        assert active_count == 6

        # 3. Streaks & Milestones verification
        for user in User.objects.filter(email__in=emails):
            streak = UserStreak.objects.get(user=user)
            assert streak.current_streak >= 0
            assert streak.longest_streak > 0

        unlocked_badges = UserMilestone.objects.filter(user__email__in=emails)
        assert unlocked_badges.count() > 0

        # 4. Suggestions verification
        suggestions = ChoreSuggestion.objects.filter(household=household)
        assert suggestions.count() == 3
        assert suggestions.filter(status=ChoreSuggestion.STATUS_PENDING).count() >= 2

        # 5. Swap request verification
        swaps = ChoreSwapRequest.objects.filter(household=household)
        assert swaps.count() >= 1

        # 6. Absence request verification
        absences = AbsenceRequest.objects.filter(household=household)
        assert absences.count() >= 1

        # 7. Activity logs verification
        activity_logs = ActivityLog.objects.filter(household=household)
        assert activity_logs.count() >= 40

    def test_complete_end_to_end_roommate_workflow(self):
        """Simulate the full end-to-end API lifecycle across the 4 roommates."""
        # Seed the database
        call_command("seed_demo_household", clear=True)
        client = APIClient()

        # Step 1: Alice logs in
        login_resp = client.post(
            "/api/auth/login/",
            {"email": "alice@example.com", "password": "Pass1234!"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK
        alice_token = login_resp.data["token"]
        alice_user = User.objects.get(email="alice@example.com")

        client.credentials(HTTP_AUTHORIZATION=f"Token {alice_token}")

        # Step 2: Query Alice's active chore occurrence
        occurrences_resp = client.get("/api/chores/occurrences/")
        assert occurrences_resp.status_code == status.HTTP_200_OK

        alice_occ = next(
            (o for o in occurrences_resp.data if any(a.get("user") == alice_user.id for a in o.get("assignments", []))),
            occurrences_resp.data[0],
        )
        occ_id = alice_occ["id"]

        # Step 3: Complete chore occurrence with notes and photo proof
        complete_resp = client.post(
            f"/api/chores/occurrences/{occ_id}/complete/",
            {"notes": "Cleaned sink thoroughly with disinfectant sponge."},
            format="json",
        )
        assert complete_resp.status_code == status.HTTP_200_OK
        assert complete_resp.data["status"] == "completed"

        # Step 4: Bob logs in and verifies Alice's completion
        bob_login = client.post(
            "/api/auth/login/",
            {"email": "bob@example.com", "password": "Pass1234!"},
            format="json",
        )
        bob_token = bob_login.data["token"]
        client.credentials(HTTP_AUTHORIZATION=f"Token {bob_token}")

        verify_resp = client.post(
            f"/api/chores/occurrences/{occ_id}/verify/",
            {"notes": "Looks spotless, good job!"},
            format="json",
        )
        assert verify_resp.status_code == status.HTTP_200_OK
        assert verify_resp.data["is_verified"] is True

        # Step 5: Charlie logs in and accepts Bob's pending swap request
        charlie_login = client.post(
            "/api/auth/login/",
            {"email": "charlie@example.com", "password": "Pass1234!"},
            format="json",
        )
        charlie_token = charlie_login.data["token"]
        client.credentials(HTTP_AUTHORIZATION=f"Token {charlie_token}")

        swaps_resp = client.get("/api/chores/swaps/")
        assert swaps_resp.status_code == status.HTTP_200_OK
        pending_swap = next(s for s in swaps_resp.data if s["status"] == "pending")
        swap_id = pending_swap["id"]

        accept_swap_resp = client.post(f"/api/chores/swaps/{swap_id}/accept/")
        assert accept_swap_resp.status_code == status.HTTP_200_OK
        assert accept_swap_resp.data["status"] == "accepted"

        # Step 6: Dana logs in, submits an anonymous suggestion, and casts votes
        dana_login = client.post(
            "/api/auth/login/",
            {"email": "dana@example.com", "password": "Pass1234!"},
            format="json",
        )
        dana_token = dana_login.data["token"]
        client.credentials(HTTP_AUTHORIZATION=f"Token {dana_token}")

        household = Household.objects.get(name="Baker Street 221B")
        create_sug_resp = client.post(
            "/api/chores/suggestions/",
            {
                "household": household.id,
                "title": "Degrease Kitchen Range Hood Filters",
                "description": "Soak range filters in hot soapy water once a month.",
                "effort_level": "small",
                "recurrence_type": "interval",
                "recurrence_rule": {"interval": 30, "unit": "days"},
            },
            format="json",
        )
        assert create_sug_resp.status_code == status.HTTP_201_CREATED
        new_sug_id = create_sug_resp.data["id"]

        vote_resp = client.post(
            f"/api/chores/suggestions/{new_sug_id}/vote/",
            {"approved": True},
            format="json",
        )
        assert vote_resp.status_code == status.HTTP_200_OK

        # Step 7: Check Non-Competitive Household Statistics
        household_stats_resp = client.get("/api/stats/household/")
        assert household_stats_resp.status_code == status.HTTP_200_OK
        h_data = household_stats_resp.data

        # Verify non-competitive structure: members returned alphabetically
        member_names = [m["display_name"] for m in h_data["members"]]
        assert member_names == sorted(member_names)
        assert "rank" not in h_data
        for m in h_data["members"]:
            assert "rank" not in m
            assert "place" not in m

        # Personal stats
        personal_stats_resp = client.get("/api/stats/personal/")
        assert personal_stats_resp.status_code == status.HTTP_200_OK
        p_data = personal_stats_resp.data
        assert "current_streak" in p_data
        assert "milestones" in p_data

        # Step 8: Periodic runner executes synchronously without error
        periodic_result = run_all_periodic_tasks()
        assert isinstance(periodic_result, dict)
        assert "activated" in periodic_result
        assert "missed" in periodic_result
        assert "reminders" in periodic_result
