from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from chores.assignment import FairAssignmentEngine
from chores.models import Chore, ChoreAssignment, ChoreOccurrence
from chores.services import OccurrenceService
from households.models import Household, HouseholdMember

User = get_user_model()


class MissedChoreDetectionAndLateCompletionTestCase(TestCase):
    """
    Test suite for Task 11: Missed Chore Detection and Late Completion Handling.
    Verifies:
    1. Automatic transition of past-due active occurrences to Missed.
    2. Preservation of assigned roommate and recording of missed statistics.
    3. Uncompleted missed chores provide 0 fairness workload credit.
    4. Completing missed chores transitions to Completed Late, preserving the missed record.
    5. Late completions credit effort points toward the roommate's 8-week fairness workload.
    """

    def setUp(self):
        self.client = APIClient()

        self.user_alice = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.user_bob = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )
        self.token_alice = Token.objects.create(user=self.user_alice)

        self.household = Household.objects.create(name="Baker Street Flat")
        HouseholdMember.objects.create(
            household=self.household, user=self.user_alice, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=self.household, user=self.user_bob, status=HouseholdMember.STATUS_ACTIVE
        )

        self.chore = Chore.objects.create(
            household=self.household,
            title="Clean Kitchen Oven",
            effort_level=Chore.EFFORT_LARGE,  # 3 points
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
            deadline_mode=Chore.DEADLINE_SPECIFIC,
            deadline_window_hours=24,
        )

    def test_detect_and_transition_past_due_active_chores_to_missed(self):
        """Active chores past their due date are transitioned to Missed while on-time chores stay active."""
        now = timezone.now()

        # Overdue active occurrence
        overdue_occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=2),
        )
        ChoreAssignment.objects.create(occurrence=overdue_occ, user=self.user_alice)

        # On-time active occurrence (on a different chore)
        chore2 = Chore.objects.create(
            household=self.household,
            title="Wipe Table",
            effort_level=Chore.EFFORT_SMALL,
            recurrence_type=Chore.RECURRENCE_NONE,
        )
        ontime_occ = ChoreOccurrence.objects.create(
            chore=chore2,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=1),
            due_date=now + timedelta(hours=5),
        )
        ChoreAssignment.objects.create(occurrence=ontime_occ, user=self.user_bob)

        # Chore without deadline (due_date is None)
        chore3 = Chore.objects.create(
            household=self.household,
            title="Sort Magazines",
            effort_level=Chore.EFFORT_SMALL,
            recurrence_type=Chore.RECURRENCE_NONE,
        )
        no_deadline_occ = ChoreOccurrence.objects.create(
            chore=chore3,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=3),
            due_date=None,
        )
        ChoreAssignment.objects.create(occurrence=no_deadline_occ, user=self.user_alice)

        # Run missed detection service
        missed = OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)

        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0].id, overdue_occ.id)

        overdue_occ.refresh_from_db()
        ontime_occ.refresh_from_db()
        no_deadline_occ.refresh_from_db()

        self.assertEqual(overdue_occ.status, ChoreOccurrence.STATUS_MISSED)
        self.assertTrue(overdue_occ.was_missed)
        self.assertIsNotNone(overdue_occ.missed_at)

        self.assertEqual(ontime_occ.status, ChoreOccurrence.STATUS_ACTIVE)
        self.assertFalse(ontime_occ.was_missed)

        self.assertEqual(no_deadline_occ.status, ChoreOccurrence.STATUS_ACTIVE)
        self.assertFalse(no_deadline_occ.was_missed)

    def test_missed_chore_retains_assigned_roommate_and_records_assignment_missed_state(self):
        """Transitioning to Missed retains assignments and marks assignment was_missed."""
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=1),
        )
        assignment = ChoreAssignment.objects.create(occurrence=occ, user=self.user_alice)

        OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)

        occ.refresh_from_db()
        assignment.refresh_from_db()

        # Assigned roommate is strictly retained
        self.assertEqual(occ.assignments.count(), 1)
        self.assertEqual(occ.assignments.first().user, self.user_alice)
        self.assertTrue(assignment.was_missed)
        self.assertIsNotNone(assignment.missed_at)

    def test_uncompleted_missed_chore_provides_zero_fairness_workload_credit(self):
        """Uncompleted missed chore does not grant any points toward 8-week fairness workload."""
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=1),
        )
        ChoreAssignment.objects.create(occurrence=occ, user=self.user_alice)

        OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)
        occ.refresh_from_db()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_MISSED)

        points = FairAssignmentEngine.get_completed_workload_points(
            user=self.user_alice, household=self.household, current_time=now
        )
        self.assertEqual(points, 0)

    def test_late_completion_transitions_to_completed_late_and_preserves_missed_record(self):
        """Completing a missed occurrence transitions to completed_late while preserving was_missed and missed_at."""
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=1),
        )
        ChoreAssignment.objects.create(occurrence=occ, user=self.user_alice)

        OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)
        occ.refresh_from_db()
        original_missed_at = occ.missed_at

        # Complete late
        completion_time = now + timedelta(hours=3)
        completed_occ = OccurrenceService.complete_occurrence(
            occurrence=occ,
            user=self.user_alice,
            notes="Apologies, finished late!",
            completed_time=completion_time,
        )

        self.assertEqual(completed_occ.status, ChoreOccurrence.STATUS_COMPLETED_LATE)
        self.assertTrue(completed_occ.was_missed)
        self.assertEqual(completed_occ.missed_at, original_missed_at)
        self.assertEqual(completed_occ.completed_at, completion_time)

        assignment = completed_occ.assignments.first()
        self.assertTrue(assignment.completed)
        self.assertTrue(assignment.was_missed)
        self.assertEqual(assignment.notes, "Apologies, finished late!")

    def test_late_completion_credits_workload_points_to_8_week_fairness_score(self):
        """Late completions credit full chore effort points toward the roommate's 8-week fairness workload."""
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=1),
        )
        ChoreAssignment.objects.create(occurrence=occ, user=self.user_alice)

        OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)

        # Before late completion: 0 points
        points_before = FairAssignmentEngine.get_completed_workload_points(
            user=self.user_alice, household=self.household, current_time=now
        )
        self.assertEqual(points_before, 0)

        # Complete late
        OccurrenceService.complete_occurrence(
            occurrence=occ,
            user=self.user_alice,
            completed_time=now + timedelta(hours=2),
        )

        # After late completion: full 3 points credited (Large chore)
        points_after = FairAssignmentEngine.get_completed_workload_points(
            user=self.user_alice, household=self.household, current_time=now + timedelta(hours=2)
        )
        self.assertEqual(points_after, 3)

    def test_late_completion_of_recurring_chore_generates_next_single_occurrence(self):
        """Completing a missed recurring chore late triggers generation of the next single upcoming occurrence."""
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=1),
        )
        ChoreAssignment.objects.create(occurrence=occ, user=self.user_alice)

        OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)

        OccurrenceService.complete_occurrence(
            occurrence=occ,
            user=self.user_alice,
            completed_time=now + timedelta(hours=2),
        )

        # Verify next single upcoming occurrence is generated
        upcoming_occurrences = self.chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING)
        self.assertEqual(upcoming_occurrences.count(), 1)
        next_occ = upcoming_occurrences.first()
        self.assertFalse(next_occ.was_missed)
        self.assertIsNone(next_occ.missed_at)

    def test_detect_missed_api_endpoint(self):
        """POST /api/occurrences/detect-missed/ transitions overdue chores and returns results."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=1),
        )
        ChoreAssignment.objects.create(occurrence=occ, user=self.user_alice)

        url = f"{reverse('chore-occurrence-list')}detect-missed/"
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["missed_count"], 1)
        self.assertIn(occ.id, data["missed_ids"])

        occ.refresh_from_db()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_MISSED)
        self.assertTrue(occ.was_missed)

    def test_missed_statistics_api_endpoint(self):
        """GET /api/occurrences/missed-statistics/ returns comprehensive missed metrics."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        now = timezone.now()

        # Occurrence 1: Missed and not yet completed
        occ1 = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=1),
        )
        ChoreAssignment.objects.create(occurrence=occ1, user=self.user_alice)

        # Occurrence 2: Missed and completed late
        chore2 = Chore.objects.create(
            household=self.household,
            title="Take Out Compost",
            effort_level=Chore.EFFORT_SMALL,
            recurrence_type=Chore.RECURRENCE_NONE,
        )
        occ2 = ChoreOccurrence.objects.create(
            chore=chore2,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=3),
            due_date=now - timedelta(days=1),
        )
        ChoreAssignment.objects.create(occurrence=occ2, user=self.user_alice)

        # Detect missed
        OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)

        # Complete occ2 late
        OccurrenceService.complete_occurrence(
            occurrence=occ2,
            user=self.user_alice,
            completed_time=now,
        )

        url = f"{reverse('chore-occurrence-list')}missed-statistics/?household={self.household.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stats = response.json()

        self.assertEqual(stats["user_total_missed"], 2)
        self.assertEqual(stats["user_currently_missed"], 1)
        self.assertEqual(stats["user_completed_late"], 1)
        self.assertEqual(stats["user_late_recovery_rate"], 50.0)
        self.assertEqual(stats["household_total_missed"], 2)
        self.assertEqual(stats["household_currently_missed"], 1)
        self.assertEqual(stats["household_completed_late"], 1)

    def test_complete_missed_via_api(self):
        """POST /api/occurrences/{id}/complete/ completes a missed chore as completed_late."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=1),
        )
        ChoreAssignment.objects.create(occurrence=occ, user=self.user_alice)
        OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)

        url = reverse("chore-occurrence-complete", kwargs={"pk": occ.id})
        response = self.client.post(url, {"notes": "Completed late via API"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "completed_late")
        self.assertTrue(data["was_missed"])
        self.assertIsNotNone(data["missed_at"])
        self.assertIsNotNone(data["completed_at"])
