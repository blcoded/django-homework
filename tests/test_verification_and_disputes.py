from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from chores.models import Chore, ChoreAssignment, ChoreOccurrence
from chores.services import OccurrenceService
from households.models import Household, HouseholdMember

User = get_user_model()


class HouseholdVerificationAndDisputeTestCase(TestCase):
    """
    Test suite for Task 13: Household Completion Verification and Dispute Workflows.
    Verifies:
    1. Household verification toggle configuration.
    2. Roommate completion verification with notes and non-self-verification rule.
    3. Audit-preserving dispute mechanism that flags occurrences as Disputed without
       erasing completion records, timestamps, notes, or photo evidence.
    4. Dispute resolution workflow.
    5. Access control restricting verification and disputes to active household members.
    """

    def setUp(self):
        self.client = APIClient()

        self.user_alice = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.user_bob = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )
        self.user_outsider = User.objects.create_user(
            email="outsider@example.com", password="Password123!", display_name="Outsider"
        )

        self.token_alice = Token.objects.create(user=self.user_alice)
        self.token_bob = Token.objects.create(user=self.user_bob)
        self.token_outsider = Token.objects.create(user=self.user_outsider)

        self.household = Household.objects.create(
            name="Baker Street Flat", require_completion_verification=True
        )
        HouseholdMember.objects.create(
            household=self.household, user=self.user_alice, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=self.household, user=self.user_bob, status=HouseholdMember.STATUS_ACTIVE
        )

        self.chore = Chore.objects.create(
            household=self.household,
            title="Clean Kitchen Range",
            effort_level=Chore.EFFORT_MEDIUM,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
        )

    def _complete_chore_with_proof(self):
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=3),
            due_date=now + timedelta(hours=21),
        )
        photo_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00" + (
            b"\x00" * 64
        ) + b"\xff\xd9"
        dummy_photo = SimpleUploadedFile("clean_range.jpg", photo_content, content_type="image/jpeg")

        completed_time = now - timedelta(hours=1)
        OccurrenceService.complete_occurrence(
            occurrence=occ,
            user=self.user_alice,
            notes="Wiped down range, burners scrubbed clean.",
            proof_image=dummy_photo,
            completed_time=completed_time,
        )
        occ.refresh_from_db()
        return occ, completed_time

    def test_household_completion_verification_toggle(self):
        """Household completion verification toggle can be updated via household endpoint."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("household-detail", kwargs={"pk": self.household.id})

        # Turn toggle off
        res_off = self.client.patch(url, {"require_completion_verification": False}, format="json")
        self.assertEqual(res_off.status_code, status.HTTP_200_OK)
        self.assertFalse(res_off.json()["require_completion_verification"])

        self.household.refresh_from_db()
        self.assertFalse(self.household.require_completion_verification)

        # Turn toggle on
        res_on = self.client.patch(url, {"require_completion_verification": True}, format="json")
        self.assertEqual(res_on.status_code, status.HTTP_200_OK)
        self.assertTrue(res_on.json()["require_completion_verification"])

    def test_roommate_can_formally_verify_completed_chore(self):
        """Active roommate can formally verify completed chore with verification notes."""
        occ, _ = self._complete_chore_with_proof()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")

        url = reverse("chore-occurrence-verify", kwargs={"pk": occ.id})
        response = self.client.post(
            url, {"notes": "Inspected stove, completely spotless. Great job!"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertTrue(data["is_verified"])
        self.assertIsNotNone(data["verified_at"])
        self.assertEqual(data["verified_by"]["id"], self.user_bob.id)
        self.assertEqual(
            data["verification_notes"], "Inspected stove, completely spotless. Great job!"
        )

        occ.refresh_from_db()
        self.assertTrue(occ.is_verified)
        self.assertEqual(occ.verified_by, self.user_bob)

    def test_cannot_self_verify_in_multi_member_household(self):
        """Roommate cannot verify their own completion when other roommates exist."""
        occ, _ = self._complete_chore_with_proof()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")

        url = reverse("chore-occurrence-verify", kwargs={"pk": occ.id})
        response = self.client.post(url, {"notes": "I verify myself"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot verify your own", response.json()["detail"])

    def test_cannot_verify_uncompleted_chore(self):
        """Cannot verify an active or uncompleted occurrence."""
        now = timezone.now()
        active_occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        url = reverse("chore-occurrence-verify", kwargs={"pk": active_occ.id})

        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must be completed first", response.json()["detail"].lower())

    def test_audit_preserving_dispute_endpoint(self):
        """
        Disputing flags the occurrence as Disputed with explanation notes
        WITHOUT erasing underlying completion records, timestamps, notes, or photo evidence.
        """
        occ, original_completed_time = self._complete_chore_with_proof()
        assignment = occ.assignments.first()
        original_proof_name = assignment.proof_image.name

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        url = reverse("chore-occurrence-dispute", kwargs={"pk": occ.id})
        response = self.client.post(
            url,
            {"reason": "Burners were not wiped underneath; grease remains."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["status"], "disputed")
        self.assertTrue(data["is_disputed"])
        self.assertEqual(data["disputed_by"]["id"], self.user_bob.id)
        self.assertIsNotNone(data["disputed_at"])
        self.assertEqual(
            data["dispute_reason"], "Burners were not wiped underneath; grease remains."
        )

        # STRICT AUDIT INTEGRITY CHECKS
        occ.refresh_from_db()
        assignment.refresh_from_db()

        # Occurrence completion timestamp is NOT erased
        self.assertIsNotNone(occ.completed_at)
        self.assertEqual(occ.completed_at, original_completed_time)

        # Assignment completion status is NOT erased
        self.assertTrue(assignment.completed)
        self.assertEqual(assignment.completed_at, original_completed_time)

        # Assignment notes are NOT erased
        self.assertEqual(assignment.notes, "Wiped down range, burners scrubbed clean.")

        # Photo evidence is NOT erased and remains intact
        self.assertTrue(bool(assignment.proof_image))
        self.assertEqual(assignment.proof_image.name, original_proof_name)

    def test_dispute_requires_non_empty_reason(self):
        """Disputing without a reason fails validation."""
        occ, _ = self._complete_chore_with_proof()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        url = reverse("chore-occurrence-dispute", kwargs={"pk": occ.id})

        response = self.client.post(url, {"reason": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.json())

    def test_cannot_dispute_uncompleted_chore(self):
        """Active chores that have not been completed cannot be disputed."""
        now = timezone.now()
        active_occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        url = reverse("chore-occurrence-dispute", kwargs={"pk": active_occ.id})

        response = self.client.post(url, {"reason": "Not done"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resolve_dispute_workflow(self):
        """Disputed occurrence can have its dispute resolved back to completed."""
        occ, _ = self._complete_chore_with_proof()
        occ.dispute(
            disputed_by=self.user_bob,
            reason="Grease still on knobs",
        )
        occ.refresh_from_db()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_DISPUTED)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        url = reverse("chore-occurrence-resolve-dispute", kwargs={"pk": occ.id})
        response = self.client.post(
            url, {"notes": "Alice re-cleaned the knobs; resolved!"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertFalse(data["is_disputed"])
        self.assertIn("Alice re-cleaned", data["verification_notes"])

    def test_outsider_cannot_verify_or_dispute(self):
        """Users who are not active members of the household cannot verify or dispute chores."""
        occ, _ = self._complete_chore_with_proof()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_outsider.key}")

        # Verify attempt
        res_verify = self.client.post(
            reverse("chore-occurrence-verify", kwargs={"pk": occ.id}), {}, format="json"
        )
        self.assertEqual(res_verify.status_code, status.HTTP_404_NOT_FOUND)

        # Dispute attempt
        res_dispute = self.client.post(
            reverse("chore-occurrence-dispute", kwargs={"pk": occ.id}),
            {"reason": "Outsider complains"},
            format="json",
        )
        self.assertEqual(res_dispute.status_code, status.HTTP_404_NOT_FOUND)
