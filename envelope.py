"""
Shared envelope-definition builder, used by both the standalone test script
(send_envelope.py) and the live middleware endpoint (server.py).
"""


def build_envelope_definition(
    pdf_base64: str,
    elementum_record_id: str,
    signer_email: str,
    signer_name: str,
    email_subject: str,
) -> dict:
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
                "name": "CAPA Report",
                "fileExtension": "pdf",
                "documentBase64": pdf_base64,
            }
        ],
        "recipients": {
            "signers": [
                {
                    "recipientId": "1",
                    "routingOrder": "1",
                    "email": signer_email,
                    "name": signer_name,
                    "tabs": {
                        "signHereTabs": [
                            {
                                "anchorString": "/sig1/",
                                "anchorUnits": "pixels",
                                "anchorXOffset": "0",
                                "anchorYOffset": "0",
                            }
                        ],
                        "dateSignedTabs": [
                            {
                                "anchorString": "/date1/",
                                "anchorUnits": "pixels",
                                "anchorXOffset": "0",
                                "anchorYOffset": "0",
                            }
                        ],
                    },
                }
            ]
        },
    }
