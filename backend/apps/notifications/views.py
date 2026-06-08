from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response

from .models import ReminderSettings, RestReminder
from .serializers import (
    NotifyResultSerializer,
    ReminderSettingsSerializer,
    RestScheduleSerializer,
)
from .services import ha_notify_result


@extend_schema(tags=["notifications"])
class ReminderSettingsView(generics.RetrieveUpdateAPIView):
    """Get/update the current user's reminder preferences (slot times + toggles)."""

    serializer_class = ReminderSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj, _ = ReminderSettings.objects.get_or_create(owner=self.request.user)
        return obj


@extend_schema(tags=["notifications"], responses=NotifyResultSerializer)
class RestScheduleView(generics.GenericAPIView):
    """Schedule (or replace) the user's pending 'rest over' notification."""

    serializer_class = RestScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        prefs, _ = ReminderSettings.objects.get_or_create(owner=request.user)
        if not (prefs.enabled and prefs.rest_enabled):
            return Response({"ok": False})
        RestReminder.objects.update_or_create(
            owner=request.user,
            defaults={"fire_at": timezone.now() + timedelta(seconds=s.validated_data["seconds"])},
        )
        return Response({"ok": True})


@extend_schema(tags=["notifications"], request=None, responses=NotifyResultSerializer)
class RestCancelView(generics.GenericAPIView):
    """Cancel any pending 'rest over' notification (rest skipped/finished early)."""

    serializer_class = NotifyResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        RestReminder.objects.filter(owner=request.user).delete()
        return Response({"ok": True})


@extend_schema(tags=["notifications"], request=None, responses=NotifyResultSerializer)
class TestNotificationView(generics.GenericAPIView):
    """Send a test notification to confirm the Home Assistant wiring works."""

    serializer_class = NotifyResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ok, detail = ha_notify_result(
            "BBTracker", "Test notification — Home Assistant wiring works."
        )
        return Response({"ok": ok, "detail": detail})
