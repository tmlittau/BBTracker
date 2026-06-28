from django.contrib import admin

from .models import BodyMeasurement


@admin.register(BodyMeasurement)
class BodyMeasurementAdmin(admin.ModelAdmin):
    list_display = ["date", "owner", "type", "value", "method"]
    list_filter = ["type", "method"]
    search_fields = ["owner__email"]
    date_hierarchy = "date"
