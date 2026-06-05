"""Move DiaryEntry.meal from a fixed TextChoices CharField to a per-day Meal FK.

Data-preserving: each existing entry's old meal label becomes a real Meal row
(deduped per owner+date+label), then the entry is repointed at it.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Old TextChoices value -> display name + a sensible default order.
MEAL_LABELS = {
    "breakfast": "Breakfast",
    "lunch": "Lunch",
    "dinner": "Dinner",
    "snack": "Snack",
    "pre_workout": "Pre-workout",
    "post_workout": "Post-workout",
}
MEAL_ORDER = {
    "breakfast": 0,
    "pre_workout": 1,
    "lunch": 2,
    "snack": 3,
    "post_workout": 4,
    "dinner": 5,
}


def backfill_meals(apps, schema_editor):
    DiaryEntry = apps.get_model("nutrition", "DiaryEntry")
    Meal = apps.get_model("nutrition", "Meal")
    cache: dict[tuple, object] = {}
    for entry in DiaryEntry.objects.all().order_by("date", "id"):
        old = entry.meal_old or "meal"
        key = (entry.owner_id, entry.date, old)
        meal = cache.get(key)
        if meal is None:
            meal = Meal.objects.create(
                owner_id=entry.owner_id,
                date=entry.date,
                name=MEAL_LABELS.get(old, old.replace("_", " ").title()),
                order=MEAL_ORDER.get(old, 0),
            )
            cache[key] = meal
        entry.meal = meal
        entry.save(update_fields=["meal"])


class Migration(migrations.Migration):

    dependencies = [
        ('nutrition', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='diaryentry',
            options={'ordering': ['date', 'id']},
        ),
        migrations.CreateModel(
            name='Meal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField()),
                ('name', models.CharField(max_length=80)),
                ('order', models.PositiveIntegerField(default=0)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meals', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['date', 'order', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='meal',
            index=models.Index(fields=['owner', 'date'], name='nutrition_m_owner_i_6b4f38_idx'),
        ),
        # Keep the old label column, add the FK, backfill, then drop the old column.
        migrations.RenameField('diaryentry', old_name='meal', new_name='meal_old'),
        migrations.AddField(
            model_name='diaryentry',
            name='meal',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='entries', to='nutrition.meal'),
        ),
        migrations.RunPython(backfill_meals, migrations.RunPython.noop),
        migrations.RemoveField(model_name='diaryentry', name='meal_old'),
    ]
