from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from activity.models import ActivityLog
from chores.models import Chore, ChoreAssignment, ChoreOccurrence, ChoreSwapRequest
from chores.services import OccurrenceService
from households.models import (
    AbsenceRequest,
    Household,
    HouseholdMember,
    JoinRequest,
    LeaveRequest,
)

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
    user3 = User.objects.create_user(
        email="charlie@example.com",
        password="password123",
        display_name="Charlie",
    )

    household = Household.objects.create(
        name="Maple Villa",
        timezone="UTC",
        require_join_approval=True,
    )
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
        title="Dishes",
        effort_level=Chore.EFFORT_SMALL,
        recurrence_type=Chore.RECURRENCE_INTERVAL,
        recurrence_rule={"interval": 1, "unit": "days"},
    )

    client1 = APIClient()
    client1.force_authenticate(user=user1)

    client2 = APIClient()
    client2.force_authenticate(user=user2)

    client3 = APIClient()
    client3.force_authenticate(user=user3)

    return {
        "user1": user1,
        "user2": user2,
        "user3": user3,
        "household": household,
        "chore": chore,
        "client1": client1,
        "client2": client2,
        "client3": client3,
    }


@pytest.mark.django_db
def test_automatic_activity_logging_on_chore_actions(test_setup):
    """Test automatic activity logging for completion, missed, verification, and dispute."""
    now = timezone.now()
    chore = test_setup["chore"]
    user1 = test_setup["user1"]
    user2 = test_setup["user2"]

    # 1. Occurrence completion
    occ1 = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(hours=2),
    )
    OccurrenceService.complete_occurrence(
        occurrence=occ1,
        user=user1,
        notes="Cleaned everything sparkling!",
    )
    occ1.refresh_from_db()

    completion_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_CHORE_COMPLETED,
        occurrence=occ1,
    ).first()
    assert completion_log is not None
    assert "Alice completed Dishes" in completion_log.title
    assert completion_log.metadata.get("notes") == "Cleaned everything sparkling!"

    # 2. Verification
    occ1.verify(verified_by=user2, notes="Confirmed clean!")
    verify_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_CHORE_VERIFIED,
        occurrence=occ1,
    ).first()
    assert verify_log is not None
    assert "Bob verified completion of Dishes" in verify_log.title

    # 3. Dispute
    occ1.dispute(disputed_by=user2, reason="Forgot the pots and pans!")
    dispute_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_CHORE_DISPUTED,
        occurrence=occ1,
    ).first()
    assert dispute_log is not None
    assert "Bob disputed completion of Dishes" in dispute_log.title
    assert dispute_log.metadata.get("reason") == "Forgot the pots and pans!"

    # 4. Missed occurrence
    occ2 = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(days=2),
        due_date=now - timedelta(hours=1),
    )
    occ2.mark_missed()
    missed_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_CHORE_MISSED,
        occurrence=occ2,
    ).first()
    assert missed_log is not None
    assert "Dishes was missed" in missed_log.title


@pytest.mark.django_db
def test_automatic_activity_logging_on_swap(test_setup):
    """Test automatic activity logging when a swap request is accepted."""
    now = timezone.now()
    chore1 = test_setup["chore"]
    household = test_setup["household"]
    user1 = test_setup["user1"]
    user2 = test_setup["user2"]

    chore2 = Chore.objects.create(
        household=household,
        title="Take Out Trash",
        effort_level=Chore.EFFORT_SMALL,
    )

    occ1 = ChoreOccurrence.objects.create(
        chore=chore1,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now,
    )
    ChoreAssignment.objects.create(occurrence=occ1, user=user1)

    occ2 = ChoreOccurrence.objects.create(
        chore=chore2,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now,
    )
    ChoreAssignment.objects.create(occurrence=occ2, user=user2)

    swap = ChoreSwapRequest.objects.create(
        household=household,
        proposer=user1,
        recipient=user2,
        proposer_occurrence=occ1,
        recipient_occurrence=occ2,
    )

    swap.accept(user=user2)

    swap_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_CHORE_SWAP_ACCEPTED,
    ).first()
    assert swap_log is not None
    assert "Chore swap accepted between Alice and Bob" in swap_log.title


