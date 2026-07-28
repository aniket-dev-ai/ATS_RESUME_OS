
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger("ats_resume_scorer")


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #

class PDFGenerationError(Exception):
    """Raised when the combined PDF report cannot be generated."""


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #

def _build_stylesheet() -> StyleSheet1:
    """Build and return the shared, reusable ParagraphStyle set for the report.

    Styles are created exactly once per PDF generation call and reused
    throughout the document to avoid redundant object construction.
    """
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontSize=26,
            leading=32,
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=colors.HexColor("#111827"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle",
            parent=styles["Normal"],
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4b5563"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            spaceBefore=18,
            spaceAfter=10,
            textColor=colors.HexColor("#111827"),
            borderColor=colors.HexColor("#e5e7eb"),
            borderWidth=0,
            borderPadding=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubsectionTitle",
            parent=styles["Heading2"],
            fontSize=13,
            leading=17,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#1f2937"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyText2",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1f2937"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="ScoreDisplay",
            parent=styles["Normal"],
            fontSize=48,
            leading=54,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="Interpretation",
            parent=styles["Normal"],
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#374151"),
            spaceBefore=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Success",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#166534"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Warning",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#92400e"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Danger",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#991b1b"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            fontName="Helvetica-Bold",
            textColor=colors.white,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1f2937"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="FooterText",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#9ca3af"),
        )
    )
    return styles


# --------------------------------------------------------------------------- #
# Small shared helpers
# --------------------------------------------------------------------------- #

def _score_color(score: float) -> colors.Color:
    """Map a 0-100 score to a green / amber / red color, matching the
    thresholds used elsewhere in the application."""
    if score >= 80:
        return colors.HexColor("#16a34a")
    if score >= 60:
        return colors.HexColor("#d97706")
    return colors.HexColor("#dc2626")


def _safe_text(value: Any, default: str = "N/A") -> str:
    """Coerce arbitrary values to a display-safe string for Paragraph flowables."""
    if value is None or value == "":
        return default
    return str(value)


def _make_table(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    styles: StyleSheet1,
    col_widths: Optional[Sequence[float]] = None,
) -> Table:
    """Build a consistently styled table with a header row and body rows."""
    header_cells = [Paragraph(_safe_text(h), styles["TableHeader"]) for h in header]
    data: List[List[Any]] = [header_cells]

    for row in rows:
        data.append([Paragraph(_safe_text(cell), styles["TableCell"]) for cell in row])

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #

def _add_cover_page(
    story: List[Any],
    styles: StyleSheet1,
    report_data: Dict[str, Any],
) -> None:
    """Cover page: title, generation date, overall score, interpretation."""
    overall_score = float(report_data.get("overall_score", 0) or 0)
    interpretation = _safe_text(report_data.get("interpretation"), default="")
    timestamp = report_data.get("timestamp")

    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")) if timestamp else datetime.now()
    except Exception:
        dt = datetime.now()
    generated_str = dt.strftime("%B %d, %Y at %I:%M %p")

    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph("ATS Resume Analysis Report", styles["CoverTitle"]))
    story.append(Paragraph(f"Generated {generated_str}", styles["CoverSubtitle"]))
    story.append(Spacer(1, 0.5 * inch))

    score_color = _score_color(overall_score)
    score_style = ParagraphStyle(
        name="CoverScore",
        parent=styles["ScoreDisplay"],
        textColor=score_color,
    )
    story.append(Paragraph(f"{overall_score:.0f}", score_style))
    story.append(Paragraph("Overall ATS Score", styles["CoverSubtitle"]))

    if interpretation:
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph(interpretation, styles["Interpretation"]))

    story.append(PageBreak())


def _add_component_scores(
    story: List[Any],
    styles: StyleSheet1,
    report_data: Dict[str, Any],
) -> None:
    """Component score breakdown table (formatting, keywords, content, etc.)."""
    component_scores: Dict[str, Any] = report_data.get("component_scores") or {}
    component_pct: Dict[str, Any] = report_data.get("component_pct") or {}

    labels = {
        "formatting": "Formatting",
        "keywords": "Keywords",
        "content": "Content",
        "skill_validation": "Skill Validation",
        "ats_compatibility": "ATS Compatibility",
    }

    story.append(Paragraph("Component Scores", styles["SectionTitle"]))

    rows = []
    for key, label in labels.items():
        score = component_scores.get(key, 0)
        percent = component_pct.get(key, 0)
        rows.append([label, f"{score:.1f}", f"{percent}%"])

    table = _make_table(
        header=["Component", "Score", "% of Max"],
        rows=rows,
        styles=styles,
        col_widths=[2.8 * inch, 1.5 * inch, 1.5 * inch],
    )
    story.append(table)
    story.append(Spacer(1, 0.2 * inch))


