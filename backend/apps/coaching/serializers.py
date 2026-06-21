from rest_framework import serializers

from .models import CoachClientLink


def _display_name(user):
    return (user.get_full_name() or "").strip() or user.email


class ClientBriefSerializer(serializers.Serializer):
    """A coach's at-a-glance row for one client (computed, read-only)."""

    link_id = serializers.IntegerField()
    client_id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    status = serializers.CharField()
    phase = serializers.CharField(allow_null=True)
    last_check_in = serializers.DateField(allow_null=True)
    bodyweight = serializers.FloatField(allow_null=True)


class LinkSerializer(serializers.ModelSerializer):
    """A coach↔client link as seen by either party."""

    coach_email = serializers.EmailField(source="coach.email", read_only=True)
    client_email = serializers.EmailField(source="client.email", read_only=True)
    coach_name = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()

    class Meta:
        model = CoachClientLink
        fields = [
            "id", "coach", "client", "coach_email", "client_email",
            "coach_name", "client_name", "status", "created_at", "responded_at",
        ]
        read_only_fields = fields

    def get_coach_name(self, obj):
        return _display_name(obj.coach)

    def get_client_name(self, obj):
        return _display_name(obj.client)


class InviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()


class InviteRespondSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
