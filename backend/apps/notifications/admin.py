from django.contrib import admin

from .models import DeviceToken, ReminderDispatch, ReminderSettings, RestReminder


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ["owner", "platform", "environment", "is_active", "last_seen"]
    list_filter = ["platform", "environment", "is_active"]
    search_fields = ["owner__email", "token"]


@admin.register(ReminderSettings)
class ReminderSettingsAdmin(admin.ModelAdmin):
    list_display = ["owner", "enabled", "rest_enabled"]
    search_fields = ["owner__email"]


@admin.register(ReminderDispatch)
class ReminderDispatchAdmin(admin.ModelAdmin):
    list_display = ["owner", "slot", "sent_on", "items"]
    list_filter = ["slot", "sent_on"]
    search_fields = ["owner__email"]


@admin.register(RestReminder)
class RestReminderAdmin(admin.ModelAdmin):
    list_display = ["owner", "fire_at"]
    search_fields = ["owner__email"]
