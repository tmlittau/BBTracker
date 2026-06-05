"""The periodization timeline spine.

A `Phase` ("Off-season bulk", "Prep", "Cruise") spans a date range. Within it a
dated `PhaseAdjustment` timeline records how the prescription evolves — calories
drop when weight stalls, the split changes, compounds rotate — each adjustment
carrying the nutrition target / program / protocol in force from its
`effective_date`. The config for any date resolves to the latest adjustment on or
before it. Cross-app links are string FKs (SET_NULL) so the timeline never blocks
editing or deleting the things it points at.
"""
from django.conf import settings
from django.db import models

from .enums import PhaseType


class Phase(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="phases"
    )
    name = models.CharField(max_length=120)
    phase_type = models.CharField(
        max_length=12, choices=PhaseType.choices, default=PhaseType.OTHER
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Null = ongoing.")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["owner", "start_date"])]

    @property
    def is_ongoing(self) -> bool:
        return self.end_date is None

    def __str__(self):
        return f"{self.name} ({self.start_date}→{self.end_date or 'ongoing'})"


class PhaseAdjustment(models.Model):
    """A dated change of prescription within a phase.

    Each adjustment sets the nutrition target / program / protocol that apply from
    `effective_date` onward (until the next adjustment). This keeps a full history
    of what was prescribed when — the record a coach reviews.
    """

    phase = models.ForeignKey(Phase, on_delete=models.CASCADE, related_name="adjustments")
    effective_date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)

    nutrition_target = models.ForeignKey(
        "nutrition.NutritionTarget", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="phase_adjustments",
    )
    program = models.ForeignKey(
        "training.Program", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="phase_adjustments",
    )
    protocol = models.ForeignKey(
        "protocols.Protocol", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="phase_adjustments",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["effective_date", "id"]
        indexes = [models.Index(fields=["phase", "effective_date"])]

    def __str__(self):
        return f"{self.phase.name} @ {self.effective_date}"
