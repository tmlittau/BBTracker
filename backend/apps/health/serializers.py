from decimal import Decimal

from rest_framework import serializers

from .models import HealthDailyAggregate


class HealthDailyAggregateSerializer(serializers.ModelSerializer):
    value = serializers.FloatField()
    minimum = serializers.FloatField(allow_null=True, required=False)
    maximum = serializers.FloatField(allow_null=True, required=False)

    class Meta:
        model = HealthDailyAggregate
        fields = [
            "kind",
            "date",
            "value",
            "minimum",
            "maximum",
            "sample_count",
            "source",
            "source_fingerprint",
            "updated_at",
        ]
        validators = []

    def validate(self, attrs):
        for field in ("value", "minimum", "maximum"):
            value = attrs.get(field)
            if value is not None:
                attrs[field] = Decimal(str(round(value, 4)))
        return attrs
