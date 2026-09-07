from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import models
from households.models import Household


class Chore(models.Model):
    """
    Core Chore definition supporting one-off and recurring schedules,
    effort ratings, flexible deadlines, and multi-person assignments.
    """

    EFFORT_SMALL = "small"
    EFFORT_MEDIUM = "medium"
    EFFORT_LARGE = "large"

    EFFORT_CHOICES = [
        (EFFORT_SMALL, "Small (1 pt)"),
        (EFFORT_MEDIUM, "Medium (2 pts)"),
        (EFFORT_LARGE, "Large (3 pts)"),
    ]

    EFFORT_POINTS = {
        EFFORT_SMALL: 1,
        EFFORT_MEDIUM: 2,
        EFFORT_LARGE: 3,
    }

    RECURRENCE_NONE = "none"
    RECURRENCE_CALENDAR = "calendar"
    RECURRENCE_INTERVAL = "interval"

    RECURRENCE_CHOICES = [
        (RECURRENCE_NONE, "One-off (None)"),
        (RECURRENCE_CALENDAR, "Calendar (e.g. Days of week)"),
        (RECURRENCE_INTERVAL, "Interval (e.g. Every N days)"),
    ]

    DEADLINE_NONE = "none"
    DEADLINE_SPECIFIC = "specific"
    DEADLINE_FLEXIBLE_WINDOW = "flexible_window"

    DEADLINE_CHOICES = [
        (DEADLINE_NONE, "No Deadline"),
        (DEADLINE_SPECIFIC, "Specific Point / Duration"),
        (DEADLINE_FLEXIBLE_WINDOW, "Flexible Window"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="chores"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    effort_level = models.CharField(
        max_length=20, choices=EFFORT_CHOICES, default=EFFORT_MEDIUM
    )

    # Recurrence configuration
    recurrence_type = models.CharField(
        max_length=20, choices=RECURRENCE_CHOICES, default=RECURRENCE_NONE
    )
    recurrence_rule = models.JSONField(
        default=dict,
        blank=True,
        help_text="Serialized schedule rules (e.g., {'days': ['mon', 'thu']} or {'interval': 7, 'unit': 'days'}).",
    )

    # Deadline configuration
    deadline_mode = models.CharField(
        max_length=20, choices=DEADLINE_CHOICES, default=DEADLINE_NONE
    )
    deadline_window_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration in hours defining the deadline or flexible action window.",
    )

    # Multi-assignee support
    is_multi_assignee = models.BooleanField(
        default=False,
        help_text="Whether this chore requires multiple roommates to independently complete.",
    )
    required_assignees_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of distinct roommates required if multi-assignee is enabled.",
    )

    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} ({self.household.name})"

    @property
    def points(self) -> int:
        """Workload points corresponding to the effort level."""
        return self.EFFORT_POINTS.get(self.effort_level, 2)

    @property
    def is_recurring(self) -> bool:
        return self.recurrence_type != self.RECURRENCE_NONE

    def clean(self):
        super().clean()

        # Multi-assignee constraint
        if self.is_multi_assignee:
            if self.required_assignees_count < 2:
                raise ValidationError(
                    {
                        "required_assignees_count": "Multi-assignee chores must require at least 2 assignees."
                    }
                )
        else:
            if self.required_assignees_count != 1:
                self.required_assignees_count = 1

        # Deadline validation
        if self.deadline_mode in [self.DEADLINE_SPECIFIC, self.DEADLINE_FLEXIBLE_WINDOW]:
            if not self.deadline_window_hours or self.deadline_window_hours <= 0:
                raise ValidationError(
                    {
                        "deadline_window_hours": f"Deadline mode '{self.deadline_mode}' requires a positive deadline_window_hours."
                    }
                )
        elif self.deadline_mode == self.DEADLINE_NONE:
            self.deadline_window_hours = None

        # Recurrence validation
        if self.recurrence_type == self.RECURRENCE_CALENDAR:
            if not isinstance(self.recurrence_rule, dict) or "days" not in self.recurrence_rule:
                raise ValidationError(
                    {
                        "recurrence_rule": "Calendar recurrence requires a 'days' list in recurrence_rule."
                    }
                )
        elif self.recurrence_type == self.RECURRENCE_INTERVAL:
            if (
                not isinstance(self.recurrence_rule, dict)
                or "interval" not in self.recurrence_rule
                or "unit" not in self.recurrence_rule
            ):
                raise ValidationError(
                    {
                        "recurrence_rule": "Interval recurrence requires 'interval' and 'unit' in recurrence_rule."
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def calculate_deadline(self, start_time):
        """
        Calculate the deadline datetime given an occurrence start time.
        Returns None if no deadline mode is set.
        """
        if self.deadline_mode == self.DEADLINE_NONE or not self.deadline_window_hours:
            return None
        return start_time + timedelta(hours=self.deadline_window_hours)
