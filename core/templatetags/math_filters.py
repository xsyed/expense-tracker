import math
from django import template

register = template.Library()


@register.filter
def floor(value):
    try:
        return math.floor(float(value))
    except (TypeError, ValueError):
        return value
