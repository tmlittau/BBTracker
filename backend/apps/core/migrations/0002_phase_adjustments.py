"""Move a Phase's nutrition target / program / protocol onto a dated
PhaseAdjustment timeline. Data-preserving: each existing phase gets one initial
adjustment (effective from its start date) carrying its current links, then the
direct FKs are dropped from Phase.
"""
import django.db.models.deletion
from django.db import migrations, models


def backfill_adjustments(apps, schema_editor):
    Phase = apps.get_model("core", "Phase")
    PhaseAdjustment = apps.get_model("core", "PhaseAdjustment")
    for phase in Phase.objects.all():
        PhaseAdjustment.objects.create(
            phase=phase,
            effective_date=phase.start_date,
            reason="Initial",
            nutrition_target_id=phase.nutrition_target_id,
            program_id=phase.program_id,
            protocol_id=phase.protocol_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("nutrition", "0002_meal_model"),
        ("protocols", "0002_item_scheduling"),
        ("training", "0002_loggedset_rest_seconds"),
    ]

    operations = [
        migrations.CreateModel(
            name="PhaseAdjustment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("effective_date", models.DateField()),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "nutrition_target",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="phase_adjustments",
                        to="nutrition.nutritiontarget",
                    ),
                ),
                (
                    "phase",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adjustments",
                        to="core.phase",
                    ),
                ),
                (
                    "program",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="phase_adjustments",
                        to="training.program",
                    ),
                ),
                (
                    "protocol",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="phase_adjustments",
                        to="protocols.protocol",
                    ),
                ),
            ],
            options={
                "ordering": ["effective_date", "id"],
                "indexes": [
                    models.Index(
                        fields=["phase", "effective_date"],
                        name="core_phasea_phase_i_5d83d3_idx",
                    )
                ],
            },
        ),
        migrations.RunPython(backfill_adjustments, migrations.RunPython.noop),
        migrations.RemoveField(model_name="phase", name="nutrition_target"),
        migrations.RemoveField(model_name="phase", name="program"),
        migrations.RemoveField(model_name="phase", name="protocol"),
    ]
