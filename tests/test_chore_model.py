from datetime import datetime, timedelta, timezone
from django.core.exceptions import ValidationError
from django.test import TestCase

from chores.models import Chore
from households.models import Household


class ChoreModelTestCase(TestCase):
    """Model tests validating effort levels, schedule serialization, deadline calculations, and multi-assignee constraints."""

    def setUp(self):
        self.household = Household.objects.create(name="Pine House")

    def test_effort_points_mapping(self):
        """Effort ratings map directly to points: Small=1, Medium=2, Large=3."""
        chore_small = Chore.objects.create(
            household=self.household,
            title="Wipe kitchen counters",
            effort_level=Chore.EFFORT_SMALL,
        )
        chore_medium = Chore.objects.create(
            household=self.household,
            title="Clean bathroom",
            effort_level=Chore.EFFORT_MEDIUM,
        )
        chore_large = Chore.objects.create(
            household=self.household,
            title="Deep clean refrigerator",
            effort_level=Chore.EFFORT_LARGE,
        )

        self.assertEqual(chore_small.points, 1)
        self.assertEqual(chore_medium.points, 2)
        self.assertEqual(chore_large.points, 3)

    def test_one_off_chore(self):
        """One-off chores have no recurrence and is_recurring is False."""
        chore = Chore.objects.create(
            household=self.household,
            title="Fix squeaky cabinet",
            recurrence_type=Chore.RECURRENCE_NONE,
        )
        self.assertFalse(chore.is_recurring)
        self.assertEqual(chore.recurrence_type, Chore.RECURRENCE_NONE)

    def test_calendar_recurrence_rule_serialization_and_validation(self):
        """Calendar recurrence requires a valid serialized 'days' list in recurrence_rule."""
        # Valid calendar rule
        chore = Chore.objects.create(
            household=self.household,
            title="Take out recycling",
            recurrence_type=Chore.RECURRENCE_CALENDAR,
            recurrence_rule={"days": ["tue", "fri"]},
        )
        self.assertTrue(chore.is_recurring)
        self.assertEqual(chore.recurrence_rule["days"], ["tue", "fri"])

        # Invalid calendar rule missing 'days'
        invalid_chore = Chore(
            household=self.household,
            title="Bad Calendar Chore",
            recurrence_type=Chore.RECURRENCE_CALENDAR,
            recurrence_rule={"invalid": "payload"},
        )
        with self.assertRaises(ValidationError):
            invalid_chore.full_clean()

    def test_interval_recurrence_rule_serialization_and_validation(self):
        """Interval recurrence requires serialized 'interval' and 'unit' in recurrence_rule."""
        # Valid interval rule
        chore = Chore.objects.create(
            household=self.household,
            title="Water house plants",
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 3, "unit": "days"},
        )
        self.assertTrue(chore.is_recurring)
        self.assertEqual(chore.recurrence_rule["interval"], 3)
        self.assertEqual(chore.recurrence_rule["unit"], "days")

        # Invalid interval rule missing 'unit'
        invalid_chore = Chore(
            household=self.household,
            title="Bad Interval Chore",
            recurrence_type=Chore.RECURRENCE_INTERVAL,
            recurrence_rule={"interval": 5},
        )
        with self.assertRaises(ValidationError):
            invalid_chore.full_clean()

    def test_deadline_calculation_modes(self):
        """Deadlines correctly compute based on none, specific, or flexible window."""
        start_time = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)

        # Mode None
        chore_no_deadline = Chore.objects.create(
            household=self.household,
            title="Declutter hallway",
            deadline_mode=Chore.DEADLINE_NONE,
        )
        self.assertIsNone(chore_no_deadline.calculate_deadline(start_time))

        # Specific point / duration (24h)
        chore_specific = Chore.objects.create(
            household=self.household,
            title="Wash dishes",
            deadline_mode=Chore.DEADLINE_SPECIFIC,
            deadline_window_hours=24,
        )
        self.assertEqual(
            chore_specific.calculate_deadline(start_time),
            start_time + timedelta(hours=24),
        )

        # Flexible window (72h, e.g. "this weekend")
        chore_flexible = Chore.objects.create(
            household=self.household,
            title="Mop common areas",
            deadline_mode=Chore.DEADLINE_FLEXIBLE_WINDOW,
            deadline_window_hours=72,
        )
        self.assertEqual(
            chore_flexible.calculate_deadline(start_time),
            start_time + timedelta(hours=72),
        )

        # Specific deadline without hours raises ValidationError
        invalid_deadline_chore = Chore(
            household=self.household,
            title="Missing Deadline Window",
            deadline_mode=Chore.DEADLINE_SPECIFIC,
            deadline_window_hours=None,
        )
        with self.assertRaises(ValidationError):
            invalid_deadline_chore.full_clean()

    def test_multi_assignee_validation_constraints(self):
        """Multi-assignee chores must require at least 2 distinct assignees."""
        # Valid multi-assignee chore
        chore_multi = Chore.objects.create(
            household=self.household,
            title="Move heavy furniture",
            is_multi_assignee=True,
            required_assignees_count=2,
        )
        self.assertTrue(chore_multi.is_multi_assignee)
        self.assertEqual(chore_multi.required_assignees_count, 2)

        # Invalid multi-assignee chore with count < 2
        invalid_multi = Chore(
            household=self.household,
            title="Invalid Multi Chore",
            is_multi_assignee=True,
            required_assignees_count=1,
        )
        with self.assertRaises(ValidationError):
            invalid_multi.full_clean()

        # Single assignee chore automatically sets count to 1
        chore_single = Chore.objects.create(
            household=self.household,
            title="Take out trash",
            is_multi_assignee=False,
            required_assignees_count=4,  # Clean should reset to 1
        )
        self.assertEqual(chore_single.required_assignees_count, 1)
