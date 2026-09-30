from django import template

register = template.Library()


@register.filter
def at_most(value, cap):
    """min(value, cap), for capping masonry columns at the photo count.

    A three-photo gallery laid out in four columns leaves an empty one; this
    keeps the column count from exceeding the number of photos.
    """
    try:
        return min(int(value), int(cap))
    except (TypeError, ValueError):
        return cap
