"""Protocol-owned dose-slot defaults and cloning helpers."""

from __future__ import annotations

import datetime

# Keep the historical keys during the compatibility window. The key is a stable
# machine identifier; users edit the name and reminder time instead.
DEFAULT_DOSE_SLOTS = (
    ("waking", "Waking", datetime.time(6, 30)),
    ("am", "AM", datetime.time(10, 0)),
    ("noon", "Noon", datetime.time(15, 0)),
    ("pm", "PM", datetime.time(19, 0)),
    ("night", "Night", datetime.time(21, 0)),
)


def create_default_dose_slots(protocol):
    """Create the legacy five slots for a new protocol, idempotently."""
    from .models import ProtocolDoseSlot

    if protocol.dose_slots.exists():
        return list(protocol.dose_slots.order_by("order", "id"))
    return [
        ProtocolDoseSlot.objects.create(
            protocol=protocol,
            key=key,
            name=name,
            reminder_time=reminder_time,
            order=order,
        )
        for order, (key, name, reminder_time) in enumerate(DEFAULT_DOSE_SLOTS)
    ]


def copy_dose_slots(source, target):
    """Replace target defaults with copies of source slots and return an id map."""
    from .models import ProtocolDoseSlot

    source_slots = list(source.dose_slots.order_by("order", "id"))
    if not source_slots:
        return {}
    target.dose_slots.all().delete()
    mapping = {}
    for slot in source_slots:
        copied = ProtocolDoseSlot.objects.create(
            protocol=target,
            key=slot.key,
            name=slot.name,
            reminder_time=slot.reminder_time,
            order=slot.order,
        )
        mapping[slot.id] = copied
    return mapping
