from rest_framework import serializers

from .models import CheckInComment, CoachClientLink


def _display_name(user):
    return (user.get_full_name() or "").strip() or user.email


class ClientBriefSerializer(serializers.Serializer):
    """A coach's at-a-glance row for one client (computed, read-only)."""

    link_id = serializers.IntegerField()
    client_id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    status = serializers.CharField()
    can_edit_prescriptions = serializers.BooleanField()
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
            "coach_name", "client_name", "status", "can_edit_prescriptions",
            "created_at", "responded_at",
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


class LinkPermissionSerializer(serializers.Serializer):
    can_edit_prescriptions = serializers.BooleanField()


class CheckInCommentSerializer(serializers.ModelSerializer):
    """One message in a check-in thread. `by_coach` = author is not the check-in owner."""

    author_name = serializers.SerializerMethodField()
    by_coach = serializers.SerializerMethodField()

    class Meta:
        model = CheckInComment
        fields = ["id", "check_in", "author", "author_name", "by_coach", "body", "created_at"]
        read_only_fields = ["author", "created_at"]

    def get_author_name(self, obj) -> str:
        return _display_name(obj.author)

    def get_by_coach(self, obj) -> bool:
        return obj.author_id != obj.check_in.owner_id


class CheckInReviewRowSerializer(serializers.Serializer):
    """A row in the coach's review queue (computed, read-only)."""

    id = serializers.IntegerField()
    client_id = serializers.IntegerField()
    client_name = serializers.CharField()
    date = serializers.DateField()
    bodyweight = serializers.FloatField(allow_null=True)
    energy = serializers.IntegerField(allow_null=True)
    sleep = serializers.IntegerField(allow_null=True)
    has_notes = serializers.BooleanField()
    comment_count = serializers.IntegerField()
    reviewed = serializers.BooleanField()
