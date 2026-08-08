from django.apps import AppConfig


class ExtensionApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.extension"
    verbose_name = "Browser Extension Bridge"
