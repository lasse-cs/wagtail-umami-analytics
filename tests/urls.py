from django.urls import include, path

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls

from wagtail_umami_analytics.views import UmamiAnalyticsViewSet


analytics_viewset = UmamiAnalyticsViewSet()

urlpatterns = [
    path("admin/", include(wagtailadmin_urls)),
    path("", include(wagtail_urls)),
]
