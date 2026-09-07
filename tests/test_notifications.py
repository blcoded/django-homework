from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from chores.models import Chore, ChoreOccurrence
from chores.services import OccurrenceService
from households.models import Household, HouseholdMember
from notifications.adapter import EmailDispatchAdapter
from notifications.models import Notification
from notifications.services import NotificationService

User = get_user_model()


class NotificationSystemTestCase(TestCase):
    """
    Test suite for Task 17: In-App and Email Notification System with Core Dispatch Moments.
    Verifies:
    1. Early "You're next" warning dispatch upon chore assignment.
    2. Active "It's your turn" alert dispatch upon occurrence window activation.
    3. Email formatting, delivery adapter, and mailbox logging.
    4. Notification API endpoints, unread filtering, and read status updates.
    """

    def setUp(self):
        self.client = APIClient()

        self.alice = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )
        self.token_alice = Token.objects.create(user=self.alice)
        self.token_bob = Token.objects.create(user=self.bob)

        self.household = Household.objects.create(name="Notification Manor", timezone="UTC")
        self.member_alice = HouseholdMember.objects.create(
            household=self.household, user=self.alice, status=HouseholdMember.STATUS_ACTIVE
        )
        self.member_bob = HouseholdMember.objects.create(
            household=self.household, user=self.bob, status=HouseholdMember.STATUS_ACTIVE
        )

        self.chore = Chore.objects.create(
            household=self.household,
            title="Clean Bathroom",
            effort_level=Chore.EFFORT_LARGE,
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 7, "unit": "days"},
            deadline_mode=Chore.DEADLINE_SPECIFIC,
            deadline_window_hours=24,
        )

    def test_early_youre_next_dispatch_upon_assignment(self):
        """
        Moment 1: When an upcoming occurrence is generated and assigned,
        an early "You're next" advance notification and email are dispatched.
        """
        mail.outbox.clear()
        now = timezone.now()

        # Generate upcoming occurrence (scheduled 7 days in future)
        occ = OccurrenceService.generate_next_occurrence(self.chore, from_time=now)
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_UPCOMING)

        # Check assigned user received notification
        assignee = occ.assignments.first().user
        notif = Notification.objects.filter(
            user=assignee,
            occurrence=occ,
            notification_type=Notification.TYPE_YOURE_NEXT,
        ).first()

        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, f"You're next: {self.chore.title}")
        self.assertIn("next up", notif.message)
        self.assertFalse(notif.is_read)
        self.assertTrue(notif.email_sent)
        self.assertIsNotNone(notif.email_sent_at)

        # Verify email was sent to the assignee
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("You're next: Clean Bathroom", sent_email.subject)
        self.assertIn(assignee.email, sent_email.to)
        self.assertIn("scheduled next for 'Clean Bathroom'", sent_email.body)

    def test_active_its_your_turn_dispatch_upon_window_activation(self):
        """
        Moment 2: When an upcoming occurrence reaches its start time and activates,
        an active "It's your turn" notification and email are dispatched.
        """
        mail.outbox.clear()
        now = timezone.now()

        # Create upcoming occurrence whose scheduled start has arrived
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_UPCOMING,
            scheduled_start=now - timedelta(minutes=5),
            due_date=now + timedelta(hours=20),
        )
        from chores.models import ChoreAssignment
        ChoreAssignment.objects.create(occurrence=occ, user=self.alice)

        mail.outbox.clear()

        # Transition upcoming to active
        activated = OccurrenceService.activate_upcoming_occurrences(current_time=now)
        self.assertIn(occ, activated)
        occ.refresh_from_db()
        self.assertEqual(occ.status, ChoreOccurrence.STATUS_ACTIVE)

        # Alice should have received an "It's your turn" notification
        notif = Notification.objects.filter(
            user=self.alice,
            occurrence=occ,
            notification_type=Notification.TYPE_YOUR_TURN,
        ).first()

        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, f"It's your turn: {self.chore.title}")
        self.assertIn("now your turn", notif.message)
        self.assertTrue(notif.email_sent)

        # Verify email dispatch
        self.assertTrue(len(mail.outbox) >= 1)
        sent_email = [e for e in mail.outbox if "It's your turn" in e.subject][0]
        self.assertIn(self.alice.email, sent_email.to)
        self.assertIn("action window for 'Clean Bathroom' is now open", sent_email.body)

    def test_email_dispatch_adapter_formatting(self):
        """EmailDispatchAdapter formats subjects and body cleanly for both core moments."""
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=timezone.now(),
            due_date=timezone.now() + timedelta(hours=24),
        )

        # Test You're Next format
        n1 = Notification(
            user=self.alice,
            occurrence=occ,
            notification_type=Notification.TYPE_YOURE_NEXT,
            title="You're next: Clean Bathroom",
            message="Advance notice.",
        )
        subj1, body1 = EmailDispatchAdapter.format_email_content(n1)
        self.assertEqual(subj1, "You're next: Clean Bathroom")
        self.assertIn("Hi Alice,", body1)
        self.assertIn("Due:", body1)

        # Test Your Turn format
        n2 = Notification(
            user=self.alice,
            occurrence=occ,
            notification_type=Notification.TYPE_YOUR_TURN,
            title="It's your turn: Clean Bathroom",
            message="Active notice.",
        )
        subj2, body2 = EmailDispatchAdapter.format_email_content(n2)
        self.assertEqual(subj2, "It's your turn: Clean Bathroom")
        self.assertIn("Hi Alice,", body2)
        self.assertIn("action window for 'Clean Bathroom' is now open", body2)

    def test_notification_endpoints_and_read_tracking(self):
        """Test listing, filtering unread, marking single and all notifications read."""
        now = timezone.now()
        occ = ChoreOccurrence.objects.create(
            chore=self.chore,
            status=ChoreOccurrence.STATUS_ACTIVE,
            scheduled_start=now,
        )

        n1 = Notification.objects.create(
            user=self.alice,
            household=self.household,
            occurrence=occ,
            notification_type=Notification.TYPE_YOURE_NEXT,
            title="Notice 1",
            message="Msg 1",
            is_read=False,
        )
        n2 = Notification.objects.create(
            user=self.alice,
            household=self.household,
            occurrence=occ,
            notification_type=Notification.TYPE_YOUR_TURN,
            title="Notice 2",
            message="Msg 2",
            is_read=False,
        )
        n_bob = Notification.objects.create(
            user=self.bob,
            household=self.household,
            occurrence=occ,
            notification_type=Notification.TYPE_YOURE_NEXT,
            title="Bob notice",
            message="For Bob",
            is_read=False,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_alice.key}")

        # 1. Unread count
        count_res = self.client.get(reverse("notification-unread-count"))
        self.assertEqual(count_res.status_code, status.HTTP_200_OK)
        self.assertEqual(count_res.json()["unread_count"], 2)

        # 2. List notifications: Alice sees only her own
        list_res = self.client.get(reverse("notification-list"))
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in list_res.json()]
        self.assertIn(n1.id, ids)
        self.assertIn(n2.id, ids)
        self.assertNotIn(n_bob.id, ids)

        # 3. Mark single notification as read
        read_url = reverse("notification-mark-read", kwargs={"pk": n1.id})
        res_read = self.client.post(read_url)
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)
        self.assertTrue(res_read.json()["is_read"])
        self.assertIsNotNone(res_read.json()["read_at"])
        n1.refresh_from_db()
        self.assertTrue(n1.is_read)

        # Check unread count is now 1
        count_res2 = self.client.get(reverse("notification-unread-count"))
        self.assertEqual(count_res2.json()["unread_count"], 1)

        # 4. Mark all read
        mark_all_url = reverse("notification-mark-all-read")
        res_all = self.client.post(mark_all_url)
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertEqual(res_all.json()["marked_read_count"], 1)

        count_res3 = self.client.get(reverse("notification-unread-count"))
        self.assertEqual(count_res3.json()["unread_count"], 0)

        # 5. Alice cannot read Bob's notification
        bob_read_url = reverse("notification-mark-read", kwargs={"pk": n_bob.id})
        res_bob_read = self.client.post(bob_read_url)
        self.assertEqual(res_bob_read.status_code, status.HTTP_404_NOT_FOUND)
