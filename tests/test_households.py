from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from households.models import Household, HouseholdMember

User = get_user_model()


class HouseholdManagementTestCase(TestCase):
    """Automated tests for household creation, membership, invite codes, and equal permissions."""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.user_b = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )
        self.user_c = User.objects.create_user(
            email="charlie@example.com", password="Password123!", display_name="Charlie"
        )

        self.token_a = Token.objects.create(user=self.user_a)
        self.token_b = Token.objects.create(user=self.user_b)
        self.token_c = Token.objects.create(user=self.user_c)

        self.households_url = reverse("household-list")

    def test_create_household_enrolls_creator_as_active_member(self):
        """Creating a household automatically enrolls creator as the first active member."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        payload = {
            "name": "Maple Apartment",
            "timezone": "America/New_York",
            "require_join_approval": True,
        }
        response = self.client.post(self.households_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["name"], "Maple Apartment")
        self.assertEqual(data["timezone"], "America/New_York")
        self.assertTrue(data["require_join_approval"])
        self.assertTrue(len(data["invite_code"]) > 10)

        # Creator should be in HouseholdMember with active status
        household = Household.objects.get(id=data["id"])
        memberships = HouseholdMember.objects.filter(household=household)
        self.assertEqual(memberships.count(), 1)
        member = memberships.first()
        self.assertEqual(member.user, self.user_a)
        self.assertEqual(member.status, HouseholdMember.STATUS_ACTIVE)

    def test_invite_code_uniqueness(self):
        """Every generated household invite code is distinct and unique."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        codes = set()
        for i in range(5):
            res = self.client.post(
                self.households_url, {"name": f"House {i}"}, format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)
            code = res.json()["invite_code"]
            self.assertNotIn(code, codes)
            codes.add(code)

    def test_equal_permissions_all_active_members_can_update_settings(self):
        """Any active member can update household settings; there is no boss/admin role."""
        # Create household with user_a
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        create_res = self.client.post(
            self.households_url, {"name": "Cozy Flat"}, format="json"
        )
        household_id = create_res.json()["id"]
        household = Household.objects.get(id=household_id)

        # Add user_b as an active roommate
        HouseholdMember.objects.create(
            household=household, user=self.user_b, status=HouseholdMember.STATUS_ACTIVE
        )

        # User B (non-creator roommate) updates household settings
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        detail_url = reverse("household-detail", kwargs={"pk": household_id})
        update_payload = {
            "name": "Cozy Flat Renovated",
            "require_completion_verification": True,
        }
        patch_res = self.client.patch(detail_url, update_payload, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)

        household.refresh_from_db()
        self.assertEqual(household.name, "Cozy Flat Renovated")
        self.assertTrue(household.require_completion_verification)

    def test_equal_permissions_all_active_members_can_regenerate_invite_code(self):
        """Any active member can regenerate the invite code."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        create_res = self.client.post(
            self.households_url, {"name": "Greenhouse"}, format="json"
        )
        household_id = create_res.json()["id"]
        old_code = create_res.json()["invite_code"]

        household = Household.objects.get(id=household_id)
        HouseholdMember.objects.create(
            household=household, user=self.user_b, status=HouseholdMember.STATUS_ACTIVE
        )

        # User B regenerates invite code
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        regen_url = reverse("household-regenerate-invite", kwargs={"pk": household_id})
        regen_res = self.client.post(regen_url)
        self.assertEqual(regen_res.status_code, status.HTTP_200_OK)
        new_code = regen_res.json()["invite_code"]
        self.assertNotEqual(old_code, new_code)

        household.refresh_from_db()
        self.assertEqual(household.invite_code, new_code)

    def test_non_member_cannot_access_or_modify_household(self):
        """Non-members cannot view or modify household details."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        create_res = self.client.post(
            self.households_url, {"name": "Private Flat"}, format="json"
        )
        household_id = create_res.json()["id"]

        # User C (outsider) attempts access
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_c.key}")
        detail_url = reverse("household-detail", kwargs={"pk": household_id})
        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_404_NOT_FOUND)

        patch_res = self.client.patch(detail_url, {"name": "Hacked Name"}, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_404_NOT_FOUND)

    def test_departed_member_denied_access(self):
        """Departed member is excluded from active permissions and views."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        create_res = self.client.post(
            self.households_url, {"name": "Loft Space"}, format="json"
        )
        household_id = create_res.json()["id"]
        household = Household.objects.get(id=household_id)

        # User B was a member, now departed
        membership = HouseholdMember.objects.create(
            household=household, user=self.user_b, status=HouseholdMember.STATUS_DEPARTED
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        detail_url = reverse("household-detail", kwargs={"pk": household_id})
        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_404_NOT_FOUND)

    def test_members_list_and_my_membership(self):
        """Active members can query membership list and their own membership status."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        create_res = self.client.post(
            self.households_url, {"name": "Shared Nest"}, format="json"
        )
        household_id = create_res.json()["id"]
        household = Household.objects.get(id=household_id)

        HouseholdMember.objects.create(
            household=household, user=self.user_b, status=HouseholdMember.STATUS_ACTIVE
        )

        # User A checks members list
        members_url = reverse("household-members", kwargs={"pk": household_id})
        members_res = self.client.get(members_url)
        self.assertEqual(members_res.status_code, status.HTTP_200_OK)
        members_data = members_res.json()
        self.assertEqual(len(members_data), 2)

        # User B checks my_membership
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        my_url = reverse("household-my-membership", kwargs={"pk": household_id})
        my_res = self.client.get(my_url)
        self.assertEqual(my_res.status_code, status.HTTP_200_OK)
        self.assertEqual(my_res.json()["status"], HouseholdMember.STATUS_ACTIVE)
