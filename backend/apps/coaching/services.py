"""Template application: a coach owns programs / protocols / meal plans as their own
(built with no acting header), then deep-copies one onto a client. Reference FKs
(exercise / food / compound / supplement / serving) are preserved as-is."""
from rest_framework.exceptions import ValidationError


def clone_program(src, owner):
    from apps.training.models import ExerciseSlot, PlannedSet, Program, TrainingDay

    new = Program.objects.create(
        owner=owner, name=src.name, description=src.description, is_active=False
    )
    for day in src.days.all():
        nd = TrainingDay.objects.create(
            program=new, name=day.name, order=day.order, notes=day.notes
        )
        for slot in day.slots.all():
            ns = ExerciseSlot.objects.create(
                day=nd, exercise_id=slot.exercise_id, order=slot.order,
                notes=slot.notes, superset_group=slot.superset_group,
            )
            for ps in slot.planned_sets.all():
                PlannedSet.objects.create(
                    slot=ns, set_type=ps.set_type,
                    target_reps_low=ps.target_reps_low, target_reps_high=ps.target_reps_high,
                    target_weight=ps.target_weight, rest_seconds=ps.rest_seconds, order=ps.order,
                )
    return new


def clone_protocol(src, owner):
    from apps.protocols.models import Protocol, ProtocolItem

    new = Protocol.objects.create(owner=owner, name=src.name, is_active=False, notes=src.notes)
    for it in src.items.all():
        ProtocolItem.objects.create(
            protocol=new, compound_id=it.compound_id, supplement_id=it.supplement_id,
            dose_amount=it.dose_amount, dose_unit=it.dose_unit, route=it.route,
            frequency=it.frequency, days_of_week=it.days_of_week, times_of_day=it.times_of_day,
            target_benefit=it.target_benefit, notes=it.notes, order=it.order,
        )
    return new


def clone_meal_plan(src, owner):
    from apps.nutrition.models import MealPlan, MealPlanItem, MealPlanMeal

    new = MealPlan.objects.create(owner=owner, name=src.name, notes=src.notes)
    for meal in src.meals.all():
        nm = MealPlanMeal.objects.create(plan=new, name=meal.name, order=meal.order)
        for it in meal.items.all():
            MealPlanItem.objects.create(
                meal=nm, food_id=it.food_id, serving_id=it.serving_id,
                quantity=it.quantity, order=it.order,
            )
    return new


TEMPLATE_KINDS = ("program", "protocol", "meal_plan")


def apply_template(coach, kind, template_id, client):
    """Deep-copy one of the coach's own templates onto `client`. Returns the new object."""
    from django.shortcuts import get_object_or_404

    from apps.nutrition.models import MealPlan
    from apps.protocols.models import Protocol
    from apps.training.models import Program

    registry = {
        "program": (Program, clone_program),
        "protocol": (Protocol, clone_protocol),
        "meal_plan": (MealPlan, clone_meal_plan),
    }
    if kind not in registry:
        raise ValidationError({"kind": f"Unknown template kind {kind!r}."})
    model, cloner = registry[kind]
    src = get_object_or_404(model, pk=template_id, owner=coach)
    return cloner(src, client)
