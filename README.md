# Wagtail Umami Analytics

Adds a simple dashboard of Umami Analytics data into the Wagtail admin UI.

## Setup

1. Add `wagtail_umami_analytics` to your `INSTALLED_APPS`.
1. Ensure that `wagtail.contrib.settings` is in your `INSTALLED_APPS`
1. Set the following settings
    - `UMAMI_HOST` to the URL of the Umami instance
    - `UMAMI_API_BASE` to the base URL of the Umami API
    - `UMAMI_API_KEY` to your umami api key
1. Register the `wagtail_umami_analytics.UmamiAnalyticsSetting` setting
    ```python
    from wagtail.contrib.settings.models import register_setting
    from wagtail_umami_analytics.models import UmamiAnalyticsSetting
    
    register_setting(UmamiAnalyticsSetting)
    ```
1. Register the dashboard admin viewset
    ```python
    from wagtail import hooks

    @hooks.register("register_admin_viewset")
    def register_umami_dashboard():
        return UmamiAnalyticsViewSet()
    ```
1. Add the Umami analytics template tag to the pages you wish to track
    ```django+html
    {% load umami_analytics_tags %}
    
    {% umami_analytics_tracker %}
    ```