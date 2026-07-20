"""
Shared DocuSign JWT Grant auth helpers, used by every script in this project.
"""

import os
import time

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

INTEGRATION_KEY = os.environ["DOCUSIGN_INTEGRATION_KEY"]
USER_ID = os.environ["DOCUSIGN_USER_ID"]
AUTH_SERVER = os.environ["DOCUSIGN_AUTH_SERVER"]

SCOPE = "signature impersonation"
TOKEN_LIFETIME_SECONDS = 3600


def load_private_key() -> str:
    # Locally, the key lives in a file (see .env's DOCUSIGN_PRIVATE_KEY_PATH).
    # On Vercel, there's no gitignored secrets/ folder to read from, so the
    # key's raw text is set directly as the DOCUSIGN_PRIVATE_KEY env var
    # instead. Whichever is present wins.
    key_text = os.environ.get("DOCUSIGN_PRIVATE_KEY")
    if key_text:
        return key_text

    key_path = os.environ["DOCUSIGN_PRIVATE_KEY_PATH"]
    with open(key_path, "r") as f:
        return f.read()


def build_assertion() -> str:
    private_key = load_private_key()

    now = int(time.time())
    payload = {
        "iss": INTEGRATION_KEY,
        "sub": USER_ID,
        "aud": AUTH_SERVER,
        "iat": now,
        "exp": now + TOKEN_LIFETIME_SECONDS,
        "scope": SCOPE,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_access_token() -> str:
    assertion = build_assertion()
    response = requests.post(
        f"https://{AUTH_SERVER}/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_user_info(access_token: str) -> dict:
    response = requests.get(
        f"https://{AUTH_SERVER}/oauth/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()
