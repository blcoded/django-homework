from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    User notification center:
    - Lists notifications scoped strictly to the authenticated user.
    - Endpoints for marking individual notifications or all notifications as read.
    - Unread count query.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        unread = self.request.query_params.get("unread")
        if unread and unread.lower() in ["true", "1", "yes"]:
            qs = qs.filter(is_read=False)
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() in ["true", "1", "yes"])
        return qs

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        return Response(
            self.get_serializer(notification).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Mark all unread notifications of the current user as read."""
        now = timezone.now()
        unread_qs = Notification.objects.filter(user=request.user, is_read=False)
        count = unread_qs.count()
        unread_qs.update(is_read=True, read_at=now, updated_at=now)
        return Response(
            {"status": "ok", "marked_read_count": count},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Retrieve count of unread notifications for the current user."""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)
