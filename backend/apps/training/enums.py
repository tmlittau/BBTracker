from django.db import models


class SetType(models.TextChoices):
    """How a given set is performed. Drives logging UI and volume analytics.

    `WARMUP` sets are typically excluded from working-volume counts.
    """

    WARMUP = "warmup", "Warm-up"
    WORKING = "working", "Working"
    DROP = "drop", "Drop set"
    REST_PAUSE = "rest_pause", "Rest-pause"
    MYO_REP = "myo_rep", "Myo-rep"
    CLUSTER = "cluster", "Cluster"
    AMRAP = "amrap", "AMRAP"
    BACKOFF = "backoff", "Back-off"
    TOP_SET = "top_set", "Top set"
    FAILURE = "failure", "To failure"


# Set types that count toward "working" volume / tonnage (exclude warm-ups).
WORKING_SET_TYPES = frozenset(
    t for t in SetType.values if t != SetType.WARMUP
)


# Set types tallied as a discrete "hard set" for weekly set-count targets. Intensity
# techniques (drop / rest-pause / myo-rep / cluster / back-off / AMRAP / failure)
# extend an adjacent working set rather than adding a separate set, so they still add
# tonnage but are not counted as extra sets. Warm-ups count for neither.
COUNTED_SET_TYPES = frozenset({SetType.WORKING, SetType.TOP_SET})


# Sensible default rest (seconds) per set type, used when a planned set leaves
# `rest_seconds` blank or a freeform set is logged. Warm-ups rest little; heavy
# top/back-off/AMRAP work rests longest; intensity techniques are near-continuous.
DEFAULT_REST_BY_SET_TYPE = {
    SetType.WARMUP: 45,
    SetType.WORKING: 150,
    SetType.DROP: 30,
    SetType.REST_PAUSE: 30,
    SetType.MYO_REP: 30,
    SetType.CLUSTER: 30,
    SetType.AMRAP: 180,
    SetType.BACKOFF: 120,
    SetType.TOP_SET: 180,
    SetType.FAILURE: 180,
}


class ExerciseCategory(models.TextChoices):
    BARBELL = "barbell", "Barbell"
    DUMBBELL = "dumbbell", "Dumbbell"
    MACHINE = "machine", "Machine"
    CABLE = "cable", "Cable"
    BODYWEIGHT = "bodyweight", "Bodyweight"
    SMITH = "smith", "Smith machine"
    KETTLEBELL = "kettlebell", "Kettlebell"
    BANDED = "banded", "Resistance band"
    OTHER = "other", "Other"


class LoadType(models.TextChoices):
    """How an exercise's load is measured — drives logging inputs & e1RM validity."""

    WEIGHT_REPS = "weight_reps", "Weight × reps"
    BODYWEIGHT_REPS = "bodyweight_reps", "Bodyweight reps"
    WEIGHTED_BODYWEIGHT = "weighted_bodyweight", "Bodyweight + added weight"
    DURATION = "duration", "Duration (e.g. plank)"
    DISTANCE_DURATION = "distance_duration", "Distance + duration (cardio)"
