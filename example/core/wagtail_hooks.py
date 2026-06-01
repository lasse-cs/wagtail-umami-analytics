from wagtail import hooks

from wagtail.contrib.settings.models import register_setting
from wagtail_umami_analytics.models import UmamiAnalyticsSetting

from wagtail_umami_analytics.views import UmamiAnalyticsViewSet


register_setting(UmamiAnalyticsSetting)


@hooks.register("register_admin_viewset")
def register_umami_dashboard():
    return UmamiAnalyticsViewSet()
