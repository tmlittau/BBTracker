from rest_framework import serializers

from .models import Phase, PhaseAdjustment


class PhaseAdjustmentSerializer(serializers.ModelSerializer):
    nutrition_target_name = serializers.CharField(
        source="nutrition_target.name", read_only=True, default=None
    )
    program_name = serializers.CharField(source="program.name", read_only=True, default=None)
    protocol_name = serializers.CharField(source="protocol.name", read_only=True, default=None)

    class Meta:
        model = PhaseAdjustment
        fields = [
            "id", "phase", "effective_date", "reason",
            "nutrition_target", "program", "protocol",
            "nutrition_target_name", "program_name", "protocol_name",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class PhaseSerializer(serializers.ModelSerializer):
    is_ongoing = serializers.BooleanField(read_only=True)
    adjustments = PhaseAdjustmentSerializer(many=True, read_only=True)

    class Meta:
        model = Phase
        fields = [
            "id", "name", "phase_type", "start_date", "end_date", "notes",
            "is_ongoing", "adjustments", "created_at",
        ]
        read_only_fields = ["created_at"]


# --- Computed read-only payloads (documented for the schema) ---


class DashboardTodaySerializer(serializers.Serializer):
    date = serializers.CharField()
    phase = serializers.DictField(allow_null=True)
    nutrition = serializers.DictField()
    workout = serializers.DictField(allow_null=True)
    doses = serializers.ListField(child=serializers.DictField())


class WeeklyCheckInSerializer(serializers.Serializer):
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    phase = serializers.DictField(allow_null=True)
    bodyweight = serializers.DictField(allow_null=True)
    subjective = serializers.DictField()
    training = serializers.DictField()
    nutrition = serializers.DictField()
    doses = serializers.IntegerField()
    photos = serializers.IntegerField()
    last_bloodwork = serializers.CharField(allow_null=True)
    check_ins = serializers.IntegerField()
