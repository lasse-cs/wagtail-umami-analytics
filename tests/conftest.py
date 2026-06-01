import pytest

from django.conf import settings

from wagtail import hooks
from wagtail.contrib.settings.models import register_setting as wagtail_register_setting
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import Locale, Page, Site

from wagtail_factories import SiteFactory

from wagtail_umami_analytics.client import UmamiClient
from wagtail_umami_analytics.models import UmamiAnalyticsSetting
from wagtail_umami_analytics.views import UmamiAnalyticsViewSet


@pytest.fixture(scope="session")
def register_viewset():
    with hooks.register_temporarily(
        "register_admin_viewset", lambda: UmamiAnalyticsViewSet()
    ):
        yield


@pytest.fixture(scope="session")
def register_setting():
    wagtail_register_setting(UmamiAnalyticsSetting)


@pytest.fixture
def site():
    # Ensure that all site and page objects are deleted.
    # Wagtail will initially create ones, but we don't
    # want those
    Site.objects.all().delete()
    Page.objects.all().delete()

    # We also need a Locale
    language_code = get_supported_content_language_variant(settings.LANGUAGE_CODE)
    Locale.objects.get_or_create(language_code=language_code)

    yield SiteFactory(is_default_site=True)


@pytest.fixture
def umami_api_base():
    return "https://test.umami.is/api/"


@pytest.fixture
def umami_api_key():
    return "api_key"


@pytest.fixture
def website_id():
    return "website_id"


@pytest.fixture
def umami_client(umami_api_base, website_id):
    with UmamiClient(umami_api_base, website_id=website_id) as client:
        yield client


@pytest.fixture
def umami_api_client(umami_client, umami_api_key):
    umami_client.set_api_key(umami_api_key)
    yield umami_client


@pytest.fixture
def configured_umami_settings(settings, umami_api_base, umami_api_key):
    settings.UMAMI_API_BASE = umami_api_base
    settings.UMAMI_API_KEY = umami_api_key
    return settings
