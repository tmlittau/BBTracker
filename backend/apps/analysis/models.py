from django.conf import settings
from django.db import models


class MeasurementType(models.TextChoices):
    WAIST = "waist", "Waist"
    NECK = "neck", "Neck"
    HIP = "hip", "Hip"
    CHEST = "chest", "Chest"
    UPPER_ARM_LEFT = "upper_arm_left", "Upper arm (left)"
    UPPER_ARM_RIGHT = "upper_arm_right", "Upper arm (right)"
    FOREARM_LEFT = "forearm_left", "Forearm (left)"
    FOREARM_RIGHT = "forearm_right", "Forearm (right)"
    THIGH_LEFT = "thigh_left", "Thigh (left)"
    THIGH_RIGHT = "thigh_right", "Thigh (right)"
    CALF_LEFT = "calf_left", "Calf (left)"
    CALF_RIGHT = "calf_right", "Calf (right)"
    BODY_FAT = "body_fat", "Body fat %"
    RESTING_HR = "resting_hr", "Resting heart rate"


class BodyFatMethod(models.TextChoices):
    DEXA = "dexa", "DEXA"
    BIA = "bia", "Bioimpedance"
    CALIPERS = "calipers", "Calipers"
    SCALE = "scale", "Smart scale"
    ESTIMATE = "estimate", "Estimated"


# Unit per measurement type (circumferences are cm; body fat %, resting HR bpm).
MEASUREMENT_UNITS = {
    MeasurementType.BODY_FAT: "%",
    MeasurementType.RESTING_HR: "bpm",
}
DEFAULT_MEASUREMENT_UNIT = "cm"


def unit_for(measurement_type: str) -> str:
    return MEASUREMENT_UNITS.get(measurement_type, DEFAULT_MEASUREMENT_UNIT)


class BodyMeasurement(models.Model):
    """A less-frequent body measurement (circumference, body-fat %, resting HR).

    Weight + blood pressure live on the daily check-in, bloodwork on protocols, and
    height/sex/DOB on the profile; the Body Analysis reads all of those and adds
    these. `method` records how a body-fat % was obtained (DEXA outranks a tape
    estimate); it's blank for circumferences.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="body_measurements"
    )
    date = models.DateField()
    type = models.CharField(max_length=20, choices=MeasurementType.choices)
    value = models.DecimalField(max_digits=6, decimal_places=2)
    method = models.CharField(max_length=10, choices=BodyFatMethod.choices, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "type"]
        indexes = [models.Index(fields=["owner", "type", "date"])]

    def __str__(self):
        return f"{self.date} {self.type}={self.value}"
