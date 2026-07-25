from django.conf import settings
from django.db import models


class HealthMetricKind(models.TextChoices):
    HRV = "hrv", "Heart-rate variability"
    RESTING_HEART_RATE = "resting_hr", "Resting heart rate"
    SLEEP_HOURS = "sleep_hours", "Sleep"
    BODYWEIGHT = "bodyweight", "Bodyweight"
    STEPS = "steps", "Steps"
    WATER_ML = "water_ml", "Water"


class HealthDailyAggregate(models.Model):
    """Compact backup projection; raw HealthKit samples never leave the device."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="health_daily_aggregates",
    )
    kind = models.CharField(max_length=24, choices=HealthMetricKind.choices)
    date = models.DateField()
    value = models.DecimalField(max_digits=14, decimal_places=4)
    minimum = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    maximum = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    sample_count = models.PositiveIntegerField()
    source = models.CharField(max_length=64)
    source_fingerprint = models.CharField(max_length=64)
    updated_at = models.DateTimeField()
    server_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "kind", "source"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "kind", "date", "source"],
                name="unique_owner_health_day_source",
            )
        ]
        indexes = [models.Index(fields=["owner", "kind", "date"])]

    def __str__(self):
        return f"{self.owner_id}: {self.kind} {self.date}={self.value}"