def _add_strengths(
    story: List[Any],
    styles: StyleSheet1,
    report_data: Dict[str, Any],
) -> None:
    """Bulleted list of resume strengths, if any were identified."""
    strengths: List[str] = report_data.get("strengths") or []
    if not strengths:
        return

    story.append(Paragraph("Strengths", styles["SectionTitle"]))
    items = [
        ListItem(Paragraph(_safe_text(item), styles["Success"]), bulletColor=colors.HexColor("#16a34a"))
        for item in strengths
    ]
    story.append(ListFlowable(items, bulletType="bullet", start="circle"))
    story.append(Spacer(1, 0.2 * inch))


def _add_feedback_section(
    story: List[Any],
    styles: StyleSheet1,
    title: str,
    items: List[Dict[str, Any]],
    style_name: str,
) -> None:
    """Render one priority tier (High / Medium / Low) of feedback issues.

    Each issue is rendered as a small keep-together block containing the
    issue, explanation, recommendation, and expected impact so that a
    single issue's fields never split across a page boundary.
    """
    if not items:
        return

    story.append(Paragraph(title, styles["SubsectionTitle"]))

    for fb in items:
        issue = _safe_text(fb.get("issue") or fb.get("title"))
        explanation = _safe_text(fb.get("explanation") or fb.get("description"), default="")
        recommendation = _safe_text(fb.get("recommendation"), default="")
        impact = _safe_text(fb.get("expected_impact") or fb.get("impact"), default="")

        block: List[Any] = [Paragraph(issue, _issue_style(style_name))]
        if explanation:
            block.append(Paragraph(f"<b>Explanation:</b> {explanation}", styles["BodyText2"]))
        if recommendation:
            block.append(Paragraph(f"<b>Recommendation:</b> {recommendation}", styles["BodyText2"]))
        if impact:
            block.append(Paragraph(f"<b>Expected Impact:</b> {impact}", styles["BodyText2"]))
        block.append(Spacer(1, 0.12 * inch))

        story.append(KeepTogether(block))


_ISSUE_STYLE_CACHE: Dict[str, ParagraphStyle] = {}


def _issue_style(style_name: str) -> ParagraphStyle:
    """Lazily build and cache the bold issue-title style per severity, so the
    same ParagraphStyle object is reused rather than recreated per issue."""
    if style_name not in _ISSUE_STYLE_CACHE:
        color_map = {
            "Danger": colors.HexColor("#991b1b"),
            "Warning": colors.HexColor("#92400e"),
            "Success": colors.HexColor("#166534"),
        }
        _ISSUE_STYLE_CACHE[style_name] = ParagraphStyle(
            name=f"IssueTitle_{style_name}",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=color_map.get(style_name, colors.black),
            spaceBefore=6,
        )
    return _ISSUE_STYLE_CACHE[style_name]


def _add_feedback(
    story: List[Any],
    styles: StyleSheet1,
    report_data: Dict[str, Any],
) -> None:
    """High / Medium / Low priority issue sections."""
    high = report_data.get("high_priority") or []
    medium = report_data.get("medium_priority") or []
    low = report_data.get("low_priority") or []

    if not (high or medium or low):
        return

    story.append(Paragraph("Detailed Feedback", styles["SectionTitle"]))
    _add_feedback_section(story, styles, "High Priority Issues", high, "Danger")
    _add_feedback_section(story, styles, "Medium Priority Issues", medium, "Warning")
    _add_feedback_section(story, styles, "Low Priority Issues", low, "Success")
    story.append(Spacer(1, 0.2 * inch))


def _add_skill_validation(
    story: List[Any],
    styles: StyleSheet1,
    report_data: Dict[str, Any],
) -> None:
    """Validated / unvalidated skills summary table."""
    validated_skills: List[Dict[str, Any]] = report_data.get("validated_skills") or []
    unvalidated_skills: List[str] = report_data.get("unvalidated_skills") or []
    total_skills = report_data.get("total_skills", len(validated_skills) + len(unvalidated_skills))
    validated_count = report_data.get("validated_count", len(validated_skills))
    validation_pct = report_data.get("validation_pct", 0.0)

    if not (validated_skills or unvalidated_skills):
        return

    story.append(Paragraph("Skill Validation", styles["SectionTitle"]))
    story.append(
        Paragraph(
            f"{validated_count} of {total_skills} skills validated "
            f"({validation_pct:.0f}% validation rate)",
            styles["BodyText2"],
        )
    )
    story.append(Spacer(1, 0.1 * inch))

    if validated_skills:
        story.append(Paragraph("Validated Skills", styles["SubsectionTitle"]))
        rows = []
        for entry in validated_skills:
            skill = _safe_text(entry.get("skill"))
            projects = entry.get("projects") or []
            projects_str = ", ".join(str(p) for p in projects) if projects else "N/A"
            rows.append([skill, projects_str])

        table = _make_table(
            header=["Skill", "Projects Mentioned"],
            rows=rows,
            styles=styles,
            col_widths=[2 * inch, 3.8 * inch],
        )
        story.append(table)
        story.append(Spacer(1, 0.15 * inch))

    if unvalidated_skills:
        story.append(Paragraph("Unvalidated Skills", styles["SubsectionTitle"]))
        items = [
            ListItem(Paragraph(_safe_text(skill), styles["Warning"]))
            for skill in unvalidated_skills
        ]
        story.append(ListFlowable(items, bulletType="bullet"))

    story.append(Spacer(1, 0.2 * inch))


