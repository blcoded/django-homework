from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """
    Centralized activity stream recording chore completions, misses, late recoveries,
    disputes, verifications, swaps, and household member status changes.
    """

    EVENT_CHORE_COMPLETED = "chore_completed"
    EVENT_CHORE_COMPLETED_LATE = "chore_completed_late"
    EVENT_CHORE_MISSED = "chore_missed"
    EVENT_CHORE_DISPUTED = "chore_disputed"
    EVENT_CHORE_VERIFIED = "chore_verified"
    EVENT_CHORE_SWAP_ACCEPTED = "chore_swap_accepted"
    EVENT_MEMBER_JOINED = "member_joined"
    EVENT_MEMBER_LEFT = "member_left"
    EVENT_MEMBER_ABSENCE_APPROVED = "member_absence_approved"
    EVENT_HOUSEHOLD_PAUSED = "household_paused"
    EVENT_HOUSEHOLD_RESUMED = "household_resumed"

    EVENT_TYPE_CHOICES = [
        (EVENT_CHORE_COMPLETED, "Chore Completed"),
        (EVENT_CHORE_COMPLETED_LATE, "Chore Completed Late"),
        (EVENT_CHORE_MISSED, "Chore Missed"),
        (EVENT_CHORE_DISPUTED, "Chore Disputed"),
        (EVENT_CHORE_VERIFIED, "Chore Verified"),
        (EVENT_CHORE_SWAP_ACCEPTED, "Chore Swap Accepted"),
        (EVENT_MEMBER_JOINED, "Member Joined"),
        (EVENT_MEMBER_LEFT, "Member Left"),
        (EVENT_MEMBER_ABSENCE_APPROVED, "Member Absence Approved"),
        (EVENT_HOUSEHOLD_PAUSED, "Household Paused"),
        (EVENT_HOUSEHOLD_RESUMED, "Household Resumed"),
    ]

    household = models.ForeignKey(
        "households.Household",
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    chore = models.ForeignKey(
        "chores.Chore",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    occurrence = models.ForeignKey(
        "chores.ChoreOccurrence",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.event_type}] {self.title} ({self.created_at})"
