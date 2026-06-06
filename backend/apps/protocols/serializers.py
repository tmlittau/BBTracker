from rest_framework import serializers

from .models import (
    BloodMarker,
    BloodPressureLog,
    BloodResult,
    Compound,
    DoseLog,
    InjectionSite,
    Protocol,
    ProtocolItem,
    Supplement,
    SupplementNutrient,
    Vial,
)


class CompoundSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(read_only=True)

    class Meta:
        model = Compound
        fields = [
            "id", "name", "slug", "compound_class", "default_unit", "default_route",
            "half_life_hours", "ester", "active_fraction", "notes", "is_global",
        ]
        read_only_fields = ["slug", "is_global"]


class SupplementNutrientSerializer(serializers.ModelSerializer):
    nutrient_name = serializers.CharField(source="nutrient.name", read_only=True)
    slug = serializers.CharField(source="nutrient.slug", read_only=True)
    unit = serializers.CharField(source="nutrient.unit", read_only=True)

    class Meta:
        model = SupplementNutrient
        fields = ["id", "nutrient", "nutrient_name", "slug", "unit", "amount_per_serving"]


class SupplementSerializer(serializers.ModelSerializer):
    supplement_nutrients = SupplementNutrientSerializer(many=True, required=False)
    is_global = serializers.BooleanField(read_only=True)

    class Meta:
        model = Supplement
        fields = [
            "id", "name", "brand", "serving_label", "target_benefit", "notes",
            "is_global", "supplement_nutrients",
        ]
        read_only_fields = ["is_global"]

    def create(self, validated_data):
        nutrients = validated_data.pop("supplement_nutrients", [])
        supp = Supplement.objects.create(**validated_data)
        for n in nutrients:
            SupplementNutrient.objects.create(supplement=supp, **n)
        return supp

    def update(self, instance, validated_data):
        nutrients = validated_data.pop("supplement_nutrients", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if nutrients is not None:
            instance.supplement_nutrients.all().delete()
            for n in nutrients:
                SupplementNutrient.objects.create(supplement=instance, **n)
        return instance


class InjectionSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InjectionSite
        fields = ["id", "name", "slug", "region", "side", "x", "y"]


class BloodMarkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodMarker
        fields = [
            "id", "name", "slug", "unit", "category",
            "ref_low", "ref_high", "ref_low_male", "ref_high_male",
            "ref_low_female", "ref_high_female", "display_order",
        ]


class ProtocolItemSerializer(serializers.ModelSerializer):
    item_name = serializers.SerializerMethodField()

    class Meta:
        model = ProtocolItem
        fields = [
            "id", "protocol", "compound", "supplement", "item_name",
            "dose_amount", "dose_unit", "route", "frequency",
            "days_of_week", "times_of_day",
            "target_benefit", "notes", "order",
        ]

    def get_item_name(self, obj) -> str:
        item = obj.compound or obj.supplement
        return str(item) if item else ""

    def validate(self, attrs):
        compound = attrs.get("compound", getattr(self.instance, "compound", None))
        supplement = attrs.get("supplement", getattr(self.instance, "supplement", None))
        if not compound and not supplement:
            raise serializers.ValidationError("A protocol item needs a compound or a supplement.")
        return attrs


class ProtocolSerializer(serializers.ModelSerializer):
    items = ProtocolItemSerializer(many=True, read_only=True)

    class Meta:
        model = Protocol
        fields = ["id", "name", "is_active", "started_on", "ended_on", "notes", "items"]


class DoseLogSerializer(serializers.ModelSerializer):
    item_name = serializers.SerializerMethodField()
    site_name = serializers.CharField(source="injection_site.name", read_only=True)

    class Meta:
        model = DoseLog
        fields = [
            "id", "protocol_item", "compound", "supplement", "item_name",
            "taken_at", "amount", "unit", "route", "injection_site", "site_name",
            "notes", "side_effects",
        ]

    def get_item_name(self, obj) -> str:
        item = obj.compound or obj.supplement
        return str(item) if item else ""

    def validate(self, attrs):
        compound = attrs.get("compound", getattr(self.instance, "compound", None))
        supplement = attrs.get("supplement", getattr(self.instance, "supplement", None))
        if not compound and not supplement:
            raise serializers.ValidationError("A dose needs a compound or a supplement.")
        return attrs


class VialSerializer(serializers.ModelSerializer):
    compound_name = serializers.CharField(source="compound.name", read_only=True)
    needs_reorder = serializers.BooleanField(read_only=True)

    class Meta:
        model = Vial
        fields = [
            "id", "compound", "compound_name", "label", "concentration_mg_ml",
            "total_amount", "remaining_amount", "unit", "reorder_threshold", "needs_reorder",
        ]


class BloodResultSerializer(serializers.ModelSerializer):
    marker_name = serializers.CharField(source="marker.name", read_only=True)
    unit = serializers.SerializerMethodField()

    class Meta:
        model = BloodResult
        fields = [
            "id", "marker", "marker_name", "unit", "value",
            "ref_low", "ref_high", "source", "measured_on", "notes",
        ]

    def get_unit(self, obj) -> str:
        """Effective unit: the result's own, else the marker's default."""
        return obj.unit or (obj.marker.unit if obj.marker_id else "")


class BloodPressureLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodPressureLog
        fields = ["id", "systolic", "diastolic", "pulse", "measured_at", "notes"]


# --- Computed read-only payloads ---


class ReleasePointSerializer(serializers.Serializer):
    day = serializers.IntegerField()
    date = serializers.CharField()
    rate = serializers.FloatField()
    projected = serializers.BooleanField()


class ReleaseCompoundSerializer(serializers.Serializer):
    compound_id = serializers.IntegerField()
    name = serializers.CharField()
    unit = serializers.CharField()
    half_life_hours = serializers.FloatField()
    active_fraction = serializers.FloatField()
    points = ReleasePointSerializer(many=True)


class ProtocolReleaseSerializer(serializers.Serializer):
    now = serializers.CharField()
    today_day = serializers.IntegerField()
    start = serializers.CharField(allow_null=True)
    end = serializers.CharField(allow_null=True)
    unit = serializers.CharField()
    compounds = ReleaseCompoundSerializer(many=True)
    excluded = serializers.ListField(child=serializers.CharField())


class SiteRecencySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    region = serializers.CharField()
    side = serializers.CharField()
    x = serializers.DecimalField(max_digits=5, decimal_places=2)
    y = serializers.DecimalField(max_digits=5, decimal_places=2)
    last_used = serializers.CharField(allow_null=True)
    days_since = serializers.FloatField(allow_null=True)
    status = serializers.CharField()


class AdherenceRowSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    name = serializers.CharField()
    frequency = serializers.CharField()
    expected = serializers.FloatField()
    actual = serializers.IntegerField()
    adherence = serializers.IntegerField(allow_null=True)


class MarkerTrendPointSerializer(serializers.Serializer):
    date = serializers.CharField()
    value = serializers.DecimalField(max_digits=10, decimal_places=3)
    unit = serializers.CharField()
    flag = serializers.CharField()