@pytest.mark.django_db
def test_automatic_activity_logging_on_member_status_changes(test_setup):
    """Test activity logging on member join, departure, absence, and pause."""
    household = test_setup["household"]
    user1 = test_setup["user1"]
    user2 = test_setup["user2"]
    user3 = test_setup["user3"]

    # 1. Join request approved
    join_req = JoinRequest.objects.create(household=household, user=user3)
    join_req.votes.create(voter=user1, approved=True)
    join_req.votes.create(voter=user2, approved=True)
    join_req.evaluate_votes()

    join_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_MEMBER_JOINED,
        actor=user3,
    ).first()
    assert join_log is not None
    assert "Charlie joined the household" in join_log.title

    # 2. Absence request approved
    now = timezone.now()
    member3 = HouseholdMember.objects.get(household=household, user=user3)
    absence = AbsenceRequest.objects.create(
        household=household,
        member=member3,
        start_date=now.date(),
        end_date=(now + timedelta(days=5)).date(),
        reason="Vacation trip",
    )
    absence.votes.create(voter=user1, approved=True)
    absence.votes.create(voter=user2, approved=True)
    absence.evaluate_votes()

    absence_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_MEMBER_ABSENCE_APPROVED,
        actor=user3,
    ).first()
    assert absence_log is not None
    assert "Absence approved for Charlie" in absence_log.title

    # 3. Departure approved
    leave_req = LeaveRequest.objects.create(
        household=household,
        member=member3,
    )
    leave_req.votes.create(voter=user1, approved=True)
    leave_req.votes.create(voter=user2, approved=True)
    leave_req.evaluate_votes()

    leave_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_MEMBER_LEFT,
        actor=user3,
    ).first()
    assert leave_log is not None
    assert "Charlie left the household" in leave_log.title

    # 4. Household pause & resume
    household.pause_chores()
    pause_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_HOUSEHOLD_PAUSED,
    ).first()
    assert pause_log is not None

    household.resume_chores()
    resume_log = ActivityLog.objects.filter(
        event_type=ActivityLog.EVENT_HOUSEHOLD_RESUMED,
    ).first()
    assert resume_log is not None


@pytest.mark.django_db
def test_activity_feed_api(test_setup):
    """Test /api/activity/ endpoint permissions and filters."""
    client1 = test_setup["client1"]
    client3 = test_setup["client3"]
    household = test_setup["household"]
    user1 = test_setup["user1"]

    ActivityLog.objects.create(
        household=household,
        actor=user1,
        event_type=ActivityLog.EVENT_CHORE_COMPLETED,
        title="Alice completed chore",
    )

    # Active member can view
    res = client1.get("/api/activity/")
    assert res.status_code == status.HTTP_200_OK
    assert len(res.data) >= 1
    assert res.data[0]["title"] == "Alice completed chore"

    # Non-member cannot see activities for this household
    res3 = client3.get("/api/activity/")
    assert res3.status_code == status.HTTP_200_OK
    assert len(res3.data) == 0

    # Filter by event_type
    res_filter = client1.get(
        f"/api/activity/?event_type={ActivityLog.EVENT_CHORE_COMPLETED}"
    )
    assert res_filter.status_code == status.HTTP_200_OK
    assert len(res_filter.data) >= 1

    res_empty = client1.get(
        f"/api/activity/?event_type={ActivityLog.EVENT_HOUSEHOLD_PAUSED}"
    )
    assert res_empty.status_code == status.HTTP_200_OK
    assert len(res_empty.data) == 0


@pytest.mark.django_db
def test_filterable_history_archive_api(test_setup):
    """Test historical occurrences search filters by date, chore, assignee, and status."""
    client1 = test_setup["client1"]
    household = test_setup["household"]
    chore = test_setup["chore"]
    user1 = test_setup["user1"]
    user2 = test_setup["user2"]
    now = timezone.now()

    # Create past occurrences
    occ_completed = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_COMPLETED,
        scheduled_start=now - timedelta(days=10),
        completed_at=now - timedelta(days=10),
    )
    ChoreAssignment.objects.create(
        occurrence=occ_completed, user=user1, completed=True
    )

    occ_missed = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_MISSED,
        scheduled_start=now - timedelta(days=5),
        due_date=now - timedelta(days=4),
        was_missed=True,
    )
    ChoreAssignment.objects.create(occurrence=occ_missed, user=user2)

    # 1. Query all history via /api/activity/history/
    res_all = client1.get("/api/activity/history/")
    assert res_all.status_code == status.HTTP_200_OK
    assert len(res_all.data) >= 2

    # 2. Filter by status
    res_completed = client1.get("/api/activity/history/?status=completed")
    assert res_completed.status_code == status.HTTP_200_OK
    statuses = [item["status"] for item in res_completed.data]
    assert "completed" in statuses
    assert "missed" not in statuses

    # 3. Filter by assignee
    res_user1 = client1.get(f"/api/activity/history/?assignee={user1.id}")
    assert res_user1.status_code == status.HTTP_200_OK
    assert any(item["id"] == occ_completed.id for item in res_user1.data)
    assert not any(item["id"] == occ_missed.id for item in res_user1.data)

    # 4. Filter by date range
    start_str = (now - timedelta(days=7)).date().isoformat()
    res_date = client1.get(f"/api/activity/history/?start_date={start_str}")
    assert res_date.status_code == status.HTTP_200_OK
    # occ_completed was 10 days ago (before start_date), occ_missed was 5 days ago
    assert not any(item["id"] == occ_completed.id for item in res_date.data)
    assert any(item["id"] == occ_missed.id for item in res_date.data)

    # 5. Also verify /api/chores/occurrences/history/ endpoint works
    res_occurrences_history = client1.get("/api/chores/occurrences/history/")
    assert res_occurrences_history.status_code == status.HTTP_200_OK
    assert len(res_occurrences_history.data) >= 2
