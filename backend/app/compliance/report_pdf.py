"""Render a ComplianceDecisionReport as a professional PDF using ReportLab.

The PDF is generated strictly from the persisted backend report data - no
compliance logic is re-run and no information is invented. Long evidence and
explanation text wraps inside Paragraphs and flows across pages; page numbers
are stamped in the footer.
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.compliance.phase8_service import get_compliance_decision_report

logger = logging.getLogger(__name__)

NAVY = colors.HexColor("#163A5F")
BLUE = colors.HexColor("#2B6CB0")
LIGHT_BG = colors.HexColor("#F0F5FA")
BORDER = colors.HexColor("#D8E0EA")
TEXT = colors.HexColor("#1A202C")
MUTED = colors.HexColor("#4A5568")
SUCCESS = colors.HexColor("#2F855A")
ERROR = colors.HexColor("#C53030")
WARNING = colors.HexColor("#B7791F")

DISCLAIMER = (
    "AI analysis is advisory only. The final procurement decision remains "
    "with the authorized officer."
)

STATUS_COLORS = {
    "COMPLIANT": SUCCESS,
    "POTENTIAL_NON_COMPLIANCE": ERROR,
    "REQUIRES_REVIEW": WARNING,
    "INSUFFICIENT_EVIDENCE": WARNING,
    "NOT_APPLICABLE": MUTED,
    "UNKNOWN": MUTED,
}

RISK_COLORS = {
    "CRITICAL": ERROR,
    "HIGH": ERROR,
    "MEDIUM": WARNING,
    "LOW": SUCCESS,
    "INFO": MUTED,
}


def _escape(text: Any) -> str:
    """XML-escape for Paragraph, with None-safe empty string."""
    import html

    return html.escape(str(text if text is not None else ""))


def _hex(color: colors.Color) -> str:
    """ReportLab para markup expects '#rrggbb'."""
    return f"#{color.hexval()[2:]}"


def _fmt_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y, %H:%M UTC")
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime(
            "%d %b %Y, %H:%M UTC"
        )
    except Exception:
        return str(value or "-")


def _build_styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "pgTitle", parent=base["Title"], fontSize=20, textColor=NAVY, spaceAfter=2 * mm
        ),
        "subtitle": ParagraphStyle(
            "pgSubtitle", parent=base["Normal"], fontSize=10, textColor=MUTED, alignment=TA_CENTER
        ),
        "h2": ParagraphStyle(
            "pgH2", parent=base["Heading2"], fontSize=13, textColor=NAVY,
            spaceBefore=6 * mm, spaceAfter=2.5 * mm,
        ),
        "body": ParagraphStyle(
            "pgBody", parent=base["Normal"], fontSize=9.5, leading=13.5, textColor=TEXT
        ),
        "body_small": ParagraphStyle(
            "pgBodySmall", parent=base["Normal"], fontSize=8.5, leading=12, textColor=MUTED
        ),
        "cell": ParagraphStyle(
            "pgCell", parent=base["Normal"], fontSize=8.5, leading=11.5, textColor=TEXT
        ),
        "cell_bold": ParagraphStyle(
            "pgCellBold", parent=base["Normal"], fontSize=8.5, leading=11.5, textColor=TEXT,
            fontName="Helvetica-Bold",
        ),
        "badge": ParagraphStyle(
            "pgBadge", parent=base["Normal"], fontSize=8, leading=10, textColor=colors.white,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "disclaimer": ParagraphStyle(
            "pgDisclaimer", parent=base["Normal"], fontSize=8.5, leading=12, textColor=MUTED,
            alignment=TA_CENTER, borderWidth=0.5, borderColor=BORDER,
            borderPadding=5, borderRadius=3,
        ),
        "page_label": ParagraphStyle(
            "pgPageLabel", parent=base["Normal"], fontSize=8, textColor=MUTED, alignment=TA_CENTER
        ),
    }


def _kv_table(rows: List[List[str]], styles) -> Table:
    data = [[Paragraph(f"<b>{_escape(k)}</b>", styles["cell"]),
             Paragraph(_escape(v), styles["cell"])] for k, v in rows]
    table = Table(data, colWidths=[45 * mm, None])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_BG, colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, BORDER),
    ]))
    return table


def _summary_table(report, styles) -> Table:
    rows = [
        ("Overall Status", report.overall_status.value),
        ("Overall Risk", report.overall_risk.value),
        ("Total Requirements", str(report.total_requirements)),
        ("Applicable Requirements", str(report.applicable_requirements)),
        ("Compliant", str(report.compliant_count)),
        ("Potential Non-Compliance", str(report.potential_non_compliance_count)),
        ("Insufficient Evidence", str(report.insufficient_evidence_count)),
        ("Requires Review", str(report.requires_review_count)),
        ("Unknown", str(report.unknown_count)),
        ("Critical / High / Medium / Low / Info Risk",
         f"{report.critical_count} / {report.high_count} / {report.medium_count} / "
         f"{report.low_count} / {report.info_count}"),
    ]
    return _kv_table(rows, styles)


def _findings_table(report, styles) -> Table:
    header = ["#", "Requirement", "Category*", "Status", "Risk", "Mandatory", "Explanation"]
    data = [[Paragraph(f"<b>{h}</b>", styles["cell"]) for h in header]]
    for idx, finding in enumerate(report.findings, start=1):
        status_color = STATUS_COLORS.get(finding.status, MUTED)
        risk_color = RISK_COLORS.get(finding.risk_level.value, MUTED)
        data.append([
            Paragraph(str(idx), styles["cell"]),
            Paragraph(_escape(finding.requirement_title), styles["cell"]),
            Paragraph(_escape(getattr(finding, "category", "")), styles["cell"]),
            Paragraph(
                f'<para textColor="{_hex(status_color)}"><b>{_escape(finding.status)}</b></para>',
                styles["cell"],
            ),
            Paragraph(
                f'<para textColor="{_hex(risk_color)}"><b>{_escape(finding.risk_level.value)}</b></para>',
                styles["cell"],
            ),
            Paragraph("Yes" if finding.mandatory else "No", styles["cell"]),
            Paragraph(_escape(finding.explanation), styles["cell"]),
        ])
    col_widths = [8 * mm, 38 * mm, 22 * mm, 30 * mm, 16 * mm, 15 * mm, None]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _requirement_detail_block(finding, explanation: Optional[dict], styles) -> List:
    """One requirement's evidence/provenance detail block."""
    flow: List = []
    heading = (
        f"{_escape(finding.requirement_title)} "
        f'<font size="8" color="#4A5568">({_escape(finding.requirement_id[:16])}…)</font>'
    )
    flow.append(Paragraph(heading, styles["cell_bold"]))
    flow.append(Spacer(1, 1.5 * mm))

    rows: List[List[str]] = [("Status", finding.status), ("Risk", finding.risk_level.value)]
    if explanation:
        if explanation.get("category"):
            rows.append(("Category", explanation.get("category")))
        if explanation.get("mandatory"):
            rows.append(("Mandatory", "Yes"))
        if explanation.get("source_page"):
            loc = f"Page {explanation.get('source_page')}"
            if explanation.get("source_section"):
                loc += f" — {explanation.get('source_section')}"
            rows.append(("Source Location", loc))
        if explanation.get("regulatory_reference"):
            reg = explanation.get("regulatory_reference")
            if explanation.get("regulatory_authority"):
                reg += f" ({explanation.get('regulatory_authority')})"
            rows.append(("Regulatory Reference", reg))
        if explanation.get("evidence_summary"):
            rows.append(("Evidence", explanation.get("evidence_summary")))

    flow.append(_kv_table(rows, styles))

    if explanation:
        reason = explanation.get("reason") or explanation.get("requirement_description")
        if reason:
            flow.append(Spacer(1, 1.5 * mm))
            flow.append(Paragraph(f"<b>Evaluation explanation:</b> {_escape(reason)}", styles["body_small"]))
        trace = explanation.get("evidence_trace") or {}
        if trace.get("source_text"):
            flow.append(Spacer(1, 1.5 * mm))
            flow.append(Paragraph(
                f"<b>Source extract (verbatim):</b> {_escape(trace.get('source_text'))}",
                styles["body_small"],
            ))
        if explanation.get("human_review_required"):
            reason_txt = explanation.get("requires_review_reason") or "Human officer review required."
            flow.append(Spacer(1, 1.5 * mm))
            flow.append(Paragraph(
                f'<para textColor="{_hex(WARNING)}">👤 Human review required — '
                f"{_escape(reason_txt)}</para>",
                styles["body_small"],
            ))
    return flow


