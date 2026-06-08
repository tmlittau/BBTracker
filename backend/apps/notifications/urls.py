from django.urls import path

from .views import (
    ReminderSettingsView,
    RestCancelView,
    RestScheduleView,
    TestNotificationView,
)

urlpatterns = [
    path("reminder-settings/", ReminderSettingsView.as_view(), name="reminder-settings"),
    path("rest/schedule/", RestScheduleView.as_view(), name="rest-schedule"),
    path("rest/cancel/", RestCancelView.as_view(), name="rest-cancel"),
    path("test/", TestNotificationView.as_view(), name="notify-test"),
]
