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
    ChoreSwapRequest,
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
    original_user = UserSerializer(read_only=True)

    class Meta:
        model = ChoreAssignment
        fields = [
            "id",
            "user",
            "original_user",
            "is_swapped",
            "completed",
            "completed_at",
            "was_missed",
            "missed_at",
            "notes",
            "proof_image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "original_user",
            "is_swapped",
            "completed",
            "completed_at",
            "was_missed",
            "missed_at",
            "proof_image",
            "created_at",
            "updated_at",
        ]


class ChoreCompletionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    proof_image = serializers.FileField(
        required=False,
        allow_null=True,
        default=None,
    )

    def validate_proof_image(self, value):
        if value:
            from .validators import validate_image_proof

            validate_image_proof(value)
        return value


class ChoreVerificationSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ChoreDisputeSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False)


class ChoreOccurrenceSerializer(serializers.ModelSerializer):
    chore = ChoreSerializer(read_only=True)
    assignments = ChoreAssignmentSerializer(many=True, read_only=True)
    is_actionable = serializers.BooleanField(read_only=True)
    verified_by = UserSerializer(read_only=True)
    disputed_by = UserSerializer(read_only=True)

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
            "is_verified",
            "verified_by",
            "verified_at",
            "verification_notes",
            "is_disputed",
            "disputed_by",
            "disputed_at",
            "dispute_reason",
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
            "is_verified",
            "verified_by",
            "verified_at",
            "verification_notes",
            "is_disputed",
            "disputed_by",
            "disputed_at",
            "dispute_reason",
            "assignments",
            "is_actionable",
            "created_at",
            "updated_at",
        ]


class ChoreSwapRequestSerializer(serializers.ModelSerializer):
    proposer = UserSerializer(read_only=True)
    recipient = UserSerializer(read_only=True)
    recipient_id = serializers.PrimaryKeyRelatedField(
        queryset=HouseholdMember.objects.none(),
        write_only=True,
        source="recipient",
    )
    proposer_occurrence = ChoreOccurrenceSerializer(read_only=True)
    proposer_occurrence_id = serializers.PrimaryKeyRelatedField(
        queryset=ChoreOccurrence.objects.all(),
        write_only=True,
        source="proposer_occurrence",
    )
    recipient_occurrence = ChoreOccurrenceSerializer(read_only=True)
    recipient_occurrence_id = serializers.PrimaryKeyRelatedField(
        queryset=ChoreOccurrence.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
        source="recipient_occurrence",
    )

    class Meta:
        model = ChoreSwapRequest
        fields = [
            "id",
            "household",
            "proposer",
            "recipient",
            "recipient_id",
            "proposer_occurrence",
            "proposer_occurrence_id",
            "recipient_occurrence",
            "recipient_occurrence_id",
            "status",
            "notes",
            "created_at",
            "responded_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "household",
            "proposer",
            "recipient",
            "proposer_occurrence",
            "recipient_occurrence",
            "status",
            "created_at",
            "responded_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.fields["recipient_id"].queryset = User.objects.all()

    def validate(self, attrs):
        request = self.context.get("request")
        proposer = request.user if request else None
        recipient = attrs.get("recipient")
        proposer_occurrence = attrs.get("proposer_occurrence")
        recipient_occurrence = attrs.get("recipient_occurrence")

        if proposer == recipient:
            raise serializers.ValidationError(
                "You cannot propose a chore swap with yourself."
            )

        household = proposer_occurrence.chore.household
        is_proposer_active = HouseholdMember.objects.filter(
            household=household, user=proposer, status=HouseholdMember.STATUS_ACTIVE
        ).exists()
        is_recipient_active = HouseholdMember.objects.filter(
            household=household, user=recipient, status=HouseholdMember.STATUS_ACTIVE
        ).exists()

        if not (is_proposer_active and is_recipient_active):
            raise serializers.ValidationError(
                "Both proposer and recipient must be active members of the same household."
            )

        if not proposer_occurrence.assignments.filter(user=proposer).exists():
            raise serializers.ValidationError(
                "You can only offer chore occurrences that are currently assigned to you."
            )

        if proposer_occurrence.status not in [
            ChoreOccurrence.STATUS_ACTIVE,
            ChoreOccurrence.STATUS_UPCOMING,
        ]:
            raise serializers.ValidationError(
                "You cannot swap an occurrence that is already completed or past-due."
            )

        if recipient_occurrence:
            if recipient_occurrence.chore.household != household:
                raise serializers.ValidationError(
                    "Swapped occurrences must belong to the same household."
                )
            if not recipient_occurrence.assignments.filter(user=recipient).exists():
                raise serializers.ValidationError(
                    "The requested occurrence must be currently assigned to the recipient."
                )
            if recipient_occurrence.status not in [
                ChoreOccurrence.STATUS_ACTIVE,
                ChoreOccurrence.STATUS_UPCOMING,
            ]:
                raise serializers.ValidationError(
                    "Cannot request an occurrence that is already completed or past-due."
                )

        attrs["household"] = household
        attrs["proposer"] = proposer
        return attrs

