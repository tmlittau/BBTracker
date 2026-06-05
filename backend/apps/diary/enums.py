from django.db import models


class PoseView(models.TextChoices):
    FRONT = "front", "Front"
    BACK = "back", "Back"
    SIDE = "side", "Side"


# 1–5 subjective scales used in check-ins.
SCORE_MIN = 1
SCORE_MAX = 5
