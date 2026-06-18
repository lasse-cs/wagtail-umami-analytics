from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
import logging
from typing import TypeVar

from django.conf import settings
from django import forms
from django.core.cache import cache
from django.db import models
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, View
from wagtail.admin.views.generic import WagtailAdminTemplateMixin
from wagtail.admin.viewsets.base import ViewSet
from wagtail.contrib.settings.forms import SiteSwitchForm
from wagtail.models import Site

from wagtail_umami_analytics.client import (
    Metric,
    MetricType,
    Stats,
    UmamiAPIError,
    UmamiClient,
    UmamiClientError,
)
from wagtail_umami_analytics.models import UmamiAnalyticsSetting


logger = logging.getLogger(__name__)

UMAMI_TOKEN_CACHE_KEY = "wagtail_umami_analytics:token"
UMAMI_TOKEN_CACHE_TIMEOUT = 60 * 60


class TimeRange(models.TextChoices):
    TODAY = "today", "Today"
    LAST_7_DAYS = "7d", "Last 7 days"
    LAST_30_DAYS = "30d", "Last 30 days"


DEFAULT_TIME_RANGE = TimeRange.LAST_7_DAYS

T = TypeVar("T")


class TimeRangeForm(forms.Form):
    range = forms.ChoiceField(
        choices=TimeRange.choices,
        initial=DEFAULT_TIME_RANGE,
        required=False,
        label="Time range",
    )

    def clean_range(self):
        return self.cleaned_data["range"] or DEFAULT_TIME_RANGE


class TimeRangeRedirectForm(forms.Form):
    range = forms.ChoiceField(
        choices=(),
        label="Time range",
        widget=forms.Select(
            attrs={
                "data-controller": "w-action",
                "data-action": "change->w-action#redirect",
            }
        ),
    )


def _login_and_cache_token(client: UmamiClient) -> str:
    token = client.login(settings.UMAMI_USERNAME, settings.UMAMI_PASSWORD)
    cache.set(
        UMAMI_TOKEN_CACHE_KEY,
        token,
        timeout=getattr(
            settings, "UMAMI_TOKEN_CACHE_TIMEOUT", UMAMI_TOKEN_CACHE_TIMEOUT
        ),
    )
    return token


def _get_client() -> UmamiClient:
    client = UmamiClient(base_url=getattr(settings, "UMAMI_API_BASE", None))
    if getattr(settings, "UMAMI_API_KEY", None):
        client.set_api_key(api_key=getattr(settings, "UMAMI_API_KEY", None))
    else:
        token = cache.get(UMAMI_TOKEN_CACHE_KEY)
        if token is None:
            _login_and_cache_token(client)
        else:
            client.set_bearer_token(token)
    return client


def _call_umami(client: UmamiClient, callback: Callable[[UmamiClient], T]) -> T:
    try:
        return callback(client)
    except UmamiAPIError as e:
        if client.uses_api_key() or e.status_code not in (401, 403):
            raise

        cache.delete(UMAMI_TOKEN_CACHE_KEY)
        _login_and_cache_token(client)
        return callback(client)


def _get_time_range(time_range: str = DEFAULT_TIME_RANGE) -> tuple[int, int]:
    now = timezone.now().replace(microsecond=0)

    match time_range:
        case TimeRange.TODAY:
            start = timezone.localtime(now).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        case TimeRange.LAST_30_DAYS:
            start = now - timedelta(days=30)
        case TimeRange.LAST_7_DAYS:
            start = now - timedelta(days=7)
        case _:
            raise ValueError(f"Unsupported time range: {time_range}")

    return int(start.timestamp() * 1000), int(now.timestamp() * 1000)


def _fetch_stats(start_at: int, end_at: int, website_id: str) -> Stats:
    with _get_client() as client:
        return _call_umami(
            client,
            lambda client: client.stats(start_at, end_at, website_id=website_id),
        )


def _fetch_metrics(
    start_at: int, end_at: int, metric_type: MetricType, website_id: str
) -> list[Metric]:
    with _get_client() as client:
        return _call_umami(
            client,
            lambda client: client.metrics(
                start_at, end_at, metric_type, limit=10, website_id=website_id
            ),
        )


def get_active_users(website_id: str) -> int:
    cache_key = f"analytics:active_users:{website_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    with _get_client() as client:
        active = _call_umami(
            client,
            lambda client: client.active_users(website_id=website_id),
        )
    cache.set(cache_key, active, timeout=300)
    return active


def get_stats(website_id: str, time_range: str = DEFAULT_TIME_RANGE) -> Stats:
    cache_key = f"analytics:stats:{website_id}:{time_range}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    start_at, end_at = _get_time_range(time_range)
    stats = _fetch_stats(start_at, end_at, website_id)
    if stats:
        cache.set(cache_key, stats)
    return stats


def get_metrics(
    website_id: str, time_range: str = DEFAULT_TIME_RANGE
) -> dict[str, list[Metric]]:
    cache_key = f"analytics:stats_metrics:{website_id}:{time_range}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    start_at, end_at = _get_time_range(time_range)

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


class TimeRangeMixin:
    def get_time_range(self):
        form = TimeRangeForm(self.request.GET)
        if form.is_valid():
            return form.cleaned_data["range"]

        return DEFAULT_TIME_RANGE

    def get_time_range_form(self):
        selected_range = self.get_time_range()
        choices = []
        selected_url = None

        for value, label in TimeRange.choices:
            query = self.request.GET.copy()
            query["range"] = value
            url = f"{self.request.path}?{query.urlencode()}"
            choices.append((url, label))
            if value == selected_range:
                selected_url = url

        form = TimeRangeRedirectForm(initial={"range": selected_url})
        form.fields["range"].choices = choices
        return form


class IndexView(
    TimeRangeMixin, AnalyticsSiteMixin, WagtailAdminTemplateMixin, TemplateView
):
    page_title = "Umami Analytics"
    header_icon = "desktop"
    template_name = "wagtail_umami_analytics/index.html"

    def get_breadcrumbs_items(self):
        site = self.get_site()
        return [
            *WagtailAdminTemplateMixin.breadcrumbs_items,
            {
                "url": reverse_lazy("analytics:index_for_site", args=[site.pk]),
                "label": "Umami Analytics",
            },
        ]

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
                "time_range_form": self.get_time_range_form(),
                "time_range": self.get_time_range(),
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


class StatsView(TimeRangeMixin, AnalyticsJsonView):
    error_message = "Failed to fetch stats from Umami"

    def get_response_data(self):
        return {"stats": get_stats(self.website_id, self.get_time_range()).to_dict()}


class MetricsView(TimeRangeMixin, AnalyticsJsonView):
    error_message = "Failed to fetch metrics from Umami"

    def get_response_data(self):
        metrics = get_metrics(self.website_id, self.get_time_range())
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
