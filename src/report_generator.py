"""
AgriGuide India — PDF Report Generator
======================================
Produces a clean, citizen-friendly PDF agricultural suitability report
for any selected district. Uses ReportLab.
"""

from __future__ import annotations
import io
from typing import Dict, List, Optional
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)

from . import data_processor as dp
from . import recommendation_engine as rec


# Brand palette
BRAND_GREEN = colors.HexColor("#16a34a")
BRAND_DARK  = colors.HexColor("#0f172a")
BRAND_GREY  = colors.HexColor("#475569")
BRAND_LIGHT = colors.HexColor("#f1f5f9")
CAT_COLORS = {
    "Excellent": colors.HexColor("#16a34a"),
    "Good":      colors.HexColor("#eab308"),
    "Moderate":  colors.HexColor("#f97316"),
    "Poor":      colors.HexColor("#dc2626"),
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"],
                                fontName="Helvetica-Bold", fontSize=22,
                                textColor=BRAND_DARK, spaceAfter=4, alignment=TA_LEFT),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"],
                                   fontName="Helvetica", fontSize=11,
                                   textColor=BRAND_GREY, spaceAfter=14, alignment=TA_LEFT),
        "h2": ParagraphStyle("h2", parent=base["Heading2"],
                             fontName="Helvetica-Bold", fontSize=14,
                             textColor=BRAND_GREEN, spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base["Heading3"],
                             fontName="Helvetica-Bold", fontSize=12,
                             textColor=BRAND_DARK, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["Normal"],
                               fontName="Helvetica", fontSize=10.5,
                               textColor=BRAND_DARK, leading=15, alignment=TA_JUSTIFY,
                               spaceAfter=6),
        "bullet": ParagraphStyle("bullet", parent=base["Normal"],
                                 fontName="Helvetica", fontSize=10.5,
                                 textColor=BRAND_DARK, leading=15, leftIndent=12,
                                 bulletIndent=0, spaceAfter=3),
        "small": ParagraphStyle("small", parent=base["Normal"],
                                fontName="Helvetica", fontSize=8.5,
                                textColor=BRAND_GREY, alignment=TA_CENTER),
        "score_big": ParagraphStyle("score_big", parent=base["Normal"],
                                    fontName="Helvetica-Bold", fontSize=36,
                                    textColor=BRAND_DARK, alignment=TA_CENTER, spaceAfter=0),
        "score_label": ParagraphStyle("score_label", parent=base["Normal"],
                                      fontName="Helvetica-Bold", fontSize=11,
                                      textColor=BRAND_GREY, alignment=TA_CENTER),
    }


def _score_color(score: float) -> colors.Color:
    if score >= 76: return CAT_COLORS["Excellent"]
    if score >= 51: return CAT_COLORS["Good"]
    if score >= 26: return CAT_COLORS["Moderate"]
    return CAT_COLORS["Poor"]


def _header_footer(canvas, doc):
    canvas.saveState()
    # Header band
    canvas.setFillColor(BRAND_GREEN)
    canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
    # Footer
    canvas.setFillColor(BRAND_GREY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(20 * mm, 12 * mm, "AgriGuide India — Agricultural Suitability Report")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm,
                           f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}")
    canvas.setStrokeColor(BRAND_LIGHT)
    canvas.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
    canvas.restoreState()


