from rest_framework import serializers
from users.serializers import UserSerializer
from .models import (
    Household,
    HouseholdMember,
    JoinRequest,
    JoinRequestVote,
    LeaveRequest,
    LeaveRequestVote,
)


class HouseholdMemberSerializer(serializers.ModelSerializer):
    """Serializer for household members."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = HouseholdMember
        fields = ["id", "user", "status", "joined_at", "updated_at"]
        read_only_fields = ["id", "joined_at", "updated_at"]


class HouseholdSerializer(serializers.ModelSerializer):
    """Serializer for household details and updates."""

    active_members_count = serializers.SerializerMethodField()

    class Meta:
        model = Household
        fields = [
            "id",
            "name",
            "timezone",
            "require_join_approval",
            "require_completion_verification",
            "invite_code",
            "active_members_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "invite_code", "created_at", "updated_at"]

    def get_active_members_count(self, obj):
        return obj.members.filter(status=HouseholdMember.STATUS_ACTIVE).count()


class HouseholdCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new household, enrolling the creator as first active member."""

    class Meta:
        model = Household
        fields = [
            "id",
            "name",
            "timezone",
            "require_join_approval",
            "require_completion_verification",
            "invite_code",
            "created_at",
        ]
        read_only_fields = ["id", "invite_code", "created_at"]

    def create(self, validated_data):
        user = self.context["request"].user
        household = Household.objects.create(**validated_data)
        # Automatically enroll creator as the first active member with equal permissions
        HouseholdMember.objects.create(
            household=household,
            user=user,
            status=HouseholdMember.STATUS_ACTIVE,
        )
        return household


class JoinRequestVoteSerializer(serializers.ModelSerializer):
    voter = UserSerializer(read_only=True)

    class Meta:
        model = JoinRequestVote
        fields = ["id", "voter", "approved", "voted_at"]
        read_only_fields = ["id", "voter", "voted_at"]


class JoinRequestSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    votes = JoinRequestVoteSerializer(many=True, read_only=True)
    household_name = serializers.CharField(source="household.name", read_only=True)

    class Meta:
        model = JoinRequest
        fields = [
            "id",
            "household",
            "household_name",
            "user",
            "status",
            "votes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "household", "user", "status", "created_at", "updated_at"]


class LeaveRequestVoteSerializer(serializers.ModelSerializer):
    voter = UserSerializer(read_only=True)

    class Meta:
        model = LeaveRequestVote
        fields = ["id", "voter", "approved", "voted_at"]
        read_only_fields = ["id", "voter", "voted_at"]


class LeaveRequestSerializer(serializers.ModelSerializer):
    member = HouseholdMemberSerializer(read_only=True)
    votes = LeaveRequestVoteSerializer(many=True, read_only=True)
    household_name = serializers.CharField(source="household.name", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "household",
            "household_name",
            "member",
            "status",
            "votes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "household", "member", "status", "created_at", "updated_at"]


class VoteActionSerializer(serializers.Serializer):
    approved = serializers.BooleanField(required=True)


class JoinHouseholdSerializer(serializers.Serializer):
    invite_code = serializers.CharField(required=True)
