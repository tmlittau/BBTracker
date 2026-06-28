"""Account-level operations that the API/admin share."""
from django.db import transaction


def hard_delete_user(user):
    """Delete a user and ALL their data — including the custom library items
    (compounds / supplements / foods / exercises) that their own dose logs, protocol
    items, diary entries and workouts ``PROTECT``-reference.

    A plain ``user.delete()`` raises ``ProtectedError`` here: the user owns, say, a
    custom compound (``owner`` CASCADE) *and* dose logs that protect it, so the cascade
    can't drop the compound. We delete those protecting rows first, then the user — at
    which point the now-unreferenced library items cascade away cleanly.

    NOTE: if a new ``on_delete=PROTECT`` relation onto an owner-owned model is added,
    add its protecting rows to the teardown below.
    """
    from apps.nutrition.models import DiaryEntry, Meal, MealTemplate, Recipe
    from apps.protocols.models import DoseLog, Protocol
    from apps.training.models import Program, WorkoutSession

    with transaction.atomic():
        DoseLog.objects.filter(owner=user).delete()          # → Compound / Supplement
        Protocol.objects.filter(owner=user).delete()         # ProtocolItem → Compound / Supplement
        WorkoutSession.objects.filter(owner=user).delete()   # LoggedExercise → Exercise
        Program.objects.filter(owner=user).delete()          # ExerciseSlot → Exercise
        DiaryEntry.objects.filter(owner=user).delete()       # → Food / Recipe
        Recipe.objects.filter(owner=user).delete()           # RecipeItem → Food
        MealTemplate.objects.filter(owner=user).delete()     # MealTemplateItem → Food
        Meal.objects.filter(owner=user).delete()
        # Everything else (library items, targets, phases, photos, bloodwork,
        # measurements, reminders, profile, …) cascades from the user.
        user.delete()
