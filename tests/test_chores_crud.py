from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from chores.models import Chore
from households.models import Household, HouseholdMember

User = get_user_model()


class ChoreManagementCRUDTestCase(TestCase):
    """Integration tests for Chore CRUD endpoints, permission scoping, soft-deletion, and effort heuristic."""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.user_b = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )
        self.user_outsider = User.objects.create_user(
            email="outsider@example.com",
            password="Password123!",
            display_name="Outsider",
        )

        self.token_a = Token.objects.create(user=self.user_a)
        self.token_b = Token.objects.create(user=self.user_b)
        self.token_outsider = Token.objects.create(user=self.user_outsider)

        self.household = Household.objects.create(name="Cedar Flat")
        HouseholdMember.objects.create(
            household=self.household,
            user=self.user_a,
            status=HouseholdMember.STATUS_ACTIVE,
        )
        HouseholdMember.objects.create(
            household=self.household,
            user=self.user_b,
            status=HouseholdMember.STATUS_ACTIVE,
        )

        self.chores_list_url = reverse("chore-list")
        self.suggest_effort_url = reverse("chore-suggest-effort")

    def test_effort_suggestion_heuristic_endpoint(self):
        """Heuristic helper accurately suggests Small, Medium, or Large effort levels."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")

        # Small chore test
        res_small = self.client.post(
            self.suggest_effort_url,
            {"title": "Take out kitchen trash and recycling"},
            format="json",
        )
        self.assertEqual(res_small.status_code, status.HTTP_200_OK)
        self.assertEqual(res_small.json()["suggested_effort"], "small")
        self.assertEqual(res_small.json()["points"], 1)

        # Large chore test
        res_large = self.client.post(
            self.suggest_effort_url,
            {"title": "Deep clean the oven and refrigerator"},
            format="json",
        )
        self.assertEqual(res_large.status_code, status.HTTP_200_OK)
        self.assertEqual(res_large.json()["suggested_effort"], "large")
        self.assertEqual(res_large.json()["points"], 3)

        # Medium chore test
        res_med = self.client.post(
            self.suggest_effort_url,
            {"title": "Mop common hallway and kitchen floor"},
            format="json",
        )
        self.assertEqual(res_med.status_code, status.HTTP_200_OK)
        self.assertEqual(res_med.json()["suggested_effort"], "medium")
        self.assertEqual(res_med.json()["points"], 2)

    def test_create_chore_with_auto_effort_heuristic(self):
        """Creating a chore without specifying effort_level automatically applies the heuristic."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        payload = {
            "household": self.household.id,
            "title": "Wipe dining table counters",
            "recurrence_type": Chore.RECURRENCE_NONE,
        }
        response = self.client.post(self.chores_list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["effort_level"], "small")
        self.assertEqual(data["points"], 1)

    def test_create_chore_creator_override(self):
        """Explicitly specifying effort_level overrides the heuristic suggestion."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        payload = {
            "household": self.household.id,
            "title": "Wipe kitchen counters",  # normally small
            "effort_level": "large",  # creator override
            "recurrence_type": Chore.RECURRENCE_NONE,
        }
        response = self.client.post(self.chores_list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["effort_level"], "large")
        self.assertEqual(data["points"], 3)

    def test_permission_scoping_non_member_restricted(self):
        """Users who are not active members cannot create, view, or update household chores."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_outsider.key}")

        # Attempt to create chore in a household they do not belong to
        payload = {
            "household": self.household.id,
            "title": "Intruder Chore",
            "recurrence_type": Chore.RECURRENCE_NONE,
        }
        res_create = self.client.post(self.chores_list_url, payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempt to view existing chore in the household
        chore = Chore.objects.create(household=self.household, title="Member Chore")
        detail_url = reverse("chore-detail", kwargs={"pk": chore.id})
        res_get = self.client.get(detail_url)
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

    def test_chore_update(self):
        """Active roommate can update chore details."""
        chore = Chore.objects.create(
            household=self.household,
            title="Old Title",
            effort_level=Chore.EFFORT_SMALL,
            deadline_mode=Chore.DEADLINE_NONE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        detail_url = reverse("chore-detail", kwargs={"pk": chore.id})
        update_data = {
            "title": "Updated Title",
            "deadline_mode": Chore.DEADLINE_SPECIFIC,
            "deadline_window_hours": 36,
        }
        response = self.client.patch(detail_url, update_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        chore.refresh_from_db()
        self.assertEqual(chore.title, "Updated Title")
        self.assertEqual(chore.deadline_mode, Chore.DEADLINE_SPECIFIC)
        self.assertEqual(chore.deadline_window_hours, 36)

    def test_soft_deletion_and_archive_filtering(self):
        """Deleting a chore marks is_archived=True, preserving database history while hiding from active lists."""
        chore = Chore.objects.create(
            household=self.household,
            title="Archivable Chore",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        detail_url = reverse("chore-detail", kwargs={"pk": chore.id})

        # Soft delete via DELETE request
        del_res = self.client.delete(detail_url)
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)

        # Still exists in DB with is_archived=True
        chore.refresh_from_db()
        self.assertTrue(chore.is_archived)

        # Excluded from standard list
        list_res = self.client.get(self.chores_list_url)
        chore_ids = [c["id"] for c in list_res.json()]
        self.assertNotIn(chore.id, chore_ids)

        # Included when include_archived=true
        archived_list_res = self.client.get(f"{self.chores_list_url}?include_archived=true")
        archived_ids = [c["id"] for c in archived_list_res.json()]
        self.assertIn(chore.id, archived_ids)

    def test_explicit_archive_and_unarchive(self):
        """Chore can be explicitly archived and unarchived via dedicated actions."""
        chore = Chore.objects.create(household=self.household, title="Toggle Chore")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")

        archive_url = reverse("chore-archive", kwargs={"pk": chore.id})
        res_arch = self.client.post(archive_url)
        self.assertEqual(res_arch.status_code, status.HTTP_200_OK)
        chore.refresh_from_db()
        self.assertTrue(chore.is_archived)

        unarchive_url = reverse("chore-unarchive", kwargs={"pk": chore.id})
        res_unarch = self.client.post(unarchive_url)
        self.assertEqual(res_unarch.status_code, status.HTTP_200_OK)
        chore.refresh_from_db()
        self.assertFalse(chore.is_archived)
