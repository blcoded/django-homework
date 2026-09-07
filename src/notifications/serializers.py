from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for user notifications."""

    class Meta:
        model = Notification
        fields = [
            "id",
            "household",
            "occurrence",
            "notification_type",
            "title",
            "message",
            "is_read",
            "read_at",
            "email_sent",
            "email_sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "household",
            "occurrence",
            "notification_type",
            "title",
            "message",
            "email_sent",
            "email_sent_at",
            "created_at",
            "updated_at",
        ]
