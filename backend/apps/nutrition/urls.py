from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DiaryEntryViewSet,
    FoodViewSet,
    MealTemplateViewSet,
    MealViewSet,
    NutrientTargetViewSet,
    NutrientViewSet,
    NutritionSummaryView,
    NutritionTargetViewSet,
    RecipeItemViewSet,
    RecipeViewSet,
    WaterLogViewSet,
)

router = DefaultRouter()
router.register("nutrients", NutrientViewSet, basename="nutrient")
router.register("foods", FoodViewSet, basename="food")
router.register("diary-entries", DiaryEntryViewSet, basename="diaryentry")
router.register("meals", MealViewSet, basename="meal")
router.register("meal-templates", MealTemplateViewSet, basename="mealtemplate")
router.register("targets", NutritionTargetViewSet, basename="nutritiontarget")
router.register("nutrient-targets", NutrientTargetViewSet, basename="nutrienttarget")
router.register("recipes", RecipeViewSet, basename="recipe")
router.register("recipe-items", RecipeItemViewSet, basename="recipeitem")
router.register("water", WaterLogViewSet, basename="waterlog")

urlpatterns = [
    path("summary/", NutritionSummaryView.as_view(), name="nutrition-summary"),
    *router.urls,
]
