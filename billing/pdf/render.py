"""Renders a Document to PDF bytes.

Information architecture follows the invoice this replaces -- business
identity top-left, a large title with its date, the "Invoice for" / "Payable
to" / "Invoice #" band, project, line items, then notes beside the totals.
What changed is everything about how it is set.
"""

from __future__ import annotations

import datetime as dt
import io
from xml.sax.saxutils import escape

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import Document, Kind, Status
from ..money import format_money, format_quantity
from .style import (
    BODY,
    BODY_MUTED,
    BUSINESS_NAME,
    CELL,
    CONTENT_WIDTH,
    FINE,
    FINE_MUTED,
    FONT_BOLD,
    FONT_REGULAR,
    HAIRLINE,
    INK,
    MARGIN_BOTTOM,
    MARGIN_TOP,
    MARGIN_X,
    MUTED,
    NUMBER_LARGE,
    PAGE_SIZE,
    TITLE,
    Label,
    Palette,
    Rule,
)


def render_document(document: Document) -> bytes:
    """Build the PDF. Returns bytes; the view decides the disposition."""
    snapshot = document.snapshot
    palette = Palette(snapshot.accent_colour)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=f"{document.title} {document.display_number}".strip(),
        author=snapshot.business.name,
        subject=document.project or document.title,
    )

    story = _build_story(document, snapshot, palette)
    doc.build(
        story,
        onFirstPage=_masthead(palette),
        onLaterPages=_masthead(palette),
        canvasmaker=_canvas_class(snapshot, palette),
    )
    return buffer.getvalue()


# --- page furniture ------------------------------------------------------


def _masthead(palette):
    """The accent rule across the top of every page. Accent use 1 of 3."""

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(palette.accent)
        canvas.setLineWidth(2.2)
        y = PAGE_SIZE[1] - MARGIN_TOP + 6 * mm
        canvas.line(MARGIN_X, y, PAGE_SIZE[0] - MARGIN_X, y)
        canvas.restoreState()

    return draw


def _canvas_class(snapshot, palette):
    """A canvas that knows the page count before it stamps the footer.

    "Page 1 of 3" needs a total that does not exist during the first pass, so
    pages are buffered and the footer drawn on the way out.
    """
    identity = " · ".join(
        part for part in (snapshot.business.name, snapshot.business.phone_display) if part
    )

    class NumberedCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self._draw_footer(total)
                super().showPage()
            super().save()

        def _draw_footer(self, total):
            self.saveState()
            y = MARGIN_BOTTOM - 8 * mm
            self.setStrokeColor(HAIRLINE)
            self.setLineWidth(0.5)
            self.line(MARGIN_X, y + 5 * mm, PAGE_SIZE[0] - MARGIN_X, y + 5 * mm)

            self.setFont(FONT_REGULAR, 7.2)
            self.setFillColor(MUTED)
            self.drawString(MARGIN_X, y, identity)
            self.drawRightString(
                PAGE_SIZE[0] - MARGIN_X, y, f"Page {self._pageNumber} of {total}"
            )
            self.restoreState()

    return NumberedCanvas


# --- content -------------------------------------------------------------


def _build_story(document, snapshot, palette) -> list:
    story: list = []
    story += _identity(snapshot)
    story.append(Spacer(1, 13 * mm))
    story += _title_block(document, palette)
    story.append(Spacer(1, 9 * mm))
    story.append(Rule(space_after=0))
    story.append(Spacer(1, 6 * mm))
    story.append(_band(document, snapshot))
    story.append(Spacer(1, 7 * mm))
    story += _project(document)
    story.append(Spacer(1, 4 * mm))
    story.append(_items_and_totals(document, snapshot, palette))
    return story


def _identity(snapshot) -> list:
    business = snapshot.business
    block = [Paragraph(_esc(business.name), BUSINESS_NAME), Spacer(1, 2.2 * mm)]
    details = [*business.address_lines]
    if business.phone_display:
        details.append(business.phone_display)
    if business.email:
        details.append(business.email)
    if details:
        block.append(Paragraph("<br/>".join(_esc(d) for d in details), BODY_MUTED))
    return block


def _title_block(document, palette) -> list:
    block = [Paragraph(_esc(document.title), TITLE), Spacer(1, 1.5 * mm)]

    meta = f"Issued {_date(document.issue_date)}"
    if document.status == Status.CANCELLED:
        # Said plainly rather than stamped across the page: the number stays
        # valid as a record, the document does not.
        block.append(
            Label("Cancelled", size=8, tracking=1.6, colour=palette.accent)
        )
        block.append(Spacer(1, 1 * mm))
    elif document.is_draft:
        block.append(Label("Draft — not yet issued", size=8, tracking=1.6, colour=MUTED))
        block.append(Spacer(1, 1 * mm))

    block.append(Paragraph(_esc(meta), BODY_MUTED))
    return block


