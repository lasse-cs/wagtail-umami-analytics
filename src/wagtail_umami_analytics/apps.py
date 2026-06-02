from django.apps import AppConfig
from django.core.checks import register

from wagtail_umami_analytics.checks import check_for_wagtail_settings


class AnalyticsConfig(AppConfig):
    name = "wagtail_umami_analytics"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        return register(check_for_wagtail_settings)