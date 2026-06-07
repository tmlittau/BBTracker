import re

from rest_framework import serializers

from .models import (
    DiaryEntry,
    Food,
    FoodNutrient,
    Meal,
    Nutrient,
    NutrientTarget,
    NutritionTarget,
    Recipe,
    RecipeItem,
    ServingSize,
)


class NutrientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nutrient
        fields = ["id", "name", "slug", "category", "unit", "rda", "display_order", "is_energy"]


class ServingSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServingSize
        fields = ["id", "label", "grams", "is_default"]


class FoodNutrientSerializer(serializers.ModelSerializer):
    nutrient_name = serializers.CharField(source="nutrient.name", read_only=True)
    unit = serializers.CharField(source="nutrient.unit", read_only=True)
    slug = serializers.CharField(source="nutrient.slug", read_only=True)

    class Meta:
        model = FoodNutrient
        fields = ["id", "nutrient", "nutrient_name", "slug", "unit", "amount_per_100g"]


class FoodSerializer(serializers.ModelSerializer):
    servings = ServingSizeSerializer(many=True, required=False)
    food_nutrients = FoodNutrientSerializer(many=True, required=False)
    is_global = serializers.BooleanField(read_only=True)

    class Meta:
        model = Food
        fields = [
            "id", "name", "brand", "source", "barcode", "unit", "is_verified", "is_global",
            "servings", "food_nutrients",
        ]
        read_only_fields = ["source", "is_verified", "is_global"]

    def create(self, validated_data):
        servings = validated_data.pop("servings", [])
        nutrients = validated_data.pop("food_nutrients", [])
        food = Food.objects.create(**validated_data)
        for s in servings:
            ServingSize.objects.create(food=food, **s)
        for n in nutrients:
            FoodNutrient.objects.create(food=food, **n)
        return food

    def update(self, instance, validated_data):
        servings = validated_data.pop("servings", None)
        nutrients = validated_data.pop("food_nutrients", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if servings is not None:
            instance.servings.all().delete()
            for s in servings:
                ServingSize.objects.create(food=instance, **s)
        if nutrients is not None:
            instance.food_nutrients.all().delete()
            for n in nutrients:
                FoodNutrient.objects.create(food=instance, **n)
        return instance


class BarcodeImportSerializer(serializers.Serializer):
    """Request body for the barcode-import action: a single UPC/EAN."""

    barcode = serializers.CharField(max_length=32)

    def validate_barcode(self, value: str) -> str:
        code = value.strip()
        if not re.fullmatch(r"\d{6,14}", code):
            raise serializers.ValidationError(
                "Enter a valid 6–14 digit barcode (UPC/EAN)."
            )
        return code


class BarcodeDraftSerializer(serializers.Serializer):
    """A New-Food draft from a barcode lookup (nothing persisted yet)."""

    name = serializers.CharField()
    brand = serializers.CharField(allow_blank=True)
    unit = serializers.CharField()
    barcode = serializers.CharField()
    nutrients = serializers.DictField(child=serializers.CharField())


class MealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meal
        fields = ["id", "date", "name", "order"]


class DiaryEntrySerializer(serializers.ModelSerializer):
    grams = serializers.DecimalField(max_digits=9, decimal_places=2, read_only=True)
    item_name = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()

    class Meta:
        model = DiaryEntry
        fields = [
            "id", "date", "meal", "food", "recipe", "serving",
            "quantity", "grams", "item_name", "unit",
        ]

    def get_item_name(self, obj) -> str:
        item = obj.food or obj.recipe
        return str(item) if item else ""

    def get_unit(self, obj) -> str:
        return obj.food.unit if obj.food_id else "g"

    def validate(self, attrs):
        food = attrs.get("food", getattr(self.instance, "food", None))
        recipe = attrs.get("recipe", getattr(self.instance, "recipe", None))
        if not food and not recipe:
            raise serializers.ValidationError("A diary entry needs a food or a recipe.")
        return attrs


class NutrientTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutrientTarget
        fields = ["id", "nutrient", "amount"]


class NutritionTargetSerializer(serializers.ModelSerializer):
    nutrient_targets = NutrientTargetSerializer(many=True, required=False)

    class Meta:
        model = NutritionTarget
        fields = [
            "id", "name", "is_active", "day_type",
            "calories", "protein_g", "carb_g", "fat_g", "fiber_g",
            "nutrient_targets",
        ]

    def create(self, validated_data):
        micros = validated_data.pop("nutrient_targets", [])
        target = NutritionTarget.objects.create(**validated_data)
        for m in micros:
            NutrientTarget.objects.create(target=target, **m)
        return target

    def update(self, instance, validated_data):
        micros = validated_data.pop("nutrient_targets", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if micros is not None:
            instance.nutrient_targets.all().delete()
            for m in micros:
                NutrientTarget.objects.create(target=instance, **m)
        return instance


class RecipeItemSerializer(serializers.ModelSerializer):
    food_name = serializers.CharField(source="food.name", read_only=True)

    class Meta:
        model = RecipeItem
        fields = ["id", "recipe", "food", "food_name", "grams"]


class RecipeSerializer(serializers.ModelSerializer):
    items = RecipeItemSerializer(many=True, read_only=True)

    class Meta:
        model = Recipe
        fields = ["id", "name", "servings", "notes", "items"]


# --- Summary (computed) ---


class SummaryNutrientSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    unit = serializers.CharField()
    category = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=3)
    target = serializers.DecimalField(
        max_digits=12, decimal_places=3, allow_null=True
    )
    percent = serializers.IntegerField(allow_null=True)


class DailySummarySerializer(serializers.Serializer):
    date = serializers.CharField()
    has_target = serializers.BooleanField()
    target_name = serializers.CharField(allow_null=True)
    totals = serializers.DictField()
    nutrients = SummaryNutrientSerializer(many=True)
