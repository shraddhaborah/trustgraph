import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

def create_sample_ilit_pdf(filename="sample_ilit_trust.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )

    styles = getSampleStyleSheet()
    
    # Custom document styling
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1, # Center
        spaceAfter=15
    )
    
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=10,
        leading=14,
        alignment=4, # Justified
        spaceAfter=8
    )

    story = []

    # Title
    story.append(Paragraph("THE ALEXANDER FAMILY IRREVOCABLE LIFE INSURANCE TRUST", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color="black", spaceAfter=15))

    # Preamble
    story.append(Paragraph(
        "This Irrevocable Trust Agreement is made this 12th day of March, 2024, by and between "
        "<b>ROBERT C. ALEXANDER</b> (hereinafter referred to as the 'Grantor'), residing in New York, NY, "
        "and <b>BEACON TRUST COMPANY, N.A.</b>, along with <b>ELEANOR V. ALEXANDER</b> (hereinafter "
        "referred to as the 'Co-Trustees').",
        body_style
    ))

    # Article I: Trust Purpose & Assets
    story.append(Paragraph("ARTICLE I: TRUST ESTATE AND PURPOSE", heading_style))
    story.append(Paragraph(
        "1.1 <b>Primary Purpose:</b> The Grantor hereby establishes this trust primarily to hold life insurance "
        "policies on the life of the Grantor (including Policy No. NY-994821 issued by Northwestern Mutual in the "
        "face amount of $15,000,000) and to receive, invest, and distribute the proceeds thereof for the benefit of "
        "the Grantor's descendants.",
        body_style
    ))
    story.append(Paragraph(
        "1.2 <b>Irrevocability:</b> This Agreement and the trust created hereunder shall be strictly irrevocable. "
        "The Grantor expressly waives all rights to alter, amend, revoke, or terminate this Agreement in whole or in part.",
        body_style
    ))

    # Article II: Crummey Withdrawal Powers
    story.append(Paragraph("ARTICLE II: CRUMMEY WITHDRAWAL POWERS", heading_style))
    story.append(Paragraph(
        "2.1 <b>Annual Withdrawal Right:</b> Following any contribution or transfer of property (including premium payments) "
        "to the Trust, each primary beneficiary—namely <b>SOPHIA M. ALEXANDER</b> and <b>LUCAS R. ALEXANDER</b>—shall "
        "have the absolute power to withdraw a pro-rata portion of such contribution, up to the maximum annual gift tax "
        "exclusion amount authorized under Section 2503(b) of the Internal Revenue Code.",
        body_style
    ))
    story.append(Paragraph(
        "2.2 <b>Lapse and Notice:</b> The Co-Trustees shall provide written notice to each beneficiary upon receiving a "
        "qualifying contribution. The withdrawal power shall lapse sixty (60) days following the date of notice.",
        body_style
    ))

    # Page Break forced for testing multi-page parsing
    story.append(Spacer(1, 0.5 * inch))

    # Article III: Distributions During Grantor's Lifetime & Post-Mortem
    story.append(Paragraph("ARTICLE III: TRUST DISTRIBUTIONS AND APPOINTMENTS", heading_style))
    story.append(Paragraph(
        "3.1 <b>Lifetime Distributions:</b> During the Grantor's lifetime, the Co-Trustees may distribute income or "
        "principal to the Grantor's spouse, <b>ELEANOR V. ALEXANDER</b>, solely for her health, education, support, and "
        "maintenance (HEMS standard).",
        body_style
    ))
    story.append(Paragraph(
        "3.2 <b>Post-Mortem Distribution & Division:</b> Upon the Grantor's death and collection of the insurance policy "
        "proceeds, the Co-Trustees shall divide the remaining trust estate into equal, separate sub-trusts for "
        "<b>SOPHIA M. ALEXANDER</b> and <b>LUCAS R. ALEXANDER</b>.",
        body_style
    ))
    story.append(Paragraph(
        "3.3 <b>Mandatory Age Milestones:</b> Each beneficiary's sub-trust shall distribute 33% of principal upon attaining "
        "the age of thirty (30), 50% of the remaining balance upon attaining the age of thirty-five (35), and the balance "
        "in full upon attaining the age of forty (40).",
        body_style
    ))

    # Article IV: Trustee Powers & GST Provisions
    story.append(Paragraph("ARTICLE IV: ADMINISTRATIVE POWERS AND TAX CLAUSES", heading_style))
    story.append(Paragraph(
        "4.1 <b>Generation-Skipping Transfer (GST) Exemption:</b> The Co-Trustees are authorized to allocate any available "
        "GST exemption under Section 2632 of the Code to transfers made to this Trust.",
        body_style
    ))
    story.append(Paragraph(
        "4.2 <b>Successor Trustees:</b> In the event <b>BEACON TRUST COMPANY, N.A.</b> resigns or fails to act, "
        "<b>MERIDIAN CAPITAL TRUST CO.</b> is hereby appointed as Successor Corporate Co-Trustee.",
        body_style
    ))

    # Signature Block
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("IN WITNESS WHEREOF, the Grantor and Co-Trustees have executed this Agreement.", body_style))
    story.append(Spacer(1, 0.3 * inch))
    
    signatures = (
        "____________________________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;____________________________________<br/>"
        "<b>ROBERT C. ALEXANDER</b>, Grantor&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>ELEANOR V. ALEXANDER</b>, Co-Trustee<br/><br/><br/>"
        "____________________________________<br/>"
        "<b>BEACON TRUST COMPANY, N.A.</b>, Corporate Co-Trustee"
    )
    story.append(Paragraph(signatures, body_style))

    # Build PDF document
    doc.build(story)
    print(f"Successfully generated sample trust PDF: {os.path.abspath(filename)}")

if __name__ == "__main__":
    create_sample_ilit_pdf()