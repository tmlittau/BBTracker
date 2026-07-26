from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_devicetoken"),
    ]

    operations = [
        migrations.DeleteModel(
            name="DeviceToken",
        ),
    ]
