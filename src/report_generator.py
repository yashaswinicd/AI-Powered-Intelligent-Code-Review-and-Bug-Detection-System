import os
import sys
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import REPORTS_DIR

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    PDF_AVAILABLE = True
except:
    PDF_AVAILABLE = False

class ReportGenerator:
    def __init__(self):
        os.makedirs(REPORTS_DIR, exist_ok=True)

    def generate(self, review_result, security_result):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}"

        text_report = self._generate_text_report(review_result, security_result)
        json_report = self._generate_json_report(review_result, security_result)

        text_path = os.path.join(REPORTS_DIR, f"{filename}.txt")
        json_path = os.path.join(REPORTS_DIR, f"{filename}.json")

        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_report)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2)

        pdf_file = None
        if PDF_AVAILABLE:
            pdf_file = f"{filename}.pdf"
            self._generate_pdf_report(review_result, security_result, os.path.join(REPORTS_DIR, pdf_file))

        return {
            'text_report': text_report,
            'json_report': json_report,
            'text_file': f"{filename}.txt",
            'json_file': f"{filename}.json",
            'pdf_file': pdf_file
        }

    def _generate_pdf_report(self, review_result, security_result, path):
        doc = SimpleDocTemplate(path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('Title', parent=styles['Title'],
            fontSize=20, textColor=colors.HexColor('#0080ff'))
        heading_style = ParagraphStyle('Heading', parent=styles['Heading2'],
            fontSize=14, textColor=colors.HexColor('#64c8ff'))

        story.append(Paragraph("AI-Powered Code Review Report", title_style))
        story.append(Spacer(1, 0.3*inch))

        info_data = [
            ['File', review_result.get('filename', 'Unknown')],
            ['Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Score', f"{review_result.get('score', 0)}/100"],
            ['Grade', review_result.get('grade', 'N/A')],
            ['Total Issues', str(review_result.get('total_issues', 0))],
        ]
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('FONTSIZE', (0,0), (-1,-1), 11),
            ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor('#1a1a2e'), colors.HexColor('#16213e')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#64c8ff')),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))

        story.append(Paragraph("Bugs Detected", heading_style))
        story.append(Spacer(1, 0.1*inch))
        bugs = review_result.get('bugs', {}).get('bugs', [])
        if bugs:
            for bug in bugs:
                story.append(Paragraph(
                    f"• [{bug.get('severity')}] Line {bug.get('line')}: {bug.get('message')}",
                    styles['Normal']))
        else:
            story.append(Paragraph("✅ No bugs detected!", styles['Normal']))

        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("Security Issues", heading_style))
        story.append(Spacer(1, 0.1*inch))
        security_issues = security_result.get('issues', [])
        if security_issues:
            for issue in security_issues:
                story.append(Paragraph(
                    f"• [{issue.get('severity')}] Line {issue.get('line')}: {issue.get('message')}",
                    styles['Normal']))
        else:
            story.append(Paragraph("✅ No security issues!", styles['Normal']))

        doc.build(story)

    def _generate_text_report(self, review_result, security_result):
        report = []
        report.append("=" * 60)
        report.append("AI-POWERED CODE REVIEW REPORT")
        report.append("=" * 60)
        report.append(f"File: {review_result.get('filename', 'Unknown')}")
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Score: {review_result.get('score', 0)}/100")
        report.append(f"Grade: {review_result.get('grade', 'N/A')}")
        report.append(f"Total Issues: {review_result.get('total_issues', 0)}")
        report.append("")
        report.append("BUGS DETECTED:")
        report.append("-" * 40)
        bugs = review_result.get('bugs', {}).get('bugs', [])
        if bugs:
            for bug in bugs:
                report.append(f"  [{bug.get('severity')}] Line {bug.get('line')}: {bug.get('message')}")
        else:
            report.append("  No bugs detected!")
        report.append("")
        report.append("SECURITY ISSUES:")
        report.append("-" * 40)
        security_issues = security_result.get('issues', [])
        if security_issues:
            for issue in security_issues:
                report.append(f"  [{issue.get('severity')}] Line {issue.get('line')}: {issue.get('message')}")
        else:
            report.append("  No security issues detected!")
        report.append("")
        report.append("=" * 60)
        return "\n".join(report)

    def _generate_json_report(self, review_result, security_result):
        return {
            'timestamp': datetime.now().isoformat(),
            'filename': review_result.get('filename'),
            'score': review_result.get('score'),
            'grade': review_result.get('grade'),
            'total_issues': review_result.get('total_issues'),
            'bugs': review_result.get('bugs'),
            'security': security_result,
            'review_issues': review_result.get('review_issues'),
            'ml_prediction': review_result.get('ml_prediction')
        }