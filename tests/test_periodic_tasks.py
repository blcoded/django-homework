from datetime import timedelta
import io
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from chores.models import Chore, ChoreOccurrence
from chores.tasks import (
    check_and_activate_occurrences,
    check_and_transition_missed_occurrences,
    dispatch_scheduled_reminders,
    run_all_periodic_tasks,
)
from households.models import Household, HouseholdMember

User = get_user_model()


@pytest.fixture
def test_setup(db):
    user = User.objects.create_user(
        email="worker@example.com",
        password="password123",
        display_name="Worker User",
    )
    household = Household.objects.create(name="Task Household", timezone="UTC")
    HouseholdMember.objects.create(
        household=household,
        user=user,
        status=HouseholdMember.STATUS_ACTIVE,
    )
    chore = Chore.objects.create(
        household=household,
        title="Vacuum Living Room",
        effort_level=Chore.EFFORT_MEDIUM,
        recurrence_type=Chore.RECURRENCE_INTERVAL,
        recurrence_rule={"interval": 1, "unit": "days"},
    )
    return {
        "user": user,
        "household": household,
        "chore": chore,
    }


@pytest.mark.django_db
def test_celery_settings_and_beat_schedule():
    """Verify Celery configuration and beat schedule entries exist."""
    assert hasattr(settings, "CELERY_BROKER_URL")
    assert hasattr(settings, "CELERY_RESULT_BACKEND")
    assert hasattr(settings, "CELERY_BEAT_SCHEDULE")

    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "activate-upcoming-occurrences-every-minute" in schedule
    assert "detect-missed-occurrences-every-5-minutes" in schedule
    assert "dispatch-reminders-every-15-minutes" in schedule
    assert "run-all-periodic-tasks-every-5-minutes" in schedule


@pytest.mark.django_db
def test_periodic_tasks_activation(test_setup):
    """Upcoming occurrences past scheduled_start get activated by periodic tasks."""
    now = timezone.now()
    chore1 = test_setup["chore"]
    chore2 = Chore.objects.create(
        household=test_setup["household"],
        title="Dust Bookshelves",
        effort_level=Chore.EFFORT_SMALL,
        recurrence_type=Chore.RECURRENCE_INTERVAL,
        recurrence_rule={"interval": 1, "unit": "days"},
    )

    past_scheduled = ChoreOccurrence.objects.create(
        chore=chore1,
        status=ChoreOccurrence.STATUS_UPCOMING,
        scheduled_start=now - timedelta(minutes=10),
    )

    future_scheduled = ChoreOccurrence.objects.create(
        chore=chore2,
        status=ChoreOccurrence.STATUS_UPCOMING,
        scheduled_start=now + timedelta(hours=2),
    )

    activated_ids = check_and_activate_occurrences()
    assert past_scheduled.id in activated_ids

    past_scheduled.refresh_from_db()
    future_scheduled.refresh_from_db()

    assert past_scheduled.status == ChoreOccurrence.STATUS_ACTIVE
    assert future_scheduled.status == ChoreOccurrence.STATUS_UPCOMING


@pytest.mark.django_db
def test_periodic_tasks_missed_transition(test_setup):
    """Active occurrences past due_date get transitioned to missed."""
    now = timezone.now()
    chore = test_setup["chore"]

    past_due_occ = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(days=2),
        due_date=now - timedelta(hours=1),
    )

    not_past_due_occ = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(hours=2),
        due_date=now + timedelta(hours=5),
    )

    missed_ids = check_and_transition_missed_occurrences()
    assert past_due_occ.id in missed_ids

    past_due_occ.refresh_from_db()
    not_past_due_occ.refresh_from_db()

    assert past_due_occ.status == ChoreOccurrence.STATUS_MISSED
    assert past_due_occ.was_missed is True
    assert not_past_due_occ.status == ChoreOccurrence.STATUS_ACTIVE


@pytest.mark.django_db
def test_periodic_tasks_respect_household_pause(test_setup):
    """Occurrences for paused households are neither activated nor transitioned to missed."""
    now = timezone.now()
    household = test_setup["household"]
    household.is_paused = True
    household.save()

    chore = test_setup["chore"]

    upcoming_occ = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_UPCOMING,
        scheduled_start=now - timedelta(minutes=10),
    )
    active_past_due = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(days=2),
        due_date=now - timedelta(hours=1),
    )

    result = run_all_periodic_tasks()

    upcoming_occ.refresh_from_db()
    active_past_due.refresh_from_db()

    assert upcoming_occ.id not in result["activated"]
    assert active_past_due.id not in result["missed"]
    assert upcoming_occ.status == ChoreOccurrence.STATUS_UPCOMING
    assert active_past_due.status == ChoreOccurrence.STATUS_ACTIVE


@pytest.mark.django_db
def test_run_periodic_tasks_management_command(test_setup):
    """Test the synchronous fallback management command run_periodic_tasks."""
    now = timezone.now()
    chore = test_setup["chore"]

    upcoming_occ = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_UPCOMING,
        scheduled_start=now - timedelta(minutes=15),
    )
    active_occ = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_ACTIVE,
        scheduled_start=now - timedelta(days=1),
        due_date=now - timedelta(minutes=5),
    )

    out = io.StringIO()
    call_command("run_periodic_tasks", stdout=out)
    output = out.getvalue()

    assert "Periodic tasks completed successfully" in output
    upcoming_occ.refresh_from_db()
    active_occ.refresh_from_db()
    assert upcoming_occ.status == ChoreOccurrence.STATUS_ACTIVE
    assert active_occ.status == ChoreOccurrence.STATUS_MISSED


@pytest.mark.django_db
def test_management_command_flags(test_setup):
    """Test management command with selective execution flags."""
    now = timezone.now()
    chore = test_setup["chore"]

    upcoming_occ = ChoreOccurrence.objects.create(
        chore=chore,
        status=ChoreOccurrence.STATUS_UPCOMING,
        scheduled_start=now - timedelta(minutes=5),
    )

    out = io.StringIO()
    call_command("run_periodic_tasks", "--only-activate", stdout=out)
    assert "Successfully activated" in out.getvalue()

    upcoming_occ.refresh_from_db()
    assert upcoming_occ.status == ChoreOccurrence.STATUS_ACTIVE

    upcoming_occ.due_date = now - timedelta(minutes=1)
    upcoming_occ.save()

    out_missed = io.StringIO()
    call_command("run_periodic_tasks", "--only-missed", stdout=out_missed)
    assert "Successfully transitioned" in out_missed.getvalue()

    upcoming_occ.refresh_from_db()
    assert upcoming_occ.status == ChoreOccurrence.STATUS_MISSED
