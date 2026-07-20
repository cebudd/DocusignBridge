"""
Generates a bare-bones one-page PDF to use as our test document for
Milestone 2. Contains anchor strings ("/sig1/", "/date1/") that DocuSign
will use to position the signature and date fields -- see send_envelope.py
for how those anchors get turned into tabs.
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

OUTPUT_PATH = "test_capa_report.pdf"

c = canvas.Canvas(OUTPUT_PATH, pagesize=letter)

c.setFont("Helvetica-Bold", 16)
c.drawString(72, 720, "Test CAPA Report")

c.setFont("Helvetica", 12)
c.drawString(72, 690, "This is a placeholder document for testing the DocuSign bridge.")

c.drawString(72, 640, "Approver Signature: /sig1/")
c.drawString(72, 610, "Date: /date1/")

c.save()

print(f"Wrote {OUTPUT_PATH}")