def render_decision_report_pdf(report_id: str) -> bytes:
    """Render the persisted ComplianceDecisionReport as a PDF and return bytes."""
    report = get_compliance_decision_report(report_id)
    if report is None:
        raise ValueError(f"Compliance decision report not found: {report_id}")

    from app.compliance.phase8_service import get_requirement_explanation

    styles = _build_styles()
    buf = io.BytesIO()

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"PolicyGuard AI Compliance Report {report_id}",
        author="PolicyGuard AI",
        subject="Bid compliance verification report",
    )

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(
            A4[0] / 2, 8 * mm, f"PolicyGuard AI — Compliance Report — Page {doc_.page}"
        )
        canvas.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=_footer)])

    story: List = []

    # ---- Header ----
    story.append(Paragraph("PolicyGuard AI", styles["title"]))
    story.append(Paragraph(
        "AI-Powered Bid Compliance Verification Report — GeM Procurement", styles["subtitle"]
    ))
    story.append(Spacer(1, 4 * mm))

    # ---- Report identification ----
    story.append(Paragraph("Report Identification", styles["h2"]))
    story.append(_kv_table([
        ("Report ID", report.report_id),
        ("Analysis ID", report.analysis_id or "-"),
        ("Tender Document ID", report.document_id),
        ("Generated At", _fmt_dt(report.generated_at)),
        ("Report Version", report.version),
    ], styles))

    # ---- Executive summary ----
    if report.executive_summary:
        story.append(Paragraph("Executive Summary", styles["h2"]))
        story.append(Paragraph(_escape(report.executive_summary), styles["body"]))

    # ---- Summary statistics ----
    story.append(Paragraph("Compliance Summary", styles["h2"]))
    story.append(_summary_table(report, styles))

    # ---- Key findings / critical issues ----
    if report.key_findings:
        story.append(Paragraph("Key Findings", styles["h2"]))
        for item in report.key_findings:
            story.append(Paragraph(f"• {_escape(item)}", styles["body"]))
    if report.critical_issues:
        story.append(Paragraph("Critical Issues", styles["h2"]))
        for item in report.critical_issues:
            story.append(
                Paragraph(f'<para textColor="{_hex(ERROR)}">• {_escape(item)}</para>', styles["body"])
            )

    # ---- Requirements table ----
    story.append(Paragraph("Requirements Overview", styles["h2"]))
    story.append(_findings_table(report, styles))
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(
        "* Category is shown where available from the requirement explanation record.",
        styles["body_small"],
    ))

    # ---- Per-requirement evidence detail ----
    story.append(Paragraph("Requirement Evidence & Provenance Detail", styles["h2"]))
    for finding in report.findings:
        explanation = None
        if report.analysis_id:
            try:
                expl = get_requirement_explanation(finding.requirement_id, report.analysis_id)
                explanation = expl.model_dump(mode="json") if expl else None
            except Exception:
                explanation = None
        story.append(KeepTogether(_requirement_detail_block(finding, explanation, styles)))
        story.append(Spacer(1, 4 * mm))

    # ---- Human review queue ----
    if report.human_review_queue:
        story.append(Paragraph("Human Review Queue", styles["h2"]))
        rows = [[Paragraph("<b>Priority</b>", styles["cell"]),
                 Paragraph("<b>Requirement</b>", styles["cell"]),
                 Paragraph("<b>Status</b>", styles["cell"]),
                 Paragraph("<b>Suggested Action</b>", styles["cell"])]]
        for item in sorted(report.human_review_queue, key=lambda i: i.priority):
            rows.append([
                Paragraph(str(item.priority), styles["cell"]),
                Paragraph(_escape(item.requirement_title), styles["cell"]),
                Paragraph(_escape(item.status), styles["cell"]),
                Paragraph(_escape(item.suggested_action), styles["cell"]),
            ])
        table = Table(rows, colWidths=[16 * mm, 60 * mm, 34 * mm, None], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ("GRID", (0, 0), (-1, -1), 0.25, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)

    # ---- Disclaimer ----
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(f"⚖️ {_escape(DISCLAIMER)}", styles["disclaimer"]))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    logger.info("Rendered compliance report PDF report_id=%s (%d bytes)", report_id, len(pdf_bytes))
    return pdf_bytes
