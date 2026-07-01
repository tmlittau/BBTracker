from rest_framework import serializers

from .models import BodyMeasurement, unit_for


class BodyMeasurementSerializer(serializers.ModelSerializer):
    unit = serializers.SerializerMethodField()

    class Meta:
        model = BodyMeasurement
        fields = ["id", "date", "type", "value", "unit", "method", "notes"]

    def get_unit(self, obj) -> str:
        return unit_for(obj.type)


class MetricSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.CharField()
    group = serializers.CharField()


class SeriesOverlaySerializer(serializers.Serializer):
    """Aligned metric series + phase/protocol annotations for the explore tool."""

    start = serializers.CharField()
    end = serializers.CharField()
    metrics = serializers.ListField(child=serializers.DictField())
    phases = serializers.ListField(child=serializers.DictField())
    events = serializers.ListField(child=serializers.DictField())


class BodyAnalysisSerializer(serializers.Serializer):
    """Loose shape for the computed analysis (documented for the client)."""

    date = serializers.CharField()
    sex = serializers.CharField()
    composition = serializers.DictField()
    distribution = serializers.DictField()
    energy = serializers.DictField()
    blood_pressure = serializers.DictField(allow_null=True)
    bloodwork = serializers.DictField()
    composition_trend = serializers.ListField(child=serializers.DictField())
    insights = serializers.ListField(child=serializers.DictField())
    assessments = serializers.ListField(child=serializers.DictField())
    measurements = serializers.ListField(child=serializers.DictField())
