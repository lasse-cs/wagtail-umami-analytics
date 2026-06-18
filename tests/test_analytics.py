import pytest

from datetime import datetime, timedelta, timezone

from pytest_django.asserts import assertTemplateUsed

import responses

from django.core.cache import cache
from django.urls import reverse

from wagtail.models import Site
from wagtail_factories import SiteFactory
from wagtail_umami_analytics.views import UMAMI_TOKEN_CACHE_KEY

from .factories import UmamiAnalyticsSettingFactory


pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures(
        "register_viewset", "register_setting", "configured_umami_settings"
    ),
]


def _time_range_query_params(now: datetime, days: int = 7) -> dict[str, str]:
    return {
        "startAt": str(int((now - timedelta(days=days)).timestamp() * 1000)),
        "endAt": str(int(now.timestamp() * 1000)),
    }


def _today_query_params(now: datetime) -> dict[str, str]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "startAt": str(int(start.timestamp() * 1000)),
        "endAt": str(int(now.timestamp() * 1000)),
    }


def _stats_response() -> dict[str, int | dict[str, int]]:
    return {
        "pageviews": 10,
        "visitors": 8,
        "visits": 9,
        "bounces": 2,
        "totaltime": 120,
        "comparison": {
            "pageviews": 1,
            "visitors": 1,
            "visits": 1,
            "bounces": 0,
            "totaltime": 10,
        },
    }


def test_can_visit_analytics_dashboard(admin_client, site, website_id):
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    response = admin_client.get(reverse("analytics:index"))
    assert response.status_code == 200


def test_analytics_dashboard_uses_correct_template(admin_client, site, website_id):
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    response = admin_client.get(reverse("analytics:index"))
    assertTemplateUsed(response, "wagtail_umami_analytics/index.html")


def test_analytics_dashboard_returns_404_when_no_site_exists(admin_client):
    Site.objects.all().delete()

    response = admin_client.get(reverse("analytics:index"))

    assert response.status_code == 404


def test_analytics_dashboard_uses_site_specific_fetch_urls(
    admin_client, site, website_id
):
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)

    response = admin_client.get(reverse("analytics:index_for_site", args=[site.pk]))

    content = response.content.decode()
    assert reverse("analytics:active_users", args=[site.pk]) in content
    assert reverse("analytics:stats", args=[site.pk]) in content
    assert reverse("analytics:metrics", args=[site.pk]) in content


def test_analytics_dashboard_displays_site_switcher(admin_client, site, website_id):
    other_site = SiteFactory(hostname="other.example.com", is_default_site=False)
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    UmamiAnalyticsSettingFactory(site=other_site, umami_id="other_website_id")

    response = admin_client.get(
        reverse("analytics:index_for_site", args=[other_site.pk])
    )

    content = response.content.decode()
    assert reverse("analytics:index_for_site", args=[site.pk]) in content
    assert reverse("analytics:index_for_site", args=[other_site.pk]) in content


@responses.activate
def test_active_users_returns_503_when_umami_fails(
    admin_client, site, website_id, umami_api_base
):
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    responses.get(
        f"{umami_api_base}websites/{website_id}/active",
        json={},
        status=500,
    )

    response = admin_client.get(reverse("analytics:active_users", args=[site.pk]))

    assert response.status_code == 503
    assert response.json() == {"error": "Umami is unavailable"}


@responses.activate
def test_active_users_uses_selected_site_settings(admin_client, site, umami_api_base):
    other_site = SiteFactory(hostname="other.example.com", is_default_site=False)
    UmamiAnalyticsSettingFactory(site=site, umami_id="default_website_id")
    UmamiAnalyticsSettingFactory(site=other_site, umami_id="other_website_id")
    responses.get(
        f"{umami_api_base}websites/other_website_id/active",
        json={"visitors": 3},
    )

    response = admin_client.get(reverse("analytics:active_users", args=[other_site.pk]))

    assert response.status_code == 200
    assert response.json() == {"active_users": 3}


@responses.activate
def test_active_users_reuses_cached_login_token(
    admin_client, settings, site, website_id, umami_api_base
):
    cache.clear()
    settings.UMAMI_API_KEY = None
    settings.UMAMI_USERNAME = "admin"
    settings.UMAMI_PASSWORD = "umami"
    other_site = SiteFactory(hostname="other.example.com", is_default_site=False)
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    UmamiAnalyticsSettingFactory(site=other_site, umami_id="other_website_id")
    token = "Token"
    responses.post(f"{umami_api_base}auth/login", json={"token": token})
    responses.get(
        f"{umami_api_base}websites/{website_id}/active",
        json={"visitors": 3},
        match=[responses.matchers.header_matcher({"Authorization": f"Bearer {token}"})],
    )
    responses.get(
        f"{umami_api_base}websites/other_website_id/active",
        json={"visitors": 5},
        match=[responses.matchers.header_matcher({"Authorization": f"Bearer {token}"})],
    )

    first_response = admin_client.get(reverse("analytics:active_users", args=[site.pk]))
    second_response = admin_client.get(
        reverse("analytics:active_users", args=[other_site.pk])
    )

    assert first_response.status_code == 200
    assert first_response.json() == {"active_users": 3}
    assert second_response.status_code == 200
    assert second_response.json() == {"active_users": 5}
    login_calls = [
        call
        for call in responses.calls
        if call.request.url == f"{umami_api_base}auth/login"
    ]
    assert len(login_calls) == 1


