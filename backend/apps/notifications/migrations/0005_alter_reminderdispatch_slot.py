from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0004_delete_devicetoken")]

    operations = [
        migrations.AlterField(
            model_name="reminderdispatch",
            name="slot",
            field=models.CharField(max_length=64),
        ),
    ]
