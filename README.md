# Wagtail Umami Analytics

Adds a simple dashboard of Umami Analytics data into the Wagtail admin UI.

## Setup

1. Add `wagtail_umami_analytics` to your `INSTALLED_APPS`.
1. Ensure that `wagtail.contrib.settings` is in your `INSTALLED_APPS`
1. Set the following settings
    - `UMAMI_HOST` to the URL of the Umami instance
    - `UMAMI_API_BASE` to the base URL of the Umami API
    - `UMAMI_API_KEY` to your umami api key (only for umami cloud)
    - `UMAMI_USERNAME` to your umami username (only for self hosted umami)
    - `UMAMI_PASSWORD` to your umami password (only for self hosted umami)
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

## Page editor analytics panel

You can add an opt-in analytics panel to Wagtail page editors. The panel shows
page-level Umami stats for the live page over the last 30 days.

Register the stats endpoint in `wagtail_hooks.py`:

```python
from wagtail import hooks

from wagtail_umami_analytics.views import register_umami_page_analytics_urls


hooks.register("register_admin_urls", register_umami_page_analytics_urls)
```

Add the panel to the page models that should show analytics:

```python
from wagtail.models import Page

from wagtail_umami_analytics.panels import UmamiAnalyticsPanel


class ContentPage(Page):
    content_panels = Page.content_panels + [
        UmamiAnalyticsPanel(),
    ]
```

The page stats cache timeout defaults to 20 minutes. Override it with:

```python
WAGTAIL_UMAMI_PAGE_STATS_CACHE_TIMEOUT = 1200
```
