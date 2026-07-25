from rest_framework import serializers

from .models import DeviceToken, ReminderSettings


class DeviceTokenSerializer(serializers.ModelSerializer):
    token = serializers.RegexField(
        r"^[0-9a-fA-F]+$",
        min_length=32,
        max_length=200,
        trim_whitespace=True,
    )

    class Meta:
        model = DeviceToken
        fields = ["token", "platform", "environment", "last_seen"]
        read_only_fields = ["platform", "last_seen"]

    def validate_token(self, value):
        return value.lower()


class ReminderSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderSettings
        fields = [
            "enabled", "rest_enabled",
            "waking", "am", "noon", "pm", "night",
            "waking_label", "am_label", "noon_label", "pm_label", "night_label",
        ]


class RestScheduleSerializer(serializers.Serializer):
    seconds = serializers.IntegerField(min_value=1, max_value=3600)


class NotifyResultSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
