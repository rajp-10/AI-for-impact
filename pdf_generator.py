from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


def generate_pdf(company_name, report, filename="ShieldAI_Report.pdf"):

    doc = SimpleDocTemplate(filename)

    styles = getSampleStyleSheet()

    content = []

    title = Paragraph(
        "<b>ShieldAI - Recruitment Fraud Audit Report</b>",
        styles["Title"]
    )

    content.append(title)
    content.append(Spacer(1, 20))

    content.append(
        Paragraph(
            f"<b>Company:</b> {company_name}",
            styles["Normal"]
        )
    )

    content.append(
        Paragraph(
            f"<b>Risk Score:</b> {report['risk_score']}%",
            styles["Normal"]
        )
    )

    content.append(
        Paragraph(
            f"<b>Risk Level:</b> {report['risk_level']}",
            styles["Normal"]
        )
    )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "<b>Analysis Summary</b>",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            report["analysis_summary"],
            styles["Normal"]
        )
    )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "<b>Identified Red Flags</b>",
            styles["Heading2"]
        )
    )

    for flag in report["red_flags"]:
        content.append(
            Paragraph(f"• {flag}", styles["Normal"])
        )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "<b>Recommended Actions</b>",
            styles["Heading2"]
        )
    )

    for item in report["safety_checklist"]:
        content.append(
            Paragraph(f"• {item}", styles["Normal"])
        )

    doc.build(content)

    return filename