@responses.activate
def test_active_users_refreshes_stale_cached_login_token(
    admin_client, settings, site, website_id, umami_api_base
):
    cache.clear()
    settings.UMAMI_API_KEY = None
    settings.UMAMI_USERNAME = "admin"
    settings.UMAMI_PASSWORD = "umami"
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    cache.set(UMAMI_TOKEN_CACHE_KEY, "StaleToken")
    responses.get(
        f"{umami_api_base}websites/{website_id}/active",
        json={"error": "Unauthorized"},
        status=401,
        match=[
            responses.matchers.header_matcher({"Authorization": "Bearer StaleToken"})
        ],
    )
    responses.post(f"{umami_api_base}auth/login", json={"token": "FreshToken"})
    responses.get(
        f"{umami_api_base}websites/{website_id}/active",
        json={"visitors": 3},
        match=[
            responses.matchers.header_matcher({"Authorization": "Bearer FreshToken"})
        ],
    )

    response = admin_client.get(reverse("analytics:active_users", args=[site.pk]))

    assert response.status_code == 200
    assert response.json() == {"active_users": 3}
    assert cache.get(UMAMI_TOKEN_CACHE_KEY) == "FreshToken"


@responses.activate
def test_stats_returns_503_when_umami_fails(
    admin_client,
    time_machine,
    site,
    website_id,
    umami_api_base,
):
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    now = datetime(2026, 1, 10, 8, tzinfo=timezone.utc)
    time_machine.move_to(now)

    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        json={},
        status=500,
        match=[responses.matchers.query_param_matcher(_time_range_query_params(now))],
    )

    response = admin_client.get(reverse("analytics:stats", args=[site.pk]))

    assert response.status_code == 503
    assert response.json() == {"error": "Umami is unavailable"}


@responses.activate
def test_stats_uses_selected_time_range(
    admin_client,
    time_machine,
    site,
    website_id,
    umami_api_base,
):
    cache.clear()
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    now = datetime(2026, 1, 10, 8, tzinfo=timezone.utc)
    time_machine.move_to(now)

    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        json=_stats_response(),
        match=[
            responses.matchers.query_param_matcher(
                _time_range_query_params(now, days=30)
            )
        ],
    )

    response = admin_client.get(
        reverse("analytics:stats", args=[site.pk]), {"range": "30d"}
    )

    assert response.status_code == 200
    assert response.json()["stats"]["pageviews"] == 10


@responses.activate
def test_stats_today_time_range_starts_at_midnight(
    admin_client,
    time_machine,
    site,
    website_id,
    umami_api_base,
):
    cache.clear()
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    now = datetime(2026, 1, 10, 8, 30, tzinfo=timezone.utc)
    time_machine.move_to(now)

    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        json=_stats_response(),
        match=[responses.matchers.query_param_matcher(_today_query_params(now))],
    )

    response = admin_client.get(
        reverse("analytics:stats", args=[site.pk]), {"range": "today"}
    )

    assert response.status_code == 200
    assert response.json()["stats"]["pageviews"] == 10


@responses.activate
def test_metrics_returns_503_when_umami_fails(
    admin_client,
    time_machine,
    site,
    website_id,
    umami_api_base,
):
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    now = datetime(2026, 1, 10, 8, tzinfo=timezone.utc)
    time_machine.move_to(now)
    time_range_params = _time_range_query_params(now)

    response_url = f"{umami_api_base}websites/{website_id}/metrics"
    responses.get(
        response_url,
        json=[{"x": "path", "y": 1}],
        match=[
            responses.matchers.query_param_matcher(
                {**time_range_params, "type": "path", "limit": "10"}
            )
        ],
    )
    responses.get(
        response_url,
        json={},
        status=500,
        match=[
            responses.matchers.query_param_matcher(
                {
                    **time_range_params,
                    "type": "referrer",
                    "limit": "10",
                }
            )
        ],
    )
    responses.get(
        response_url,
        json=[{"x": "country", "y": 1}],
        match=[
            responses.matchers.query_param_matcher(
                {
                    **time_range_params,
                    "type": "country",
                    "limit": "10",
                }
            )
        ],
    )

    response = admin_client.get(reverse("analytics:metrics", args=[site.pk]))

    assert response.status_code == 503
    assert response.json() == {"error": "Umami is unavailable"}


@responses.activate
def test_metrics_uses_selected_time_range(
    admin_client,
    time_machine,
    site,
    website_id,
    umami_api_base,
):
    cache.clear()
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    now = datetime(2026, 1, 10, 8, tzinfo=timezone.utc)
    time_machine.move_to(now)
    time_range_params = _time_range_query_params(now, days=30)

    response_url = f"{umami_api_base}websites/{website_id}/metrics"
    responses.get(
        response_url,
        json=[{"x": "path", "y": 1}],
        match=[
            responses.matchers.query_param_matcher(
                {**time_range_params, "type": "path", "limit": "10"}
            )
        ],
    )
    responses.get(
        response_url,
        json=[{"x": "referrer", "y": 2}],
        match=[
            responses.matchers.query_param_matcher(
                {**time_range_params, "type": "referrer", "limit": "10"}
            )
        ],
    )
    responses.get(
        response_url,
        json=[{"x": "country", "y": 3}],
        match=[
            responses.matchers.query_param_matcher(
                {**time_range_params, "type": "country", "limit": "10"}
            )
        ],
    )

    response = admin_client.get(
        reverse("analytics:metrics", args=[site.pk]), {"range": "30d"}
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["paths"] == [{"x": "path", "y": 1}]
