from rest_framework import serializers
from users.serializers import UserSerializer
from .models import (
    Household,
    HouseholdMember,
    JoinRequest,
    JoinRequestVote,
    LeaveRequest,
    LeaveRequestVote,
    AbsenceRequest,
    AbsenceRequestVote,
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


class AbsenceRequestVoteSerializer(serializers.ModelSerializer):
    voter = UserSerializer(read_only=True)

    class Meta:
        model = AbsenceRequestVote
        fields = ["id", "voter", "approved", "voted_at"]
        read_only_fields = ["id", "voter", "voted_at"]


class AbsenceRequestSerializer(serializers.ModelSerializer):
    member = HouseholdMemberSerializer(read_only=True)
    votes = AbsenceRequestVoteSerializer(many=True, read_only=True)
    household_name = serializers.CharField(source="household.name", read_only=True)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    class Meta:
        model = AbsenceRequest
        fields = [
            "id",
            "household",
            "household_name",
            "member",
            "start_date",
            "end_date",
            "preset",
            "reason",
            "status",
            "votes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "household",
            "household_name",
            "member",
            "status",
            "votes",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        from datetime import timedelta
        from django.utils import timezone

        preset = attrs.get("preset", "").strip().lower()
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        today = timezone.localdate()

        if preset:
            if preset == "weekend":
                days_ahead = (5 - today.weekday()) % 7
                computed_start = today + timedelta(days=days_ahead)
                computed_end = computed_start + timedelta(days=1)
            elif preset == "1_week":
                computed_start = today
                computed_end = today + timedelta(days=7)
            elif preset == "2_weeks":
                computed_start = today
                computed_end = today + timedelta(days=14)
            elif preset == "1_month":
                computed_start = today
                computed_end = today + timedelta(days=30)
            else:
                raise serializers.ValidationError(
                    {"preset": f"Unknown preset: '{preset}'. Valid presets: 'weekend', '1_week', '2_weeks', '1_month'."}
                )

            if not start_date:
                attrs["start_date"] = computed_start
            if not end_date:
                attrs["end_date"] = computed_end
        else:
            if not start_date or not end_date:
                raise serializers.ValidationError(
                    "Either a valid 'preset' or both 'start_date' and 'end_date' must be provided."
                )

        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError(
                {"end_date": "end_date cannot be earlier than start_date."}
            )

        return attrs
