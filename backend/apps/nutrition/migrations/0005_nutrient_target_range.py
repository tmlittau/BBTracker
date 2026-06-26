"""Turn NutrientTarget's single `amount` into an optional min/max range.

The old `amount` was a floor (daily goal), so it carries over to `min_amount`;
`max_amount` (the toxicity ceiling) starts empty.
"""
from django.db import migrations, models


def amount_to_min(apps, schema_editor):
    NutrientTarget = apps.get_model("nutrition", "NutrientTarget")
    for nt in NutrientTarget.objects.all():
        nt.min_amount = nt.amount
        nt.save(update_fields=["min_amount"])


class Migration(migrations.Migration):
    dependencies = [
        ("nutrition", "0004_mealtemplate_mealtemplateitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="nutrienttarget",
            name="min_amount",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="nutrienttarget",
            name="max_amount",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True),
        ),
        migrations.RunPython(amount_to_min, migrations.RunPython.noop),
        migrations.RemoveField(model_name="nutrienttarget", name="amount"),
        migrations.AddConstraint(
            model_name="nutrienttarget",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(min_amount__isnull=True)
                    | models.Q(max_amount__isnull=True)
                    | models.Q(max_amount__gte=models.F("min_amount"))
                ),
                name="nutrient_target_max_gte_min",
            ),
        ),
    ]
