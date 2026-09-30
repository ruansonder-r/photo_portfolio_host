import os
import re
from urllib.parse import quote

from django.utils import timezone

# wa.me needs the number in international format with no +, spaces or dashes.
WHATSAPP_GREETING = "Hi Ruan, I'd like to enquire about a shoot."


def _whatsapp(raw: str) -> tuple[str, str]:
    """Return (display number, wa.me link) for a raw phone number."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return "", ""
    return raw.strip(), f"https://wa.me/{digits}?text={quote(WHATSAPP_GREETING)}"


def site_info(request):
    """Site-wide identity, overridable by environment without a code change."""
    whatsapp_display, whatsapp_url = _whatsapp(
        os.environ.get("PHOTOGRAPHER_WHATSAPP", "+27 82 813 9850")
    )
    return {
        "PHOTOGRAPHER_WHATSAPP": whatsapp_display,
        "WHATSAPP_URL": whatsapp_url,
        # Path only: a canonical URL carrying whatever query string the visitor
        # arrived with tells crawlers every variant is its own canonical page.
        "canonical_url": request.build_absolute_uri(request.path),
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
