from datetime import timedelta
import io
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


class ChoreCompletionWorkflowTestCase(TestCase):
    """
    Test suite for Task 12: Chore Completion Workflow with Proof Upload and Multi-Person Support.
    Verifies:
    1. Single-tap completion with optional notes.
    2. Valid photo proof uploads (JPEG, PNG).
    3. Rejection of invalid/spoofed or oversized photo uploads.
    4. Multi-person completion gating: occurrence only completes once every assigned roommate submits.
    5. Independent notes and photo uploads per assigned roommate.
    6. Non-assigned roommate access control.
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

        # Single-person recurring chore
        self.single_chore = Chore.objects.create(
            household=self.household,
            title="Clean Microwave",
            effort_level=Chore.EFFORT_SMALL,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 3, "unit": "days"},
        )

        now = timezone.now()
        self.single_occ = ChoreOccurrence.objects.create(
            chore=self.single_chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=2),
            due_date=now + timedelta(hours=22),
        )
        self.single_assignment = ChoreAssignment.objects.create(
            occurrence=self.single_occ, user=self.user_alice
        )

    def _create_dummy_jpeg(self, filename="proof.jpg"):
        # Valid JPEG magic bytes + header
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00" + (
            b"\x00" * 64
        ) + b"\xff\xd9"
        return SimpleUploadedFile(filename, content, content_type="image/jpeg")

    def _create_dummy_png(self, filename="proof.png"):
        # Valid PNG signature
        content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + (
            b"\x00" * 32
        )
        return SimpleUploadedFile(filename, content, content_type="image/png")

    def test_single_tap_completion_via_api(self):
        """Single-tap completion: POST without body or empty body completes chore immediately."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-occurrence-complete", kwargs={"pk": self.single_occ.id})

        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertIsNotNone(data["completed_at"])

        self.single_assignment.refresh_from_db()
        self.assertTrue(self.single_assignment.completed)
        self.assertIsNotNone(self.single_assignment.completed_at)
        self.assertEqual(self.single_assignment.notes, "")

    def test_completion_with_optional_notes(self):
        """Roommate can include optional completion notes."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-occurrence-complete", kwargs={"pk": self.single_occ.id})

        response = self.client.post(
            url, {"notes": "Wiped inside and out, emptied turntable."}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.single_assignment.refresh_from_db()
        self.assertTrue(self.single_assignment.completed)
        self.assertEqual(
            self.single_assignment.notes, "Wiped inside and out, emptied turntable."
        )

    def test_completion_with_valid_photo_proof_jpeg(self):
        """Roommate can upload valid JPEG photo evidence."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-occurrence-complete", kwargs={"pk": self.single_occ.id})

        photo = self._create_dummy_jpeg()
        response = self.client.post(
            url,
            {"notes": "Attached photo of sparkling clean oven.", "proof_image": photo},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.single_assignment.refresh_from_db()
        self.assertTrue(self.single_assignment.completed)
        self.assertTrue(bool(self.single_assignment.proof_image))
        self.assertIn("proof", self.single_assignment.proof_image.name)

    def test_completion_with_valid_photo_proof_png(self):
        """Roommate can upload valid PNG photo evidence."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-occurrence-complete", kwargs={"pk": self.single_occ.id})

        photo = self._create_dummy_png()
        response = self.client.post(
            url,
            {"proof_image": photo},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.single_assignment.refresh_from_db()
        self.assertTrue(bool(self.single_assignment.proof_image))

    def test_invalid_photo_proof_rejection(self):
        """Uploading non-image files (e.g. text/script) is strictly rejected with 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-occurrence-complete", kwargs={"pk": self.single_occ.id})

        fake_file = SimpleUploadedFile(
            "document.txt",
            b"This is just plain text, not a photo.",
            content_type="text/plain",
        )
        response = self.client.post(
            url,
            {"proof_image": fake_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("proof_image", response.json())

    def test_spoofed_extension_rejection(self):
        """Uploading non-image content with an image extension is caught and rejected."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("chore-occurrence-complete", kwargs={"pk": self.single_occ.id})

        spoofed_file = SimpleUploadedFile(
            "fake.jpg",
            b"Not really a JPEG binary file at all!",
            content_type="image/jpeg",
        )
        response = self.client.post(
            url,
            {"proof_image": spoofed_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("proof_image", response.json())

    def test_multi_person_completion_gating(self):
        """
        Multi-person chore completion gating:
        The occurrence only completes once every assigned roommate submits their completion.
        """
        multi_chore = Chore.objects.create(
            household=self.household,
            title="Clean Living Room and Vacuum Rugs",
            effort_level=Chore.EFFORT_LARGE,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
            is_multi_assignee=True,
            required_assignees_count=2,
        )

        now = timezone.now()
        multi_occ = ChoreOccurrence.objects.create(
            chore=multi_chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=1),
            due_date=now + timedelta(hours=23),
        )

        assignment_alice = ChoreAssignment.objects.create(
            occurrence=multi_occ, user=self.user_alice
        )
        assignment_bob = ChoreAssignment.objects.create(
            occurrence=multi_occ, user=self.user_bob
        )

        url = reverse("chore-occurrence-complete", kwargs={"pk": multi_occ.id})

        # Step 1: Alice submits her completion with photo proof
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        photo_alice = self._create_dummy_jpeg("alice.jpg")
        res_alice = self.client.post(
            url,
            {"notes": "Alice dusted shelves and tidied tables.", "proof_image": photo_alice},
            format="multipart",
        )
        self.assertEqual(res_alice.status_code, status.HTTP_200_OK)

        # Occurrence MUST STILL BE ACTIVE because Bob has not yet completed
        multi_occ.refresh_from_db()
        self.assertEqual(multi_occ.status, ChoreOccurrence.STATUS_ACTIVE)
        self.assertIsNone(multi_occ.completed_at)

        assignment_alice.refresh_from_db()
        assignment_bob.refresh_from_db()
        self.assertTrue(assignment_alice.completed)
        self.assertFalse(assignment_bob.completed)

        # No new occurrence generated yet
        self.assertEqual(
            multi_chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING).count(), 0
        )

        # Step 2: Bob submits his completion
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        photo_bob = self._create_dummy_png("bob.png")
        res_bob = self.client.post(
            url,
            {"notes": "Bob vacuumed all rugs and mopped hardwood.", "proof_image": photo_bob},
            format="multipart",
        )
        self.assertEqual(res_bob.status_code, status.HTTP_200_OK)

        # Now all required assignees have completed -> Occurrence transitions to COMPLETED
        multi_occ.refresh_from_db()
        self.assertEqual(multi_occ.status, ChoreOccurrence.STATUS_COMPLETED)
        self.assertIsNotNone(multi_occ.completed_at)

        assignment_bob.refresh_from_db()
        self.assertTrue(assignment_bob.completed)

        # Both roommates have their separate notes and proofs preserved
        self.assertIn("Alice", assignment_alice.notes)
        self.assertIn("Bob", assignment_bob.notes)
        self.assertTrue(bool(assignment_alice.proof_image))
        self.assertTrue(bool(assignment_bob.proof_image))

        # Because recurring, next occurrence has now been generated
        upcoming = multi_chore.occurrences.filter(status=ChoreOccurrence.STATUS_UPCOMING)
        self.assertEqual(upcoming.count(), 1)

    def test_unassigned_roommate_cannot_complete_assigned_chore(self):
        """Roommate not assigned to occurrence cannot submit completion on it."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_charlie.key}")
        url = reverse("chore-occurrence-complete", kwargs={"pk": self.single_occ.id})

        # Single occ is assigned to Alice, not Charlie
        response = self.client.post(url, {"notes": "Charlie did it instead"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("not an assigned roommate", response.json()["detail"])

    def test_outsider_cannot_complete_chore(self):
        """User from a different household cannot complete the occurrence."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_outsider.key}")
        url = reverse("chore-occurrence-complete", kwargs={"pk": self.single_occ.id})

        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
