"""
Milestone 2 finale: download the combined signed PDF + Certificate of
Completion for a completed envelope.
"""

import sys

import requests

from auth import get_access_token, get_user_info

DEFAULT_ENVELOPE_ID = "f77b23b7-353c-87f4-81d2-5d865f70142b"
OUTPUT_PATH = "signed_capa_report.pdf"


if __name__ == "__main__":
    envelope_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ENVELOPE_ID

    token = get_access_token()
    info = get_user_info(token)
    account = info["accounts"][0]
    account_id = account["account_id"]
    base_uri = account["base_uri"]

    url = (
        f"{base_uri}/restapi/v2.1/accounts/{account_id}"
        f"/envelopes/{envelope_id}/documents/combined"
    )
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"certificate": "true"},
    )
    response.raise_for_status()

    with open(OUTPUT_PATH, "wb") as f:
        f.write(response.content)

    print(f"Wrote {OUTPUT_PATH} ({len(response.content)} bytes)")
