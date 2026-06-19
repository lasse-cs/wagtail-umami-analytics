from urllib.parse import urlencode

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import Panel

from wagtail_umami_analytics.views import (
    DEFAULT_PAGE_STATS_TIME_RANGE,
    TimeRange,
    get_page_site_id_and_path,
)


class UmamiAnalyticsPanel(Panel):
    def __init__(
        self,
        *,
        time_range=DEFAULT_PAGE_STATS_TIME_RANGE,
        **kwargs,
    ):
        time_range = str(time_range)
        if time_range not in TimeRange.values:
            expected_values = ", ".join(TimeRange.values)
            raise ValueError(
                f'Unsupported time_range "{time_range}". '
                f"Expected one of: {expected_values}."
            )

        kwargs.setdefault("heading", _("Analytics"))
        kwargs.setdefault("icon", "desktop")
        super().__init__(**kwargs)
        self.time_range = time_range

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs.update(time_range=self.time_range)
        return kwargs

    class BoundPanel(Panel.BoundPanel):
        template_name = "wagtail_umami_analytics/panels/umami_analytics_panel.html"

        @property
        def media(self):
            return forms.Media(
                css={
                    "all": [
                        "wagtail_umami_analytics/css/page_analytics_panel.css",
                    ]
                },
                js=[
                    "wagtail_umami_analytics/js/controllers/content_loader_controller.js",
                    "wagtail_umami_analytics/js/controllers/page_analytics_panel_controller.js",
                ],
            )

        def _reverse_stats_url(self, page_id):
            try:
                return reverse(
                    "wagtail_umami_page_analytics_stats",
                    kwargs={"page_id": page_id},
                )
            except NoReverseMatch as e:
                raise ImproperlyConfigured(
                    'UmamiAnalyticsPanel could not reverse "wagtail_umami_page_analytics_stats" '
                    "with a page_id keyword argument. Register PageAnalyticsStatsView "
                    "with register_umami_page_analytics_urls."
                ) from e

        def _get_stats_url(self):
            # Validate the URL contract even when this page will not load stats.
            stats_url = self._reverse_stats_url(self.instance.pk or 1)

            if not self.instance.pk or not self.instance.live:
                return ""

            if get_page_site_id_and_path(self.instance) is None:
                return ""

            query = urlencode({"range": self.panel.time_range})
            return f"{stats_url}?{query}"

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)
            time_range_label = TimeRange(self.panel.time_range).label
            stats_url = self._get_stats_url()
            context.update(
                {
                    "message": ""
                    if stats_url
                    else _("Analytics are available for published pages."),
                    "stats_url": stats_url,
                    "time_range_label": time_range_label,
                }
            )
            return context
