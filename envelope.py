"""
Shared envelope-definition builder, used by both the standalone test script
(send_envelope.py) and the live middleware endpoint (server.py).
"""

import io

from pypdf import PdfReader

# How far up from the bottom edge of the last page to place the fields, in
# points (1/72 inch). Leaves room for both fields plus a margin.
BOTTOM_MARGIN_POINTS = 130
LEFT_MARGIN_POINTS = 72  # Sign Here field's x position (1 inch from the left)
DATE_FIELD_X_POINTS = 300  # Date Signed field sits to the right of it


def get_last_page_info(pdf_bytes: bytes) -> tuple[int, float]:
    """Returns (last_page_number, last_page_height_in_points) for a PDF.

    Reading the actual PDF lets us place the signature on whichever page
    turns out to be last, and near the bottom of that page's real height --
    regardless of how many pages the report ends up being.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    last_page_height = float(reader.pages[-1].mediabox.height)
    return page_count, last_page_height


def build_envelope_definition(
    pdf_base64: str,
    elementum_record_id: str,
    signer_email: str,
    signer_name: str,
    email_subject: str,
    last_page_number: int,
    last_page_height: float,
    document_name: str = "CAPA Report",
    access_code: str = None,
) -> dict:
    field_y_position = int(last_page_height - BOTTOM_MARGIN_POINTS)

    signer = {
        "recipientId": "1",
        "routingOrder": "1",
        "email": signer_email,
        "name": signer_name,
        "tabs": {
            "signHereTabs": [
                {
                    "documentId": "1",
                    "pageNumber": str(last_page_number),
                    "xPosition": str(LEFT_MARGIN_POINTS),
                    "yPosition": str(field_y_position),
                }
            ],
            "dateSignedTabs": [
                {
                    "documentId": "1",
                    "pageNumber": str(last_page_number),
                    "xPosition": str(DATE_FIELD_X_POINTS),
                    "yPosition": str(field_y_position),
                }
            ],
        },
    }

    if access_code:
        signer["accessCode"] = access_code

    return {
        "emailSubject": email_subject,
        "status": "sent",
        "customFields": {
            "textCustomFields": [
                {
                    "name": "elementumRecordId",
                    "value": elementum_record_id,
                }
            ]
        },
        "documents": [
            {
                "documentId": "1",
                "name": document_name,
                "fileExtension": "pdf",
                "documentBase64": pdf_base64,
            }
        ],
        "recipients": {"signers": [signer]},
    }
