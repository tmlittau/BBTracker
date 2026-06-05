from django.db import models


class PhaseType(models.TextChoices):
    BULK = "bulk", "Off-season bulk"
    CUT = "cut", "Cut"
    MAINTAIN = "maintain", "Maintenance"
    RECOMP = "recomp", "Recomp"
    PREP = "prep", "Contest prep"
    CRUISE = "cruise", "Cruise"
    BLAST = "blast", "Blast"
    TRT = "trt", "TRT"
    MINI_CUT = "mini_cut", "Mini-cut"
    OTHER = "other", "Other"
