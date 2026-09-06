import secrets
from django.conf import settings
from django.db import models


def generate_invite_code():
    return secrets.token_urlsafe(16)


class Household(models.Model):
    """
    Shared household model storing configuration flags, timezone,
    and unique invite code for prospective roommates.
    """

    name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=50, default="UTC")
    require_join_approval = models.BooleanField(
        default=False,
        help_text="Whether prospective members require household approval before joining.",
    )
    require_completion_verification = models.BooleanField(
        default=False,
        help_text="Whether chore completions require roommate verification.",
    )
    invite_code = models.CharField(
        max_length=64, unique=True, default=generate_invite_code
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def regenerate_invite_code(self):
        self.invite_code = generate_invite_code()
        self.save(update_fields=["invite_code", "updated_at"])
        return self.invite_code


class HouseholdMember(models.Model):
    """
    Household membership model with equal permissions for all active members.
    There are no admin or boss roles.
    """

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_DEPARTED = "departed"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_DEPARTED, "Departed"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="household_memberships",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("household", "user")
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} in {self.household.name} ({self.status})"
