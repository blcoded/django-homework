from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from chores.models import Chore, ChoreAssignment, ChoreOccurrence
from chores.rotation import HiddenRotationService, HiddenRotationViolationError
from chores.services import OccurrenceService
from households.models import Household, HouseholdMember

User = get_user_model()


class HiddenRotationServiceTestCase(TestCase):
    """
    Test suite for Task 10: Single Next-Up Visibility and Hidden Rotation Service.
    Verifies that:
    1. The API exposes only the single next upcoming occurrence and its assigned roommate for each chore.
    2. The database and endpoints prevent generating or leaking multi-week future schedules.
    3. Client responses never disclose future rotation order.
    """

    def setUp(self):
        self.client = APIClient()

        self.user_alice = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.user_bob = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )
        self.user_charlie = User.objects.create_user(
            email="charlie@example.com", password="Password123!", display_name="Charlie"
        )
        self.user_outsider = User.objects.create_user(
            email="outsider@example.com", password="Password123!", display_name="Outsider"
        )

        self.token_alice = Token.objects.create(user=self.user_alice)
        self.token_outsider = Token.objects.create(user=self.user_outsider)

        self.household = Household.objects.create(name="Baker Street Flat")
        HouseholdMember.objects.create(
            household=self.household, user=self.user_alice, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=self.household, user=self.user_bob, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=self.household, user=self.user_charlie, status=HouseholdMember.STATUS_ACTIVE
        )

        self.chore = Chore.objects.create(
            household=self.household,
            title="Clean Kitchen Stove",
            effort_level=Chore.EFFORT_MEDIUM,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 3, "unit": "days"},
            deadline_mode=Chore.DEADLINE_FLEXIBLE_WINDOW,
            deadline_window_hours=24,
        )

        # Generate single next-up occurrence scheduled in the future
        future_time = timezone.now() + timedelta(days=3)
        self.occurrence = OccurrenceService.generate_next_occurrence(
            chore=self.chore, from_time=future_time
        )

    def test_next_up_service_returns_single_next_upcoming_occurrence_and_assignee(self):
        """HiddenRotationService returns the single upcoming occurrence and its assigned roommate."""
        next_occ = HiddenRotationService.get_next_up_occurrence(self.chore)
        self.assertIsNotNone(next_occ)
        self.assertEqual(next_occ.id, self.occurrence.id)
        self.assertEqual(next_occ.status, ChoreOccurrence.STATUS_UPCOMING)

        assignees = HiddenRotationService.get_next_assignees(self.chore)
        self.assertEqual(len(assignees), 1)
        self.assertIn(assignees[0], [self.user_alice, self.user_bob, self.user_charlie])

        data = HiddenRotationService.get_next_up_data(self.chore)
        self.assertEqual(data["chore_id"], self.chore.id)
        self.assertEqual(data["occurrence_id"], self.occurrence.id)
        self.assertEqual(data["status"], ChoreOccurrence.STATUS_UPCOMING)
        self.assertEqual(data["assigned_roommate"]["id"], assignees[0].id)
        self.assertEqual(data["assigned_roommate"]["display_name"], assignees[0].display_name)

    def test_database_constraint_blocks_multiple_upcoming_occurrences(self):
        """Database UniqueConstraint strictly prevents multiple upcoming occurrences for the same chore."""
        self.assertEqual(
            self.chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).count(), 1
        )
        with self.assertRaises(IntegrityError):
            ChoreOccurrence.objects.create(
                chore=self.chore,
                status=ChoreOccurrence.STATUS_UPCOMING,
                scheduled_start=timezone.now() + timedelta(days=7),
            )

    def test_service_prevents_multi_week_generation_and_future_rotation_requests(self):
        """Calling generate_next_occurrence returns existing upcoming and blocks multi-week creation."""
        # Calling generate_next_occurrence when upcoming exists does not duplicate
        second = OccurrenceService.generate_next_occurrence(self.chore)
        self.assertEqual(second.id, self.occurrence.id)
        self.assertEqual(
            self.chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).count(), 1
        )

        # Explicit multi-week check raises error
        with self.assertRaises(HiddenRotationViolationError):
            HiddenRotationService.prevent_multi_week_generation(self.chore)

        # Future rotation request raises error
        with self.assertRaises(HiddenRotationViolationError):
            HiddenRotationService.request_future_rotation(self.chore, weeks=4)

    def test_api_chore_detail_exposes_only_immediate_next_up_without_leakage(self):
        """GET /api/chores/{id}/ exposes single next_up and never leaks future rotation order."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-detail", kwargs={"pk": self.chore.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()

        self.assertIn("next_up", payload)
        next_up = payload["next_up"]
        self.assertIsNotNone(next_up)
        self.assertEqual(next_up["occurrence_id"], self.occurrence.id)
        self.assertEqual(next_up["status"], "upcoming")
        self.assertIn("assigned_roommate", next_up)
        self.assertIsNotNone(next_up["assigned_roommate"])

        # Deep assertions: verify no forbidden rotation leakage keys exist anywhere in payload
        HiddenRotationService.assert_no_rotation_leakage(payload)
        self.assertNotIn("future_rotation", payload)
        self.assertNotIn("rotation_order", payload)
        self.assertNotIn("future_assignees", payload)
        self.assertNotIn("rotation_queue", payload)
        self.assertNotIn("upcoming_queue", payload)
        self.assertNotIn("multi_week_schedule", payload)

    def test_api_chore_next_up_endpoint(self):
        """GET /api/chores/{id}/next-up/ returns single next-up occurrence with assigned roommate."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-next-up", kwargs={"pk": self.chore.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["occurrence_id"], self.occurrence.id)
        self.assertEqual(data["status"], "upcoming")
        self.assertIsNotNone(data["assigned_roommate"])
        self.assertIn("email", data["assigned_roommate"])

        HiddenRotationService.assert_no_rotation_leakage(data)

    def test_api_household_next_up_endpoint(self):
        """GET /api/chores/next-up/?household={id} returns list of next-up for household chores."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")

        # Create a second chore with an upcoming occurrence
        chore2 = Chore.objects.create(
            household=self.household,
            title="Clean Bathroom Mirror",
            effort_level=Chore.EFFORT_SMALL,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 2, "unit": "days"},
        )
        occ2 = OccurrenceService.generate_next_occurrence(
            chore=chore2, from_time=timezone.now() + timedelta(days=2)
        )

        url = f"{reverse('chore-list')}next-up/?household={self.household.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

        occurrence_ids = [item["occurrence_id"] for item in data]
        self.assertIn(self.occurrence.id, occurrence_ids)
        self.assertIn(occ2.id, occurrence_ids)

        for item in data:
            self.assertIsNotNone(item["assigned_roommate"])
            self.assertEqual(item["status"], "upcoming")
            HiddenRotationService.assert_no_rotation_leakage(item)

    def test_future_rotation_endpoints_return_forbidden(self):
        """Querying rotation order or future multi-week schedules returns 403 Forbidden."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")

        # Detail rotation endpoint
        url_detail = reverse("chore-rotation", kwargs={"pk": self.chore.id})
        res_detail = self.client.get(url_detail)
        self.assertEqual(res_detail.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Future rotation order is hidden", res_detail.json()["detail"])

        # List rotation endpoint
        url_list = f"{reverse('chore-list')}rotation/"
        res_list = self.client.get(url_list)
        self.assertEqual(res_list.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Future rotation schedules are hidden", res_list.json()["detail"])

        # Occurrence future schedule endpoint
        url_occ_future = f"{reverse('chore-occurrence-list')}future-schedule/"
        res_occ_future = self.client.get(url_occ_future)
        self.assertEqual(res_occ_future.status_code, status.HTTP_403_FORBIDDEN)

    def test_occurrences_next_up_endpoint_contains_single_occurrence_per_chore(self):
        """GET /api/occurrences/next-up/ returns only upcoming occurrences without future duplicates."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = f"{reverse('chore-occurrence-list')}next-up/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], self.occurrence.id)
        self.assertEqual(items[0]["status"], "upcoming")

        HiddenRotationService.assert_no_rotation_leakage(items)

    def test_rotation_advances_just_in_time_preserving_surprise(self):
        """
        Completing an occurrence generates the next single upcoming occurrence just-in-time,
        maintaining zero pre-generated future occurrences before completion.
        """
        # Activate the upcoming occurrence
        self.occurrence.activate()
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.status, ChoreOccurrence.STATUS_ACTIVE)

        # While active, there are ZERO upcoming occurrences (future rotation remains undisclosed)
        self.assertEqual(
            self.chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).count(), 0
        )
        self.assertIsNone(HiddenRotationService.get_next_up_data(self.chore))

        # Complete the active occurrence
        assigned_user = self.occurrence.assignments.first().user
        OccurrenceService.complete_occurrence(
            occurrence=self.occurrence,
            user=assigned_user,
            notes="Done on time",
            completed_time=timezone.now(),
        )

        # Now exactly ONE upcoming occurrence has been generated JIT
        self.assertEqual(
            self.chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).count(), 1
        )
        new_next_up = HiddenRotationService.get_next_up_data(self.chore)
        self.assertIsNotNone(new_next_up)
        self.assertNotEqual(new_next_up["occurrence_id"], self.occurrence.id)
        self.assertEqual(new_next_up["status"], "upcoming")
        self.assertIsNotNone(new_next_up["assigned_roommate"])

    def test_multi_assignee_chore_next_up_exposes_all_next_assignees_without_future_leak(self):
        """Multi-assignee chore next-up exposes all immediate assignees and no future rotation."""
        multi_chore = Chore.objects.create(
            household=self.household,
            title="Clean Shared Balcony",
            effort_level=Chore.EFFORT_LARGE,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
            is_multi_assignee=True,
            required_assignees_count=2,
        )

        multi_occ = OccurrenceService.generate_next_occurrence(
            chore=multi_chore, from_time=timezone.now() + timedelta(days=7)
        )

        data = HiddenRotationService.get_next_up_data(multi_chore)
        self.assertIsNotNone(data)
        self.assertEqual(len(data["assignees"]), 2)
        HiddenRotationService.assert_no_rotation_leakage(data)

    def test_outsider_cannot_view_household_next_up(self):
        """Users who are not active members of the household cannot access next-up endpoints."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_outsider.key}")
        url = reverse("chore-next-up", kwargs={"pk": self.chore.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
