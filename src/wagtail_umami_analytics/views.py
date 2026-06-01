from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.views.generic import TemplateView, View
from wagtail.admin.viewsets.base import ViewSet
from wagtail.contrib.settings.forms import SiteSwitchForm
from wagtail.models import Site

from wagtail_umami_analytics.client import (
    Metric,
    MetricType,
    Stats,
    UmamiClient,
    UmamiClientError,
)
from wagtail_umami_analytics.models import UmamiAnalyticsSetting


logger = logging.getLogger(__name__)


def _get_client():
    client = UmamiClient(base_url=getattr(settings, "UMAMI_API_BASE", None))
    if getattr(settings, "UMAMI_API_KEY", None):
        client.set_api_key(api_key=getattr(settings, "UMAMI_API_KEY", None))
    else:
        username = getattr(settings, "UMAMI_USERNAME", None)
        password = getattr(settings, "UMAMI_PASSWORD", None)
        client.login(username, password)
    return client


def _get_time_range_days(days: int = 7) -> tuple[int, int]:
    now = timezone.now()
    start = now - timedelta(days=days)
    return int(start.timestamp() * 1000), int(now.timestamp() * 1000)


def _fetch_stats(start_at: int, end_at: int, website_id: str) -> Stats:
    with _get_client() as client:
        return client.stats(start_at, end_at, website_id=website_id)


def _fetch_metrics(
    start_at: int, end_at: int, metric_type: MetricType, website_id: str
) -> list[Metric]:
    with _get_client() as client:
        return client.metrics(
            start_at, end_at, metric_type, limit=10, website_id=website_id
        )


def get_active_users(website_id: str) -> int:
    cache_key = f"analytics:active_users:{website_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    with _get_client() as client:
        active = client.active_users(website_id=website_id)
    cache.set(cache_key, active, timeout=300)
    return active


def get_stats(website_id: str) -> Stats:
    cache_key = f"analytics:stats:{website_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    start_at, end_at = _get_time_range_days(7)
    stats = _fetch_stats(start_at, end_at, website_id)
    if stats:
        cache.set(cache_key, stats)
    return stats


def get_metrics(website_id: str) -> dict[str, list[Metric]]:
    cache_key = f"analytics:stats_metrics:{website_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    start_at, end_at = _get_time_range_days(7)

    metrics = {"paths": [], "referrers": [], "countries": []}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                _fetch_metrics, start_at, end_at, MetricType.PATH, website_id
            ): "paths",
            executor.submit(
                _fetch_metrics, start_at, end_at, MetricType.REFERRER, website_id
            ): "referrers",
            executor.submit(
                _fetch_metrics, start_at, end_at, MetricType.COUNTRY, website_id
            ): "countries",
        }
        for future in as_completed(futures):
            key = futures[future]
            metrics[key] = future.result()

    cache.set(cache_key, metrics, timeout=1200)
    return metrics


def _umami_unavailable_response() -> JsonResponse:
    return JsonResponse({"error": "Umami is unavailable"}, status=503)


class AnalyticsSiteSwitchForm(SiteSwitchForm):
    @classmethod
    def get_change_url(cls, site, model):
        return reverse("analytics:index_for_site", args=[site.pk])


class AnalyticsSiteMixin:
    settings_model = UmamiAnalyticsSetting

    def dispatch(self, request, *args, **kwargs):
        self.site = self.get_site()
        self.analytics_settings = self.settings_model.for_site(self.site)
        self.website_id = self.analytics_settings.umami_id
        return super().dispatch(request, *args, **kwargs)

    def get_available_sites(self):
        return Site.objects.all()

    def get_default_site(self):
        return Site.objects.filter(is_default_site=True).first() or Site.objects.first()

    def get_site(self):
        site_pk = self.kwargs.get("site_pk")

        if site_pk is None:
            site = self.get_default_site()
            if site is None:
                raise Http404("No sites configured")
            return site

        return get_object_or_404(Site, pk=site_pk)


class IndexView(AnalyticsSiteMixin, TemplateView):
    template_name = "wagtail_umami_analytics/index.html"

    def _umami_configured(self):
        if not getattr(settings, "UMAMI_API_BASE", None):
            return False
        if not getattr(settings, "UMAMI_API_KEY", None) and not (
            getattr(settings, "UMAMI_USERNAME", None)
            and getattr(settings, "UMAMI_PASSWORD", None)
        ):
            return False
        if not self.website_id:
            return False
        return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sites = self.get_available_sites()
        site_switcher = None

        if len(sites) > 1:
            site_switcher = AnalyticsSiteSwitchForm(
                self.site, self.settings_model, sites=sites
            )

        context.update(
            {
                "site": self.site,
                "site_switcher": site_switcher,
                "umami_configured": self._umami_configured(),
            }
        )
        return context


class AnalyticsJsonView(AnalyticsSiteMixin, View):
    error_message = "Failed to fetch data from Umami"

    def get(self, request, *args, **kwargs):
        try:
            return JsonResponse(self.get_response_data())
        except UmamiClientError:
            logger.exception(self.error_message)
            return _umami_unavailable_response()

    def get_response_data(self):
        raise NotImplementedError


class ActiveUsersView(AnalyticsJsonView):
    error_message = "Failed to fetch active users from Umami"

    def get_response_data(self):
        return {"active_users": get_active_users(self.website_id)}


class StatsView(AnalyticsJsonView):
    error_message = "Failed to fetch stats from Umami"

    def get_response_data(self):
        return {"stats": get_stats(self.website_id).to_dict()}


class MetricsView(AnalyticsJsonView):
    error_message = "Failed to fetch metrics from Umami"

    def get_response_data(self):
        metrics = get_metrics(self.website_id)
        metrics_response = {
            key: [metric.to_dict() for metric in value]
            for key, value in metrics.items()
        }
        return {"metrics": metrics_response}


class UmamiAnalyticsViewSet(ViewSet):
    add_to_admin_menu = True
    menu_label = "Analytics"
    icon = "desktop"
    name = "analytics"

    def get_urlpatterns(self):
        return [
            path("", IndexView.as_view(), name="index"),
            path("<int:site_pk>/", IndexView.as_view(), name="index_for_site"),
            path(
                "<int:site_pk>/active_users/",
                ActiveUsersView.as_view(),
                name="active_users",
            ),
            path("<int:site_pk>/stats/", StatsView.as_view(), name="stats"),
            path("<int:site_pk>/metrics/", MetricsView.as_view(), name="metrics"),
        ]
