from rest_framework import serializers
from activity.models import ActivityLog
from chores.serializers import ChoreOccurrenceSerializer, ChoreSerializer
from users.serializers import UserSerializer


class ActivityLogSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    chore_title = serializers.CharField(source="chore.title", read_only=True, default=None)
    occurrence_status = serializers.CharField(source="occurrence.status", read_only=True, default=None)

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "household",
            "actor",
            "event_type",
            "chore",
            "chore_title",
            "occurrence",
            "occurrence_status",
            "title",
            "description",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
