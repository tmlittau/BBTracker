from django.db import models


class CompoundClass(models.TextChoices):
    ANABOLIC = "anabolic", "Anabolic steroid"
    PEPTIDE = "peptide", "Peptide"
    SARM = "sarm", "SARM"
    ANCILLARY = "ancillary", "Ancillary / pharmaceutical"
    OTHER = "other", "Other"


class DoseUnit(models.TextChoices):
    MG = "mg", "mg"
    MCG = "mcg", "µg"
    IU = "iu", "IU"
    ML = "ml", "ml"
    TABLET = "tablet", "tablet"
    CAPSULE = "capsule", "capsule"
    SERVING = "serving", "serving"


class Route(models.TextChoices):
    """Administration route. IM/SubQ are injections (drive the body-map picker)."""

    IM = "im", "Intramuscular"
    SUBQ = "subq", "Subcutaneous"
    ORAL = "oral", "Oral"
    TOPICAL = "topical", "Topical"
    NASAL = "nasal", "Nasal"
    OTHER = "other", "Other"


INJECTABLE_ROUTES = frozenset({Route.IM, Route.SUBQ})


class Frequency(models.TextChoices):
    """Dosing cadence. Drives adherence math + the schedule UI.

    EVERY_3_DAYS and SPECIFIC_DAYS were added in iteration 2; the legacy
    TWICE_WEEK/THRICE_WEEK/TWICE_DAY values remain valid for old rows but are no
    longer offered in the UI (specific-days + times-of-day express them better).
    """

    DAILY = "daily", "Daily"
    EOD = "eod", "Every other day"
    EVERY_3_DAYS = "every_3_days", "Every 3 days"
    WEEKLY = "weekly", "Weekly"
    SPECIFIC_DAYS = "specific_days", "Specific days of week"
    AS_NEEDED = "prn", "As needed"
    # Legacy (kept for existing data; not shown in the picker).
    TWICE_WEEK = "2x_week", "2× / week"
    THRICE_WEEK = "3x_week", "3× / week"
    TWICE_DAY = "2x_day", "2× / day"


# Frequencies offered in the schedule picker (order matters), per the feedback.
FREQUENCY_CHOICES_UI = [
    Frequency.DAILY,
    Frequency.EOD,
    Frequency.EVERY_3_DAYS,
    Frequency.WEEKLY,
    Frequency.SPECIFIC_DAYS,
    Frequency.AS_NEEDED,
]


# Default doses-per-week for adherence, keyed by Frequency. SPECIFIC_DAYS is
# computed from the selected weekdays instead, so it is 0 here.
FREQUENCY_PER_WEEK = {
    Frequency.DAILY: 7.0,
    Frequency.EOD: 3.5,
    Frequency.EVERY_3_DAYS: 7.0 / 3.0,
    Frequency.WEEKLY: 1.0,
    Frequency.SPECIFIC_DAYS: 0.0,
    Frequency.AS_NEEDED: 0.0,
    Frequency.TWICE_WEEK: 2.0,
    Frequency.THRICE_WEEK: 3.0,
    Frequency.TWICE_DAY: 14.0,
}


class TimeOfDay(models.TextChoices):
    """When in the day a dose is taken (multi-select); also multiplies adherence."""

    WAKING = "waking", "Waking"
    AM = "am", "AM"
    NOON = "noon", "Noon"
    PM = "pm", "PM"
    NIGHT = "night", "Night"


# Order for the time-of-day multi-select UI.
TIME_OF_DAY_UI = [
    TimeOfDay.WAKING,
    TimeOfDay.AM,
    TimeOfDay.NOON,
    TimeOfDay.PM,
    TimeOfDay.NIGHT,
]


class BodyRegion(models.TextChoices):
    GLUTE = "glute", "Glute (dorsogluteal)"
    VENTROGLUTE = "ventroglute", "Ventrogluteal"
    QUAD = "quad", "Quad (vastus lateralis)"
    DELT = "delt", "Deltoid"
    LAT_DELT = "lat_delt", "Lateral delt (SubQ)"
    ABDOMEN = "abdomen", "Abdomen (SubQ)"
    PEC = "pec", "Pec"
    BICEP = "bicep", "Biceps"
    TRICEP = "tricep", "Triceps"
    CALF = "calf", "Calf"


class Side(models.TextChoices):
    LEFT = "left", "Left"
    RIGHT = "right", "Right"
    CENTER = "center", "Center"


class MarkerCategory(models.TextChoices):
    HORMONE = "hormone", "Hormone"
    LIPID = "lipid", "Lipid"
    LIVER = "liver", "Liver"
    KIDNEY = "kidney", "Kidney"
    BLOOD = "blood", "Blood count"
    METABOLIC = "metabolic", "Metabolic"
    OTHER = "other", "Other"
