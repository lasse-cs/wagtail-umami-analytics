import pytest

from wagtail_umami_analytics.templatetags.umami_analytics_tags import (
    umami_analytics_tracker,
)

from .factories import UmamiAnalyticsSettingFactory


pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("register_viewset", "register_setting"),
]


def test_valid_analytics(site, website_id, settings, rf):
    settings.UMAMI_HOST = "http://localhost:3000/"
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    context = {"request": rf.get("/", headers={"host": site.hostname})}
    result = umami_analytics_tracker(context)
    assert (
        result
        == f'<script defer src="http://localhost:3000/script.js" data-website-id="{website_id}"></script>'
    )


def test_no_umami_host(site, website_id, settings, rf):
    settings.UMAMI_HOST = ""
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    context = {"request": rf.get("/", headers={"host": site.hostname})}
    result = umami_analytics_tracker(context)
    assert result == ""


def test_no_umami_id(site, settings, rf):
    settings.UMAMI_HOST = "http://localhost:3000/"
    UmamiAnalyticsSettingFactory(site=site, umami_id="")
    context = {"request": rf.get("/", headers={"host": site.hostname})}
    result = umami_analytics_tracker(context)
    assert result == ""


def test_in_preview(site, website_id, settings, rf):
    settings.UMAMI_HOST = "http://localhost:3000/"
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    request = rf.get("/", headers={"host": site.hostname})
    request.is_preview = True
    context = {"request": request}
    result = umami_analytics_tracker(context)
    assert result == ""


def test_in_pattern_library(site, website_id, settings, rf):
    settings.UMAMI_HOST = "http://localhost:3000/"
    UmamiAnalyticsSettingFactory(site=site, umami_id=website_id)
    request = rf.get("/", headers={"host": site.hostname})
    context = {"request": request, "is_pattern_library": True}
    result = umami_analytics_tracker(context)
    assert result == ""
