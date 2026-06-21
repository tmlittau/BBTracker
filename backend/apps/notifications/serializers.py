from rest_framework import serializers

from .models import ReminderSettings


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
