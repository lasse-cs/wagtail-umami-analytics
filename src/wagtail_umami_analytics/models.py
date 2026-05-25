from django.db import models

from wagtail.contrib.settings.models import BaseSiteSetting


class UmamiAnalyticsSetting(BaseSiteSetting):
    umami_id = models.CharField("The Umami Website ID", max_length=50, blank=True)
