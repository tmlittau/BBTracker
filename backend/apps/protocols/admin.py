from django.contrib import admin

from .models import (
    BloodMarker,
    BloodPressureLog,
    BloodResult,
    Compound,
    DoseLog,
    InjectionSite,
    Protocol,
    ProtocolItem,
    Supplement,
    SupplementNutrient,
    Vial,
)


@admin.register(Compound)
class CompoundAdmin(admin.ModelAdmin):
    list_display = ["name", "compound_class", "half_life_hours", "ester", "owner"]
    list_filter = ["compound_class"]
    search_fields = ["name", "ester"]


class SupplementNutrientInline(admin.TabularInline):
    model = SupplementNutrient
    extra = 0


@admin.register(Supplement)
class SupplementAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "owner"]
    search_fields = ["name", "brand"]
    inlines = [SupplementNutrientInline]


@admin.register(InjectionSite)
class InjectionSiteAdmin(admin.ModelAdmin):
    list_display = ["name", "region", "side"]
    list_filter = ["region", "side"]


class ProtocolItemInline(admin.TabularInline):
    model = ProtocolItem
    extra = 0


@admin.register(Protocol)
class ProtocolAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "is_active", "started_on"]
    inlines = [ProtocolItemInline]


@admin.register(DoseLog)
class DoseLogAdmin(admin.ModelAdmin):
    list_display = ["taken_at", "owner", "compound", "supplement", "amount", "unit", "route"]
    list_filter = ["route"]


@admin.register(BloodMarker)
class BloodMarkerAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "unit", "display_order"]
    list_filter = ["category"]


@admin.register(BloodResult)
class BloodResultAdmin(admin.ModelAdmin):
    list_display = ["marker", "value", "measured_on", "owner"]


admin.site.register([Vial, BloodPressureLog])
