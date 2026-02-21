from zoneinfo import ZoneInfo
from datetime import timezone as dt_timezone

from django import template
from django.utils import timezone

register = template.Library()
IST = ZoneInfo('Asia/Kolkata')


@register.filter
def ist(value):
    if not value:
        return value
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return timezone.localtime(value, IST)


@register.filter
def dict_get(d, key):
    """Return d[key] or an empty list if key is missing."""
    if not d:
        return []
    return d.get(key, [])


@register.filter
def sub(value, arg):
    """Subtract arg from value (int - int)."""
    try:
        return int(value) - int(arg)
    except (TypeError, ValueError):
        return 0
