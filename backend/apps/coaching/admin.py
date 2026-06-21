from django.contrib import admin

from .models import CoachClientLink


@admin.register(CoachClientLink)
class CoachClientLinkAdmin(admin.ModelAdmin):
    list_display = ["coach", "client", "status", "created_at", "responded_at"]
    list_filter = ["status"]
    search_fields = ["coach__email", "client__email"]
    autocomplete_fields = ["coach", "client"]
