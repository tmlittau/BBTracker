from django.contrib import admin

from .models import Phase


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ["name", "phase_type", "start_date", "end_date", "owner"]
    list_filter = ["phase_type"]
    search_fields = ["name"]
