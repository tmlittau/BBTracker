"""Progress diary: mandatory-pose photos and dated subjective check-ins.

Photo binaries live in private object storage (MinIO via the S3 API); the DB only
holds object keys + metadata. Bytes are streamed back through the owner-scoped API
(`ProgressPhoto` `image` action), never exposed via public URLs, so photos stay
private. See `apps/diary/storage.py`.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .enums import SCORE_MAX, SCORE_MIN, PoseView


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Pose(models.Model):
    """A mandatory bodybuilding pose (seeded reference data)."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    view = models.CharField(max_length=8, choices=PoseView.choices, default=PoseView.FRONT)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


def _score_field(help_text):
    return models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)],
        help_text=help_text,
    )


class CheckIn(TimeStampedModel):
    """A dated subjective + bodyweight check-in (one per day per user)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="check_ins"
    )
    date = models.DateField()
    bodyweight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    systolic = models.PositiveIntegerField(null=True, blank=True)
    diastolic = models.PositiveIntegerField(null=True, blank=True)
    pulse = models.PositiveIntegerField(null=True, blank=True)
    energy = _score_field("Energy 1–5")
    sleep = _score_field("Sleep quality 1–5")
    mood = _score_field("Mood 1–5")
    motivation = _score_field("Motivation 1–5")
    soreness = _score_field("Soreness 1–5 (5 = very sore)")
    notes = models.TextField(blank=True, help_text="Headspace, physical experience, etc.")

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "date"], name="uniq_checkin_owner_date")
        ]

    def __str__(self):
        return f"Check-in {self.date} ({self.owner})"


class ProgressPhoto(TimeStampedModel):
    """A progress photo for a pose on a date. Binary lives in object storage."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progress_photos"
    )
    pose = models.ForeignKey(
        Pose, on_delete=models.SET_NULL, null=True, blank=True, related_name="photos"
    )
    taken_on = models.DateField()
    # Object-storage keys (private bucket); streamed back via the API, not public URLs.
    object_key = models.CharField(max_length=255)
    thumb_key = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=40, default="image/jpeg")
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    bytes = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-taken_on", "-created_at"]
        indexes = [models.Index(fields=["owner", "pose", "taken_on"])]

    def __str__(self):
        pose = self.pose.name if self.pose else "freeform"
        return f"Photo {pose} {self.taken_on} ({self.owner})"
