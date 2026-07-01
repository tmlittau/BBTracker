from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("training", "0004_workoutsession_training_wo_owner_i_843a4f_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="exercise",
            name="rest_by_set_type",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Rest seconds per set type, e.g. {'working': 180, 'warmup': 60}. "
                    "Missing types fall back to DEFAULT_REST_SECONDS."
                ),
            ),
        ),
    ]