def _add_jd_analysis(
    story: List[Any],
    styles: StyleSheet1,
    report_data: Dict[str, Any],
) -> None:
    """Job-description match analysis section, if JD data is present."""
    jd = report_data.get("jd_analysis")
    if not jd:
        return

    story.append(Paragraph("JD Match Analysis", styles["SectionTitle"]))

    match_pct = jd.get("match_percentage", jd.get("match_pct", 0))
    semantic_similarity = jd.get("semantic_similarity", 0)

    summary_rows = [
        ["Match Percentage", f"{match_pct}%"],
        ["Semantic Similarity", f"{semantic_similarity}%"],
    ]
    table = _make_table(
        header=["Metric", "Value"],
        rows=summary_rows,
        styles=styles,
        col_widths=[3 * inch, 2.8 * inch],
    )
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))

    matched_keywords: List[str] = jd.get("matched_keywords") or []
    missing_keywords: List[str] = jd.get("missing_keywords") or []

    if matched_keywords:
        story.append(Paragraph("Matched Keywords", styles["SubsectionTitle"]))
        story.append(Paragraph(", ".join(str(k) for k in matched_keywords), styles["Success"]))
        story.append(Spacer(1, 0.1 * inch))

    if missing_keywords:
        story.append(Paragraph("Missing Keywords", styles["SubsectionTitle"]))
        story.append(Paragraph(", ".join(str(k) for k in missing_keywords), styles["Danger"]))
        story.append(Spacer(1, 0.1 * inch))

    skill_gap = jd.get("skill_gap")
    if skill_gap:
        story.append(Paragraph("Skill Gap", styles["SubsectionTitle"]))
        if isinstance(skill_gap, (list, tuple)):
            items = [ListItem(Paragraph(_safe_text(g), styles["BodyText2"])) for g in skill_gap]
            story.append(ListFlowable(items, bulletType="bullet"))
        else:
            story.append(Paragraph(_safe_text(skill_gap), styles["BodyText2"]))
        story.append(Spacer(1, 0.1 * inch))

    recommendations = jd.get("recommendations")
    if recommendations:
        story.append(Paragraph("Recommendations", styles["SubsectionTitle"]))
        if isinstance(recommendations, (list, tuple)):
            items = [ListItem(Paragraph(_safe_text(r), styles["BodyText2"])) for r in recommendations]
            story.append(ListFlowable(items, bulletType="bullet"))
        else:
            story.append(Paragraph(_safe_text(recommendations), styles["BodyText2"]))

    story.append(Spacer(1, 0.2 * inch))


def _add_footer(canvas_obj, doc) -> None:  # noqa: ANN001 - reportlab callback signature
    """Page decoration callback: page number + branding footer on every page."""
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.HexColor("#9ca3af"))

    page_width, _ = letter
    footer_text = "Generated by ATS Resume Analyzer"
    canvas_obj.drawCentredString(page_width / 2.0, 0.5 * inch, footer_text)
    canvas_obj.drawRightString(page_width - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas_obj.restoreState()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def generate_combined_pdf(report_data: Dict[str, Any]) -> bytes:
 
    if not report_data:
        logger.error("generate_combined_pdf called with empty report_data")
        raise PDFGenerationError("No report data provided for PDF generation.")

    try:
        styles = _build_stylesheet()
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            title="ATS Resume Analysis Report",
        )

        story: List[Any] = []

        _add_cover_page(story, styles, report_data)
        _add_component_scores(story, styles, report_data)
        _add_strengths(story, styles, report_data)
        _add_feedback(story, styles, report_data)
        _add_skill_validation(story, styles, report_data)
        _add_jd_analysis(story, styles, report_data)

        doc.build(story, onFirstPage=_add_footer, onLaterPages=_add_footer)

        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    except PDFGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001 - convert any failure to a domain error
        logger.exception("Failed to generate combined PDF report")
        raise PDFGenerationError(f"PDF generation failed: {exc}") from exc