from datetime import datetime, timedelta, timezone

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse

import pytest
import responses
from wagtail.models import Page, Site
from wagtail_factories import PageFactory

from wagtail_umami_analytics.panels import UmamiAnalyticsPanel

from .factories import UmamiAnalyticsSettingFactory


pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("configured_umami_settings"),
]


def _time_range_query_params(now: datetime, days: int = 30) -> dict[str, str]:
    return {
        "startAt": str(int((now - timedelta(days=days)).timestamp() * 1000)),
        "endAt": str(int(now.timestamp() * 1000)),
        "path": "/about/",
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


def _make_page(site, *, title="About", slug="about", live=True):
    return PageFactory(parent=site.root_page, title=title, slug=slug, live=live)


@responses.activate
def test_page_analytics_stats_view_returns_filtered_page_stats(
    admin_client,
    time_machine,
    site,
    website_id,
    umami_api_base,
):
    cache.clear()
    page = _make_page(site)
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    now = datetime(2026, 1, 10, 8, tzinfo=timezone.utc)
    time_machine.move_to(now)
    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        json=_stats_response(),
        match=[responses.matchers.query_param_matcher(_time_range_query_params(now))],
    )

    response = admin_client.get(
        reverse("wagtail_umami_page_analytics_stats", kwargs={"page_id": page.pk})
    )

    assert response.status_code == 200
    assert response.json() == {
        "path": "/about/",
        "range": "30d",
        "stats": _stats_response(),
    }


def test_page_analytics_stats_view_requires_edit_permission(
    client, django_user_model, site
):
    page = _make_page(site)
    user = django_user_model.objects.create_user(username="editor")
    user.user_permissions.add(Permission.objects.get(codename="access_admin"))
    client.force_login(user)

    response = client.get(
        reverse("wagtail_umami_page_analytics_stats", kwargs={"page_id": page.pk})
    )

    assert response.status_code == 403


def test_page_analytics_stats_view_rejects_invalid_time_range(admin_client, site):
    page = _make_page(site)

    response = admin_client.get(
        reverse("wagtail_umami_page_analytics_stats", kwargs={"page_id": page.pk}),
        {"range": "90d"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_time_range"


def test_page_analytics_stats_view_rejects_non_live_pages(admin_client, site):
    page = _make_page(site, live=False)

    response = admin_client.get(
        reverse("wagtail_umami_page_analytics_stats", kwargs={"page_id": page.pk})
    )

    assert response.status_code == 400
    assert response.json()["error"] == "not_live"


def test_page_analytics_stats_view_requires_site_configuration(admin_client, site):
    page = _make_page(site)

    response = admin_client.get(
        reverse("wagtail_umami_page_analytics_stats", kwargs={"page_id": page.pk})
    )

    assert response.status_code == 400
    assert response.json()["error"] == "not_configured"


@responses.activate
def test_page_analytics_stats_view_returns_503_when_umami_fails(
    admin_client,
    time_machine,
    site,
    website_id,
    umami_api_base,
):
    cache.clear()
    page = _make_page(site)
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    now = datetime(2026, 1, 10, 8, tzinfo=timezone.utc)
    time_machine.move_to(now)
    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        json={},
        status=500,
        match=[responses.matchers.query_param_matcher(_time_range_query_params(now))],
    )

    response = admin_client.get(
        reverse("wagtail_umami_page_analytics_stats", kwargs={"page_id": page.pk})
    )

    assert response.status_code == 503
    assert response.json() == {"error": "Umami is unavailable"}


@responses.activate
def test_page_analytics_stats_view_uses_page_site_settings(
    admin_client,
    time_machine,
    site,
    umami_api_base,
):
    cache.clear()
    other_root = PageFactory(
        parent=site.root_page, title="Other root", slug="other-root"
    )
    other_site = Site.objects.create(
        hostname="other.example.com",
        root_page=other_root,
        is_default_site=False,
    )
    page = _make_page(other_site)
    UmamiAnalyticsSettingFactory(site=site, umami_id="default_website_id")
    UmamiAnalyticsSettingFactory(site=other_site, umami_id="other_website_id")
    now = datetime(2026, 1, 10, 8, tzinfo=timezone.utc)
    time_machine.move_to(now)
    responses.get(
        f"{umami_api_base}websites/other_website_id/stats",
        json=_stats_response(),
        match=[responses.matchers.query_param_matcher(_time_range_query_params(now))],
    )

    response = admin_client.get(
        reverse("wagtail_umami_page_analytics_stats", kwargs={"page_id": page.pk})
    )

    assert response.status_code == 200
    assert response.json()["stats"]["pageviews"] == 10


def _render_panel(page):
    request = RequestFactory().get("/admin/")
    panel = UmamiAnalyticsPanel().bind_to_model(Page)
    return panel.get_bound_panel(
        instance=page, request=request, form=None
    ).render_html()


def test_umami_analytics_panel_renders_unsaved_page_message():
    html = _render_panel(Page(title="New page", slug="new-page"))

    assert "Analytics are available for published pages." in html
    assert "data-content-loader-url-value" not in html


def test_umami_analytics_panel_renders_non_live_page_message(site):
    page = _make_page(site, live=False)

    html = _render_panel(page)

    assert "Analytics are available for published pages." in html
    assert "data-content-loader-url-value" not in html


def test_umami_analytics_panel_renders_live_page_loader(site):
    page = _make_page(site)

    html = _render_panel(page)

    assert "Last 30 days" in html
    assert 'data-controller="content-loader page-analytics-panel"' in html
    assert (
        reverse("wagtail_umami_page_analytics_stats", kwargs={"page_id": page.pk})
        in html
    )
    assert "range=30d" in html


def test_umami_analytics_panel_validates_time_range():
    with pytest.raises(ValueError, match="Unsupported time_range"):
        UmamiAnalyticsPanel(time_range="90d")
