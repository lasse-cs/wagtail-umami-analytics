import factory
from factory.django import DjangoModelFactory

from wagtail_factories import SiteFactory

from wagtail_umami_analytics.models import UmamiAnalyticsSetting


class UmamiAnalyticsSettingFactory(DjangoModelFactory):
    site = factory.SubFactory(SiteFactory)
    umami_id = factory.Faker("uuid4")

    class Meta:
        model = UmamiAnalyticsSetting
