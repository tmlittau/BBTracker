from django.db.models.signals import post_save
from django.dispatch import receiver

from .dose_slots import create_default_dose_slots
from .models import Protocol


@receiver(post_save, sender=Protocol)
def ensure_protocol_dose_slots(sender, instance, created, **kwargs):
    if created:
        create_default_dose_slots(instance)
