from datetime import timedelta
import logging
from django.utils import timezone
from chores.models import Chore, ChoreAssignment, ChoreOccurrence
from stats.models import UserMilestone, UserStreak

logger = logging.getLogger(__name__)


class StatsService:
    """
    Service managing personal consistency streaks, milestone achievement badges,
    and non-competitive household statistics.
    """

    @classmethod
    def get_or_create_streak(cls, user) -> UserStreak:
        streak, _ = UserStreak.objects.get_or_create(user=user)
        return streak

    @classmethod
    def record_on_time_completion(cls, user) -> UserStreak:
        """Increment on-time streak and evaluate milestone unlocks."""
        streak = cls.get_or_create_streak(user)
        streak.current_streak += 1
        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak
        streak.last_completed_at = timezone.now()
        streak.save(
            update_fields=["current_streak", "longest_streak", "last_completed_at", "updated_at"]
        )

        cls.evaluate_milestones(user, streak=streak)
        return streak

    @classmethod
    def record_missed_chore(cls, user) -> UserStreak:
        """Reset consecutive on-time streak to zero upon missed deadline."""
        streak = cls.get_or_create_streak(user)
        streak.current_streak = 0
        streak.last_missed_at = timezone.now()
        streak.save(update_fields=["current_streak", "last_missed_at", "updated_at"])
        return streak

    @classmethod
    def record_late_completion(cls, user) -> UserStreak:
        """Record late completion, preserving missed status and awarding recovery badge."""
        streak = cls.get_or_create_streak(user)
        cls.unlock_milestone(user, UserMilestone.BADGE_LATE_RECOVERY)
        cls.evaluate_milestones(user, streak=streak)
        return streak

    @classmethod
    def unlock_milestone(cls, user, badge_key: str) -> UserMilestone | None:
        """Award a milestone badge to a user if not already earned."""
        if badge_key not in UserMilestone.BADGE_DEFINITIONS:
            return None
        badge_info = UserMilestone.BADGE_DEFINITIONS[badge_key]
        milestone, created = UserMilestone.objects.get_or_create(
            user=user,
            badge_key=badge_key,
            defaults={
                "name": badge_info["name"],
                "description": badge_info["description"],
                "icon": badge_info["icon"],
            },
        )
        if created:
            logger.info("User %s unlocked milestone %s", user.email, badge_key)
        return milestone

    @classmethod
    def evaluate_milestones(cls, user, streak=None):
        """Evaluate and unlock applicable milestones based on completion history."""
        if streak is None:
            streak = cls.get_or_create_streak(user)

        total_completed = ChoreAssignment.objects.filter(
            user=user, completed=True
        ).count()

        if total_completed >= 1:
            cls.unlock_milestone(user, UserMilestone.BADGE_FIRST_CHORE)

        if streak.current_streak >= 5:
            cls.unlock_milestone(user, UserMilestone.BADGE_STREAK_5)

        if streak.current_streak >= 10:
            cls.unlock_milestone(user, UserMilestone.BADGE_STREAK_10)

        if total_completed >= 25:
            cls.unlock_milestone(user, UserMilestone.BADGE_COMPLETED_25)

    @classmethod
    def get_personal_stats(cls, user, household_id=None) -> dict:
        """Compute personal stats, streaks, completion metrics, and milestones."""
        streak = cls.get_or_create_streak(user)

        assignments = ChoreAssignment.objects.filter(user=user)
        if household_id:
            assignments = assignments.filter(
                occurrence__chore__household_id=household_id
            )

        on_time_completions = assignments.filter(
            completed=True, was_missed=False
        ).count()
        late_completions = assignments.filter(
            completed=True, was_missed=True
        ).count()
        total_completed = on_time_completions + late_completions
        total_missed = assignments.filter(was_missed=True).count()
        currently_missed = assignments.filter(
            occurrence__status=ChoreOccurrence.STATUS_MISSED
        ).count()

        total_actioned = total_completed + currently_missed
        completion_rate = (
            round((total_completed / total_actioned) * 100.0, 1)
            if total_actioned > 0
            else 100.0
        )

        # 8-week workload points
        now = timezone.now()
        cutoff = now - timedelta(days=56)
        recent_assignments = assignments.filter(
            completed=True,
            occurrence__completed_at__gte=cutoff,
        ).select_related("occurrence__chore")

        recent_points = sum(
            a.occurrence.chore.points for a in recent_assignments if a.occurrence and a.occurrence.chore
        )

        unlocked_keys = {
            m.badge_key: m.unlocked_at
            for m in UserMilestone.objects.filter(user=user)
        }

        milestones_list = []
        for key, defs in UserMilestone.BADGE_DEFINITIONS.items():
            unlocked = key in unlocked_keys
            milestones_list.append(
                {
                    "badge_key": key,
                    "name": defs["name"],
                    "description": defs["description"],
                    "icon": defs["icon"],
                    "is_unlocked": unlocked,
                    "unlocked_at": unlocked_keys.get(key),
                }
            )

        return {
            "user_id": user.id,
            "display_name": user.display_name or user.email,
            "current_streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
            "on_time_completions": on_time_completions,
            "late_completions": late_completions,
            "total_completed": total_completed,
            "total_missed": total_missed,
            "currently_missed": currently_missed,
            "completion_rate": completion_rate,
            "recent_workload_points": recent_points,
            "milestones": milestones_list,
        }

    @classmethod
    def get_household_stats(cls, household, requesting_user=None) -> dict:
        """
        Compute non-competitive aggregate household stats and member summaries.
        Strictly avoids competitive leaderboards or rank orderings.
        """
        occurrences = ChoreOccurrence.objects.filter(chore__household=household)
        total_completed = occurrences.filter(
            status=ChoreOccurrence.STATUS_COMPLETED
        ).count()
        total_completed_late = occurrences.filter(
            status=ChoreOccurrence.STATUS_COMPLETED_LATE
        ).count()
        total_missed = occurrences.filter(was_missed=True).count()
        currently_missed = occurrences.filter(
            status=ChoreOccurrence.STATUS_MISSED
        ).count()

        total_done = total_completed + total_completed_late
        total_actioned = total_done + currently_missed
        completion_rate = (
            round((total_done / total_actioned) * 100.0, 1)
            if total_actioned > 0
            else 100.0
        )

        # Non-competitive member summaries sorted alphabetically by name
        active_members = household.get_active_members().select_related("user")
        member_summaries = []
        for m in sorted(
            active_members,
            key=lambda x: (x.user.display_name or x.user.email).lower(),
        ):
            u = m.user
            p_stats = cls.get_personal_stats(u, household_id=household.id)
            member_summaries.append(
                {
                    "user_id": u.id,
                    "display_name": u.display_name or u.email,
                    "total_completed": p_stats["total_completed"],
                    "on_time_completions": p_stats["on_time_completions"],
                    "late_completions": p_stats["late_completions"],
                    "current_streak": p_stats["current_streak"],
                    "longest_streak": p_stats["longest_streak"],
                    "completion_rate": p_stats["completion_rate"],
                    "recent_workload_points": p_stats["recent_workload_points"],
                }
            )

        return {
            "household_id": household.id,
            "household_name": household.name,
            "total_completed": total_done,
            "total_completed_late": total_completed_late,
            "total_missed": total_missed,
            "currently_missed": currently_missed,
            "completion_rate": completion_rate,
            "members": member_summaries,
        }
