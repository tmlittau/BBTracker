from django.urls import path

from .views import (
    DeviceTokenDeleteView,
    DeviceTokenView,
    ReminderSettingsView,
    RestCancelView,
    RestScheduleView,
    TestNotificationView,
)

urlpatterns = [
    path("devices/", DeviceTokenView.as_view(), name="device-token"),
    path(
        "devices/<str:token>/",
        DeviceTokenDeleteView.as_view(),
        name="device-token-delete",
    ),
    path("reminder-settings/", ReminderSettingsView.as_view(), name="reminder-settings"),
    path("rest/schedule/", RestScheduleView.as_view(), name="rest-schedule"),
    path("rest/cancel/", RestCancelView.as_view(), name="rest-cancel"),
    path("test/", TestNotificationView.as_view(), name="notify-test"),
]
