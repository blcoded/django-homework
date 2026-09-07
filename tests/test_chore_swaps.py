from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from chores.assignment import FairAssignmentEngine
from chores.models import Chore, ChoreAssignment, ChoreOccurrence, ChoreSwapRequest
from chores.services import OccurrenceService
from households.models import Household, HouseholdMember

User = get_user_model()


class ChoreSwapWorkflowTestCase(TestCase):
    """
    Test suite for Task 14: Chore Swap Request and Mutual Acceptance Workflow.
    Verifies:
    1. Proposing a chore swap between roommates.
    2. Mutual acceptance requirement: only recipient can accept or decline.
    3. Reassignment of occurrences upon mutual agreement.
    4. Crucial rule: personal favor chore swaps leave 8-week fairness calculations unaffected.
    5. Proposer cancellation and decline flows.
    6. Validation preventing self-swaps, unassigned chores, and outsider requests.
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
        self.token_bob = Token.objects.create(user=self.user_bob)
        self.token_charlie = Token.objects.create(user=self.user_charlie)
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

        # Chore A: Large (3 pts)
        self.chore_a = Chore.objects.create(
            household=self.household,
            title="Deep Clean Kitchen",
            effort_level=Chore.EFFORT_LARGE,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
        )

        # Chore B: Small (1 pt)
        self.chore_b = Chore.objects.create(
            household=self.household,
            title="Take Out Recycling",
            effort_level=Chore.EFFORT_SMALL,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 3, "unit": "days"},
        )

        now = timezone.now()
        self.occ_a = ChoreOccurrence.objects.create(
            chore=self.chore_a,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=1),
            due_date=now + timedelta(hours=23),
        )
        self.assign_a = ChoreAssignment.objects.create(
            occurrence=self.occ_a, user=self.user_alice
        )

        self.occ_b = ChoreOccurrence.objects.create(
            chore=self.chore_b,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=1),
            due_date=now + timedelta(hours=23),
        )
        self.assign_b = ChoreAssignment.objects.create(
            occurrence=self.occ_b, user=self.user_bob
        )

        self.swaps_url = reverse("chore-swap-list")

    def test_propose_chore_swap_success(self):
        """Roommate can propose a chore swap to another roommate."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        payload = {
            "recipient_id": self.user_bob.id,
            "proposer_occurrence_id": self.occ_a.id,
            "recipient_occurrence_id": self.occ_b.id,
            "notes": "Could we swap? I have a late shift tomorrow.",
        }
        response = self.client.post(self.swaps_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["proposer"]["id"], self.user_alice.id)
        self.assertEqual(data["recipient"]["id"], self.user_bob.id)
        self.assertEqual(data["proposer_occurrence"]["id"], self.occ_a.id)
        self.assertEqual(data["recipient_occurrence"]["id"], self.occ_b.id)

    def test_recipient_can_accept_swap_and_reassigns_occurrences(self):
        """When recipient accepts, assigned roommates on respective occurrences are swapped."""
        swap = ChoreSwapRequest.objects.create(
            household=self.household,
            proposer=self.user_alice,
            recipient=self.user_bob,
            proposer_occurrence=self.occ_a,
            recipient_occurrence=self.occ_b,
            notes="Please trade!",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        url = reverse("chore-swap-accept", kwargs={"pk": swap.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        swap.refresh_from_db()
        self.assertEqual(swap.status, "accepted")
        self.assertIsNotNone(swap.responded_at)

        # Occurrence A (originally Alice) is now assigned to Bob
        self.assign_a.refresh_from_db()
        self.assertEqual(self.assign_a.user, self.user_bob)
        self.assertEqual(self.assign_a.original_user, self.user_alice)
        self.assertTrue(self.assign_a.is_swapped)

        # Occurrence B (originally Bob) is now assigned to Alice
        self.assign_b.refresh_from_db()
        self.assertEqual(self.assign_b.user, self.user_alice)
        self.assertEqual(self.assign_b.original_user, self.user_bob)
        self.assertTrue(self.assign_b.is_swapped)

    def test_proposer_cannot_accept_own_swap(self):
        """Mutual acceptance enforcement: proposer cannot accept their own swap request."""
        swap = ChoreSwapRequest.objects.create(
            household=self.household,
            proposer=self.user_alice,
            recipient=self.user_bob,
            proposer_occurrence=self.occ_a,
            recipient_occurrence=self.occ_b,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-swap-accept", kwargs={"pk": swap.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Only the recipient", response.json()["detail"])

        swap.refresh_from_db()
        self.assertEqual(swap.status, "pending")

    def test_recipient_can_decline_swap(self):
        """Recipient can decline swap request, leaving occurrences unchanged."""
        swap = ChoreSwapRequest.objects.create(
            household=self.household,
            proposer=self.user_alice,
            recipient=self.user_bob,
            proposer_occurrence=self.occ_a,
            recipient_occurrence=self.occ_b,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        url = reverse("chore-swap-decline", kwargs={"pk": swap.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        swap.refresh_from_db()
        self.assertEqual(swap.status, "declined")

        # Occurrences remain with original assignees
        self.assign_a.refresh_from_db()
        self.assertEqual(self.assign_a.user, self.user_alice)
        self.assertFalse(self.assign_a.is_swapped)

        self.assign_b.refresh_from_db()
        self.assertEqual(self.assign_b.user, self.user_bob)
        self.assertFalse(self.assign_b.is_swapped)

    def test_proposer_can_cancel_pending_swap(self):
        """Proposer can cancel their pending swap request."""
        swap = ChoreSwapRequest.objects.create(
            household=self.household,
            proposer=self.user_alice,
            recipient=self.user_bob,
            proposer_occurrence=self.occ_a,
            recipient_occurrence=self.occ_b,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-swap-cancel", kwargs={"pk": swap.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        swap.refresh_from_db()
        self.assertEqual(swap.status, "cancelled")

    def test_personal_favor_leaves_8_week_fairness_calculations_unaffected(self):
        """
        CRITICAL ACCEPTANCE CRITERION:
        Swapping chores is treated as a personal favor between roommates that leaves
        8-week fairness calculations completely unaffected.
        """
        now = timezone.now()

        # Alice had Chore A (Large = 3 pts). Bob had Chore B (Small = 1 pt).
        swap = ChoreSwapRequest.objects.create(
            household=self.household,
            proposer=self.user_alice,
            recipient=self.user_bob,
            proposer_occurrence=self.occ_a,
            recipient_occurrence=self.occ_b,
        )
        swap.accept()

        # Now Bob is doing Chore A, and Alice is doing Chore B.
        self.assertEqual(self.occ_a.assignments.first().user, self.user_bob)
        self.assertEqual(self.occ_b.assignments.first().user, self.user_alice)

        # Bob completes Chore A (Large = 3 pts)
        OccurrenceService.complete_occurrence(
            occurrence=self.occ_a,
            user=self.user_bob,
            completed_time=now,
        )

        # Alice completes Chore B (Small = 1 pt)
        OccurrenceService.complete_occurrence(
            occurrence=self.occ_b,
            user=self.user_alice,
            completed_time=now,
        )

        # Verify fairness workload points:
        # Alice should have 3 points credited (Chore A was her scheduled chore)
        alice_workload = FairAssignmentEngine.get_completed_workload_points(
            user=self.user_alice, household=self.household, current_time=now
        )
        self.assertEqual(alice_workload, 3)

        # Bob should have 1 point credited (Chore B was his scheduled chore)
        bob_workload = FairAssignmentEngine.get_completed_workload_points(
            user=self.user_bob, household=self.household, current_time=now
        )
        self.assertEqual(bob_workload, 1)

    def test_one_way_chore_cover_swap(self):
        """Roommate can propose a 1-way cover where recipient takes occurrence without giving one back."""
        swap = ChoreSwapRequest.objects.create(
            household=self.household,
            proposer=self.user_alice,
            recipient=self.user_bob,
            proposer_occurrence=self.occ_a,
            recipient_occurrence=None,  # 1-way cover
        )
        swap.accept()

        self.assign_a.refresh_from_db()
        self.assertEqual(self.assign_a.user, self.user_bob)
        self.assertEqual(self.assign_a.original_user, self.user_alice)

        now = timezone.now()
        OccurrenceService.complete_occurrence(
            occurrence=self.occ_a,
            user=self.user_bob,
            completed_time=now,
        )

        # Alice receives the fairness credit because Bob covered her as a personal favor
        self.assertEqual(
            FairAssignmentEngine.get_completed_workload_points(
                user=self.user_alice, household=self.household, current_time=now
            ),
            3,
        )
        self.assertEqual(
            FairAssignmentEngine.get_completed_workload_points(
                user=self.user_bob, household=self.household, current_time=now
            ),
            0,
        )

    def test_cannot_swap_with_yourself(self):
        """Proposing a swap with oneself is rejected."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        payload = {
            "recipient_id": self.user_alice.id,
            "proposer_occurrence_id": self.occ_a.id,
        }
        response = self.client.post(self.swaps_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_swap_unassigned_chore(self):
        """Proposing a swap with an occurrence not assigned to proposer is rejected."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        # occ_b is assigned to Bob, not Alice
        payload = {
            "recipient_id": self.user_bob.id,
            "proposer_occurrence_id": self.occ_b.id,
        }
        response = self.client.post(self.swaps_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only offer chore occurrences that are currently assigned to you", str(response.json()))

    def test_cannot_swap_with_outsider(self):
        """Proposing a swap with an outsider not in the household is rejected."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        payload = {
            "recipient_id": self.user_outsider.id,
            "proposer_occurrence_id": self.occ_a.id,
        }
        response = self.client.post(self.swaps_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
