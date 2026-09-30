"""Typography, palette and metrics for the document PDF.

The font is defined here and nowhere else. Swapping to the site's Source Code
Pro later is a ``pdfmetrics.registerFont(TTFont(...))`` call plus changing the
two constants below -- nothing else in the renderer names a typeface.

Helvetica is the default deliberately: it is one of the 14 fonts every PDF
viewer ships, so there is no file to bundle, no licence question, and no
rendering difference between viewers. Its digits are all 556/1000 em (and so
are Helvetica-Bold's), which is what makes right-aligned amounts line up on
the decimal point with no font feature at all.
"""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

# --- the one edit point for a font swap ---------------------------------
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

# --- page ---------------------------------------------------------------
PAGE_SIZE = A4  # South Africa. Not Letter.
MARGIN_X = 20 * mm
MARGIN_TOP = 16 * mm
MARGIN_BOTTOM = 22 * mm  # room for the footer band
CONTENT_WIDTH = PAGE_SIZE[0] - 2 * MARGIN_X

# --- ink ----------------------------------------------------------------
# Warm near-black and a warm grey, carried over from the site's tokens
# (--text #171714, --muted #6d6a62) so the PDF reads as the same hand.
# Printed on white: the site's dark theme deliberately does not come along.
INK = colors.HexColor("#1A1A18")
MUTED = colors.HexColor("#75726A")
HAIRLINE = colors.HexColor("#DDD9D1")
PAPER = colors.white

DEFAULT_ACCENT = "#8A3324"


class Palette:
    """The single accent, resolved per document from its snapshot.

    Used in exactly three places -- the masthead rule, the rule under the
    table header, and the total. The old invoice used three unrelated colours
    (purple name, navy heading, pink date and total); one colour used three
    times is the fix.
    """

    def __init__(self, accent: str | None = None):
        try:
            self.accent = colors.HexColor(accent or DEFAULT_ACCENT)
        except (ValueError, AttributeError):
            # A malformed hex in settings must not take the invoice down.
            self.accent = colors.HexColor(DEFAULT_ACCENT)


# --- type scale ---------------------------------------------------------
# Hierarchy comes from size, weight and letterspacing. Two faces, no more.

TITLE = ParagraphStyle(
    "title", fontName=FONT_BOLD, fontSize=27, leading=29, textColor=INK,
)
BUSINESS_NAME = ParagraphStyle(
    "businessName", fontName=FONT_BOLD, fontSize=12.5, leading=15, textColor=INK,
)
BODY = ParagraphStyle(
    "body", fontName=FONT_REGULAR, fontSize=9, leading=12.5, textColor=INK,
)
BODY_MUTED = ParagraphStyle(
    "bodyMuted", parent=BODY, fontSize=8.5, leading=12, textColor=MUTED,
)
# The banking block: small enough that it reads as reference matter rather
# than competing with the line items, which is what it did before.
FINE = ParagraphStyle(
    "fine", fontName=FONT_REGULAR, fontSize=7.8, leading=10.5, textColor=INK,
)
FINE_MUTED = ParagraphStyle(
    "fineMuted", parent=FINE, textColor=MUTED,
)
CELL = ParagraphStyle(
    "cell", fontName=FONT_REGULAR, fontSize=8.8, leading=12, textColor=INK,
    alignment=TA_LEFT,
)
CELL_RIGHT = ParagraphStyle(
    "cellRight", parent=CELL, alignment=TA_RIGHT,
)
NUMBER_LARGE = ParagraphStyle(
    "numberLarge", fontName=FONT_BOLD, fontSize=13, leading=16, textColor=INK,
)


class Label(Flowable):
    """A small uppercase letterspaced caption.

    ReportLab's ParagraphStyle carries no tracking, and inserting spacer
    glyphs between letters would break copy-paste out of the finished PDF.
    Drawing through ``canvas.setCharSpace`` is the honest way to get it.
    """

    def __init__(
        self,
        text: str,
        *,
        size: float = 6.4,
        tracking: float = 1.15,
        colour=MUTED,
        font: str = FONT_BOLD,
        align: str = "left",
    ):
        super().__init__()
        self.text = (text or "").upper()
        self.size = size
        self.tracking = tracking
        self.colour = colour
        self.font = font
        self.align = align
        self.width = 0.0
        self.height = size * 1.55

    def wrap(self, available_width, available_height):
        self.width = available_width
        return self.width, self.height

    def text_width(self) -> float:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        base = stringWidth(self.text, self.font, self.size)
        # Tracking sits after every glyph; the trailing one adds advance but
        # no ink, so ignore it when aligning to a right edge.
        return base + self.tracking * max(len(self.text) - 1, 0)

    def draw(self):
        # Tracking lives on the text object, not the canvas -- Canvas has no
        # setCharSpace.
        x = self.width - self.text_width() if self.align == "right" else 0
        text = self.canv.beginText(x, self.height - self.size)
        text.setFont(self.font, self.size)
        text.setFillColor(self.colour)
        text.setCharSpace(self.tracking)
        text.textOut(self.text)
        self.canv.drawText(text)


class Rule(Flowable):
    """A horizontal rule. Hairline by default -- never a heavy border."""

    def __init__(self, *, colour=HAIRLINE, thickness: float = 0.5, width: float | None = None,
                 space_before: float = 0, space_after: float = 0):
        super().__init__()
        self.colour = colour
        self.thickness = thickness
        self._fixed_width = width
        self.space_before = space_before
        self.space_after = space_after
        self.width = width or 0.0
        self.height = thickness + space_before + space_after

    def wrap(self, available_width, available_height):
        self.width = self._fixed_width or available_width
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(self.colour)
        canvas.setLineWidth(self.thickness)
        y = self.space_after + self.thickness / 2
        canvas.line(0, y, self.width, y)
        canvas.restoreState()
