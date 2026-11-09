from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from xml.sax.saxutils import escape
from datetime import datetime, timezone

def build_pdf(case_id, investigator, evidence, events):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    story = [
        Paragraph("CrimeVision AI — Forensic Analysis Summary", styles["Title"]),
        Paragraph("TRAINING / INVESTIGATIVE AID — NOT A COURT-ADMISSIBLE FORENSIC OPINION", styles["Heading2"]),
        Spacer(1, 8),
        Paragraph(f"Case reference: {escape(str(case_id))}", styles["BodyText"]),
        Paragraph(f"Investigator: {escape(str(investigator or 'Not specified'))}", styles["BodyText"]),
        Paragraph(f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}", styles["BodyText"]),
        Spacer(1, 12), Paragraph("Evidence register", styles["Heading1"])
    ]
    rows = [["Evidence ID","Type","Filename","SHA-256","Timestamp","Sign-off"]]
    for item in evidence:
        m = item["metadata"]
        rows.append([m["evidence_id"],m["kind"],m["filename"][:24],m["sha256"][:16]+"…",m["timestamp"][:19], "Yes" if m["signoff"] else "No"])
    table = Table(rows, repeatRows=1, colWidths=[24*mm,14*mm,34*mm,31*mm,35*mm,18*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#26374a")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                               ("GRID",(0,0),(-1,-1),.3,colors.grey),("FONTSIZE",(0,0),(-1,-1),6.5),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story += [table, Spacer(1,12), Paragraph("Analysis summaries", styles["Heading1"])]
    for item in evidence:
        m, a = item["metadata"], item["analysis"]
        story.append(Paragraph(f"{escape(m['evidence_id'])} — {escape(m['filename'])}", styles["Heading2"]))
        story.append(Paragraph(escape(str(a)[:3500]), styles["Small"]))
        story.append(Spacer(1,6))
    story += [Paragraph("Chronological event ledger", styles["Heading1"])]
    for e in sorted(events, key=lambda x:str(x.get("timestamp",""))):
        line = f"{e.get('timestamp','')} | {e.get('source','')} | {e.get('event','')} | Evidence: {e.get('evidence_id','')}"
        story.append(Paragraph(escape(line), styles["Small"]))
    story += [Spacer(1,16), Paragraph("Chain-of-custody note", styles["Heading1"]),
              Paragraph("This prototype records upload-time SHA-256 hashes, UTC ingestion timestamps, case reference, and a user-declared review checkbox. It does not establish source authenticity, secure evidence storage, access audit trails, trusted timestamps, or an independently verified chain of custody. Preserve original media and maintain custody under applicable institutional procedures.", styles["Small"])]
    doc.build(story)
    return buffer.getvalue()
