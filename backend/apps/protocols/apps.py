from django.apps import AppConfig


class ProtocolsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.protocols"

    def ready(self):
        from . import signals  # noqa: F401
