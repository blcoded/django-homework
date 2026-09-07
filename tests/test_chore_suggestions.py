from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from chores.models import Chore, ChoreSuggestion
from households.models import Household, HouseholdMember

User = get_user_model()


class ChoreSuggestionLifecycleTestCase(TestCase):
    """Unit and integration tests for anonymous chore suggestions, majority voting, and expiration handling."""

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
        self.user_d = User.objects.create_user(
            email="dave@example.com", password="Password123!", display_name="Dave"
        )

        self.token_a = Token.objects.create(user=self.user_a)
        self.token_b = Token.objects.create(user=self.user_b)
        self.token_c = Token.objects.create(user=self.user_c)
        self.token_d = Token.objects.create(user=self.user_d)

        self.household = Household.objects.create(name="Birch House")
        HouseholdMember.objects.create(
            household=self.household, user=self.user_a, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=self.household, user=self.user_b, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=self.household, user=self.user_c, status=HouseholdMember.STATUS_ACTIVE
        )

        self.suggestions_list_url = reverse("chore-suggestion-list")

    def test_creator_anonymity(self):
        """Creator identity is never exposed in create, detail, or list API payloads."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        payload = {
            "household": self.household.id,
            "title": "Clean living room windows",
            "description": "Windows are getting dusty.",
            "effort_level": "medium",
        }
        res_create = self.client.post(self.suggestions_list_url, payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        data = res_create.json()

        # Creator field must not be present in response
        self.assertNotIn("creator", data)
        self.assertNotIn("creator_id", data)
        self.assertNotIn("user", data)
        self.assertNotIn("alice", str(data).lower())

        suggestion_id = data["id"]

        # Bob views the suggestion list
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        res_list = self.client.get(self.suggestions_list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        list_payload = str(res_list.json()).lower()
        self.assertNotIn("creator", list_payload)
        self.assertNotIn("alice", list_payload)

        # Bob views suggestion detail
        detail_url = reverse("chore-suggestion-detail", kwargs={"pk": suggestion_id})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertNotIn("creator", res_detail.json())
        self.assertNotIn("alice", str(res_detail.json()).lower())

    def test_majority_voting_lifecycle_3_members(self):
        """In a 3-member household, majority threshold is 2 votes to convert to active Chore."""
        suggestion = ChoreSuggestion.objects.create(
            household=self.household,
            creator=self.user_a,
            title="Clean microwave and toaster",
            effort_level=Chore.EFFORT_SMALL,
        )

        vote_url = reverse("chore-suggestion-vote", kwargs={"pk": suggestion.id})

        # Vote 1: Bob approves -> Approvals=1, Still pending
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        res1 = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, ChoreSuggestion.STATUS_PENDING)
        self.assertIsNone(suggestion.approved_chore)
        self.assertEqual(Chore.objects.filter(household=self.household).count(), 0)

        # Vote 2: Charlie approves -> Approvals=2 (majority of 3 reached!)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_c.key}")
        res2 = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, ChoreSuggestion.STATUS_APPROVED)

        # Active Chore automatically generated
        self.assertIsNotNone(suggestion.approved_chore)
        chore = suggestion.approved_chore
        self.assertEqual(chore.title, "Clean microwave and toaster")
        self.assertEqual(chore.effort_level, Chore.EFFORT_SMALL)
        self.assertEqual(chore.household, self.household)

    def test_majority_voting_lifecycle_4_members(self):
        """In a 4-member household, majority threshold is 3 votes (strictly > 50%)."""
        # Add 4th member
        HouseholdMember.objects.create(
            household=self.household, user=self.user_d, status=HouseholdMember.STATUS_ACTIVE
        )

        suggestion = ChoreSuggestion.objects.create(
            household=self.household,
            creator=self.user_a,
            title="Mop garage entryway",
        )

        vote_url = reverse("chore-suggestion-vote", kwargs={"pk": suggestion.id})

        # Vote 1: Bob approves -> pending
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        self.client.post(vote_url, {"approved": True}, format="json")
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, ChoreSuggestion.STATUS_PENDING)

        # Vote 2: Charlie approves -> 2/4 is not strict majority, still pending
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_c.key}")
        self.client.post(vote_url, {"approved": True}, format="json")
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, ChoreSuggestion.STATUS_PENDING)

        # Vote 3: Dave approves -> 3/4 reached majority!
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_d.key}")
        self.client.post(vote_url, {"approved": True}, format="json")
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, ChoreSuggestion.STATUS_APPROVED)
        self.assertIsNotNone(suggestion.approved_chore)

    def test_majority_rejection(self):
        """When rejection votes make majority mathematically impossible, status becomes rejected."""
        suggestion = ChoreSuggestion.objects.create(
            household=self.household,
            creator=self.user_a,
            title="Impractical Chore Proposal",
        )
        vote_url = reverse("chore-suggestion-vote", kwargs={"pk": suggestion.id})

        # Bob rejects
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        self.client.post(vote_url, {"approved": False}, format="json")

        # Charlie rejects -> 2 rejections out of 3, impossible to get 2 approvals
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_c.key}")
        self.client.post(vote_url, {"approved": False}, format="json")

        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, ChoreSuggestion.STATUS_REJECTED)
        self.assertIsNone(suggestion.approved_chore)

    def test_automatic_expiration_handling(self):
        """Proposals past expires_at are transitioned to expired and voting is prevented."""
        # Create suggestion already past expiration
        expired_suggestion = ChoreSuggestion.objects.create(
            household=self.household,
            creator=self.user_a,
            title="Old Stale Proposal",
            expires_at=timezone.now() - timedelta(hours=2),
        )

        detail_url = reverse(
            "chore-suggestion-detail", kwargs={"pk": expired_suggestion.id}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["status"], "expired")

        # Attempting to vote on expired proposal is rejected with 400
        vote_url = reverse(
            "chore-suggestion-vote", kwargs={"pk": expired_suggestion.id}
        )
        vote_res = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(vote_res.status_code, status.HTTP_400_BAD_REQUEST)
