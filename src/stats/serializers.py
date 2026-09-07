from rest_framework import serializers
from stats.models import UserMilestone, UserStreak


class MilestoneBadgeSerializer(serializers.Serializer):
    badge_key = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    icon = serializers.CharField()
    is_unlocked = serializers.BooleanField()
    unlocked_at = serializers.DateTimeField(allow_null=True)


class PersonalStatsSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    display_name = serializers.CharField()
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    on_time_completions = serializers.IntegerField()
    late_completions = serializers.IntegerField()
    total_completed = serializers.IntegerField()
    total_missed = serializers.IntegerField()
    currently_missed = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    recent_workload_points = serializers.IntegerField()
    milestones = MilestoneBadgeSerializer(many=True)


class HouseholdMemberSummarySerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    display_name = serializers.CharField()
    total_completed = serializers.IntegerField()
    on_time_completions = serializers.IntegerField()
    late_completions = serializers.IntegerField()
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    recent_workload_points = serializers.IntegerField()


class HouseholdStatsSerializer(serializers.Serializer):
    household_id = serializers.IntegerField()
    household_name = serializers.CharField()
    total_completed = serializers.IntegerField()
    total_completed_late = serializers.IntegerField()
    total_missed = serializers.IntegerField()
    currently_missed = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    members = HouseholdMemberSummarySerializer(many=True)
