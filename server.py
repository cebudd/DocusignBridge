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
from envelope import build_envelope_definition

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
    pdf_file = request.files["document"]
    pdf_base64 = base64.b64encode(pdf_file.read()).decode("utf-8")

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

    url = (
        f"{account['base_uri']}/restapi/v2.1/accounts/{account['account_id']}"
        f"/envelopes/{envelope_id}/documents/combined"
    )
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"certificate": "true"},
    )
    response.raise_for_status()

    return Response(response.content, mimetype="application/pdf")


if __name__ == "__main__":
    app.run(port=5001, debug=True)
