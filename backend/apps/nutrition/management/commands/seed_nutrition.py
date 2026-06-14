"""Seed canonical nutrients + a starter global food library (idempotent).

Run:  python manage.py seed_nutrition
Safe to re-run (keyed on stable slugs/names).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.nutrition.enums import FoodSource, NutrientCategory, NutrientUnit
from apps.nutrition.models import Food, FoodNutrient, Nutrient, ServingSize

C = NutrientCategory
U = NutrientUnit

# (slug, name, category, unit, rda, display_order, is_energy)
NUTRIENTS = [
    ("energy", "Calories", C.ENERGY, U.KCAL, None, 0, True),
    ("protein", "Protein", C.MACRO, U.G, Decimal("56"), 10, False),
    ("carbohydrate", "Carbohydrate", C.MACRO, U.G, Decimal("130"), 11, False),
    ("fat", "Fat", C.MACRO, U.G, Decimal("70"), 12, False),
    ("saturated_fat", "Saturated fat", C.MACRO, U.G, Decimal("20"), 13, False),
    ("fiber", "Fiber", C.MACRO, U.G, Decimal("38"), 14, False),
    ("sugar", "Sugar", C.MACRO, U.G, None, 15, False),
    # Vitamins
    ("vitamin_a", "Vitamin A", C.VITAMIN, U.MCG, Decimal("900"), 30, False),
    ("vitamin_c", "Vitamin C", C.VITAMIN, U.MG, Decimal("90"), 31, False),
    ("vitamin_d", "Vitamin D", C.VITAMIN, U.MCG, Decimal("20"), 32, False),
    ("vitamin_e", "Vitamin E", C.VITAMIN, U.MG, Decimal("15"), 33, False),
    ("vitamin_k", "Vitamin K", C.VITAMIN, U.MCG, Decimal("120"), 34, False),
    ("thiamin", "Thiamin (B1)", C.VITAMIN, U.MG, Decimal("1.2"), 35, False),
    ("riboflavin", "Riboflavin (B2)", C.VITAMIN, U.MG, Decimal("1.3"), 36, False),
    ("niacin", "Niacin (B3)", C.VITAMIN, U.MG, Decimal("16"), 37, False),
    ("vitamin_b6", "Vitamin B6", C.VITAMIN, U.MG, Decimal("1.3"), 38, False),
    ("folate", "Folate", C.VITAMIN, U.MCG, Decimal("400"), 39, False),
    ("vitamin_b12", "Vitamin B12", C.VITAMIN, U.MCG, Decimal("2.4"), 40, False),
    # Minerals
    ("calcium", "Calcium", C.MINERAL, U.MG, Decimal("1000"), 50, False),
    ("iron", "Iron", C.MINERAL, U.MG, Decimal("8"), 51, False),
    ("magnesium", "Magnesium", C.MINERAL, U.MG, Decimal("400"), 52, False),
    ("phosphorus", "Phosphorus", C.MINERAL, U.MG, Decimal("700"), 53, False),
    ("potassium", "Potassium", C.MINERAL, U.MG, Decimal("3400"), 54, False),
    ("sodium", "Sodium", C.MINERAL, U.MG, Decimal("2300"), 55, False),
    ("zinc", "Zinc", C.MINERAL, U.MG, Decimal("11"), 56, False),
    ("selenium", "Selenium", C.MINERAL, U.MCG, Decimal("55"), 57, False),
]

# name, brand, [(serving_label, grams, is_default)], {nutrient_slug: per_100g}
FOODS = [
    ("Chicken breast, cooked", "", [("100 g", 100, True), ("1 breast (172 g)", 172, False)],
     {"energy": 165, "protein": 31, "carbohydrate": 0, "fat": 3.6, "saturated_fat": 1.0,
      "potassium": 256, "sodium": 74, "phosphorus": 196, "niacin": 13.7}),
    ("White rice, cooked", "", [("100 g", 100, True), ("1 cup (158 g)", 158, False)],
     {"energy": 130, "protein": 2.7, "carbohydrate": 28, "fat": 0.3, "fiber": 0.4,
      "sodium": 1, "magnesium": 12}),
    ("Whole egg", "", [("1 large (50 g)", 50, True), ("100 g", 100, False)],
     {"energy": 143, "protein": 12.6, "carbohydrate": 0.7, "fat": 9.5, "saturated_fat": 3.1,
      "vitamin_a": 160, "vitamin_d": 2.0, "vitamin_b12": 1.1, "calcium": 56, "iron": 1.8}),
    ("Rolled oats, dry", "", [("100 g", 100, True), ("1/2 cup (40 g)", 40, False)],
     {"energy": 379, "protein": 13, "carbohydrate": 67, "fat": 6.5, "fiber": 10, "sugar": 1,
      "iron": 4.7, "magnesium": 138, "zinc": 4, "thiamin": 0.5}),
    ("Banana", "", [("1 medium (118 g)", 118, True), ("100 g", 100, False)],
     {"energy": 89, "protein": 1.1, "carbohydrate": 23, "fat": 0.3, "fiber": 2.6, "sugar": 12,
      "vitamin_c": 8.7, "vitamin_b6": 0.4, "potassium": 358, "magnesium": 27}),
    ("Whey protein powder", "", [("1 scoop (30 g)", 30, True), ("100 g", 100, False)],
     {"energy": 400, "protein": 80, "carbohydrate": 8, "fat": 7, "saturated_fat": 3,
      "calcium": 500, "sodium": 300}),
    ("Broccoli, cooked", "", [("100 g", 100, True), ("1 cup (156 g)", 156, False)],
     {"energy": 35, "protein": 2.4, "carbohydrate": 7, "fat": 0.4, "fiber": 3.3,
      "vitamin_c": 65, "vitamin_k": 141, "folate": 108, "potassium": 293, "calcium": 40}),
    ("Almonds", "", [("100 g", 100, False), ("1 oz (28 g)", 28, True)],
     {"energy": 579, "protein": 21, "carbohydrate": 22, "fat": 50, "saturated_fat": 3.8,
      "fiber": 12.5, "vitamin_e": 25.6, "magnesium": 270, "calcium": 269, "iron": 3.7}),
    ("Greek yogurt, nonfat", "", [("100 g", 100, True), ("1 container (170 g)", 170, False)],
     {"energy": 59, "protein": 10, "carbohydrate": 3.6, "fat": 0.4, "sugar": 3.2,
      "calcium": 110, "potassium": 141, "vitamin_b12": 0.8}),
    ("Sweet potato, baked", "", [("100 g", 100, True), ("1 medium (151 g)", 151, False)],
     {"energy": 90, "protein": 2, "carbohydrate": 21, "fat": 0.1, "fiber": 3.3, "sugar": 6.5,
      "vitamin_a": 961, "vitamin_c": 19.6, "potassium": 475, "magnesium": 27}),
    ("Olive oil", "", [("1 tbsp (14 g)", 14, True), ("100 g", 100, False)],
     {"energy": 884, "protein": 0, "carbohydrate": 0, "fat": 100, "saturated_fat": 13.8,
      "vitamin_e": 14.4, "vitamin_k": 60}),
    ("Salmon, cooked", "", [("100 g", 100, True), ("1 fillet (170 g)", 170, False)],
     {"energy": 206, "protein": 22, "carbohydrate": 0, "fat": 13, "saturated_fat": 3.1,
      "vitamin_d": 11, "vitamin_b12": 2.8, "potassium": 384, "selenium": 41}),
]


class Command(BaseCommand):
    help = "Seed canonical nutrients and a starter global food library (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        by_slug: dict[str, Nutrient] = {}
        for slug, name, cat, unit, rda, order, is_energy in NUTRIENTS:
            nutrient, _ = Nutrient.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name, "category": cat, "unit": unit,
                    "rda": rda, "display_order": order, "is_energy": is_energy,
                },
            )
            by_slug[slug] = nutrient

        created = 0
        for name, brand, servings, profile in FOODS:
            food, was_created = Food.objects.get_or_create(
                owner=None, name=name, brand=brand,
                defaults={"source": FoodSource.SEED, "is_verified": True},
            )
            if was_created:
                created += 1
            food.servings.all().delete()
            for label, grams, is_default in servings:
                ServingSize.objects.create(
                    food=food, label=label, grams=Decimal(str(grams)), is_default=is_default
                )
            for slug, amount in profile.items():
                FoodNutrient.objects.update_or_create(
                    food=food, nutrient=by_slug[slug],
                    defaults={"amount_per_100g": Decimal(str(amount))},
                )

        # Reference data changed → drop the cached nutrient list (see services).
        from django.core.cache import cache

        from apps.nutrition.services import NUTRIENTS_CACHE_KEY

        cache.delete(NUTRIENTS_CACHE_KEY)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(by_slug)} nutrients and {len(FOODS)} foods ({created} new)."
            )
        )
