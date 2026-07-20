"""
Milestone 2: create and send a real envelope from a local PDF, to prove the
full "create envelope -> DocuSign emails signer" path works.
"""

import base64

import requests

from auth import get_access_token, get_user_info
from envelope import build_envelope_definition

PDF_PATH = "test_capa_report.pdf"
SIGNER_EMAIL = "cbudd@elementum.com"
SIGNER_NAME = "Curt Budd"
EMAIL_SUBJECT = "Please sign: Test CAPA Report"

# Placeholder until Elementum is wired up for real -- this is the value the
# middleware's "create envelope" endpoint will eventually receive from
# Elementum (the CAPA record's ID), so the DocuSign Connect webhook can hand
# it straight back to us later without a lookup.
ELEMENTUM_RECORD_ID = "TEST-CAPA-001"


if __name__ == "__main__":
    with open(PDF_PATH, "rb") as f:
        pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

    token = get_access_token()
    info = get_user_info(token)
    account = info["accounts"][0]
    account_id = account["account_id"]
    base_uri = account["base_uri"]

    envelope_definition = build_envelope_definition(
        pdf_base64,
        ELEMENTUM_RECORD_ID,
        SIGNER_EMAIL,
        SIGNER_NAME,
        EMAIL_SUBJECT,
    )

    response = requests.post(
        f"{base_uri}/restapi/v2.1/accounts/{account_id}/envelopes",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=envelope_definition,
    )
    response.raise_for_status()
    result = response.json()

    print("Envelope sent.")
    print("Envelope ID:", result["envelopeId"])
    print("Status:", result["status"])
