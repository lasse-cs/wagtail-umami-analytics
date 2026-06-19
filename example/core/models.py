from wagtail.models import Page

from wagtail_umami_analytics.panels import UmamiAnalyticsPanel


class ContentPage(Page):
    content_panels = Page.content_panels + [
        UmamiAnalyticsPanel(),
    ]
