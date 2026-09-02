"""Step 9: server-side PDF rendering of a verification report.

Pure presentation layer for :class:`~app.schemas.report.VerificationReport`:
it turns an already-assembled report into a professional PDF document.

Hard rules enforced here
------------------------
* **No raw DNA data.** Only aggregate numbers (classification, match
  percentage, marker counts) ever reach the page — allele values are not even
  part of the report schema, and nothing is looked up in the database.
* **No filesystem paths.** Upload names are reduced to their base name and
  the storage layout is never mentioned.
* **No certainty claims.** Every statement comes from the report payload
  (including the disclaimer and the "not a forensic probability" note), so
  this renderer can never invent legal or forensic language.
* **No new logic.** No scoring, no comparison, no AI call, no ownership
  check — those all happened upstream.

Output is latin-1 safe for the built-in core fonts (typographic dashes,
check marks and cross marks are folded to ASCII equivalents).
"""

from __future__ import annotations

import re
from datetime import datetime

from fpdf import FPDF, XPos, YPos

from app.schemas.report import (
    ReportDecisionSection,
    ReportDnaSection,
    ReportDocumentSection,
    ReportEvidenceSection,
    ReportExtractionSection,
    ReportIdentity,
    VerificationReport,
)

# --- Layout (mm) ---------------------------------------------------------------

PAGE_MARGIN = 15.0
TOP_MARGIN = 16.0
BOTTOM_MARGIN = 18.0
LINE_HEIGHT = 4.4
LABEL_WIDTH = 46.0

# --- Brand palette (matches the frontend Tailwind "brand" scale) --------------

BRAND = (5, 150, 105)  # brand-600
BRAND_DARK = (4, 120, 87)  # brand-700
INK = (17, 24, 39)  # gray-900
MUTED = (107, 114, 128)  # gray-500
RULE = (209, 213, 219)  # gray-300
SOFT_BG = (243, 244, 246)  # gray-100

_BANNERS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "VERIFIED": ((209, 250, 229), (6, 78, 59)),
    "REVIEW_REQUIRED": ((254, 243, 199), (124, 45, 18)),
    "MISMATCH": ((254, 226, 226), (127, 29, 29)),
}
_DEFAULT_BANNER = (SOFT_BG, INK)

# --- Text safety ---------------------------------------------------------------

#: Core PDF fonts are latin-1; fold the pretty characters we use elsewhere.
_FALLBACKS = {
    "\u2014": "-",  # em dash
    "\u2013": "-",  # en dash
    "\u2212": "-",  # minus sign
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2022": "-",  # bullet
    "\u00a0": " ",
    "\u2713": "v",  # check mark
    "\u2714": "v",
    "\u2715": "x",  # cross mark
    "\u00d7": "x",
    "\u2265": ">=",
    "\u2264": "<=",
}
_FALLBACK_TABLE = str.maketrans(_FALLBACKS)


