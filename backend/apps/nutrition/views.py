from datetime import date as date_cls

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.viewsets import OwnerScopedViewSet, ReorderMixin

from .models import (
    DiaryEntry,
    Food,
    Meal,
    MealTemplate,
    MealTemplateItem,
    Nutrient,
    NutrientTarget,
    NutritionTarget,
    Recipe,
    RecipeItem,
)
from .serializers import (
    BarcodeDraftSerializer,
    BarcodeImportSerializer,
    DailySummarySerializer,
    DiaryEntrySerializer,
    FoodSerializer,
    MealSerializer,
    MealTemplateSerializer,
    NutrientSerializer,
    NutrientTargetSerializer,
    NutritionTargetSerializer,
    RecipeItemSerializer,
    RecipeSerializer,
)
from .services import (
    NoNutrimentsError,
    ProductNotFound,
    UpstreamUnavailable,
    daily_summary,
    import_food_from_barcode,
    lookup_barcode_draft,
)


def _assert_food_visible(user, food):
    """A food may be logged if it is global or owned by the user."""
    if food is None:
        return
    if food.owner_id not in (None, user.id):
        raise PermissionDenied("That food does not belong to you.")


@extend_schema(tags=["nutrition"])
class NutrientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Nutrient.objects.all()
    serializer_class = NutrientSerializer
    pagination_class = None


