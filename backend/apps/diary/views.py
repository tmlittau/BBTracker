import uuid

from django.conf import settings
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.coaching.access import EffectiveOwnerMixin

from .images import InvalidImageError, make_thumbnail, process_image
from .models import CheckIn, Pose, ProgressPhoto
from .serializers import (
    CheckInSerializer,
    PoseSerializer,
    ProgressPhotoSerializer,
    ProgressPhotoUploadSerializer,
)
from .services import latest_photo_for_pose
from .storage import get_storage


@extend_schema(tags=["diary"])
class PoseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Pose.objects.all()
    serializer_class = PoseSerializer
    pagination_class = None


@extend_schema(tags=["diary"])
class CheckInViewSet(EffectiveOwnerMixin, viewsets.ModelViewSet):
    serializer_class = CheckInSerializer

    def get_queryset(self):
        qs = CheckIn.objects.filter(owner=self.effective_owner)
        date = self.request.query_params.get("date")
        if date:
            qs = qs.filter(date=date)
        start, end = self.request.query_params.get("from"), self.request.query_params.get("to")
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs

    def _reject_duplicate(self, date, exclude_pk=None):
        qs = CheckIn.objects.filter(owner=self.request.user, date=date)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValidationError(
                {"date": "You already have a check-in for this date; edit that one."}
            )

    def perform_create(self, serializer):
        self._reject_duplicate(serializer.validated_data.get("date"))
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        date = serializer.validated_data.get("date", serializer.instance.date)
        self._reject_duplicate(date, exclude_pk=serializer.instance.pk)
        serializer.save()


@extend_schema(tags=["diary"])
class ProgressPhotoViewSet(EffectiveOwnerMixin, viewsets.ModelViewSet):
    serializer_class = ProgressPhotoSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = ProgressPhoto.objects.filter(owner=self.effective_owner).select_related("pose")
        pose = self.request.query_params.get("pose")
        if pose:
            qs = qs.filter(pose_id=pose)
        taken_on = self.request.query_params.get("taken_on")
        if taken_on:
            qs = qs.filter(taken_on=taken_on)
        return qs

    @extend_schema(request=ProgressPhotoUploadSerializer, responses=ProgressPhotoSerializer)
    def create(self, request, *args, **kwargs):
        upload = ProgressPhotoUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        image = upload.validated_data["image"]

        if image.size > settings.DIARY_MAX_UPLOAD_BYTES:
            raise ValidationError({"image": "File is too large."})

        raw = image.read()
        try:
            clean, width, height = process_image(raw)
            thumb = make_thumbnail(raw)
        except InvalidImageError as exc:
            raise ValidationError({"image": str(exc)}) from exc

        key = f"{request.user.id}/{uuid.uuid4().hex}.jpg"
        thumb_key = f"{request.user.id}/{uuid.uuid4().hex}_thumb.jpg"
        storage = get_storage()
        storage.put(key, clean, "image/jpeg")
        storage.put(thumb_key, thumb, "image/jpeg")

        photo = ProgressPhoto.objects.create(
            owner=request.user,
            pose=upload.validated_data.get("pose"),
            taken_on=upload.validated_data["taken_on"],
            notes=upload.validated_data.get("notes", ""),
            object_key=key,
            thumb_key=thumb_key,
            content_type="image/jpeg",
            width=width,
            height=height,
            bytes=len(clean),
        )
        data = ProgressPhotoSerializer(photo, context=self.get_serializer_context()).data
        return Response(data, status=201)

    def perform_destroy(self, instance):
        storage = get_storage()
        for key in (instance.object_key, instance.thumb_key):
            if key:
                storage.delete(key)
        instance.delete()

    @extend_schema(
        parameters=[OpenApiParameter("variant", str, description="full (default) | thumb")],
        responses={(200, "image/jpeg"): bytes},
    )
    @action(detail=True, methods=["get"])
    def image(self, request, pk=None):
        """Stream the photo bytes (owner-scoped). Private — never a public URL."""
        photo = self.get_object()
        variant = request.query_params.get("variant", "full")
        key = photo.thumb_key if variant == "thumb" and photo.thumb_key else photo.object_key
        try:
            data = get_storage().get(key)
        except FileNotFoundError:
            return Response({"detail": "Image data not found."}, status=404)
        resp = HttpResponse(data, content_type=photo.content_type)
        resp["Cache-Control"] = "private, max-age=3600"
        return resp

    @extend_schema(
        parameters=[OpenApiParameter("pose", int, required=True)],
        responses=ProgressPhotoSerializer,
    )
    @action(detail=False, methods=["get"])
    def latest(self, request):
        """Latest photo for a pose — drives the capture ghost overlay."""
        pose_id = request.query_params.get("pose")
        if not pose_id:
            raise ValidationError({"pose": "required"})
        photo = latest_photo_for_pose(self.effective_owner, pose_id)
        if photo is None:
            return Response({})
        return Response(ProgressPhotoSerializer(photo, context=self.get_serializer_context()).data)


# Permissions are the project default (IsAuthenticated); declared here for clarity.
for _vs in (PoseViewSet, CheckInViewSet, ProgressPhotoViewSet):
    _vs.permission_classes = [permissions.IsAuthenticated]
