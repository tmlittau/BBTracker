"""Supplements, medications/PEDs, dosing protocols, and health monitoring.

DISCLAIMER: BBTracker is a personal tracking/journaling tool, not a medical
device. These models record the *user's own* data — compounds carry factual
pharmacokinetic reference constants (half-life, ester active fraction) only; the
app does not recommend, prescribe, or endorse any substance, dose, or protocol.

Design mirrors the other domains: a `Compound`/`Supplement` reference layer (global
or user-custom), a `Protocol → ProtocolItem` template layer, and a `DoseLog`
record layer that is never rewritten by template edits. Supplements contribute to
the shared `nutrition.Nutrient` daily totals via `SupplementNutrient`.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from .enums import (
    BodyRegion,
    CompoundClass,
    DoseUnit,
    Frequency,
    MarkerCategory,
    Route,
    Side,
)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Compound(TimeStampedModel):
    """A medication/PED reference entry. Global (seeded) or user-custom.

    `half_life_hours` and `active_fraction` (ester/salt correction, ≤1.0) are
    factual constants used to model active concentration over time.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="compounds",
        help_text="Null = global/seeded compound available to everyone.",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, blank=True)
    compound_class = models.CharField(
        max_length=12, choices=CompoundClass.choices, default=CompoundClass.OTHER
    )
    default_unit = models.CharField(max_length=8, choices=DoseUnit.choices, default=DoseUnit.MG)
    default_route = models.CharField(max_length=8, choices=Route.choices, default=Route.IM)
    half_life_hours = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="Elimination half-life in hours (for concentration modelling).",
    )
    ester = models.CharField(max_length=40, blank=True)
    active_fraction = models.DecimalField(
        max_digits=4, decimal_places=3, default=Decimal("1.000"),
        help_text="Fraction of dose that is active drug (ester/salt weight correction).",
    )
    # Pharmacokinetics for the concentration (Bateman) model. Optional: with no
    # tmax the model degrades to instantaneous absorption (exponential decay).
    tmax_hours = models.DecimalField(
        max_digits=9, decimal_places=3, null=True, blank=True,
        help_text="Time to peak (hours) — drives the absorption phase of the curve.",
    )
    bioavailability = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True,
        help_text="Fraction absorbed (0–1); treated as 1 when unknown.",
    )
    pk_source = models.TextField(
        blank=True, help_text="Source(s) for the half-life / Tmax / bioavailability values.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="uniq_compound_owner_name")
        ]

    @property
    def is_global(self) -> bool:
        return self.owner_id is None

    def __str__(self):
        return self.name


class Supplement(TimeStampedModel):
    """A supplement. Its per-serving nutrients feed the daily micronutrient totals."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="supplements",
    )
    name = models.CharField(max_length=140)
    brand = models.CharField(max_length=120, blank=True)
    serving_label = models.CharField(max_length=80, default="1 serving")
    target_benefit = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    nutrients = models.ManyToManyField(
        "nutrition.Nutrient", through="SupplementNutrient", related_name="supplements"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name", "brand"], name="uniq_supp_owner_name")
        ]

    @property
    def is_global(self) -> bool:
        return self.owner_id is None

    def __str__(self):
        return f"{self.brand} {self.name}".strip() if self.brand else self.name


class SupplementNutrient(models.Model):
    """Amount of a nutrient delivered per serving of a supplement."""

    supplement = models.ForeignKey(
        Supplement, on_delete=models.CASCADE, related_name="supplement_nutrients"
    )
    nutrient = models.ForeignKey(
        "nutrition.Nutrient", on_delete=models.PROTECT, related_name="supplement_nutrients"
    )
    amount_per_serving = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0"))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["supplement", "nutrient"], name="uniq_supplement_nutrient"
            )
        ]

    def __str__(self):
        return f"{self.supplement.name} · {self.nutrient.name}={self.amount_per_serving}"


class InjectionSite(models.Model):
    """Canonical injection location for the body-map picker + rotation tracking."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    region = models.CharField(max_length=12, choices=BodyRegion.choices)
    side = models.CharField(max_length=8, choices=Side.choices, default=Side.LEFT)
    # SVG body-map coordinates (percent of viewbox), for the interactive picker.
    x = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("50"))
    y = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("50"))

    class Meta:
        ordering = ["region", "side"]

    def __str__(self):
        return self.name


