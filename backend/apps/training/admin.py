from django.contrib import admin

from .models import (
    Exercise,
    ExerciseSlot,
    LoggedExercise,
    LoggedSet,
    Muscle,
    PlannedSet,
    Program,
    TrainingDay,
    WorkoutSession,
)


@admin.register(Muscle)
class MuscleAdmin(admin.ModelAdmin):
    list_display = ["name", "group", "slug"]
    list_filter = ["group"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "load_type", "owner"]
    list_filter = ["category", "load_type"]
    search_fields = ["name"]
    filter_horizontal = ["primary_muscles", "secondary_muscles"]


class TrainingDayInline(admin.TabularInline):
    model = TrainingDay
    extra = 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "is_active"]
    inlines = [TrainingDayInline]


class LoggedSetInline(admin.TabularInline):
    model = LoggedSet
    extra = 0


@admin.register(LoggedExercise)
class LoggedExerciseAdmin(admin.ModelAdmin):
    list_display = ["session", "exercise", "order"]
    inlines = [LoggedSetInline]


admin.site.register([TrainingDay, ExerciseSlot, PlannedSet, WorkoutSession])