@extend_schema(tags=["nutrition"])
class FoodViewSet(viewsets.ModelViewSet):
    """Global (seeded/imported) + the user's custom foods. Users edit only their own."""

    serializer_class = FoodSerializer

    def get_queryset(self):
        qs = Food.objects.filter(Q(owner=self.request.user) | Q(owner__isnull=True))
        qs = qs.prefetch_related("servings", "food_nutrients__nutrient")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(brand__icontains=q))
        barcode = self.request.query_params.get("barcode")
        if barcode:
            qs = qs.filter(barcode=barcode)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, source="custom")

    def _ensure_owned(self, instance):
        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("You can only modify your own foods.")

    def perform_update(self, serializer):
        self._ensure_owned(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_owned(instance)
        instance.delete()

    @extend_schema(
        request=BarcodeImportSerializer,
        responses={200: FoodSerializer, 201: FoodSerializer},
    )
    @action(detail=False, methods=["post"], url_path="import_barcode")
    def import_barcode(self, request):
        """Resolve a UPC/EAN to a Food.

        Returns an existing global/owned Food for the barcode (200), or imports
        the product from Open Food Facts and returns the new global Food (201).
        """
        serializer = BarcodeImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        barcode = serializer.validated_data["barcode"]
        try:
            food, created = import_food_from_barcode(request.user, barcode)
        except ProductNotFound:
            return Response(
                {"detail": f"No product found for barcode {barcode}."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NoNutrimentsError:
            return Response(
                {"detail": "That product has no nutrition data we can import."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except UpstreamUnavailable:
            return Response(
                {"detail": "Couldn't reach Open Food Facts. Try again shortly."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        data = self.get_serializer(food).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(request=BarcodeImportSerializer, responses=BarcodeDraftSerializer)
    @action(detail=False, methods=["post"], url_path="lookup_barcode")
    def lookup_barcode(self, request):
        """Look up a barcode WITHOUT saving — a draft to prefill the New Food form.

        Resolves to an existing global/owned Food, else fetches + parses the Open
        Food Facts product. Returns ``{name, brand, unit, barcode, nutrients}``
        (nutrients keyed by our canonical slug) so the user can confirm/adjust the
        values before the food is actually created.
        """
        serializer = BarcodeImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        barcode = serializer.validated_data["barcode"]
        try:
            draft = lookup_barcode_draft(request.user, barcode)
        except ProductNotFound:
            return Response(
                {"detail": f"No product found for barcode {barcode}."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NoNutrimentsError:
            return Response(
                {"detail": "That product has no nutrition data we can import."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except UpstreamUnavailable:
            return Response(
                {"detail": "Couldn't reach Open Food Facts. Try again shortly."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(draft, status=status.HTTP_200_OK)


@extend_schema(tags=["nutrition"])
class DiaryEntryViewSet(viewsets.ModelViewSet):
    serializer_class = DiaryEntrySerializer

    def get_queryset(self):
        qs = DiaryEntry.objects.filter(owner=self.request.user).select_related(
            "food", "recipe", "serving"
        )
        d = self.request.query_params.get("date")
        if d:
            qs = qs.filter(date=d)
        return qs

    def _validate_refs(self, serializer):
        _assert_food_visible(self.request.user, serializer.validated_data.get("food"))
        recipe = serializer.validated_data.get("recipe")
        if recipe is not None and recipe.owner_id != self.request.user.id:
            raise PermissionDenied("That recipe does not belong to you.")
        meal = serializer.validated_data.get("meal")
        if meal is not None and meal.owner_id != self.request.user.id:
            raise PermissionDenied("That meal does not belong to you.")

    def perform_create(self, serializer):
        self._validate_refs(serializer)
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        self._validate_refs(serializer)
        serializer.save()


@extend_schema(tags=["nutrition"])
class MealViewSet(ReorderMixin, OwnerScopedViewSet):
    """Per-day meals (create/rename/reorder/delete); diary entries attach to one."""

    queryset = Meal.objects.all()
    serializer_class = MealSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        d = self.request.query_params.get("date")
        if d:
            qs = qs.filter(date=d)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=["post"])
    def copy_yesterday(self, request):
        """Clone the most recent prior day's meal names onto a target date."""
        target = request.data.get("date")
        if not target:
            return Response(
                {"detail": "A target date is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        prev = (
            Meal.objects.filter(owner=request.user, date__lt=target)
            .order_by("-date")
            .values_list("date", flat=True)
            .first()
        )
        created = []
        if prev is not None:
            for m in Meal.objects.filter(owner=request.user, date=prev).order_by("order", "id"):
                created.append(
                    Meal.objects.create(
                        owner=request.user, date=target, name=m.name, order=m.order
                    )
                )
        return Response(MealSerializer(created, many=True).data)


@extend_schema(tags=["nutrition"])
class NutritionTargetViewSet(viewsets.ModelViewSet):
    serializer_class = NutritionTargetSerializer

    def get_queryset(self):
        return NutritionTarget.objects.filter(owner=self.request.user).prefetch_related(
            "nutrient_targets"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        target = self.get_object()
        NutritionTarget.objects.filter(owner=request.user).update(is_active=False)
        target.is_active = True
        target.save(update_fields=["is_active"])
        return Response(self.get_serializer(target).data)


@extend_schema(tags=["nutrition"])
class NutrientTargetViewSet(OwnerScopedViewSet):
    queryset = NutrientTarget.objects.all()
    serializer_class = NutrientTargetSerializer
    owner_path = "target__owner"
    parent_checks = [("target", NutritionTarget, "owner")]


@extend_schema(tags=["nutrition"])
class RecipeViewSet(viewsets.ModelViewSet):
    serializer_class = RecipeSerializer

    def get_queryset(self):
        return Recipe.objects.filter(owner=self.request.user).prefetch_related("items__food")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(tags=["nutrition"])
class RecipeItemViewSet(OwnerScopedViewSet):
    queryset = RecipeItem.objects.all()
    serializer_class = RecipeItemSerializer
    owner_path = "recipe__owner"
    parent_checks = [("recipe", Recipe, "owner")]

    def _validate_refs(self, serializer):
        _assert_food_visible(self.request.user, serializer.validated_data.get("food"))

    def perform_create(self, serializer):
        self._validate_parents(serializer)
        self._validate_refs(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_parents(serializer)
        self._validate_refs(serializer)
        serializer.save()


@extend_schema(
    tags=["nutrition"],
    parameters=[OpenApiParameter("date", str, description="ISO date (default today)")],
    responses=DailySummarySerializer,
)
class NutritionSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        d = request.query_params.get("date")
        if d:
            try:
                day = date_cls.fromisoformat(d)
            except ValueError as exc:
                raise ValidationError({"date": "must be ISO format YYYY-MM-DD"}) from exc
        else:
            day = date_cls.today()
        return Response(daily_summary(request.user, day))


@extend_schema(tags=["nutrition"])
class MealTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = MealTemplateSerializer

    def get_queryset(self):
        return MealTemplate.objects.filter(owner=self.request.user).prefetch_related(
            "items__food"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def _meal(self, request):
        return Meal.objects.filter(owner=request.user, id=request.data.get("meal")).first()

    @extend_schema(responses=MealTemplateSerializer)
    @action(detail=False, methods=["post"], url_path="from_meal")
    def from_meal(self, request):
        """Create a template from an existing meal's food entries."""
        meal = self._meal(request)
        if meal is None:
            return Response({"detail": "Meal not found."}, status=status.HTTP_404_NOT_FOUND)
        name = (request.data.get("name") or meal.name or "Meal template").strip()
        template = MealTemplate.objects.create(owner=request.user, name=name)
        for order, e in enumerate(
            meal.entries.filter(food__isnull=False).select_related("food", "serving")
        ):
            MealTemplateItem.objects.create(
                template=template, food=e.food, serving=e.serving,
                quantity=e.quantity, order=order,
            )
        return Response(self.get_serializer(template).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        """Create diary entries from this template into a target meal."""
        template = self.get_object()
        meal = self._meal(request)
        if meal is None:
            return Response({"detail": "Meal not found."}, status=status.HTTP_404_NOT_FOUND)
        created = 0
        for it in template.items.select_related("food", "serving").all():
            DiaryEntry.objects.create(
                owner=request.user, date=meal.date, meal=meal,
                food=it.food, serving=it.serving, quantity=it.quantity,
            )
            created += 1
        return Response({"created": created}, status=status.HTTP_201_CREATED)
