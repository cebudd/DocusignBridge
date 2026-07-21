"""
The middleware server: exposes REST endpoints for Elementum's automations
to call. This is where the DocuSign-specific logic (JWT signing, envelope
creation, document retrieval) lives, so Elementum never has to know
anything about DocuSign directly.

Endpoints:
  POST /create-envelope                -- accepts a PDF file + signer info,
                                          creates and sends a DocuSign
                                          envelope, returns its envelopeId.
  GET /signed-document/<envelope_id>  -- returns the combined signed PDF
                                          + Certificate of Completion for a
                                          completed envelope.
"""

import base64
import hmac
import os

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request

from auth import get_access_token, get_user_info
from envelope import build_envelope_definition, get_last_page_info

load_dotenv()

MIDDLEWARE_API_KEY = os.environ["MIDDLEWARE_API_KEY"]

app = Flask(__name__)


@app.before_request
def require_api_key():
    auth_header = request.headers.get("Authorization", "")
    provided_key = auth_header.removeprefix("Bearer ").strip()

    if not hmac.compare_digest(provided_key, MIDDLEWARE_API_KEY):
        return jsonify({"error": "unauthorized"}), 401


@app.route("/create-envelope", methods=["POST"])
def create_envelope():
    uploaded_file = request.files["document"]
    pdf_bytes = uploaded_file.read()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    last_page_number, last_page_height = get_last_page_info(pdf_bytes)

    original_filename = uploaded_file.filename or "CAPA Report.pdf"
    document_name = os.path.splitext(original_filename)[0]

    elementum_record_id = request.form["elementum_record_id"]
    signer_email = request.form["signer_email"]
    signer_name = request.form["signer_name"]
    email_subject = request.form.get("email_subject", "Please sign your document")

    token = get_access_token()
    info = get_user_info(token)
    account = info["accounts"][0]

    envelope_definition = build_envelope_definition(
        pdf_base64,
        elementum_record_id,
        signer_email,
        signer_name,
        email_subject,
        last_page_number,
        last_page_height,
        document_name,
    )

    response = requests.post(
        f"{account['base_uri']}/restapi/v2.1/accounts/{account['account_id']}/envelopes",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=envelope_definition,
    )
    response.raise_for_status()
    result = response.json()

    return jsonify({"envelopeId": result["envelopeId"], "status": result["status"]})


@app.route("/signed-document/<envelope_id>", methods=["GET"])
def get_signed_document(envelope_id):
    token = get_access_token()
    info = get_user_info(token)
    account = info["accounts"][0]
    base = f"{account['base_uri']}/restapi/v2.1/accounts/{account['account_id']}"
    auth_header = {"Authorization": f"Bearer {token}"}

    documents_response = requests.get(f"{base}/envelopes/{envelope_id}/documents", headers=auth_header)
    documents_response.raise_for_status()
    documents = documents_response.json().get("envelopeDocuments", [])
    document_name = next(
        (doc["name"] for doc in documents if doc.get("documentId") == "1"),
        "document",
    )

    combined_response = requests.get(
        f"{base}/envelopes/{envelope_id}/documents/combined",
        headers=auth_header,
        params={"certificate": "true"},
    )
    combined_response.raise_for_status()

    signed_filename = f"{document_name}-signed.pdf"
    response = Response(combined_response.content, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="{signed_filename}"'
    return response


if __name__ == "__main__":
    app.run(port=5001, debug=True)
