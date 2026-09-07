from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from chores.models import Chore, ChoreAssignment, ChoreOccurrence
from chores.services import OccurrenceService
from households.models import AbsenceRequest, AbsenceRequestVote, Household, HouseholdMember

User = get_user_model()


class MemberAbsenceWorkflowTestCase(TestCase):
    """
    Unit and integration tests covering:
    1. Member absence request lifecycle with unanimous household approval.
    2. Preset and custom absence dates.
    3. Automated pending chore rebalancing upon absence approval.
    4. Seamless reintegration of returning members into rotation without displacing active chores.
    5. Exclusion of paused members from new chore assignments.
    """

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

        self.token_alice = Token.objects.create(user=self.alice)
        self.token_bob = Token.objects.create(user=self.bob)
        self.token_charlie = Token.objects.create(user=self.charlie)

        self.household = Household.objects.create(
            name="Sunflower House", timezone="UTC"
        )
        self.member_alice = HouseholdMember.objects.create(
            household=self.household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )
        self.member_bob = HouseholdMember.objects.create(
            household=self.household, user=self.bob, status=HouseholdMember.STATUS_ACTIVE
        )
        self.member_charlie = HouseholdMember.objects.create(
            household=self.household, user=self.charlie, status=HouseholdMember.STATUS_ACTIVE
        )

    def test_solo_member_absence_immediately_approved_and_paused(self):
        """A solo occupant's absence auto-approves immediately and pauses the member."""
        solo_household = Household.objects.create(name="Solo Studio")
        solo_member = HouseholdMember.objects.create(
            household=solo_household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("household-absences", kwargs={"pk": solo_household.id})
        today = timezone.localdate()
        payload = {
            "start_date": str(today),
            "end_date": str(today + timedelta(days=7)),
            "reason": "Vacation",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertEqual(data["status"], AbsenceRequest.STATUS_APPROVED)

        solo_member.refresh_from_db()
        self.assertEqual(solo_member.status, HouseholdMember.STATUS_PAUSED)

    def test_absence_request_requires_unanimous_approval_from_roommates(self):
        """
        Absence requests require unanimous approval from all other active roommates.
        The requesting member cannot vote on their own request.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("household-absences", kwargs={"pk": self.household.id})
        payload = {
            "preset": "1_week",
            "reason": "Family visit",
        }
        create_res = self.client.post(url, payload, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        req_data = create_res.json()["absence_request"]
        req_id = req_data["id"]
        self.assertEqual(req_data["status"], AbsenceRequest.STATUS_PENDING)
        self.assertTrue(req_data["start_date"])
        self.assertTrue(req_data["end_date"])

        vote_url = reverse(
            "household-vote-absence-request",
            kwargs={"pk": self.household.id, "request_id": req_id},
        )

        # Alice cannot vote on her own absence request
        self_vote = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(self_vote.status_code, status.HTTP_400_BAD_REQUEST)

        # Bob votes approve -> Still pending, Alice still active
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        res_bob = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res_bob.status_code, status.HTTP_200_OK)
        req = AbsenceRequest.objects.get(id=req_id)
        self.assertEqual(req.status, AbsenceRequest.STATUS_PENDING)
        self.member_alice.refresh_from_db()
        self.assertEqual(self.member_alice.status, HouseholdMember.STATUS_ACTIVE)

        # Charlie votes approve -> Unanimous approval reached!
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_charlie.key}")
        res_charlie = self.client.post(vote_url, {"approved": True}, format="json")
        self.assertEqual(res_charlie.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.status, AbsenceRequest.STATUS_APPROVED)

        # Alice transitions to paused status
        self.member_alice.refresh_from_db()
        self.assertEqual(self.member_alice.status, HouseholdMember.STATUS_PAUSED)

    def test_absence_request_rejected_if_any_roommate_rejects(self):
        """If any roommate votes reject, the absence request is rejected and member remains active."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("household-absences", kwargs={"pk": self.household.id})
        create_res = self.client.post(
            url, {"preset": "2_weeks", "reason": "Trip"}, format="json"
        )
        req_id = create_res.json()["absence_request"]["id"]

        vote_url = reverse(
            "household-vote-absence-request",
            kwargs={"pk": self.household.id, "request_id": req_id},
        )

        # Bob rejects
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        res_bob = self.client.post(vote_url, {"approved": False}, format="json")
        self.assertEqual(res_bob.status_code, status.HTTP_200_OK)

        req = AbsenceRequest.objects.get(id=req_id)
        self.assertEqual(req.status, AbsenceRequest.STATUS_REJECTED)

        self.member_alice.refresh_from_db()
        self.assertEqual(self.member_alice.status, HouseholdMember.STATUS_ACTIVE)

    def test_presets_and_validation(self):
        """Validate preset computation and date boundary checks."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("household-absences", kwargs={"pk": self.household.id})

        # Test invalid preset
        bad_preset = self.client.post(url, {"preset": "6_months"}, format="json")
        self.assertEqual(bad_preset.status_code, status.HTTP_400_BAD_REQUEST)

        # Test invalid date range (start > end)
        today = timezone.localdate()
        inverted = self.client.post(
            url,
            {
                "start_date": str(today + timedelta(days=5)),
                "end_date": str(today),
            },
            format="json",
        )
        self.assertEqual(inverted.status_code, status.HTTP_400_BAD_REQUEST)

        # Test valid preset "weekend"
        weekend_res = self.client.post(url, {"preset": "weekend"}, format="json")
        self.assertEqual(weekend_res.status_code, status.HTTP_201_CREATED)
        w_data = weekend_res.json()["absence_request"]
        start_d = date.fromisoformat(w_data["start_date"])
        end_d = date.fromisoformat(w_data["end_date"])
        self.assertTrue(end_d >= start_d)

    def test_automated_chore_rebalancing_on_absence_approval(self):
        """
        When an absence request is approved, pending chores assigned to the paused member
        are automatically rebalanced and reassigned among available active roommates.
        """
        # Create chores and occurrences
        chore_kitchen = Chore.objects.create(
            household=self.household,
            title="Clean Kitchen",
            effort_level=Chore.EFFORT_MEDIUM,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
        )
        chore_trash = Chore.objects.create(
            household=self.household,
            title="Take Out Trash",
            effort_level=Chore.EFFORT_SMALL,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 3, "unit": "days"},
        )

        now = timezone.now()
        occ_kitchen = ChoreOccurrence.objects.create(
            chore=chore_kitchen,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=2),
            due_date=now + timedelta(days=2),
        )
        # Alice is assigned to kitchen
        assign_kitchen = ChoreAssignment.objects.create(
            occurrence=occ_kitchen, user=self.alice
        )

        occ_trash = ChoreOccurrence.objects.create(
            chore=chore_trash,
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start=now + timedelta(days=1),
            due_date=now + timedelta(days=3),
        )
        # Alice is assigned to trash
        assign_trash = ChoreAssignment.objects.create(
            occurrence=occ_trash, user=self.alice
        )

        # Alice submits absence request
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        url = reverse("household-absences", kwargs={"pk": self.household.id})
        res = self.client.post(url, {"preset": "1_week", "reason": "Conference"}, format="json")
        req_id = res.json()["absence_request"]["id"]

        vote_url = reverse(
            "household-vote-absence-request",
            kwargs={"pk": self.household.id, "request_id": req_id},
        )

        # Bob and Charlie approve
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        self.client.post(vote_url, {"approved": True}, format="json")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_charlie.key}")
        self.client.post(vote_url, {"approved": True}, format="json")

        # Verify Alice is paused
        self.member_alice.refresh_from_db()
        self.assertEqual(self.member_alice.status, HouseholdMember.STATUS_PAUSED)

        # Alice's pending assignments must now be rebalanced away from Alice
        alice_pending = ChoreAssignment.objects.filter(
            user=self.alice,
            completed=False,
            occurrence__chore__household=self.household,
            occurrence__status__in=[
                ChoreOccurrence.STATUS_UPCOMING,
                ChoreOccurrence.STATUS_ACTIVE,
            ],
        )
        self.assertEqual(alice_pending.count(), 0)

        # Occurrences must now be assigned to either Bob or Charlie
        assign_kitchen.refresh_from_db()
        self.assertIn(assign_kitchen.user, [self.bob, self.charlie])

        assign_trash.refresh_from_db()
        self.assertIn(assign_trash.user, [self.bob, self.charlie])

    def test_reintegration_into_next_rotation_without_displacing_active_chores(self):
        """
        When an absent member returns:
        1. Member is restored to active status.
        2. Active chores assigned to other roommates are NOT displaced.
        3. Returning member is immediately eligible and enters rotation for new/next occurrences.
        """
        # Set Alice to paused
        self.member_alice.status = HouseholdMember.STATUS_PAUSED
        self.member_alice.save()

        today = timezone.localdate()
        absence_req = AbsenceRequest.objects.create(
            household=self.household,
            member=self.member_alice,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=2),
            status=AbsenceRequest.STATUS_APPROVED,
        )

        chore = Chore.objects.create(
            household=self.household,
            title="Clean Bathroom",
            effort_level=Chore.EFFORT_LARGE,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
        )

        now = timezone.now()
        active_occ = ChoreOccurrence.objects.create(
            chore=chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=1),
            due_date=now + timedelta(days=1),
        )
        # Assigned to Bob while Alice was away
        bob_assignment = ChoreAssignment.objects.create(
            occurrence=active_occ, user=self.bob
        )

        # Alice returns from absence
        end_url = reverse(
            "household-end-absence-request",
            kwargs={"pk": self.household.id, "request_id": absence_req.id},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        end_res = self.client.post(end_url)
        self.assertEqual(end_res.status_code, status.HTTP_200_OK)

        # 1. Member restored to active
        self.member_alice.refresh_from_db()
        self.assertEqual(self.member_alice.status, HouseholdMember.STATUS_ACTIVE)
        absence_req.refresh_from_db()
        self.assertEqual(absence_req.status, AbsenceRequest.STATUS_COMPLETED)

        # 2. Active chores are NOT displaced: Bob remains assigned to active_occ
        bob_assignment.refresh_from_db()
        self.assertEqual(bob_assignment.user, self.bob)

        # 3. Next occurrence generation immediately includes Alice in rotation
        # Bob completes active chore
        OccurrenceService.complete_occurrence(active_occ, user=self.bob)

        # Check the newly generated upcoming occurrence
        next_occ = chore.occurrences.filter(
            status=ChoreOccurrence.STATUS_UPCOMING
        ).first()
        self.assertIsNotNone(next_occ)

        # Since Bob just completed large chore (3 pts), Alice has 0 completed pts in lookback,
        # Alice is the prime fair candidate and must be assigned to next_occ!
        next_assignee = next_occ.assignments.first().user
        self.assertEqual(next_assignee, self.alice)

    def test_paused_member_excluded_from_new_assignments_while_away(self):
        """While a member is paused, newly generated chore occurrences exclude them."""
        self.member_alice.status = HouseholdMember.STATUS_PAUSED
        self.member_alice.save()

        chore = Chore.objects.create(
            household=self.household,
            title="Mow Lawn",
            effort_level=Chore.EFFORT_MEDIUM,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 14, "unit": "days"},
        )

        # Generate next occurrence
        occ = OccurrenceService.generate_next_occurrence(chore)
        assignees = [a.user for a in occ.assignments.all()]

        # Alice must NOT be in assignees
        self.assertNotIn(self.alice, assignees)
        self.assertTrue(len(assignees) > 0)
        self.assertIn(assignees[0], [self.bob, self.charlie])
