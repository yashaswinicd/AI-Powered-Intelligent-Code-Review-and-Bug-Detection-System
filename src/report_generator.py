"""Build downloadable reports (TXT, JSON and PDF) from a pipeline result."""

import io
import json
from datetime import datetime

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (Paragraph, Preformatted, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)
    PDF_AVAILABLE = True
except ImportError:  # reportlab is optional
    PDF_AVAILABLE = False


def _header(result):
    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "language": result["language_name"],
        "lines": result["stats"]["total_lines"],
        "original_score": result["original_score"]["score"],
        "fixed_score": result["fixed_score"]["score"],
        "issues_found": len(result["original_issues"]),
        "fixes_applied": len(result["fixes"]),
        "verified": result["verification"]["verified"],
    }


def to_json(result):
    payload = _header(result)
    payload["issues"] = [
        {k: i.get(k) for k in ("type", "line", "severity", "category",
                               "message", "suggestion", "status")}
        for i in result["original_issues"]]
    payload["fixes"] = result["fixes"]
    payload["corrected_code"] = result["fixed_code"]
    payload["verification"] = result["verification"]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def to_text(result):
    h = _header(result)
    out = ["AI CODE REVIEW & AUTO-FIX REPORT", "=" * 60,
           f"Generated     : {h['generated']}",
           f"Language      : {h['language']}",
           f"Lines         : {h['lines']}",
           f"Score         : {h['original_score']} -> {h['fixed_score']}",
           f"Issues found  : {h['issues_found']}",
           f"Fixes applied : {h['fixes_applied']}",
           f"Verified      : {'YES' if h['verified'] else 'NO'}",
           f"Result        : {result['verification']['message']}", "",
           "ISSUES", "-" * 60]
    if not result["original_issues"]:
        out.append("No issues found.")
    for i in result["original_issues"]:
        out.append(f"Line {i['line']:>5} [{i['severity'].upper():<8}] "
                   f"{i['type']} ({i['status']})")
        out.append(f"           {i['message']}")
        out.append(f"           Suggestion: {i['suggestion']}")
    out += ["", "CORRECTED CODE", "-" * 60, result["fixed_code"]]
    return "\n".join(out)


def to_pdf(result):
    if not PDF_AVAILABLE:
        return None
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Code Review Report",
                            leftMargin=36, rightMargin=36)
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8.5)
    story = [Paragraph("AI Code Review &amp; Auto-Fix Report",
                       styles["Title"])]
    h = _header(result)
    summary = [["Language", h["language"]], ["Lines", str(h["lines"])],
               ["Score", f"{h['original_score']} -> {h['fixed_score']}"],
               ["Issues found", str(h["issues_found"])],
               ["Fixes applied", str(h["fixes_applied"])],
               ["Verified", "YES" if h["verified"] else "NO"]]
    table = Table(summary, colWidths=[110, 380])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
    story += [table, Spacer(1, 12), Paragraph("Issues", styles["Heading2"])]
    rows = [["Line", "Severity", "Type", "Status"]]
    for i in result["original_issues"][:200]:
        rows.append([str(i["line"]), i["severity"], i["type"][:40],
                     i["status"]])
    if len(rows) == 1:
        rows.append(["-", "-", "No issues found", "-"])
    issues = Table(rows, colWidths=[40, 70, 270, 110], repeatRows=1)
    issues.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    story += [issues, Spacer(1, 12),
              Paragraph("Corrected code", styles["Heading2"])]
    code = result["fixed_code"]
    lines = code.split("\n")[:300]
    story.append(Preformatted("\n".join(l[:100] for l in lines),
                              ParagraphStyle("code", fontName="Courier",
                                             fontSize=7.5, leading=9)))
    if len(code.split("\n")) > 300:
        story.append(Paragraph("(truncated to 300 lines)", small))
    doc.build(story)
    return buffer.getvalue()
