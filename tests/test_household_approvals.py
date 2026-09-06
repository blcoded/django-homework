from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from households.models import (
    Household,
    HouseholdMember,
    JoinRequest,
    LeaveRequest,
)

User = get_user_model()


class HouseholdApprovalWorkflowsTestCase(TestCase):
    """Integration tests verifying join and leave approval workflows and unanimous voting."""

    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )
        self.charlie = User.objects.create_user(
            email="charlie@example.com", password="Password123!", display_name="Charlie"
        )
        self.dave = User.objects.create_user(
            email="dave@example.com", password="Password123!", display_name="Dave"
        )

        self.token_alice = Token.objects.create(user=self.alice)
        self.token_bob = Token.objects.create(user=self.bob)
        self.token_charlie = Token.objects.create(user=self.charlie)
        self.token_dave = Token.objects.create(user=self.dave)

        self.join_url = reverse("household-join")

    def test_join_without_approval_enables_immediate_membership(self):
        """When require_join_approval is False, prospective roommate joins immediately."""
        household = Household.objects.create(
            name="Open Flat", require_join_approval=False
        )
        HouseholdMember.objects.create(
            household=household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        response = self.client.post(
            self.join_url, {"invite_code": household.invite_code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "joined")

        self.assertTrue(
            HouseholdMember.objects.filter(
                household=household,
                user=self.bob,
                status=HouseholdMember.STATUS_ACTIVE,
            ).exists()
        )

    def test_join_requires_unanimous_consent_from_all_active_roommates(self):
        """When require_join_approval is True, unanimous approval from all active roommates is required."""
        household = Household.objects.create(
            name="Guarded House", require_join_approval=True
        )
        HouseholdMember.objects.create(
            household=household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=household, user=self.bob, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=household, user=self.charlie, status=HouseholdMember.STATUS_ACTIVE
        )

        # Dave requests to join
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_dave.key}")
        join_res = self.client.post(
            self.join_url, {"invite_code": household.invite_code}, format="json"
        )
        self.assertEqual(join_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(join_res.json()["status"], "pending_approval")

        join_req_id = join_res.json()["join_request"]["id"]
        join_req = JoinRequest.objects.get(id=join_req_id)

        # Dave should NOT be an active member yet
        self.assertFalse(
            HouseholdMember.objects.filter(
                household=household, user=self.dave
            ).exists()
        )

        vote_url = reverse(
            "household-vote-join-request",
            kwargs={"pk": household.id, "request_id": join_req_id},
        )

        # Vote 1: Alice approves -> Still pending
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        res1 = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        join_req.refresh_from_db()
        self.assertEqual(join_req.status, JoinRequest.STATUS_PENDING)
        self.assertFalse(
            HouseholdMember.objects.filter(
                household=household, user=self.dave
            ).exists()
        )

        # Vote 2: Bob approves -> Still pending
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        res2 = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        join_req.refresh_from_db()
        self.assertEqual(join_req.status, JoinRequest.STATUS_PENDING)

        # Vote 3: Charlie approves -> UNANIMOUS consent reached!
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_charlie.key}")
        res3 = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        join_req.refresh_from_db()
        self.assertEqual(join_req.status, JoinRequest.STATUS_APPROVED)

        # State transition: Dave is now an active member
        self.assertTrue(
            HouseholdMember.objects.filter(
                household=household,
                user=self.dave,
                status=HouseholdMember.STATUS_ACTIVE,
            ).exists()
        )

    def test_join_rejected_if_any_active_member_votes_reject(self):
        """A single active roommate rejecting immediately rejects the prospective member."""
        household = Household.objects.create(
            name="Strict House", require_join_approval=True
        )
        HouseholdMember.objects.create(
            household=household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=household, user=self.bob, status=HouseholdMember.STATUS_ACTIVE
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_dave.key}")
        join_res = self.client.post(
            self.join_url, {"invite_code": household.invite_code}, format="json"
        )
        join_req_id = join_res.json()["join_request"]["id"]

        vote_url = reverse(
            "household-vote-join-request",
            kwargs={"pk": household.id, "request_id": join_req_id},
        )

        # Alice votes reject
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        self.client.post(vote_url, {"approved": False}, format="json")

        join_req = JoinRequest.objects.get(id=join_req_id)
        self.assertEqual(join_req.status, JoinRequest.STATUS_REJECTED)
        self.assertFalse(
            HouseholdMember.objects.filter(
                household=household, user=self.dave
            ).exists()
        )

    def test_leave_solo_member_immediately_departs(self):
        """A solo occupant leaves immediately without needing votes."""
        household = Household.objects.create(name="Studio Apartment")
        member = HouseholdMember.objects.create(
            household=household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        leave_url = reverse("household-leave", kwargs={"pk": household.id})
        response = self.client.post(leave_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "departed")

        member.refresh_from_db()
        self.assertEqual(member.status, HouseholdMember.STATUS_DEPARTED)

    def test_leave_requires_unanimous_consent_from_other_roommates(self):
        """Departing a shared household requires unanimous consent from all other active roommates."""
        household = Household.objects.create(name="Triplex")
        member_alice = HouseholdMember.objects.create(
            household=household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=household, user=self.bob, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=household, user=self.charlie, status=HouseholdMember.STATUS_ACTIVE
        )

        # Alice requests to leave
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        leave_url = reverse("household-leave", kwargs={"pk": household.id})
        response = self.client.post(leave_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["status"], "pending_approval")

        leave_req_id = response.json()["leave_request"]["id"]
        leave_req = LeaveRequest.objects.get(id=leave_req_id)

        # Alice cannot vote on her own departure request
        vote_url = reverse(
            "household-vote-leave-request",
            kwargs={"pk": household.id, "request_id": leave_req_id},
        )
        self_vote = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(self_vote.status_code, status.HTTP_400_BAD_REQUEST)

        # Vote 1: Bob approves -> Still pending, Alice still active
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        res_bob = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res_bob.status_code, status.HTTP_200_OK)
        leave_req.refresh_from_db()
        self.assertEqual(leave_req.status, LeaveRequest.STATUS_PENDING)
        member_alice.refresh_from_db()
        self.assertEqual(member_alice.status, HouseholdMember.STATUS_ACTIVE)

        # Vote 2: Charlie approves -> All other roommates unanimously consented!
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_charlie.key}")
        res_charlie = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res_charlie.status_code, status.HTTP_200_OK)
        leave_req.refresh_from_db()
        self.assertEqual(leave_req.status, LeaveRequest.STATUS_APPROVED)

        # State transition: Alice is now departed
        member_alice.refresh_from_db()
        self.assertEqual(member_alice.status, HouseholdMember.STATUS_DEPARTED)

    def test_leave_rejected_if_any_other_roommate_rejects(self):
        """If any other roommate rejects the departure request, it is marked rejected and member remains active."""
        household = Household.objects.create(name="Shared Townhouse")
        member_alice = HouseholdMember.objects.create(
            household=household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )
        HouseholdMember.objects.create(
            household=household, user=self.bob, status=HouseholdMember.STATUS_ACTIVE
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        leave_url = reverse("household-leave", kwargs={"pk": household.id})
        res = self.client.post(leave_url)
        leave_req_id = res.json()["leave_request"]["id"]

        vote_url = reverse(
            "household-vote-leave-request",
            kwargs={"pk": household.id, "request_id": leave_req_id},
        )

        # Bob rejects
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        self.client.post(vote_url, {"approved": False}, format="json")

        leave_req = LeaveRequest.objects.get(id=leave_req_id)
        self.assertEqual(leave_req.status, LeaveRequest.STATUS_REJECTED)

        member_alice.refresh_from_db()
        self.assertEqual(member_alice.status, HouseholdMember.STATUS_ACTIVE)
