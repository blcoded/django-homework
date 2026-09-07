from django.conf import settings
from django.db import models


class UserStreak(models.Model):
    """
    Tracks personal consecutive on-time chore completion streaks.
    Increments upon on-time completion, resets upon a missed chore.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="streak",
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_completed_at = models.DateTimeField(null=True, blank=True)
    last_missed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: streak={self.current_streak} (best={self.longest_streak})"


class UserMilestone(models.Model):
    """
    Milestone achievement badges awarded for personal consistency.
    """

    BADGE_FIRST_CHORE = "first_chore"
    BADGE_STREAK_5 = "streak_5"
    BADGE_STREAK_10 = "streak_10"
    BADGE_COMPLETED_25 = "completed_25"
    BADGE_LATE_RECOVERY = "late_recovery"

    BADGE_DEFINITIONS = {
        BADGE_FIRST_CHORE: {
            "name": "First Step",
            "description": "Completed your very first chore for the household!",
            "icon": "check-circle",
        },
        BADGE_STREAK_5: {
            "name": "On a Roll",
            "description": "Maintained a consecutive 5-chore on-time streak!",
            "icon": "zap",
        },
        BADGE_STREAK_10: {
            "name": "Chore Champion",
            "description": "Achieved a consecutive 10-chore on-time streak!",
            "icon": "flame",
        },
        BADGE_COMPLETED_25: {
            "name": "Household Hero",
            "description": "Completed 25 household chores in total!",
            "icon": "award",
        },
        BADGE_LATE_RECOVERY: {
            "name": "Redemption",
            "description": "Successfully completed a missed chore late!",
            "icon": "refresh-cw",
        },
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="milestones",
    )
    badge_key = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, default="award")
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["unlocked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "badge_key"],
                name="unique_user_milestone_badge",
            )
        ]

    def __str__(self):
        return f"{self.user}: {self.name} ({self.badge_key})"
