import os

from django.utils import timezone


def site_info(request):
    """Site-wide identity, overridable by environment without a code change."""
    return {
        "PHOTOGRAPHER_NAME": os.environ.get("PHOTOGRAPHER_NAME", "Ruan Sonder"),
        "PHOTOGRAPHER_HANDLE": os.environ.get("PHOTOGRAPHER_HANDLE", "ruansonder_R"),
        "PHOTOGRAPHER_EMAIL": os.environ.get("PHOTOGRAPHER_EMAIL", "ruansonder.r@gmail.com"),
        "PHOTOGRAPHER_LOCATION": os.environ.get("PHOTOGRAPHER_LOCATION", "Cape Town, South Africa"),
        "INSTAGRAM_URL": os.environ.get("INSTAGRAM_URL", "https://instagram.com/ruansonder_R"),
        "CURRENT_YEAR": timezone.now().year,
    }