def _safe_text(value: object) -> str:
    """Render any value as latin-1 printable text for the core fonts."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = text.translate(_FALLBACK_TABLE)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Control characters never belong in a report; strip unknown ones too.
    text = "".join(char for char in text if char == "\n" or char.isprintable())
    text = re.sub(r"[^\x09\x0a\x20-\x7e\xa0-\xff]", "", text)
    return text.strip()


def _basename(filename: str | None) -> str:
    """Base name only — a stored path must never appear in a report."""
    if not filename:
        return ""
    return _safe_text(re.split(r"[/\\]", filename)[-1])


#: Code words that must stay uppercase when humanized.
_WORD_ACRONYMS = frozenset({"dna", "cnic", "str", "ai", "id", "pdf"})


def _label(value: str | None) -> str:
    """Turn an enum-ish code into readable words.

    ``REVIEW_REQUIRED`` -> "Review required", ``DNA_REPORT`` -> "DNA report"
    (domain acronyms stay uppercase so the printed report reads naturally).
    """
    if not value:
        return ""
    words = [
        word.upper() if word in _WORD_ACRONYMS else word
        for word in _safe_text(value.replace("_", " ")).lower().split(" ")
    ]
    text = " ".join(words)
    return (text[:1].upper() + text[1:]).strip()


def _fmt_datetime(value: datetime | None) -> str:
    """All stored timestamps are naive UTC, so the label is always correct."""
    return "" if value is None else f"{value.strftime('%d %b %Y %H:%M')} UTC"


def _fmt_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d %b %Y")


def _fmt_size(value: int | None) -> str:
    if value is None:
        return ""
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


def _fmt_percent(value: float | None) -> str:
    return "" if value is None else f"{value:.1f}%"


def _status_line(value: str | None) -> str:
    return _label(value)


# --- PDF canvas ----------------------------------------------------------------


class _ReportPDF(FPDF):
    """A4 portrait document carrying the GeneVerify header/footer furniture."""

    def __init__(self, report: VerificationReport) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.report = report
        self.set_margins(PAGE_MARGIN, TOP_MARGIN, PAGE_MARGIN)
        self.set_auto_page_break(True, margin=BOTTOM_MARGIN)
        self.set_title(f"GeneVerify AI verification report {report.verification_id}")
        self.set_subject("Verification report (research prototype)")
        self.set_author("GeneVerify AI")
        self.set_creator("GeneVerify AI backend")
        self.set_line_width(0.2)

    @property
    def content_width(self) -> float:
        return self.w - 2 * PAGE_MARGIN

    def header(self) -> None:
        self.set_y(7)
        self.set_font("helvetica", "B", 8)
        self.set_text_color(*BRAND_DARK)
        self.cell(self.content_width / 2, 5, "GeneVerify AI - Verification Report")
        self.set_font("helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(
            self.content_width / 2,
            5,
            _safe_text(f"Case {self.report.verification_id}"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.set_draw_color(*RULE)
        rule_y = self.get_y() + 1
        self.line(PAGE_MARGIN, rule_y, self.w - PAGE_MARGIN, rule_y)
        self.set_y(rule_y + 4)
        self.set_text_color(*INK)

    def footer(self) -> None:
        self.set_y(-BOTTOM_MARGIN + 3)
        self.set_draw_color(*RULE)
        self.line(PAGE_MARGIN, self.get_y(), self.w - PAGE_MARGIN, self.get_y())
        self.set_font("helvetica", "", 7)
        self.set_text_color(*MUTED)
        self.cell(self.content_width / 2, 4, "Prototype report - not a forensic identification system")
        self.cell(self.content_width / 2, 4, f"Page {self.page_no()}", align="R")


# --- Building blocks ------------------------------------------------------------


def _ensure_space(pdf: _ReportPDF, needed: float) -> None:
    """Manual page break so blocks are never split awkwardly."""
    if pdf.get_y() + needed > pdf.page_break_trigger:
        pdf.add_page()


def _heading(pdf: _ReportPDF, number: int, title: str, reserve: float = 24.0) -> None:
    """Section title bar.

    ``reserve`` is the space required for the heading *plus* the block that
    follows it, so a title never dangles at the bottom of a page.
    """
    _ensure_space(pdf, reserve)
    y = pdf.get_y()
    pdf.set_fill_color(*BRAND)
    pdf.rect(PAGE_MARGIN, y + 0.4, 1.6, 5.2, style="F")
    pdf.set_xy(PAGE_MARGIN + 4, y)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(*INK)
    pdf.cell(
        pdf.content_width - 4,
        6,
        _safe_text(f"{number}. {title}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(1.2)


def _field(pdf: _ReportPDF, label: str, value: object) -> None:
    """One 'Label .... value' row; long values wrap under the value column."""
    text = _safe_text(value)
    if not text:
        return
    value_width = pdf.content_width - LABEL_WIDTH
    lines = _wrap(pdf, text, value_width, "helvetica", "")
    _ensure_space(pdf, len(lines) * LINE_HEIGHT + 2)
    y = pdf.get_y()
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(LABEL_WIDTH, LINE_HEIGHT, _safe_text(label))
    pdf.set_xy(PAGE_MARGIN + LABEL_WIDTH, y)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(*INK)
    pdf.multi_cell(
        value_width,
        LINE_HEIGHT,
        text,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )


def _wrap(pdf: _ReportPDF, text: str, width: float, family: str, style: str) -> list[str]:
    """Count wrapped lines for ``text`` using the given font."""
    if not text:
        return [""]
    pdf.set_font(family, style, 9)
    return list(pdf.multi_cell(width, LINE_HEIGHT, text, dry_run=True, output="LINES"))


def _paragraph(pdf: _ReportPDF, text: str, *, size: float = 9, bold: bool = False) -> None:
    body = _safe_text(text)
    if not body:
        return
    style = "B" if bold else ""
    lines = _wrap(pdf, body, pdf.content_width, "helvetica", style)
    _ensure_space(pdf, len(lines) * LINE_HEIGHT + 2)
    pdf.set_font("helvetica", style, size)
    pdf.set_text_color(*INK)
    pdf.multi_cell(
        pdf.content_width, LINE_HEIGHT, body, new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )


def _note(pdf: _ReportPDF, text: str) -> None:
    """Small grey guidance line under a section heading."""
    body = _safe_text(text)
    if not body:
        return
    lines = _wrap(pdf, body, pdf.content_width - 2, "helvetica", "I")
    _ensure_space(pdf, len(lines) * LINE_HEIGHT + 2)
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        pdf.content_width - 2, LINE_HEIGHT, body, new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.set_text_color(*INK)


def _unavailable(pdf: _ReportPDF, message: str | None, fallback: str) -> None:
    """Neutral box for evidence that does not exist yet."""
    body = _safe_text(message or fallback)
    _ensure_space(pdf, 12)
    pdf.set_font("helvetica", "", 9)
    lines = _wrap(pdf, body, pdf.content_width - 8, "helvetica", "")
    height = max(9.0, len(lines) * LINE_HEIGHT + 5)
    y = pdf.get_y()
    pdf.set_fill_color(*SOFT_BG)
    pdf.set_draw_color(*RULE)
    pdf.rect(PAGE_MARGIN, y, pdf.content_width, height, style="DF")
    pdf.set_xy(PAGE_MARGIN + 4, y + 2.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(pdf.content_width - 8, LINE_HEIGHT, body, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*INK)
    pdf.set_y(y + height + 1.5)


def _banner(pdf: _ReportPDF, primary: str, secondary: str, key: str) -> None:
    """Coloured decision banner (green/amber/red, matching the UI)."""
    background, foreground = _BANNERS.get(key, _DEFAULT_BANNER)
    _ensure_space(pdf, 22)
    y = pdf.get_y()
    height = 16.0
    pdf.set_fill_color(*background)
    pdf.set_draw_color(*background)
    pdf.rect(PAGE_MARGIN, y, pdf.content_width, height, style="F")
    pdf.set_fill_color(*foreground)
    pdf.rect(PAGE_MARGIN, y, 1.8, height, style="F")
    pdf.set_xy(PAGE_MARGIN + 6, y + 2.4)
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(*foreground)
    pdf.cell(pdf.content_width - 12, 6.5, _safe_text(primary), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(PAGE_MARGIN + 6, y + 9.4)
    pdf.set_font("helvetica", "", 8.5)
    pdf.cell(pdf.content_width - 12, 5, _safe_text(secondary), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*INK)
    pdf.set_y(y + height + 3)


def _score_row(
    pdf: _ReportPDF, component: str, points: int, maximum: int, note: str
) -> None:
    """Evidence line: component, filled bar out of its maximum, points."""
    bar_width = 60.0
    filled = max(0.0, min(float(points) / float(maximum or 1), 1.0)) * bar_width
    y = pdf.get_y()
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(*INK)
    pdf.cell(52, LINE_HEIGHT + 1, _safe_text(component))
    x_bar = PAGE_MARGIN + 54
    pdf.set_fill_color(*SOFT_BG)
    pdf.set_draw_color(*RULE)
    pdf.rect(x_bar, y + 1, bar_width, 3.2, style="DF")
    if filled > 0:
        pdf.set_fill_color(*BRAND)
        pdf.set_draw_color(*BRAND)
        pdf.rect(x_bar, y + 1, filled, 3.2, style="F")
    pdf.set_xy(x_bar + bar_width + 3, y)
    pdf.cell(22, LINE_HEIGHT + 1, f"{points} / {maximum}")
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(pdf.content_width - (x_bar + bar_width + 25) + PAGE_MARGIN, LINE_HEIGHT + 1, _safe_text(note))
    pdf.set_text_color(*INK)
    pdf.set_xy(PAGE_MARGIN, y + LINE_HEIGHT + 1.6)


# --- Sections -------------------------------------------------------------------


def _title_block(pdf: _ReportPDF, report: VerificationReport) -> None:
    pdf.set_font("helvetica", "B", 19)
    pdf.set_text_color(*BRAND_DARK)
    pdf.cell(
        pdf.content_width,
        9,
        "DNA Identity Verification Report",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font("helvetica", "", 9.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(
        pdf.content_width,
        5.5,
        _safe_text(
            f"Case {report.verification_id}   |   Status {_status_line(report.status)}"
            f"   |   Generated {_fmt_datetime(report.generated_at)}"
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(1.5)
    pdf.set_draw_color(*BRAND)
    pdf.set_line_width(0.7)
    pdf.line(PAGE_MARGIN, pdf.get_y(), pdf.w - PAGE_MARGIN, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(3)
    pdf.set_text_color(*INK)


def _identity_section(pdf: _ReportPDF, number: int, identity: ReportIdentity) -> None:
    _heading(pdf, number, "Case and Subject Identity")
    _field(pdf, "CNIC", identity.cnic)
    _field(pdf, "Name", identity.name)
    _field(pdf, "Father / Husband name", identity.father_name)
    _field(pdf, "Date of birth", _fmt_date(identity.date_of_birth))
    _field(pdf, "Gender", _label(identity.gender))
    _field(pdf, "Record status", _label(identity.identity_status))


def _document_section(pdf: _ReportPDF, number: int, document: ReportDocumentSection) -> None:
    _heading(pdf, number, "Submitted Document")
    if not document.available:
        _unavailable(pdf, document.message, "No document submitted.")
        return
    _field(pdf, "Document ID", document.document_id)
    _field(pdf, "File name", _basename(document.original_filename))
    _field(pdf, "Document type", _label(document.document_type))
    _field(pdf, "File format", document.content_type)
    _field(pdf, "File size", _fmt_size(document.file_size))
    _field(pdf, "Processing status", _label(document.processing_status))
    _field(pdf, "Uploaded by", document.uploaded_by)
    _field(pdf, "Uploaded at", _fmt_datetime(document.uploaded_at))
    if document.document_count > 1:
        _field(pdf, "Documents on case", str(document.document_count))


def _extraction_section(
    pdf: _ReportPDF, number: int, extraction: ReportExtractionSection
) -> None:
    _heading(pdf, number, "AI Document Intelligence")
    if not extraction.available:
        _unavailable(pdf, extraction.message, "Document has not been processed.")
        return
    _note(pdf, extraction.label)
    pdf.ln(0.8)
    _field(pdf, "Extraction status", _label(extraction.extraction_status))
    _field(pdf, "AI model used", extraction.model_name)
    _field(pdf, "Name on document", extraction.extracted_name)
    _field(pdf, "CNIC on document", extraction.extracted_cnic)
    _field(pdf, "CNIC consistency", _label(extraction.cnic_consistency))
    _field(pdf, "Name consistency", _label(extraction.name_consistency))
    _field(pdf, "Overall identity consistency", _label(extraction.identity_consistency))
    _field(pdf, "STR markers extracted", str(extraction.extracted_marker_count))
    _field(pdf, "Extracted at", _fmt_datetime(extraction.extracted_at))
    if extraction.validation_note:
        _field(pdf, "Validation note", extraction.validation_note)
    _note(pdf, "No raw allele values are reproduced in this report.")


def _dna_section(pdf: _ReportPDF, number: int, dna: ReportDnaSection) -> None:
    _heading(pdf, number, "DNA / STR Analysis")
    if not dna.available:
        _unavailable(pdf, dna.message, "DNA comparison not available.")
        return
    _note(pdf, dna.engine_note)
    pdf.ln(0.8)
    _field(pdf, "Comparison result", _label(dna.classification))
    _field(pdf, "Match percentage", _fmt_percent(dna.match_percentage))
    _field(pdf, "Markers compared", str(dna.total_markers))
    _field(pdf, "Markers matched", str(dna.matched_markers))
    _field(pdf, "Markers mismatched", str(dna.mismatched_markers))
    if dna.missing_markers:
        _field(pdf, "Markers missing", str(dna.missing_markers))
    if dna.invalid_markers:
        _field(pdf, "Invalid markers", str(dna.invalid_markers))
    _field(pdf, "Compared at", _fmt_datetime(dna.compared_at))


def _evidence_section(pdf: _ReportPDF, number: int, evidence: ReportEvidenceSection) -> None:
    _heading(pdf, number, "Evidence Assessment")
    if not evidence.available:
        _unavailable(pdf, evidence.message, "Verification decision not available.")
        return
    _note(pdf, evidence.score_note)
    pdf.ln(1.2)
    _score_row(
        pdf,
        "DNA STR comparison",
        evidence.dna_score,
        70,
        f"{_label(evidence.dna_classification)} / {_fmt_percent(evidence.dna_match_percentage)}",
    )
    _score_row(
        pdf,
        "Identity information consistency",
        evidence.identity_score,
        20,
        _label(evidence.identity_consistency),
    )
    _score_row(
        pdf,
        "Document consistency",
        evidence.document_score,
        10,
        _label(evidence.document_consistency),
    )
    pdf.ln(1)
    # Total box: label on the left, score right-aligned at the inner edge of the
    # frame. Both cells together must fit inside content width minus the 4 mm
    # side padding, otherwise the score is painted off the page.
    y = pdf.get_y()
    pdf.set_fill_color(*SOFT_BG)
    pdf.set_draw_color(*RULE)
    pdf.rect(PAGE_MARGIN, y, pdf.content_width, 9, style="DF")
    score_width = 40.0
    pdf.set_xy(PAGE_MARGIN + 4, y + 2.2)
    pdf.set_font("helvetica", "B", 9.5)
    pdf.cell(pdf.content_width - 8 - score_width, LINE_HEIGHT, _safe_text(evidence.score_label))
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(*BRAND_DARK)
    pdf.cell(
        score_width,
        LINE_HEIGHT,
        f"{evidence.total_score} / {evidence.max_score}",
        align="R",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_text_color(*INK)
    pdf.set_y(y + 12)


def _decision_section(pdf: _ReportPDF, number: int, decision: ReportDecisionSection) -> None:
    # 34 mm keeps the heading together with the decision banner below it.
    _heading(pdf, number, "Verification Decision", reserve=34.0)
    if not decision.available:
        _unavailable(pdf, decision.message, "Verification decision not available.")
        return
    key = (decision.decision or "").upper()
    _banner(
        pdf,
        _label(key) or "No decision",
        f"Recorded {_fmt_datetime(decision.decided_at)}" if decision.decided_at else "",
        key,
    )
    _paragraph(pdf, decision.explanation or "")
    _note(pdf, "The decision is produced by deterministic rules on existing evidence.")


def _timeline_section(pdf: _ReportPDF, number: int, report: VerificationReport) -> None:
    _heading(pdf, number, "Audit Trail")
    if not report.audit_timeline:
        _unavailable(pdf, None, "No audit events recorded.")
        return
    _note(pdf, "Append-only record of actions performed on this case.")
    pdf.ln(1.5)

    rail_x = PAGE_MARGIN + 2.5
    text_x = PAGE_MARGIN + 10
    text_width = pdf.content_width - (text_x - PAGE_MARGIN) - 2
    previous_dot_y: float | None = None

    for entry in report.audit_timeline:
        description = _safe_text(entry.description)
        desc_lines = _wrap(pdf, description, text_width, "helvetica", "")
        pdf.set_font("helvetica", "", 9)
        block_height = 4.4 + len(desc_lines) * LINE_HEIGHT + 4.0
        _ensure_space(pdf, block_height + 2)

        y = pdf.get_y()
        dot_y = y + 2.0
        if previous_dot_y is not None:
            pdf.set_draw_color(*RULE)
            pdf.line(rail_x, previous_dot_y, rail_x, dot_y)
        pdf.set_fill_color(*BRAND)
        pdf.set_draw_color(*BRAND)
        pdf.ellipse(rail_x - 1.4, dot_y - 1.4, 2.8, 2.8, style="F")
        previous_dot_y = dot_y

        pdf.set_xy(text_x, y)
        pdf.set_font("helvetica", "B", 9)
        pdf.set_text_color(*INK)
        pdf.cell(70, 4.4, _safe_text(entry.event))
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(
            text_width - 70,
            4.4,
            _safe_text(f"{_fmt_datetime(entry.timestamp)} ({entry.event_type})"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_xy(text_x, y + 4.4)
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(*INK)
        pdf.multi_cell(
            text_width, LINE_HEIGHT, description, new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(
            text_width,
            4.0,
            _safe_text(f"Actor: {entry.actor}"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_y(pdf.get_y() + 1.8)
        pdf.set_text_color(*INK)


def _disclaimer_block(pdf: _ReportPDF, report: VerificationReport) -> None:
    body = _safe_text(report.disclaimer)
    if not body:
        return
    lines = _wrap(pdf, body, pdf.content_width - 8, "helvetica", "")
    height = len(lines) * 4.2 + 8
    _ensure_space(pdf, height + 4)
    y = pdf.get_y()
    pdf.ln(1)
    y = pdf.get_y()
    pdf.set_fill_color(*SOFT_BG)
    pdf.set_draw_color(*BRAND)
    pdf.set_line_width(0.4)
    pdf.rect(PAGE_MARGIN, y, pdf.content_width, height, style="DF")
    pdf.set_line_width(0.2)
    pdf.set_xy(PAGE_MARGIN + 4, y + 2.6)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(*BRAND_DARK)
    pdf.cell(pdf.content_width - 8, 4.4, "Disclaimer", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_text_color(*INK)
    pdf.set_x(PAGE_MARGIN + 4)
    pdf.multi_cell(
        pdf.content_width - 8, 4.2, body, new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.set_y(y + height + 2)

    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(
        pdf.content_width,
        4,
        _safe_text(
            "Report generated by the deterministic report service from stored evidence; "
            "it contains no raw DNA allele data."
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )


# --- Public entry point ---------------------------------------------------------


def render_pdf(report: VerificationReport) -> bytes:
    """Render an assembled report as a standalone A4 PDF document."""
    pdf = _ReportPDF(report)
    pdf.add_page()

    _title_block(pdf, report)
    _identity_section(pdf, 1, report.identity)
    pdf.ln(1.5)
    _document_section(pdf, 2, report.document)
    pdf.ln(1.5)
    _extraction_section(pdf, 3, report.ai_extraction)
    pdf.ln(1.5)
    _dna_section(pdf, 4, report.dna_analysis)
    pdf.ln(1.5)
    _evidence_section(pdf, 5, report.evidence)
    pdf.ln(1.5)
    _decision_section(pdf, 6, report.decision)
    pdf.ln(1.5)
    _timeline_section(pdf, 7, report)
    pdf.ln(2)
    _disclaimer_block(pdf, report)

    return bytes(pdf.output())
