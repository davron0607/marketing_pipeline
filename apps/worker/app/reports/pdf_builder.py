"""
PDF report builder using reportlab and matplotlib.
"""
import io
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _make_bar_chart(labels: list, values: list, title: str) -> bytes:
    """
    Create a bar chart PNG using matplotlib. Returns PNG bytes.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 3.5))
    x = range(len(labels))
    bars = ax.bar(x, values, color="#4472C4", edgecolor="white")
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(l)[:20] for l in labels], rotation=30, ha="right", fontsize=8)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_ylabel("Count", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            str(int(height)),
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _make_distribution_chart(dist_data: dict, question_key: str) -> bytes:
    """
    Create a distribution chart for a single question.
    Returns PNG bytes.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    counts = dist_data.get("counts", {})
    if not counts:
        # Return a placeholder image
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=80)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    labels = list(counts.keys())[:15]
    values = [counts[l] for l in labels]
    title = question_key[:50] if question_key else "Distribution"
    return _make_bar_chart(labels, values, title)


def _make_numeric_histogram(values: list, title: str) -> bytes:
    """
    Create a histogram for numeric data. Returns PNG bytes.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(values, bins=min(20, len(set(values))), color="#4472C4", edgecolor="white", alpha=0.8)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_xlabel("Value", fontsize=8)
    ax.set_ylabel("Frequency", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def build_report(
    project_name: str,
    analytics: dict,
    fraud_summary: dict,
    suspicious: list,
) -> bytes:
    """
    Build a complete PDF report and return PDF bytes.

    analytics: dict with keys: sample_quality, insight_texts, distributions,
               crosstabs, top_drivers
    fraud_summary: dict with keys: total_scored, label_counts, label_percentages,
                   top_reasons, top_suspicious
    suspicious: list of dicts with respondent_id, fraud_score, label, reasons
    """
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, Image, KeepTogether, PageBreak
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=12,
        textColor=colors.HexColor("#1F3864"),
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=12,
        spaceAfter=6,
        textColor=colors.HexColor("#4472C4"),
        alignment=TA_CENTER,
    )
    h1_style = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=8,
        spaceBefore=14,
        textColor=colors.HexColor("#1F3864"),
        borderPad=4,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=13,
        spaceAfter=6,
        spaceBefore=10,
        textColor=colors.HexColor("#2F5496"),
    )
    body_style = styles["BodyText"]
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=styles["BodyText"],
        leftIndent=20,
        spaceAfter=4,
        bulletIndent=10,
    )

    story = []
    generated_at = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    # ─── 1. TITLE PAGE ────────────────────────────────────────────────────────
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("Survey Analytics Report", title_style))
    story.append(Paragraph(project_name, subtitle_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Generated on {generated_at}", styles["Normal"]))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#4472C4"), spaceAfter=12))
    story.append(Spacer(1, 1 * cm))

    # ─── 2. EXECUTIVE SUMMARY ─────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", h1_style))
    insight_texts = analytics.get("insight_texts", [])
    if insight_texts:
        for txt in insight_texts[:8]:
            story.append(Paragraph(f"• {txt}", bullet_style))
    else:
        story.append(Paragraph("No insights generated yet for this project.", body_style))
    story.append(Spacer(1, 0.5 * cm))

    # ─── 3. SAMPLE QUALITY ────────────────────────────────────────────────────
    story.append(Paragraph("Sample Quality", h1_style))
    sample = analytics.get("sample_quality", {})
    total = sample.get("total", 0)
    valid = sample.get("valid", 0)
    review = sample.get("review", 0)
    reject = sample.get("reject", 0)
    usable = sample.get("usable", valid + review)

    quality_table_data = [
        ["Metric", "Count", "Percentage"],
        ["Total Responses", str(total), "100%"],
        ["Valid", str(valid), f"{valid / total * 100:.1f}%" if total else "0%"],
        ["Review", str(review), f"{review / total * 100:.1f}%" if total else "0%"],
        ["Rejected", str(reject), f"{reject / total * 100:.1f}%" if total else "0%"],
        ["Usable (Valid + Review)", str(usable), f"{usable / total * 100:.1f}%" if total else "0%"],
    ]
    quality_table = Table(quality_table_data, colWidths=[8 * cm, 4 * cm, 4 * cm])
    quality_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EEF2F7"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D3E5")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D6E4F0")),
    ]))
    story.append(quality_table)
    story.append(Spacer(1, 0.5 * cm))

    # Sample quality bar chart
    if total > 0:
        try:
            chart_labels = ["Valid", "Review", "Rejected"]
            chart_values = [valid, review, reject]
            chart_png = _make_bar_chart(chart_labels, chart_values, "Response Classification")
            img_buf = io.BytesIO(chart_png)
            img = Image(img_buf, width=12 * cm, height=7 * cm)
            story.append(img)
        except Exception as e:
            logger.warning("Could not generate quality chart: %s", e)

    story.append(PageBreak())

    # ─── 4. KEY FINDINGS (DISTRIBUTIONS) ──────────────────────────────────────
    story.append(Paragraph("Key Findings — Question Distributions", h1_style))
    distributions = analytics.get("distributions", {})
    dist_count = 0
    for question_key, dist_info in list(distributions.items())[:5]:
        if dist_count >= 5:
            break
        try:
            dist_type = dist_info.get("type", "single_choice")
            dist_data = dist_info.get("data", {})
            story.append(Paragraph(f"Question: {question_key}", h2_style))

            if dist_type == "single_choice":
                # Table
                counts = dist_data.get("counts", {})
                pcts = dist_data.get("percentages", {})
                if counts:
                    tdata = [["Answer", "Count", "Percentage"]] + [
                        [str(k)[:40], str(v), f"{pcts.get(k, 0):.1f}%"]
                        for k, v in list(counts.items())[:10]
                    ]
                    t = Table(tdata, colWidths=[9 * cm, 3 * cm, 4 * cm])
                    t.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EEF2F7"), colors.white]),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D3E5")),
                        ("PADDING", (0, 0), (-1, -1), 5),
                    ]))
                    story.append(t)
                    # Chart
                    try:
                        png = _make_distribution_chart(dist_data, question_key)
                        img = Image(io.BytesIO(png), width=12 * cm, height=7 * cm)
                        story.append(img)
                    except Exception:
                        pass

            elif dist_type == "numeric":
                # Stats table
                tdata = [["Statistic", "Value"]] + [
                    [k.capitalize(), str(round(v, 2)) if v is not None else "N/A"]
                    for k, v in dist_data.items()
                    if k != "count"
                ] + [["Count", str(dist_data.get("count", 0))]]
                t = Table(tdata, colWidths=[8 * cm, 8 * cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EEF2F7"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D3E5")),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]))
                story.append(t)

            elif dist_type == "text":
                top_words = dist_data.get("top_words", [])
                if top_words:
                    story.append(Paragraph(
                        f"Count: {dist_data.get('count', 0)}, "
                        f"Avg length: {dist_data.get('avg_length', 0):.1f} chars",
                        body_style,
                    ))
                    top_str = ", ".join(
                        f"{w['word']} ({w['count']})"
                        for w in top_words[:10]
                    )
                    story.append(Paragraph(f"Top words: {top_str}", body_style))

            story.append(Spacer(1, 0.3 * cm))
            dist_count += 1
        except Exception as e:
            logger.warning("Could not render distribution for %s: %s", question_key, e)

    story.append(PageBreak())

    # ─── 5. SEGMENT COMPARISONS (CROSSTABS) ───────────────────────────────────
    story.append(Paragraph("Segment Comparisons", h1_style))
    crosstabs = analytics.get("crosstabs", [])
    if not crosstabs:
        story.append(Paragraph("No crosstab analysis available.", body_style))
    else:
        for ct in crosstabs[:3]:
            row_var = ct.get("row_var", "")
            col_var = ct.get("col_var", "")
            table_data = ct.get("table", {})
            p_value = ct.get("p_value")
            story.append(Paragraph(f"{row_var} × {col_var}", h2_style))
            if p_value is not None:
                sig = " (statistically significant)" if p_value < 0.05 else ""
                story.append(Paragraph(f"Chi-square p-value: {p_value:.4f}{sig}", body_style))
            if table_data:
                col_vals = sorted(set(
                    cv for row_vals in table_data.values() for cv in row_vals.keys()
                ))
                headers = [row_var[:15] + " / " + col_var[:15]] + [str(cv)[:10] for cv in col_vals[:8]]
                rows = []
                for row_val, col_counts in list(table_data.items())[:10]:
                    row = [str(row_val)[:20]] + [str(col_counts.get(cv, 0)) for cv in col_vals[:8]]
                    rows.append(row)
                tdata = [headers] + rows
                col_widths = [5 * cm] + [2 * cm] * min(len(col_vals), 8)
                t = Table(tdata, colWidths=col_widths)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EEF2F7"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D3E5")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
            story.append(Spacer(1, 0.3 * cm))

    story.append(PageBreak())

    # ─── 6. SUSPICIOUS RESPONSES APPENDIX ────────────────────────────────────
    story.append(Paragraph("Appendix: Top Suspicious Responses", h1_style))
    top_suspicious = suspicious[:20] if suspicious else fraud_summary.get("top_suspicious", [])[:20]
    if not top_suspicious:
        story.append(Paragraph("No suspicious responses flagged.", body_style))
    else:
        headers = ["Respondent ID", "Score", "Label", "Top Reasons"]
        rows = []
        for entry in top_suspicious:
            resp_id = str(entry.get("respondent_id", ""))[:20]
            score = f"{entry.get('fraud_score', 0):.1f}"
            label = str(entry.get("label", entry.get("fraud_label", "")))
            reasons_list = entry.get("reasons", entry.get("fraud_reasons", []))
            reasons_str = "; ".join(str(r)[:40] for r in reasons_list[:2]) if reasons_list else ""
            rows.append([resp_id, score, label, reasons_str[:60]])
        tdata = [headers] + rows
        t = Table(tdata, colWidths=[4 * cm, 2 * cm, 2 * cm, 8 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C00000")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFE7E7"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5BEBE")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("WORDWRAP", (3, 0), (3, -1), True),
        ]))
        story.append(t)

    story.append(PageBreak())

    # ─── 7. RECOMMENDED ACTIONS ───────────────────────────────────────────────
    story.append(Paragraph("Recommended Actions", h1_style))
    label_counts = fraud_summary.get("label_counts", {})
    total_scored = fraud_summary.get("total_scored", 0)
    reject_count = label_counts.get("reject", 0)
    top_reasons = fraud_summary.get("top_reasons", [])

    recommendations = []
    if total_scored > 0:
        fraud_rate = reject_count / total_scored
        if fraud_rate > 0.30:
            recommendations.append(
                "High fraud rate detected (>{:.0%}). Consider extending the field period "
                "and implementing stricter respondent verification.".format(fraud_rate)
            )
        if fraud_rate > 0.15:
            recommendations.append(
                "Moderate fraud rate. Review panel source quality and consider adding "
                "open-end trap questions."
            )

    # Check dominant reasons
    reason_texts = [r.get("reason", "") for r in top_reasons[:3]]
    if any("straightlin" in r.lower() for r in reason_texts):
        recommendations.append(
            "Straightlining detected as a top fraud signal. Add matrix question variety "
            "and consider randomising answer scales."
        )
    if any("speed" in r.lower() for r in reason_texts):
        recommendations.append(
            "Speed-based fraud detected. Consider adding a minimum time-on-page requirement."
        )
    if any("duplicate" in r.lower() for r in reason_texts):
        recommendations.append(
            "Duplicate answer patterns detected. Verify uniqueness of panel respondents "
            "and check for bot submissions."
        )
    if any("miss" in r.lower() for r in reason_texts):
        recommendations.append(
            "High missingness detected. Consider making critical questions required."
        )

    if not recommendations:
        recommendations.append(
            "Survey data quality looks acceptable. Continue monitoring fraud rates on future waves."
        )

    for rec in recommendations:
        story.append(Paragraph(f"• {rec}", bullet_style))

    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#C8D3E5"), spaceAfter=8))
    story.append(Paragraph(
        f"Report generated by Survey Analytics Platform on {generated_at}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.grey, alignment=TA_CENTER),
    ))

    # Build PDF
    doc.build(story)
    pdf_buf.seek(0)
    return pdf_buf.read()
