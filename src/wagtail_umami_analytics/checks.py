from django.apps import apps
from django.core.checks import Error


def check_for_wagtail_settings(app_configs, **kwargs):
    if app_configs is not None:
        if not any(app.label == "wagtail_umami_analytics" for app in app_configs):
            return []
    
    try:
        apps.get_app_config("wagtailsettings")
    except LookupError:
        return [
            Error(
                "Wagtail Umami Analytics requires wagtail.contrib.settings to be installed.",
                id="wagtail_umami_analytics.E001",
            )
        ]
    return []