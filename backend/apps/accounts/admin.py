from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Profile, User
from .services import hard_delete_user


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "is_staff", "is_superuser", "is_active", "date_joined"]
    list_filter = ["is_staff", "is_superuser", "is_active"]
    search_fields = ["email"]

    # Deleting a user can hit ProtectedError: their own dose logs / protocol items
    # PROTECT the custom compounds they own. hard_delete_user() tears those down first,
    # so override the admin's delete paths to use it and stop the confirmation page
    # blocking on those (user-owned) protected rows.
    def get_deleted_objects(self, objs, request):
        deletable, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        return deletable, model_count, perms_needed, []

    def delete_model(self, request, obj):
        hard_delete_user(obj)

    def delete_queryset(self, request, queryset):
        for user in queryset:
            hard_delete_user(user)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


admin.site.register(Profile)
