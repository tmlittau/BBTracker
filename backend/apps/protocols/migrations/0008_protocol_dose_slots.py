import datetime

from django.db import migrations, models
import django.db.models.deletion


LEGACY_SLOTS = (
    ("waking", "Waking", datetime.time(6, 30)),
    ("am", "AM", datetime.time(10, 0)),
    ("noon", "Noon", datetime.time(15, 0)),
    ("pm", "PM", datetime.time(19, 0)),
    ("night", "Night", datetime.time(21, 0)),
)


def migrate_protocol_slots(apps, schema_editor):
    Protocol = apps.get_model("protocols", "Protocol")
    ProtocolDoseSlot = apps.get_model("protocols", "ProtocolDoseSlot")
    ReminderSettings = apps.get_model("notifications", "ReminderSettings")

    settings_by_owner = {
        row.owner_id: row for row in ReminderSettings.objects.all().iterator()
    }
    for protocol in Protocol.objects.all().iterator():
        reminder_settings = settings_by_owner.get(protocol.owner_id)
        slots_by_key = {}
        for order, (key, default_name, default_time) in enumerate(LEGACY_SLOTS):
            name = default_name
            reminder_time = default_time
            if reminder_settings is not None:
                custom_name = (getattr(reminder_settings, f"{key}_label", "") or "").strip()
                name = custom_name or default_name
                reminder_time = getattr(reminder_settings, key, default_time)
            slots_by_key[key] = ProtocolDoseSlot.objects.create(
                protocol_id=protocol.id,
                key=key,
                name=name,
                reminder_time=reminder_time,
                order=order,
            )
        for item in protocol.items.all().iterator():
            selected = [
                slots_by_key[key]
                for key in (item.times_of_day or [])
                if key in slots_by_key
            ]
            if selected:
                item.dose_slots.add(*selected)


def reverse_protocol_slots(apps, schema_editor):
    apps.get_model("protocols", "ProtocolDoseSlot").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_delete_devicetoken"),
        ("protocols", "0007_injectionsite_route_alter_injectionsite_region"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProtocolDoseSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=64)),
                ("reminder_time", models.TimeField()),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("protocol", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dose_slots", to="protocols.protocol")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="protocoldoseslot",
            constraint=models.UniqueConstraint(fields=("protocol", "key"), name="uniq_protocol_dose_slot_key"),
        ),
        migrations.AddField(
            model_name="protocolitem",
            name="dose_slots",
            field=models.ManyToManyField(blank=True, help_text="Protocol-owned reminder slots selected for this item.", related_name="items", to="protocols.protocoldoseslot"),
        ),
        migrations.RunPython(migrate_protocol_slots, reverse_protocol_slots),
    ]
