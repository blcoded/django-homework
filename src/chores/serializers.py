from rest_framework import serializers

from households.models import Household, HouseholdMember
from users.serializers import UserSerializer
from .heuristic import suggest_effort_level
from .models import (
    Chore,
    ChoreAssignment,
    ChoreOccurrence,
    ChoreSuggestion,
    ChoreSuggestionVote,
)



class EffortSuggestionSerializer(serializers.Serializer):
    """Input and output for effort suggestion helper."""

    title = serializers.CharField(required=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    suggested_effort = serializers.CharField(read_only=True)
    points = serializers.IntegerField(read_only=True)


class ChoreSerializer(serializers.ModelSerializer):
    """Serializer for CRUD operations on household chores."""

    points = serializers.IntegerField(read_only=True)
    next_up = serializers.SerializerMethodField()

    class Meta:
        model = Chore
        fields = [
            "id",
            "household",
            "title",
            "description",
            "effort_level",
            "points",
            "recurrence_type",
            "recurrence_rule",
            "deadline_mode",
            "deadline_window_hours",
            "is_multi_assignee",
            "required_assignees_count",
            "is_archived",
            "next_up",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "points", "next_up", "created_at", "updated_at"]

    def get_next_up(self, obj):
        from .rotation import HiddenRotationService

        return HiddenRotationService.get_next_up_data(obj)

    def validate_household(self, household):
        user = self.context["request"].user
        # Verify user is an active member of the target household
        is_active = HouseholdMember.objects.filter(
            household=household,
            user=user,
            status=HouseholdMember.STATUS_ACTIVE,
        ).exists()
        if not is_active:
            raise serializers.ValidationError(
                "You must be an active member of this household to manage its chores."
            )
        return household

    def create(self, validated_data):
        # Apply heuristic if effort_level not specified by creator
        if not validated_data.get("effort_level"):
            title = validated_data.get("title", "")
            desc = validated_data.get("description", "")
            validated_data["effort_level"] = suggest_effort_level(title, desc)

        return super().create(validated_data)


class ChoreSuggestionVoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChoreSuggestionVote
        fields = ["id", "approved", "voted_at"]
        read_only_fields = ["id", "voted_at"]


class ChoreSuggestionSerializer(serializers.ModelSerializer):
    """
    Serializer for anonymous chore suggestions.
    Strictly omits creator identity to guarantee complete anonymity.
    """

    approvals_count = serializers.SerializerMethodField()
    rejections_count = serializers.SerializerMethodField()
    majority_needed = serializers.SerializerMethodField()
    has_user_voted = serializers.SerializerMethodField()

    class Meta:
        model = ChoreSuggestion
        fields = [
            "id",
            "household",
            "title",
            "description",
            "effort_level",
            "recurrence_type",
            "recurrence_rule",
            "deadline_mode",
            "deadline_window_hours",
            "is_multi_assignee",
            "required_assignees_count",
            "status",
            "approved_chore",
            "approvals_count",
            "rejections_count",
            "majority_needed",
            "has_user_voted",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "approved_chore",
            "expires_at",
            "created_at",
            "updated_at",
        ]

    def get_approvals_count(self, obj):
        return obj.votes.filter(approved=True).count()

    def get_rejections_count(self, obj):
        return obj.votes.filter(approved=False).count()

    def get_majority_needed(self, obj):
        total = obj.household.get_active_members().count()
        return (total // 2) + 1

    def get_has_user_voted(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.votes.filter(voter=request.user).exists()
        return False

    def validate_household(self, household):
        user = self.context["request"].user
        is_active = HouseholdMember.objects.filter(
            household=household,
            user=user,
            status=HouseholdMember.STATUS_ACTIVE,
        ).exists()
        if not is_active:
            raise serializers.ValidationError(
                "You must be an active member of this household to suggest chores."
            )
        return household

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["creator"] = user
        if not validated_data.get("effort_level"):
            title = validated_data.get("title", "")
            desc = validated_data.get("description", "")
            validated_data["effort_level"] = suggest_effort_level(title, desc)
        return super().create(validated_data)


class ChoreAssignmentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ChoreAssignment
        fields = [
            "id",
            "user",
            "completed",
            "completed_at",
            "was_missed",
            "missed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "completed",
            "completed_at",
            "was_missed",
            "missed_at",
            "created_at",
            "updated_at",
        ]


class ChoreOccurrenceSerializer(serializers.ModelSerializer):
    chore = ChoreSerializer(read_only=True)
    assignments = ChoreAssignmentSerializer(many=True, read_only=True)
    is_actionable = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChoreOccurrence
        fields = [
            "id",
            "chore",
            "status",
            "scheduled_start",
            "due_date",
            "completed_at",
            "missed_at",
            "was_missed",
            "assignments",
            "is_actionable",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "chore",
            "status",
            "scheduled_start",
            "due_date",
            "completed_at",
            "missed_at",
            "was_missed",
            "assignments",
            "is_actionable",
            "created_at",
            "updated_at",
        ]

