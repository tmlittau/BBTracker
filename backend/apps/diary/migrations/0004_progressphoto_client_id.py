from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0003_bp_logs_to_checkin"),
    ]

    operations = [
        migrations.AddField(
            model_name="progressphoto",
            name="client_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="progressphoto",
            constraint=models.UniqueConstraint(
                fields=("owner", "client_id"),
                name="uniq_progress_photo_owner_client_id",
            ),
        ),
    ]
