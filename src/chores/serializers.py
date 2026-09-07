from rest_framework import serializers

from households.models import Household, HouseholdMember
from .heuristic import suggest_effort_level
from .models import Chore


class EffortSuggestionSerializer(serializers.Serializer):
    """Input and output for effort suggestion helper."""

    title = serializers.CharField(required=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    suggested_effort = serializers.CharField(read_only=True)
    points = serializers.IntegerField(read_only=True)


class ChoreSerializer(serializers.ModelSerializer):
    """Serializer for CRUD operations on household chores."""

    points = serializers.IntegerField(read_only=True)

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "points", "created_at", "updated_at"]

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
