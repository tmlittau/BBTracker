from django.db import models


class NutrientCategory(models.TextChoices):
    ENERGY = "energy", "Energy"
    MACRO = "macro", "Macronutrient"
    VITAMIN = "vitamin", "Vitamin"
    MINERAL = "mineral", "Mineral"
    OTHER = "other", "Other"


class NutrientUnit(models.TextChoices):
    KCAL = "kcal", "kcal"
    G = "g", "g"
    MG = "mg", "mg"
    MCG = "mcg", "µg"
    IU = "iu", "IU"


class FoodSource(models.TextChoices):
    CUSTOM = "custom", "Custom"
    SEED = "seed", "Seeded"
    OFF = "off", "Open Food Facts"
    USDA = "usda", "USDA FoodData Central"


class Meal(models.TextChoices):
    BREAKFAST = "breakfast", "Breakfast"
    LUNCH = "lunch", "Lunch"
    DINNER = "dinner", "Dinner"
    SNACK = "snack", "Snack"
    PRE_WORKOUT = "pre_workout", "Pre-workout"
    POST_WORKOUT = "post_workout", "Post-workout"


class DayType(models.TextChoices):
    ANY = "any", "Any day"
    TRAINING = "training", "Training day"
    REST = "rest", "Rest day"
