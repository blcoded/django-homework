from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """
    In-app and email notification tracking system.
    Supports core V1 moments:
    - 'youre_next': advance warning when assigned to upcoming chore
    - 'your_turn': active reminder when chore window becomes active
    """

    TYPE_YOURE_NEXT = "youre_next"
    TYPE_YOUR_TURN = "your_turn"

    TYPE_CHOICES = [
        (TYPE_YOURE_NEXT, "You're Next (Advance Warning)"),
        (TYPE_YOUR_TURN, "It's Your Turn (Active Reminder)"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    household = models.ForeignKey(
        "households.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    occurrence = models.ForeignKey(
        "chores.ChoreOccurrence",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=50, choices=TYPE_CHOICES, default=TYPE_YOURE_NEXT
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        read_str = "Read" if self.is_read else "Unread"
        return f"Notification({self.user.email} - {self.title} [{read_str}])"

    def mark_as_read(self):
        """Mark notification as read with timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])

    def mark_as_unread(self):
        """Mark notification as unread."""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=["is_read", "read_at", "updated_at"])
