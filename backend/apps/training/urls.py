from rest_framework.routers import DefaultRouter

from .views import (
    ExerciseSlotViewSet,
    ExerciseViewSet,
    LoggedExerciseViewSet,
    LoggedSetViewSet,
    MuscleViewSet,
    MuscleVolumeView,
    PlannedSetViewSet,
    ProgramViewSet,
    TrainingDayViewSet,
    WorkoutSessionViewSet,
)

router = DefaultRouter()
router.register("muscles", MuscleViewSet, basename="muscle")
router.register("exercises", ExerciseViewSet, basename="exercise")
router.register("programs", ProgramViewSet, basename="program")
router.register("training-days", TrainingDayViewSet, basename="trainingday")
router.register("exercise-slots", ExerciseSlotViewSet, basename="exerciseslot")
router.register("planned-sets", PlannedSetViewSet, basename="plannedset")
router.register("workout-sessions", WorkoutSessionViewSet, basename="workoutsession")
router.register("logged-exercises", LoggedExerciseViewSet, basename="loggedexercise")
router.register("logged-sets", LoggedSetViewSet, basename="loggedset")
router.register("volume", MuscleVolumeView, basename="volume")

urlpatterns = router.urls