def _band(document, snapshot) -> Table:
    """The three columns, sharing one top baseline.

    In the old invoice "Att: Jazz" and "Customer: Four12" floated with no
    alignment relationship to the columns beside them. Here all three are
    cells of one table, so they cannot drift.
    """
    columns = [_client_column(document, snapshot), _banking_column(snapshot)]
    columns.append(_reference_column(document))

    widths = [CONTENT_WIDTH * 0.35, CONTENT_WIDTH * 0.38, CONTENT_WIDTH * 0.27]
    table = Table([columns], colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _client_column(document, snapshot) -> list:
    client = snapshot.client
    block = [Label(document.client_label), Spacer(1, 1.8 * mm)]
    if client.company:
        block.append(Paragraph(_esc(client.company), _bold(BODY)))
    if client.contact_person:
        block.append(Paragraph(f"Att: {_esc(client.contact_person)}", BODY_MUTED))
    details = [*client.address_lines]
    if client.email:
        details.append(client.email)
    if client.phone_display:
        details.append(client.phone_display)
    if details:
        block.append(Spacer(1, 1.2 * mm))
        block.append(Paragraph("<br/>".join(_esc(d) for d in details), FINE_MUTED))
    if not client.company and not client.contact_person:
        block.append(Paragraph("—", BODY_MUTED))
    return block


def _banking_column(snapshot) -> list:
    """Label/value pairs, empty fields dropped, set small.

    Before, this was a dense unformatted seven-line list that visually
    outweighed the line items. Structure plus a smaller size fixes both.
    """
    rows = snapshot.bank.rows
    if not rows:
        return []

    block = [Label("Payable to"), Spacer(1, 1.8 * mm)]
    table = Table(
        [[Paragraph(_esc(label), FINE_MUTED), Paragraph(_esc(value), FINE)] for label, value in rows],
        colWidths=[CONTENT_WIDTH * 0.38 * 0.42, CONTENT_WIDTH * 0.38 * 0.58],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0.6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6),
            ]
        )
    )
    block.append(table)
    return block


def _reference_column(document) -> list:
    block = [Label(document.number_label), Spacer(1, 1.8 * mm)]
    block.append(Paragraph(_esc(document.display_number or "Draft"), NUMBER_LARGE))

    pairs = []
    if document.kind == Kind.INVOICE and document.due_date:
        pairs.append(("Due", _date(document.due_date)))
    if document.kind == Kind.QUOTE and document.valid_until:
        pairs.append(("Valid until", _date(document.valid_until)))
    if document.snapshot.vat_registered and document.snapshot.vat_number:
        pairs.append(("VAT no.", document.snapshot.vat_number))

    # Stacked label-over-value, the same treatment the number above gets.
    # Side-by-side left a 40pt gap between a short label and its value, which
    # is the same drifting-apart the band itself was built to fix.
    for label, value in pairs:
        block.append(Spacer(1, 2.6 * mm))
        block.append(Label(label))
        block.append(Spacer(1, 1 * mm))
        block.append(Paragraph(_esc(value), FINE))
    return block


def _project(document) -> list:
    if not document.project:
        return []
    return [
        Label("Project"),
        Spacer(1, 1.6 * mm),
        Paragraph(_esc(document.project), BODY),
        Spacer(1, 3 * mm),
    ]


# Description gets the room; the three numeric columns are sized so that the
# widest realistic figure and the longest adjustment label both fit unwrapped.
ITEM_WIDTHS = [CONTENT_WIDTH * w for w in (0.54, 0.09, 0.17, 0.20)]

# How many closing line items travel with the totals. Two is enough to stop a
# total landing on a page of its own without dragging a whole block along.
KEEP_WITH_TOTALS = 2


def _items_and_totals(document, snapshot, palette) -> LongTable:
    """Line items and totals as one table, so neither can be widowed.

    They began as two flowables and, on a long invoice, the totals landed
    alone on a page of their own -- KeepTogether holds a block together but
    cannot hold it to the rows above it. Splitting into head and tail tables
    fixed that but cost the tail its column header. One table with a NOSPLIT
    range over the closing rows gets both: the header repeats on every page,
    and the total always arrives with line items above it.
    """
    return _table(
        [_item_row(line) for line in document.lines.all()],
        palette,
        totals=_totals_rows(document, snapshot),
        notes=_notes(document),
    )


def _item_row(line) -> list:
    return [
        # A Paragraph so a long description wraps inside its column and grows
        # the row, instead of overrunning it.
        Paragraph(_esc(line.description), CELL),
        format_quantity(line.quantity),
        format_money(line.unit_price),
        format_money(line.line_total),
    ]


