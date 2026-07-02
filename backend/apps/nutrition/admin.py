from django.contrib import admin

from .models import (
    DiaryEntry,
    Food,
    FoodNutrient,
    Meal,
    MealTemplate,
    MealTemplateItem,
    Nutrient,
    NutrientTarget,
    NutritionTarget,
    Recipe,
    RecipeItem,
    ServingSize,
    WaterLog,
)


@admin.register(Nutrient)
class NutrientAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "unit", "rda", "display_order"]
    list_filter = ["category"]
    search_fields = ["name"]


class FoodNutrientInline(admin.TabularInline):
    model = FoodNutrient
    extra = 0


class ServingSizeInline(admin.TabularInline):
    model = ServingSize
    extra = 0


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "source", "owner", "is_verified"]
    list_filter = ["source", "is_verified"]
    search_fields = ["name", "brand", "barcode"]
    inlines = [ServingSizeInline, FoodNutrientInline]


class NutrientTargetInline(admin.TabularInline):
    model = NutrientTarget
    extra = 0


@admin.register(NutritionTarget)
class NutritionTargetAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "is_active", "calories", "protein_g"]
    inlines = [NutrientTargetInline]


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 0


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "servings"]
    inlines = [RecipeItemInline]


@admin.register(DiaryEntry)
class DiaryEntryAdmin(admin.ModelAdmin):
    list_display = ["date", "meal", "owner", "food", "recipe", "quantity", "grams"]
    list_filter = ["date"]
    search_fields = ["owner__email"]


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "owner", "order"]
    list_filter = ["date"]
    search_fields = ["owner__email", "name"]


class MealTemplateItemInline(admin.TabularInline):
    model = MealTemplateItem
    extra = 0


@admin.register(MealTemplate)
class MealTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "owner"]
    search_fields = ["owner__email", "name"]
    inlines = [MealTemplateItemInline]


@admin.register(WaterLog)
class WaterLogAdmin(admin.ModelAdmin):
    list_display = ["date", "owner", "amount_ml", "source"]
    list_filter = ["date", "source"]
    search_fields = ["owner__email"]
