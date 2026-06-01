from django import template
from django.conf import settings
from django.utils.html import format_html

from wagtail_umami_analytics.models import UmamiAnalyticsSetting

register = template.Library()


@register.simple_tag(takes_context=True)
def umami_analytics_tracker(context):
    if "request" not in context:
        return ""
    if getattr(context["request"], "is_preview", False):
        return ""
    if context.get("is_pattern_library", False):
        return ""
    try:
        analytics_settings = UmamiAnalyticsSetting.for_request(
            request=context["request"]
        )
    except Exception:
        return ""
    umami_host = getattr(settings, "UMAMI_HOST", None)
    if not umami_host or not analytics_settings.umami_id:
        return ""
    umami_script = umami_host.rstrip("/") + "/script.js"
    return format_html(
        '<script defer src="{}" data-website-id="{}"></script>',
        umami_script,
        analytics_settings.umami_id,
    )
