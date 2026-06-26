from django.db.models import Count, ProtectedError
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.core.viewsets import OwnerScopedViewSet, ReorderMixin

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
from .serializers import (
    ExerciseHistoryPointSerializer,
    ExercisePerformanceSerializer,
    ExerciseSerializer,
    ExerciseSlotSerializer,
    LoggedExerciseSerializer,
    LoggedSetSerializer,
    MuscleSerializer,
    MuscleVolumeSerializer,
    PlannedSetSerializer,
    ProgramSerializer,
    TrainingDaySerializer,
    WorkoutSessionListSerializer,
    WorkoutSessionSerializer,
)
from .services import average_weekly_muscle_volume, exercise_history, last_performance


@extend_schema(tags=["training"])
class MuscleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Muscle.objects.all()
    serializer_class = MuscleSerializer
    pagination_class = None


@extend_schema(tags=["training"])
class ExerciseViewSet(viewsets.ModelViewSet):
    """Global (seeded) + the user's custom exercises. Users can only edit their own."""

    serializer_class = ExerciseSerializer
    # Bounded reference data — return the whole list so the exercise picker
    # (program builder + live logger) can filter/search it client-side without
    # the 50-row page cap cropping entries. Server ?q= / ?category= still work.
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Q

        qs = Exercise.objects.filter(
            Q(owner=self.request.user) | Q(owner__isnull=True)
        ).prefetch_related("primary_muscles", "secondary_muscles")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        # Single-user app: seeded exercises are deletable too, but block (clearly)
        # when the exercise is still referenced by a program slot or logged set.
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                "Can't delete — this exercise is still used in a program or logged "
                "workout. Remove those first."
            ) from None

    @extend_schema(
        parameters=[OpenApiParameter("from", str, description="ISO date lower bound")],
        responses=ExerciseHistoryPointSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        exercise = self.get_object()
        data = exercise_history(request.user, exercise)
        return Response(ExerciseHistoryPointSerializer(data, many=True).data)

    @extend_schema(responses=ExercisePerformanceSerializer)
    @action(detail=True, methods=["get"], url_path="last_performance")
    def performance(self, request, pk=None):
        """Best-ever set + last finished session's sets — for the live logger's
        at-a-glance stats and next-workout pre-fill."""
        exercise = self.get_object()
        return Response(last_performance(request.user, exercise))


@extend_schema(tags=["training"])
class ProgramViewSet(viewsets.ModelViewSet):
    serializer_class = ProgramSerializer

    def get_queryset(self):
        return (
            Program.objects.filter(owner=self.request.user)
            .prefetch_related("days__slots__planned_sets", "days__slots__exercise")
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Make this the active program (deactivates the user's others)."""
        program = self.get_object()
        Program.objects.filter(owner=request.user).update(is_active=False)
        program.is_active = True
        program.save(update_fields=["is_active"])
        return Response(self.get_serializer(program).data)


@extend_schema(tags=["training"])
class TrainingDayViewSet(OwnerScopedViewSet):
    queryset = TrainingDay.objects.all()
    serializer_class = TrainingDaySerializer
    owner_path = "program__owner"
    parent_checks = [("program", Program, "owner")]


@extend_schema(tags=["training"])
class ExerciseSlotViewSet(ReorderMixin, OwnerScopedViewSet):
    queryset = ExerciseSlot.objects.all()
    serializer_class = ExerciseSlotSerializer
    owner_path = "day__program__owner"
    parent_checks = [("day", TrainingDay, "program__owner")]


@extend_schema(tags=["training"])
class PlannedSetViewSet(ReorderMixin, OwnerScopedViewSet):
    queryset = PlannedSet.objects.all()
    serializer_class = PlannedSetSerializer
    owner_path = "slot__day__program__owner"
    parent_checks = [("slot", ExerciseSlot, "day__program__owner")]


@extend_schema(tags=["training"])
class WorkoutSessionViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        qs = WorkoutSession.objects.filter(owner=self.request.user)
        if self.action == "list":
            frm = self.request.query_params.get("from")
            if frm:
                qs = qs.filter(started_at__date__gte=frm)
            to = self.request.query_params.get("to")
            if to:
                qs = qs.filter(started_at__date__lte=to)
            return qs.annotate(exercise_count=Count("logged_exercises")).order_by("-started_at")
        return qs.prefetch_related("logged_exercises__sets", "logged_exercises__exercise")

    def get_serializer_class(self):
        if self.action == "list":
            return WorkoutSessionListSerializer
        return WorkoutSessionSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        session = self.get_object()
        # On an early finish the client can drop not-yet-completed (pending) sets
        # so history reflects only what was actually done; emptied exercises go too.
        if request.data.get("drop_incomplete"):
            LoggedSet.objects.filter(
                logged_exercise__session=session, is_completed=False
            ).delete()
            LoggedExercise.objects.filter(session=session, sets__isnull=True).delete()
        if session.ended_at is None:
            session.ended_at = timezone.now()
            session.save(update_fields=["ended_at"])
        session = self.get_queryset().get(id=session.id)
        return Response(self.get_serializer(session).data)

    @action(detail=False, methods=["post"])
    def start_from_day(self, request):
        """Create a session pre-loaded from a program day's slots + planned sets.

        Each planned set becomes a *pending* (is_completed=False) logged set
        carrying its set type + rest, so the logger shows the prescription and the
        user just fills reps/weight — which flips it complete and starts the
        countdown. SET_NULL `day` keeps history intact if the program changes.
        """
        from .enums import DEFAULT_REST_BY_SET_TYPE

        day = (
            TrainingDay.objects.filter(
                id=request.data.get("day"), program__owner=request.user
            )
            .prefetch_related("slots__planned_sets")
            .first()
        )
        if day is None:
            raise PermissionDenied("That training day does not belong to you.")
        session = WorkoutSession.objects.create(
            owner=request.user, day=day, name=day.name, started_at=timezone.now()
        )
        for slot in day.slots.all():
            le = LoggedExercise.objects.create(
                session=session,
                exercise_id=slot.exercise_id,
                order=slot.order,
                superset_group=slot.superset_group,
            )
            for ps in slot.planned_sets.all():
                rest = ps.rest_seconds
                if rest is None:
                    rest = DEFAULT_REST_BY_SET_TYPE.get(ps.set_type)
                LoggedSet.objects.create(
                    logged_exercise=le,
                    order=ps.order,
                    set_type=ps.set_type,
                    is_completed=False,
                    rest_seconds=rest,
                )
        session = self.get_queryset().get(id=session.id)
        return Response(self.get_serializer(session).data, status=201)


@extend_schema(tags=["training"])
class LoggedExerciseViewSet(ReorderMixin, OwnerScopedViewSet):
    queryset = LoggedExercise.objects.all()
    serializer_class = LoggedExerciseSerializer
    owner_path = "session__owner"
    parent_checks = [("session", WorkoutSession, "owner")]


@extend_schema(tags=["training"])
class LoggedSetViewSet(OwnerScopedViewSet):
    queryset = LoggedSet.objects.all()
    serializer_class = LoggedSetSerializer
    owner_path = "logged_exercise__session__owner"
    parent_checks = [("logged_exercise", LoggedExercise, "session__owner")]


@extend_schema(
    tags=["training"],
    parameters=[OpenApiParameter("days", int, description="Look-back window (default 7)")],
    responses=MuscleVolumeSerializer(many=True),
)
class MuscleVolumeView(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        try:
            days = int(request.query_params.get("days", 7))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"days": "must be an integer"}) from exc
        data = average_weekly_muscle_volume(request.user, window_days=days)
        rows = [
            {"muscle": name, "sets": v["sets"], "tonnage": v["tonnage"]}
            for name, v in sorted(data.items(), key=lambda kv: -kv[1]["sets"])
        ]
        return Response(MuscleVolumeSerializer(rows, many=True).data)