def generate_report(state: str, district: str, comparison_state: Optional[str] = None,
                    comparison_district: Optional[str] = None) -> bytes:
    """Build the PDF report and return as bytes."""
    profile = dp.get_district(state, district)
    if not profile:
        raise ValueError(f"No profile found for {district}, {state}")

    crops = rec.recommend_top_crops(state, district, top_n=5)
    summary = rec.get_summary(state, district)
    alts = rec.suggest_alternatives(state, district, limit=3)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=22 * mm,
                            title=f"AgriGuide India — {district} Suitability Report")

    s = _styles()
    story: List = []

    # ---------------- Header ----------------
    story.append(Paragraph("AgriGuide India", s["subtitle"]))
    story.append(Paragraph(f"Agricultural Suitability Report", s["title"]))
    story.append(Paragraph(f"{district} District, {state}", s["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=0.7, color=BRAND_GREEN, spaceAfter=10))

    # ---------------- Score block ----------------
    score = profile["suitability_score"]
    cat = profile["suitability_category"]
    score_color = _score_color(score)

    score_table = Table([[
        Paragraph(f"<font color='{score_color.hexval()}'>{score:.1f}</font>", s["score_big"]),
        Paragraph(f"<b>Category</b><br/>{cat}<br/><br/>"
                  f"<b>Score Range</b><br/>0-25 Poor | 26-50 Moderate<br/>"
                  f"51-75 Good | 76-100 Excellent", s["body"]),
    ]], colWidths=[55 * mm, 115 * mm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_GREY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LEFTPADDING", (1, 0), (1, 0), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 8))

    # ---------------- Summary ----------------
    story.append(Paragraph("Summary", s["h2"]))
    for b in summary["bullets"]:
        story.append(Paragraph(f"• {b}", s["bullet"]))

    # ---------------- District indicators ----------------
    story.append(Paragraph("Key Agricultural Indicators", s["h2"]))
    ind_data = [
        ["Indicator", "Value"],
        ["Rainfall (estimated)", f"{profile['rainfall_mm']} mm/year"],
        ["Soil quality index", f"{profile['soil_quality']}/100"],
        ["Mean temperature", f"{profile['temperature_c']} °C"],
        ["Irrigation dependency", f"{profile['irrigation_dependency']}/100"],
        ["Crops historically grown", f"{profile['n_crops_grown']}"],
        ["Years of data", f"{profile['n_years_data']}"],
        ["Total cultivated area (records)", f"{profile['total_area_ha']:,} ha"],
        ["Total production (records)", f"{profile['total_production_t']:,} t"],
    ]
    ind_tbl = Table(ind_data, colWidths=[90 * mm, 80 * mm])
    ind_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, BRAND_GREY),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ind_tbl)

    # ---------------- Recommended crops ----------------
    story.append(Paragraph("Top Recommended Crops", s["h2"]))
    if crops:
        crop_rows = [["Rank", "Crop", "Type", "Suitability %", "Confidence", "Performance"]]
        for i, c in enumerate(crops, 1):
            crop_rows.append([
                str(i), c["crop"], c.get("type", ""),
                f"{c['suitability_pct']:.1f}",
                f"{c['confidence']:.1f}",
                c["performance_rating"],
            ])
        crop_tbl = Table(crop_rows, colWidths=[15 * mm, 40 * mm, 35 * mm, 30 * mm, 25 * mm, 30 * mm])
        crop_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (4, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.3, BRAND_GREY),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(crop_tbl)
        story.append(Spacer(1, 8))

        # Per-crop farming advice for top 2
        story.append(Paragraph("Farming Advice (Top 2 Crops)", s["h3"]))
        for c in crops[:2]:
            adv = c["advice"]
            story.append(Paragraph(f"<b>{c['crop']}</b>", s["body"]))
            story.append(Paragraph(f"• Irrigation: {adv['irrigation']}", s["bullet"]))
            story.append(Paragraph(f"• Fertilizer: {adv['fertilizer']}", s["bullet"]))
            story.append(Paragraph(f"• Season: {adv['season']}", s["bullet"]))
            story.append(Paragraph(f"• Risk: {adv['risk']}", s["bullet"]))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No crop recommendations available for this district.", s["body"]))

    # ---------------- Risk factors ----------------
    story.append(Paragraph("Risk Factors", s["h2"]))
    risk_rows = [["Risk", "Level", "Score", "Mitigation"]]
    for r in profile["risks"]:
        risk_rows.append([r["name"], r["level"], f"{r['score']:.1f}", r["mitigation"]])
    risk_tbl = Table(risk_rows, colWidths=[48 * mm, 22 * mm, 18 * mm, 82 * mm])
    risk_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, BRAND_GREY),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(risk_tbl)

    # ---------------- Comparison summary (optional) ----------------
    if comparison_state and comparison_district:
        other = dp.get_district(comparison_state, comparison_district)
        if other:
            story.append(Paragraph("Comparison Summary", s["h2"]))
            cmp_rows = [
                ["Indicator", district, comparison_district],
                ["Suitability score", f"{profile['suitability_score']}", f"{other['suitability_score']}"],
                ["Category", profile["suitability_category"], other["suitability_category"]],
                ["Rainfall (mm)", str(profile["rainfall_mm"]), str(other["rainfall_mm"])],
                ["Soil quality", str(profile["soil_quality"]), str(other["soil_quality"])],
                ["Irrigation dep.", str(profile["irrigation_dependency"]), str(other["irrigation_dependency"])],
                ["Top crop", profile["top_crops"][0] if profile["top_crops"] else "—",
                             other["top_crops"][0] if other["top_crops"] else "—"],
            ]
            cmp_tbl = Table(cmp_rows, colWidths=[55 * mm, 55 * mm, 55 * mm])
            cmp_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.3, BRAND_GREY),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(cmp_tbl)

    # ---------------- Alternative districts ----------------
    if alts:
        story.append(Paragraph("Nearby Districts with Better Conditions", s["h2"]))
        alt_rows = [["District", "Distance", "Score", "Top Crop"]]
        for a in alts:
            alt_rows.append([f"{a['district']}, {a['state']}",
                             f"{a['distance_km']:.0f} km",
                             f"{a['suitability_score']}",
                             a["top_crop"]])
        alt_tbl = Table(alt_rows, colWidths=[70 * mm, 30 * mm, 25 * mm, 45 * mm])
        alt_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.3, BRAND_GREY),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(alt_tbl)

    # ---------------- Footer note ----------------
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.4, color=BRAND_LIGHT))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "This report is generated by AgriGuide India using historical crop-production data. "
        "Scores are relative comparisons across Indian districts and should be combined with "
        "local expert advice before making farming decisions.",
        s["small"]))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
