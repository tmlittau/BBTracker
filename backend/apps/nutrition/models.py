"""Nutrition domain models.

`Nutrient` is the canonical, shared vocabulary (calories, macros, vitamins,
minerals). Foods carry a per-100 g profile of `FoodNutrient` rows against it, so
the same nutrient totals can later be fed by supplements too (Phase 3). Diary
entries reference a Food (or Recipe) + a quantity; the resolved `grams` is the
source of truth for nutrient math.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from .enums import DayType, FoodSource, NutrientCategory, NutrientUnit


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Nutrient(models.Model):
    """A trackable nutrient. Seeded once; shared by foods (and later supplements)."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    category = models.CharField(max_length=12, choices=NutrientCategory.choices)
    unit = models.CharField(max_length=8, choices=NutrientUnit.choices)
    rda = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Reference daily amount in `unit`, used as a default micro target.",
    )
    display_order = models.PositiveIntegerField(default=100)
    is_energy = models.BooleanField(default=False, help_text="True only for calories.")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Food(TimeStampedModel):
    """A food item. Global (owner=None, seeded/imported) or user-custom."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="foods",
        help_text="Null = global food available to everyone.",
    )
    name = models.CharField(max_length=160)
    brand = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=8, choices=FoodSource.choices, default=FoodSource.CUSTOM)
    source_id = models.CharField(max_length=64, blank=True)
    barcode = models.CharField(max_length=32, blank=True, db_index=True)
    # Base measure for the per-100 nutrient profile + diary quantities: grams for
    # solids, millilitres for liquids (SI only).
    unit = models.CharField(max_length=4, choices=[("g", "g"), ("ml", "ml")], default="g")
    is_verified = models.BooleanField(default=False)
    nutrients = models.ManyToManyField(Nutrient, through="FoodNutrient", related_name="foods")

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    @property
    def is_global(self) -> bool:
        return self.owner_id is None

    def __str__(self):
        return f"{self.brand} {self.name}".strip() if self.brand else self.name


class ServingSize(models.Model):
    """A named portion for a food, e.g. '1 scoop (30 g)'."""

    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name="servings")
    label = models.CharField(max_length=80)
    grams = models.DecimalField(max_digits=8, decimal_places=2)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "grams"]

    def __str__(self):
        return f"{self.label} ({self.grams} g)"


class FoodNutrient(models.Model):
    """Amount of a nutrient per 100 g of a food (canonical basis for scaling)."""

    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name="food_nutrients")
    nutrient = models.ForeignKey(Nutrient, on_delete=models.PROTECT, related_name="food_nutrients")
    amount_per_100g = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["food", "nutrient"], name="uniq_food_nutrient")
        ]

    def __str__(self):
        return f"{self.food.name} · {self.nutrient.name}={self.amount_per_100g}/100g"


class Recipe(TimeStampedModel):
    """A user recipe: a set of food amounts producing N servings."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipes"
    )
    name = models.CharField(max_length=160)
    servings = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1"))
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RecipeItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.PROTECT, related_name="recipe_items")
    grams = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.recipe.name} · {self.food.name} ({self.grams} g)"


class NutritionTarget(TimeStampedModel):
    """A daily intake goal. The owner's active target drives the dashboard rings."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nutrition_targets"
    )
    name = models.CharField(max_length=120, default="Daily target")
    is_active = models.BooleanField(default=False)
    day_type = models.CharField(max_length=10, choices=DayType.choices, default=DayType.ANY)
    calories = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    protein_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    carb_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fat_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fiber_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    micro_targets = models.ManyToManyField(
        Nutrient, through="NutrientTarget", related_name="targets"
    )

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self):
        return self.name


class NutrientTarget(models.Model):
    """Optional per-micronutrient goal within a NutritionTarget — a `min_amount`
    (floor / daily goal; falls back to the nutrient's RDA when unset) and/or a
    `max_amount` (ceiling, to flag over-intake of nutrients that can be toxic). At
    least one bound is set; serious lifters / PED users often need values above the RDA.
    """

    target = models.ForeignKey(
        NutritionTarget, on_delete=models.CASCADE, related_name="nutrient_targets"
    )
    nutrient = models.ForeignKey(Nutrient, on_delete=models.PROTECT)
    min_amount = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["target", "nutrient"], name="uniq_target_nutrient"),
            models.CheckConstraint(
                condition=(
                    models.Q(min_amount__isnull=True)
                    | models.Q(max_amount__isnull=True)
                    | models.Q(max_amount__gte=models.F("min_amount"))
                ),
                name="nutrient_target_max_gte_min",
            ),
        ]


class Meal(TimeStampedModel):
    """A user-defined meal on a given day (e.g. 'Breakfast').

    Meals are created on the fly per day — their number and names vary day to
    day — and diary entries attach to one. `order` drives display sequence.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meals"
    )
    date = models.DateField()
    name = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["date", "order", "id"]
        indexes = [models.Index(fields=["owner", "date"])]

    def __str__(self):
        return f"{self.date} · {self.name}"


class DiaryEntry(TimeStampedModel):
    """A logged food (or recipe) in a meal. `grams` is resolved on save."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="diary_entries"
    )
    date = models.DateField()
    meal = models.ForeignKey(
        "Meal", on_delete=models.SET_NULL, null=True, blank=True, related_name="entries"
    )
    food = models.ForeignKey(
        Food, on_delete=models.PROTECT, null=True, blank=True, related_name="diary_entries"
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.PROTECT, null=True, blank=True, related_name="diary_entries"
    )
    serving = models.ForeignKey(
        ServingSize, on_delete=models.SET_NULL, null=True, blank=True, related_name="diary_entries"
    )
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1"))
    # Resolved canonical grams for a food entry (null for recipe entries, which
    # scale by `quantity` servings instead). Filled by services.resolve_entry_grams.
    grams = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["date", "id"]
        indexes = [models.Index(fields=["owner", "date"])]

    def save(self, *args, **kwargs):
        # Resolve canonical grams for food entries (recipes scale by `quantity`).
        from .services import resolve_entry_grams

        self.grams = resolve_entry_grams(self) if self.food_id is not None else None
        super().save(*args, **kwargs)

    def __str__(self):
        item = self.food or self.recipe
        return f"{self.date} · {item}"


class MealTemplate(TimeStampedModel):
    """A reusable named set of foods + amounts. Applying it to a meal creates the
    diary entries in one tap (bodybuilding meals repeat a lot)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meal_templates"
    )
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MealTemplateItem(models.Model):
    """One food + amount within a meal template (mirrors a DiaryEntry food log)."""

    template = models.ForeignKey(
        MealTemplate, on_delete=models.CASCADE, related_name="items"
    )
    food = models.ForeignKey(
        Food, on_delete=models.PROTECT, related_name="meal_template_items"
    )
    serving = models.ForeignKey(
        ServingSize, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="meal_template_items",
    )
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1"))
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.template.name}: {self.food}"