def _totals_rows(document, snapshot) -> list:
    """Only the lines that carry a figure. No zero adjustment, no VAT row
    when VAT is off."""
    rows = [("Subtotal", format_money(document.subtotal), False)]
    if document.has_adjustment:
        rows.append(
            (document.adjustment_label or "Adjustment",
             format_money(document.adjustment_amount), False)
        )
    if document.shows_vat:
        rows.append(
            (f"VAT @ {format_quantity(snapshot.vat_rate)}%",
             format_money(document.vat_amount), False)
        )
    rows.append(("Total", document.money(document.total), True))
    return rows


def _table(item_rows, palette, *, totals=None, notes=None) -> LongTable:
    rows = [[
        Label("Description"),
        Label("Qty", align="right"),
        Label("Unit price", align="right"),
        Label("Total", align="right"),
    ]]
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, palette.accent),   # accent 2 of 3
    ]

    first_item = len(rows)
    rows += item_rows
    last_item = len(rows) - 1

    if item_rows:
        style += [
            ("TOPPADDING", (0, first_item), (-1, last_item), 7),
            ("BOTTOMPADDING", (0, first_item), (-1, last_item), 7),
            ("LINEBELOW", (0, first_item), (-1, last_item), 0.4, HAIRLINE),
            # Right-aligned numerics. Helvetica's digits are all 556/1000 em,
            # so this alone lands every decimal point on one axis.
            ("ALIGN", (1, first_item), (-1, last_item), "RIGHT"),
            ("FONTNAME", (1, first_item), (-1, last_item), FONT_REGULAR),
            ("FONTSIZE", (1, first_item), (-1, last_item), 8.8),
            ("TEXTCOLOR", (1, first_item), (-1, last_item), INK),
        ]

    if totals:
        gap = len(rows)
        rows.append(["", "", "", ""])
        style += [
            ("TOPPADDING", (0, gap), (-1, gap), 0),
            ("BOTTOMPADDING", (0, gap), (-1, gap), 5),
        ]

        first_total = len(rows)
        for index, (label, value, is_total) in enumerate(totals):
            label_style = _right(_bold(BODY)) if is_total else _right(FINE_MUTED)
            value_style = _accent_total(palette) if is_total else _right(FINE)
            rows.append([
                notes if index == 0 else "",
                Paragraph(_esc(label), label_style),
                "",
                Paragraph(_esc(value), value_style),
            ])
        last_total = len(rows) - 1

        style += [
            # Notes beside the totals, as the brief asks. Column 0 only, so
            # the label can span columns 1-2 and stay on one line.
            ("SPAN", (0, first_total), (0, last_total)),
            ("TOPPADDING", (0, first_total), (-1, last_total), 2.5),
            ("BOTTOMPADDING", (0, first_total), (-1, last_total), 2.5),
            ("TOPPADDING", (1, last_total), (-1, last_total), 6),
            ("LINEABOVE", (1, last_total), (-1, last_total), 0.5, HAIRLINE),
            ("VALIGN", (1, last_total), (-1, last_total), "MIDDLE"),
        ]
        style += [("SPAN", (1, r), (2, r)) for r in range(first_total, last_total + 1)]

        # Widow control: the closing line items and the whole totals block
        # cannot be separated by a page break, so a total never arrives on a
        # page by itself. The header still repeats above them.
        keep_from = max(first_item, last_item - KEEP_WITH_TOTALS + 1)
        style.append(("NOSPLIT", (0, keep_from), (-1, last_total)))

    table = LongTable(rows, colWidths=ITEM_WIDTHS, repeatRows=1)
    table.setStyle(TableStyle(style))
    return table


def _notes(document) -> list:
    """Omitted entirely when empty -- no "Notes:" label with nothing after it."""
    if not document.notes.strip():
        return []
    return [
        Label("Notes"),
        Spacer(1, 1.8 * mm),
        Paragraph(_esc(document.notes).replace("\n", "<br/>"), FINE),
    ]


# --- helpers -------------------------------------------------------------


def _esc(value) -> str:
    return escape(str(value or ""))


def _date(value: dt.date) -> str:
    """26 August 2026. Never 26/08/2026, which means two different days
    depending on who is reading it."""
    return f"{value.day} {value:%B %Y}"


def _bold(style):
    from reportlab.lib.styles import ParagraphStyle

    return ParagraphStyle(f"{style.name}Bold", parent=style, fontName=FONT_BOLD)


def _right(style):
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle

    return ParagraphStyle(f"{style.name}Right", parent=style, alignment=TA_RIGHT)


def _accent_total(palette):
    """Accent use 3 of 3."""
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle

    return ParagraphStyle(
        "accentTotal",
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        alignment=TA_RIGHT,
        textColor=palette.accent,
    )
