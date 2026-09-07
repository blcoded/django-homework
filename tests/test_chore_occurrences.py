from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from chores.models import Chore, ChoreAssignment, ChoreOccurrence
from chores.services import OccurrenceService
from households.models import Household, HouseholdMember

User = get_user_model()


class ChoreOccurrenceLifecycleTestCase(TestCase):
    """Unit tests for occurrence state transitions, activation service, and single next-up constraint."""

    def setUp(self):
        self.user_a = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.user_b = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )

        self.household = Household.objects.create(name="Willow House")
        HouseholdMember.objects.create(
            household=self.household, user=self.user_a, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=self.household, user=self.user_b, status=HouseholdMember.STATUS_ACTIVE
        )

        self.chore = Chore.objects.create(
            household=self.household,
            title="Clean stove top",
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 3, "unit": "days"},
            deadline_mode=Chore.DEADLINE_SPECIFIC,
            deadline_window_hours=24,
        )

    def test_state_transitions_lifecycle(self):
        """Assert state transitions: Upcoming -> Active -> Missed -> Completed Late -> Disputed."""
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start=now + timedelta(hours=2),
            due_date=now + timedelta(hours=26),
        )

        # Upcoming -> Active
        occ.activate()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_ACTIVE)

        # Active -> Missed
        occ.mark_missed()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_MISSED)

        # Missed -> Completed Late
        occ.complete()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_COMPLETED_LATE)
        self.assertIsNotNone(occ.completed_at)

        # Completed Late -> Disputed
        occ.dispute()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_DISPUTED)

    def test_normal_completion_and_dispute(self):
        """Assert normal completion: Active -> Completed -> Disputed."""
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now,
            due_date=now + timedelta(hours=24),
        )

        occ.complete()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_COMPLETED)
        self.assertIsNotNone(occ.completed_at)

        occ.dispute()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_DISPUTED)

    def test_activation_service(self):
        """Activation service transitions past-due upcoming occurrences to active while leaving future ones upcoming."""
        now = timezone.now()
        past_upcoming = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start=now - timedelta(minutes=15),
        )
        future_upcoming = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start=now + timedelta(days=2),
        )

        activated = OccurrenceService.activate_upcoming_occurrences(current_time=now)
        self.assertIn(past_upcoming, activated)

        past_upcoming.refresh_from_db()
        future_upcoming.refresh_from_db()

        self.assertEqual(past_upcoming.status, ChoreOccurrence.STATUS_ACTIVE)
        self.assertEqual(future_upcoming.status, ChoreOccurrence.STATUS_UPCOMING)

    def test_only_one_upcoming_occurrence_exists_per_recurring_chore(self):
        """Only one upcoming occurrence exists per recurring chore at any given time."""
        # Generate initial upcoming occurrence
        occ1 = OccurrenceService.generate_next_occurrence(self.chore)
        self.assertEqual(occ1.status, ChoreOccurrence.STATUS_UPCOMING)
        self.assertEqual(
            self.chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).count(), 1
        )

        # Calling again returns the existing upcoming occurrence without creating a duplicate
        occ2 = OccurrenceService.generate_next_occurrence(self.chore)
        self.assertEqual(occ1.id, occ2.id)
        self.assertEqual(
            self.chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).count(), 1
        )

        # Now complete the current occurrence
        occ1.status = ChoreOccurrence.STATUS_ACTIVE
        occ1.save()
        ChoreAssignment.objects.create(occurrence=occ1, user=self.user_a)

        OccurrenceService.complete_occurrence(occurrence=occ1, user=self.user_a)
        occ1.refresh_from_db()
        self.assertEqual(occ1.status, ChoreOccurrence.STATUS_COMPLETED)

        # Check that the next single occurrence was generated upon completion
        upcoming_occurrences = self.chore.occurrences.filter(
            status=ChoreOccurrence.STATUS_UPCOMING
        )
        self.assertEqual(upcoming_occurrences.count(), 1)
        next_occ = upcoming_occurrences.first()
        self.assertNotEqual(occ1.id, next_occ.id)
        self.assertTrue(next_occ.scheduled_start > occ1.completed_at)

    def test_multi_person_occurrence_completion(self):
        """Multi-assignee occurrence requires every assigned roommate to independently complete."""
        multi_chore = Chore.objects.create(
            household=self.household,
            title="Clean entire kitchen together",
            is_multi_assignee=True,
            required_assignees_count=2,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
        )

        occ = ChoreOccurrence.objects.create(
            chore=multi_chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=timezone.now(),
        )
        ChoreAssignment.objects.create(occurrence=occ, user=self.user_a)
        ChoreAssignment.objects.create(occurrence=occ, user=self.user_b)

        # Alice completes her part -> occurrence remains ACTIVE
        OccurrenceService.complete_occurrence(occ, self.user_a, notes="Wiped appliances")
        occ.refresh_from_db()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_ACTIVE)
        self.assertIsNone(occ.completed_at)

        # Bob completes his part -> all required assignees completed, occurrence transitions to COMPLETED
        OccurrenceService.complete_occurrence(occ, self.user_b, notes="Mopped the floor")
        occ.refresh_from_db()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_COMPLETED)
        self.assertIsNotNone(occ.completed_at)

        # Next upcoming occurrence generated
        self.assertEqual(
            multi_chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).count(), 1
        )
