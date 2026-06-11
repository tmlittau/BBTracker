"""Carry existing BloodPressureLog readings into the daily CheckIn (BP now lives
with bodyweight + subjective scores). Oldest-first so the latest reading on a day
wins; a check-in is created for days that didn't have one."""
from django.db import migrations


def copy_bp_to_checkin(apps, schema_editor):
    BloodPressureLog = apps.get_model("protocols", "BloodPressureLog")
    CheckIn = apps.get_model("diary", "CheckIn")
    for bp in BloodPressureLog.objects.all().order_by("measured_at"):
        ci, _ = CheckIn.objects.get_or_create(
            owner_id=bp.owner_id, date=bp.measured_at.date()
        )
        ci.systolic = bp.systolic
        ci.diastolic = bp.diastolic
        ci.pulse = bp.pulse
        ci.save(update_fields=["systolic", "diastolic", "pulse"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0002_checkin_diastolic_checkin_pulse_checkin_systolic"),
        ("protocols", "0005_alter_compound_default_unit_alter_doselog_unit_and_more"),
    ]

    operations = [migrations.RunPython(copy_bp_to_checkin, noop)]
