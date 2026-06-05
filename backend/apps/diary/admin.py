from django.contrib import admin

from .models import CheckIn, Pose, ProgressPhoto


@admin.register(Pose)
class PoseAdmin(admin.ModelAdmin):
    list_display = ["name", "view", "order"]
    list_filter = ["view"]


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ["date", "owner", "bodyweight", "energy", "mood"]
    list_filter = ["date"]


@admin.register(ProgressPhoto)
class ProgressPhotoAdmin(admin.ModelAdmin):
    list_display = ["taken_on", "owner", "pose", "width", "height", "bytes"]
    list_filter = ["pose", "taken_on"]
