import os

from django.utils import timezone


def site_info(request):
    """Site-wide identity, overridable by environment without a code change."""
    return {
        "PHOTOGRAPHER_NAME": os.environ.get("PHOTOGRAPHER_NAME", "Ruansonder_R"),
        "PHOTOGRAPHER_HANDLE": os.environ.get("PHOTOGRAPHER_HANDLE", "ruansonder_R"),
        "PHOTOGRAPHER_EMAIL": os.environ.get("PHOTOGRAPHER_EMAIL", "ruansonder.r@gmail.com"),
        "PHOTOGRAPHER_LOCATION": os.environ.get("PHOTOGRAPHER_LOCATION", "Cape Town, South Africa"),
        "INSTAGRAM_URL": os.environ.get("INSTAGRAM_URL", "https://instagram.com/ruansonder_R"),
        "CURRENT_YEAR": timezone.now().year,
        "default_title": os.environ.get(
            "SITE_TITLE",
            "{name} — Portrait & Wedding Photography, {place}".format(
                name=os.environ.get("PHOTOGRAPHER_NAME", "Ruansonder_R"),
                place=os.environ.get("PHOTOGRAPHER_LOCATION", "Cape Town, South Africa").split(",")[0],
            ),
        ),
        "default_description": os.environ.get(
            "SITE_DESCRIPTION",
            "Portrait, wedding and event photography by {name} in {place}.".format(
                name=os.environ.get("PHOTOGRAPHER_NAME", "Ruansonder_R"),
                place=os.environ.get("PHOTOGRAPHER_LOCATION", "Cape Town, South Africa"),
            ),
        ),
    }
