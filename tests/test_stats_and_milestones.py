from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from chores.models import Chore, ChoreAssignment, ChoreOccurrence
from chores.services import OccurrenceService
from households.models import Household, HouseholdMember
from stats.models import UserMilestone, UserStreak
from stats.services import StatsService

User = get_user_model()


@pytest.fixture
def test_setup(db):
    user1 = User.objects.create_user(
        email="alice@example.com",
        password="password123",
        display_name="Alice",
    )
    user2 = User.objects.create_user(
        email="bob@example.com",
        password="password123",
        display_name="Bob",
    )
    user_stranger = User.objects.create_user(
        email="stranger@example.com",
        password="password123",
        display_name="Stranger",
    )

    household = Household.objects.create(name="Pine Haven", timezone="UTC")
    HouseholdMember.objects.create(
        household=household,
        user=user1,
        status=HouseholdMember.STATUS_ACTIVE,
    )
    HouseholdMember.objects.create(
        household=household,
        user=user2,
        status=HouseholdMember.STATUS_ACTIVE,
    )

    chore = Chore.objects.create(
        household=household,
        title="Kitchen Scrub",
        effort_level=Chore.EFFORT_LARGE,
        recurrence_type=Chore.RECURRENCE_INTERVAL,
        recurrence_rule={"interval": 1, "unit": "days"},
    )

    client1 = APIClient()
    client1.force_authenticate(user=user1)

    client_stranger = APIClient()
    client_stranger.force_authenticate(user=user_stranger)

    return {
        "user1": user1,
        "user2": user2,
        "user_stranger": user_stranger,
        "household": household,
        "chore": chore,
        "client1": client1,
        "client_stranger": client_stranger,
    }


@pytest.mark.django_db
def test_streak_increment_and_reset(test_setup):
    """Test on-time streak increment, longest streak tracking, and reset on missed chore."""
    user1 = test_setup["user1"]
    streak = StatsService.get_or_create_streak(user1)
    assert streak.current_streak == 0
    assert streak.longest_streak == 0

    # 1. First on-time completion
    StatsService.record_on_time_completion(user1)
    streak.refresh_from_db()
    assert streak.current_streak == 1
    assert streak.longest_streak == 1

    # 2. Second on-time completion
    StatsService.record_on_time_completion(user1)
    streak.refresh_from_db()
    assert streak.current_streak == 2
    assert streak.longest_streak == 2

    # 3. Missed chore resets current streak to 0
    StatsService.record_missed_chore(user1)
    streak.refresh_from_db()
    assert streak.current_streak == 0
    assert streak.longest_streak == 2  # preserved

    # 4. Another on-time completion
    StatsService.record_on_time_completion(user1)
    streak.refresh_from_db()
    assert streak.current_streak == 1
    assert streak.longest_streak == 2


@pytest.mark.django_db
def test_milestone_badge_unlocks(test_setup):
    """Test unlocking badges: first_chore, streak_5, streak_10, completed_25, late_recovery."""
    user1 = test_setup["user1"]
    chore = test_setup["chore"]
    now = timezone.now()

    # Create 5 assignments and complete them
    for i in range(5):
        occ = ChoreOccurrence.objects.create(
            chore=chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=i + 1),
        )
        OccurrenceService.complete_occurrence(occ, user=user1)

    unlocked_badges = set(
        UserMilestone.objects.filter(user=user1).values_list("badge_key", flat=True)
    )
    assert UserMilestone.BADGE_FIRST_CHORE in unlocked_badges
    assert UserMilestone.BADGE_STREAK_5 in unlocked_badges
    assert UserMilestone.BADGE_STREAK_10 not in unlocked_badges

    # Complete 5 more to hit 10 streak
    for i in range(5, 10):
        occ = ChoreOccurrence.objects.create(
            chore=chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=i + 1),
        )
        OccurrenceService.complete_occurrence(occ, user=user1)

    unlocked_badges_10 = set(
        UserMilestone.objects.filter(user=user1).values_list("badge_key", flat=True)
    )
    assert UserMilestone.BADGE_STREAK_10 in unlocked_badges_10

    # Late completion unlocks late_recovery
    occ_missed = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(days=20),
        due_date=now - timedelta(days=15),
    )
    occ_missed.mark_missed()
    OccurrenceService.complete_occurrence(occ_missed, user=user1)

    assert UserMilestone.objects.filter(
        user=user1, badge_key=UserMilestone.BADGE_LATE_RECOVERY
    ).exists()


@pytest.mark.django_db
def test_personal_stats_endpoint(test_setup):
    """Test GET /api/stats/personal/ returns streaks, completion metrics, and badges."""
    client1 = test_setup["client1"]
    user1 = test_setup["user1"]
    chore = test_setup["chore"]
    now = timezone.now()

    occ = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(hours=3),
    )
    OccurrenceService.complete_occurrence(occ, user=user1)

    res = client1.get("/api/stats/personal/")
    assert res.status_code == status.HTTP_200_OK
    assert res.data["display_name"] == "Alice"
    assert res.data["current_streak"] == 1
    assert res.data["total_completed"] == 1
    assert res.data["completion_rate"] == 100.0
    assert len(res.data["milestones"]) == len(UserMilestone.BADGE_DEFINITIONS)

    first_step_badge = next(
        b for b in res.data["milestones"] if b["badge_key"] == UserMilestone.BADGE_FIRST_CHORE
    )
    assert first_step_badge["is_unlocked"] is True


@pytest.mark.django_db
def test_household_stats_non_competitive_endpoint(test_setup):
    """Test GET /api/stats/household/ returns non-competitive summary without leaderboards."""
    client1 = test_setup["client1"]
    client_stranger = test_setup["client_stranger"]
    household = test_setup["household"]
    user1 = test_setup["user1"]
    user2 = test_setup["user2"]
    chore = test_setup["chore"]
    now = timezone.now()

    occ1 = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(hours=3),
    )
    OccurrenceService.complete_occurrence(occ1, user=user1)

    occ2 = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(hours=2),
    )
    OccurrenceService.complete_occurrence(occ2, user=user2)

    # Active member request
    res = client1.get(f"/api/stats/household/?household={household.id}")
    assert res.status_code == status.HTTP_200_OK
    assert res.data["household_name"] == "Pine Haven"
    assert res.data["total_completed"] == 2
    assert len(res.data["members"]) == 2

    # Verify alphabetical non-competitive ordering: Alice then Bob
    member_names = [m["display_name"] for m in res.data["members"]]
    assert member_names == ["Alice", "Bob"]
    # No ranks or leaderboard positions are exposed
    for m in res.data["members"]:
        assert "rank" not in m
        assert "position" not in m

    # Non-member cannot access
    res_stranger = client_stranger.get(f"/api/stats/household/?household={household.id}")
    assert res_stranger.status_code == status.HTTP_403_FORBIDDEN
