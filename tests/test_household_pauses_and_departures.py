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
from households.models import Household, HouseholdAlert, HouseholdMember, LeaveRequest
from households.pause import HouseholdPauseService

User = get_user_model()


class HouseholdPausesAndDeparturesTestCase(TestCase):
    """
    Integration tests for Task 16:
    1. Household-wide chore freeze without missed penalties, and resume.
    2. Departing member chore reassignments upon departure approval.
    3. Unassigned fallback state and household alerts when zero eligible roommates are available.
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

        self.household = Household.objects.create(name="Pineapple House", timezone="UTC")
        self.member_alice = HouseholdMember.objects.create(
            household=self.household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )
        self.member_bob = HouseholdMember.objects.create(
            household=self.household, user=self.bob, status=HouseholdMember.STATUS_ACTIVE
        )
        self.member_charlie = HouseholdMember.objects.create(
            household=self.household, user=self.charlie, status=HouseholdMember.STATUS_ACTIVE
        )

    def test_household_pause_suspends_missed_penalties_and_activation(self):
        """
        When a household is paused:
        1. Past-due active occurrences are NOT marked missed (missed penalties suspended).
        2. Scheduled upcoming occurrences do NOT activate.
        3. Upon resume, active chores past due transition to missed and upcoming activate.
        """
        now = timezone.now()
        chore = Chore.objects.create(
            household=self.household,
            title="Clean Kitchen",
            effort_level=Chore.EFFORT_MEDIUM,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
            deadline_mode=Chore.DEADLINE_SPECIFIC,
            deadline_window_hours=24,
        )

        # Active chore past due
        past_due_occ = ChoreOccurrence.objects.create(
            chore=chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(days=2),
            due_date=now - timedelta(hours=2),
        )
        ChoreAssignment.objects.create(occurrence=past_due_occ, user=self.alice)

        # Upcoming chore whose start time has arrived
        upcoming_occ = ChoreOccurrence.objects.create(
            chore=chore,
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start=now - timedelta(minutes=10),
            due_date=now + timedelta(days=1),
        )

        # Freeze household via API
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        pause_url = reverse("household-pause-household", kwargs={"pk": self.household.id})
        res = self.client.post(pause_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.household.refresh_from_db()
        self.assertTrue(self.household.is_paused)
        self.assertIsNotNone(self.household.paused_at)

        # Run scheduled missed detection and activation checks
        missed = OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)
        activated = OccurrenceService.activate_upcoming_occurrences(current_time=now)

        # Nothing should transition while frozen
        self.assertEqual(len(missed), 0)
        self.assertEqual(len(activated), 0)

        past_due_occ.refresh_from_db()
        self.assertEqual(past_due_occ.status, ChoreOccurrence.STATUS_ACTIVE)
        self.assertFalse(past_due_occ.was_missed)

        upcoming_occ.refresh_from_db()
        self.assertEqual(upcoming_occ.status, ChoreOccurrence.STATUS_UPCOMING)

        # Resume household via API
        resume_url = reverse("household-resume-household", kwargs={"pk": self.household.id})
        res_resume = self.client.post(resume_url)
        self.assertEqual(res_resume.status_code, status.HTTP_200_OK)
        self.household.refresh_from_db()
        self.assertFalse(self.household.is_paused)

        # Now running checks processes the occurrences
        missed_after = OccurrenceService.detect_and_transition_missed_occurrences(current_time=now)
        activated_after = OccurrenceService.activate_upcoming_occurrences(current_time=now)

        self.assertIn(past_due_occ, missed_after)
        self.assertIn(upcoming_occ, activated_after)

        past_due_occ.refresh_from_db()
        self.assertEqual(past_due_occ.status, ChoreOccurrence.STATUS_MISSED)
        self.assertTrue(past_due_occ.was_missed)

        upcoming_occ.refresh_from_db()
        self.assertEqual(upcoming_occ.status, ChoreOccurrence.STATUS_ACTIVE)

    def test_departing_member_chores_reassigned_upon_leave_approval(self):
        """
        When a roommate's departure request is approved, all active and upcoming
        chores assigned to them are automatically reassigned among remaining active members.
        """
        now = timezone.now()
        chore1 = Chore.objects.create(
            household=self.household,
            title="Mow Lawn",
            effort_level=Chore.EFFORT_LARGE,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 14, "unit": "days"},
        )
        chore2 = Chore.objects.create(
            household=self.household,
            title="Take Out Recycling",
            effort_level=Chore.EFFORT_SMALL,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
        )

        occ1 = ChoreOccurrence.objects.create(
            chore=chore1,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=1),
            due_date=now + timedelta(days=2),
        )
        assign1 = ChoreAssignment.objects.create(occurrence=occ1, user=self.alice)

        occ2 = ChoreOccurrence.objects.create(
            chore=chore2,
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start=now + timedelta(days=1),
            due_date=now + timedelta(days=3),
        )
        assign2 = ChoreAssignment.objects.create(occurrence=occ2, user=self.alice)

        # Alice requests departure
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        leave_url = reverse("household-leave", kwargs={"pk": self.household.id})
        res = self.client.post(leave_url)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        leave_req_id = res.json()["leave_request"]["id"]

        vote_url = reverse(
            "household-vote-leave-request",
            kwargs={"pk": self.household.id, "request_id": leave_req_id},
        )

        # Bob and Charlie approve departure
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_bob.key}")
        self.client.post(vote_url, {"approved": True}, format="json")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_charlie.key}")
        self.client.post(vote_url, {"approved": True}, format="json")

        # Alice is now departed
        self.member_alice.refresh_from_db()
        self.assertEqual(self.member_alice.status, HouseholdMember.STATUS_DEPARTED)

        # Alice has no pending assignments remaining in this household
        alice_pending = ChoreAssignment.objects.filter(
            user=self.alice,
            completed=False,
            occurrence__chore__household=self.household,
        )
        self.assertEqual(alice_pending.count(), 0)

        # Chores reassigned to either Bob or Charlie
        assign1.refresh_from_db()
        self.assertIn(assign1.user, [self.bob, self.charlie])

        assign2.refresh_from_db()
        self.assertIn(assign2.user, [self.bob, self.charlie])

    def test_unassigned_fallback_and_household_alert_when_zero_roommates_available(self):
        """
        When zero eligible roommates are available for assignment:
        1. Occurrence status is marked 'unassigned'.
        2. A HouseholdAlert record is generated.
        3. Household roommates can retrieve alerts from /api/households/{id}/alerts/.
        """
        # Create a solo household
        solo_house = Household.objects.create(name="Solitary Suite")
        solo_member = HouseholdMember.objects.create(
            household=solo_house, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )

        chore = Chore.objects.create(
            household=solo_house,
            title="Clean Windows",
            effort_level=Chore.EFFORT_MEDIUM,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
        )

        # Solo occupant leaves the household
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        leave_url = reverse("household-leave", kwargs={"pk": solo_house.id})
        self.client.post(leave_url)

        solo_member.refresh_from_db()
        self.assertEqual(solo_member.status, HouseholdMember.STATUS_DEPARTED)

        # Now try to generate an occurrence in this empty household
        now = timezone.now()
        occ = OccurrenceService.generate_next_occurrence(chore)

        # Occurrence must be marked unassigned because zero eligible roommates are active
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_UNASSIGNED)
        self.assertEqual(occ.assignments.count(), 0)

        # Verify HouseholdAlert was generated
        alert = HouseholdAlert.objects.filter(household=solo_house).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, HouseholdAlert.ALERT_UNASSIGNED)
        self.assertIn("cannot be assigned", alert.message)
        self.assertEqual(alert.occurrence, occ)

    def test_departing_solo_member_rebalances_assigned_chores_to_unassigned(self):
        """
        If a departing member was assigned chores and no other active roommates remain,
        those chores are transitioned to 'unassigned' and HouseholdAlerts are created.
        """
        solo_house = Household.objects.create(name="Solitary Cabin")
        solo_member = HouseholdMember.objects.create(
            household=solo_house, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )

        chore = Chore.objects.create(
            household=solo_house,
            title="Clean Chimney",
            effort_level=Chore.EFFORT_LARGE,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 30, "unit": "days"},
        )

        now = timezone.now()
        active_occ = ChoreOccurrence.objects.create(
            chore=chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now - timedelta(hours=2),
            due_date=now + timedelta(days=3),
        )
        ChoreAssignment.objects.create(occurrence=active_occ, user=self.alice)

        # Alice departs
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")
        leave_url = reverse("household-leave", kwargs={"pk": solo_house.id})
        res = self.client.post(leave_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Chore occurrence must now be unassigned with alert
        active_occ.refresh_from_db()
        self.assertEqual(active_occ.status, ChoreOccurrence.STATUS_UNASSIGNED)
        self.assertEqual(active_occ.assignments.count(), 0)

        alert = HouseholdAlert.objects.filter(household=solo_house, occurrence=active_occ).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, HouseholdAlert.ALERT_UNASSIGNED)
