"""Shared DRF base classes."""
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response


class OwnerScopedViewSet(viewsets.ModelViewSet):
    """Base for resources reachable from the user via `owner_path`.

    Subclasses set `owner_path` (ORM lookup from the model to the owning user)
    and may set `parent_checks` = list of (serializer_field, model, owner_path)
    to validate on write that a referenced *strictly-owned* parent belongs to the
    requesting user.

    NOTE: when spanning a relation in `owner_path`/parent-check paths, use the
    relation name (e.g. "program__owner"), NOT the `_id` attname — Django's
    `values_list` returns None for `..._id` across a join.
    """

    owner_path = "owner"
    parent_checks: list = []

    def get_queryset(self):
        return self.queryset.filter(**{self.owner_path: self.request.user})

    def _validate_parents(self, serializer):
        for field, model, path in self.parent_checks:
            obj = serializer.validated_data.get(field)
            if obj is None:
                continue
            owner_id = model.objects.filter(pk=obj.pk).values_list(path, flat=True).first()
            if owner_id != self.request.user.id:
                raise PermissionDenied(f"That {field} does not belong to you.")

    def perform_create(self, serializer):
        self._validate_parents(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_parents(serializer)
        serializer.save()


class ReorderMixin:
    """Adds `POST /<resource>/reorder/` taking `[{"id": .., "order": ..}, ...]`.

    Only objects already in the caller's owner-scoped `get_queryset()` are
    touched (ids outside it are silently ignored), so reorder inherits the same
    isolation as every other action. `order` is written atomically.
    """

    @action(detail=False, methods=["post"])
    def reorder(self, request, *args, **kwargs):
        raw = request.data if isinstance(request.data, list) else request.data.get("items", [])
        wanted: dict[int, int] = {}
        try:
            for it in raw:
                wanted[int(it["id"])] = int(it["order"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"detail": "Body must be a list of {id, order} objects."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        objs = list(self.get_queryset().filter(id__in=wanted.keys()))
        for obj in objs:
            obj.order = wanted[obj.id]
        with transaction.atomic():
            self.get_queryset().model.objects.bulk_update(objs, ["order"])
        return Response({"updated": len(objs)})