class Protocol(TimeStampedModel):
    """A dosing plan, e.g. 'TRT' or 'Summer cycle'."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="protocols"
    )
    name = models.CharField(max_length=140)
    is_active = models.BooleanField(default=False)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self):
        return self.name


class ProtocolItem(models.Model):
    """A scheduled compound or supplement within a protocol (exactly one of the two)."""

    protocol = models.ForeignKey(Protocol, on_delete=models.CASCADE, related_name="items")
    compound = models.ForeignKey(
        Compound, on_delete=models.PROTECT, null=True, blank=True, related_name="protocol_items"
    )
    supplement = models.ForeignKey(
        Supplement, on_delete=models.PROTECT, null=True, blank=True, related_name="protocol_items"
    )
    dose_amount = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    dose_unit = models.CharField(max_length=8, choices=DoseUnit.choices, default=DoseUnit.MG)
    route = models.CharField(max_length=8, choices=Route.choices, blank=True)
    frequency = models.CharField(max_length=16, choices=Frequency.choices, default=Frequency.WEEKLY)
    # Weekdays (0=Mon … 6=Sun) used when frequency="specific_days"; times within a
    # day (TimeOfDay values) for multiple doses/day. JSON, not ArrayField, so the
    # sqlite test path works alongside Postgres.
    days_of_week = models.JSONField(default=list, blank=True)
    times_of_day = models.JSONField(default=list, blank=True)
    target_benefit = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        item = self.compound or self.supplement
        return f"{self.protocol.name} · {item}"


class DoseLog(TimeStampedModel):
    """An actual administration (compound or supplement). Its own record."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dose_logs"
    )
    protocol_item = models.ForeignKey(
        ProtocolItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="dose_logs"
    )
    compound = models.ForeignKey(
        Compound, on_delete=models.PROTECT, null=True, blank=True, related_name="dose_logs"
    )
    supplement = models.ForeignKey(
        Supplement, on_delete=models.PROTECT, null=True, blank=True, related_name="dose_logs"
    )
    taken_at = models.DateTimeField()
    amount = models.DecimalField(max_digits=10, decimal_places=3)
    unit = models.CharField(max_length=8, choices=DoseUnit.choices, default=DoseUnit.MG)
    route = models.CharField(max_length=8, choices=Route.choices, blank=True)
    injection_site = models.ForeignKey(
        InjectionSite, on_delete=models.SET_NULL, null=True, blank=True, related_name="dose_logs"
    )
    notes = models.CharField(max_length=255, blank=True)
    side_effects = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=8,
        choices=[("taken", "Taken"), ("skipped", "Skipped")],
        default="taken",
        help_text="'skipped' = intentionally not taken (e.g. a sick day).",
    )

    class Meta:
        ordering = ["-taken_at"]
        indexes = [models.Index(fields=["owner", "taken_at"])]

    def __str__(self):
        item = self.compound or self.supplement
        return f"{self.taken_at:%Y-%m-%d} · {item} {self.amount}{self.unit}"


class Vial(TimeStampedModel):
    """Inventory for an injectable compound (or any countable stock)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vials"
    )
    compound = models.ForeignKey(Compound, on_delete=models.CASCADE, related_name="vials")
    label = models.CharField(max_length=120, blank=True)
    concentration_mg_ml = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    remaining_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    unit = models.CharField(max_length=8, choices=DoseUnit.choices, default=DoseUnit.ML)
    reorder_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )

    class Meta:
        ordering = ["compound__name", "label"]

    @property
    def needs_reorder(self) -> bool:
        return self.remaining_amount <= self.reorder_threshold

    def __str__(self):
        return f"{self.compound.name} vial ({self.remaining_amount}/{self.total_amount})"


class BloodMarker(models.Model):
    """Canonical lab marker with reference ranges (optionally sex-specific)."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    unit = models.CharField(max_length=20)
    category = models.CharField(
        max_length=12, choices=MarkerCategory.choices, default=MarkerCategory.OTHER
    )
    ref_low = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ref_high = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ref_low_male = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ref_high_male = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ref_low_female = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ref_high_female = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    display_order = models.PositiveIntegerField(default=100)
    # Alternate names (lab / Dutch synonyms) used to match this marker when importing
    # a lab PDF, e.g. ["hemoglobine", "Hb"].
    aliases = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class BloodResult(TimeStampedModel):
    """A single lab value on a date for the owner."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blood_results"
    )
    marker = models.ForeignKey(BloodMarker, on_delete=models.PROTECT, related_name="results")
    value = models.DecimalField(max_digits=10, decimal_places=3)
    # Result's own unit + reference range, captured verbatim from its source (e.g. a
    # lab PDF). Blank/null falls back to the marker's defaults — so each reading flags
    # against the exact range it shipped with, even if the marker default changes.
    unit = models.CharField(max_length=20, blank=True)
    ref_low = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ref_high = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    source = models.CharField(
        max_length=8, choices=[("manual", "Manual"), ("pdf", "PDF import")], default="manual"
    )
    measured_on = models.DateField()
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-measured_on"]
        indexes = [models.Index(fields=["owner", "marker", "measured_on"])]

    def __str__(self):
        return f"{self.marker.name}={self.value} on {self.measured_on}"


class BloodPressureLog(TimeStampedModel):
    """A blood-pressure reading (key for ancillaries like Telmisartan)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bp_logs"
    )
    systolic = models.PositiveIntegerField()
    diastolic = models.PositiveIntegerField()
    pulse = models.PositiveIntegerField(null=True, blank=True)
    measured_at = models.DateTimeField()
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-measured_at"]
        indexes = [models.Index(fields=["owner", "measured_at"])]

    def __str__(self):
        return f"{self.systolic}/{self.diastolic} @ {self.measured_at:%Y-%m-%d}"
