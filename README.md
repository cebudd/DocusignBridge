# DocuSign Bridge

A small middleware service that lets any Elementum app collect a legally
binding e-signature via DocuSign, without Elementum needing to know
anything about DocuSign's API directly.

This document covers *why* this exists and *how the whole system fits
together*. If you're here to add e-signature to a new Elementum app, skip
ahead to [docs/ADDING_A_NEW_APP.md](docs/ADDING_A_NEW_APP.md). If you need
to stand up a brand-new DocuSign account and deployment instead of reusing
an existing one, see [docs/SETUP_FROM_SCRATCH.md](docs/SETUP_FROM_SCRATCH.md).

## 1. Why this exists

Elementum doesn't have native e-signature. The first customer that needed
one was Edwards Lifesciences, replacing a legacy quality system (ETQ
Reliance) with Elementum for CAPA (Corrective and Preventive Action) — a
medical device quality process that is legally required to be
**21 CFR Part 11 compliant** (electronic signatures with forced
re-authentication at signing, a captured signing reason, a trustworthy
timestamp, and an immutable audit trail). Native e-signature in Elementum
has no near-term roadmap, so this project integrates **DocuSign**, an
already-validated third party, as an interim path.

The design generalizes past that first use case: any Elementum app that
needs "send this document out, get a legally signed copy back, attach it
to the record" can reuse this same bridge rather than building its own
DocuSign integration from scratch.

**Current limitation:** true 21 CFR Part 11 behavior (DocuSign's "Part 11
module" — forced re-authentication *at the moment of signing*, not just at
document access, plus a mandatory signing reason) requires a **DocuSign
account tier we don't currently have** — it's a commercial-plan feature
provisioned by DocuSign directly, not something togglable via API or
account settings. Confirmed by calling `Accounts:get` against our current
demo account: the `status21CFRPart11` property isn't even present in the
response, meaning the account isn't eligible for it, not just switched
off. Until a Part 11-enabled account is provisioned, this bridge does
plain remote e-signature — a real, useful capability, but the Part 11
requirement should be represented to customers as "available once we have
the right DocuSign account," backed by DocuSign's own Part 11
documentation, not as something already live in the demo.

## 2. Architecture

```
Elementum App                 Middleware (this repo)              DocuSign
─────────────                 ──────────────────────              ────────

record ready to sign
   │
   │ api_task: POST /create-envelope
   │  (PDF attachment, signer email/name,
   │   elementum_record_id, email_subject)
   ▼
                          mints a JWT-signed access
                          token, calls DocuSign's
                          Envelopes:create, embeds
                          elementum_record_id as an
                          envelope custom field
                                    │
                                    ▼
                                                              creates + sends
                                                              the envelope;
                                                              emails the signer
                                                                     │
                                                              signer clicks the
                                                              email link, signs
                                                                     │
                                                              envelope status
                                                              -> completed
                                                                     │
                    DocuSign Connect (webhook) ◄──────────────────────┘
                          │
                          │  POSTS directly to Elementum's own
                          │  webhook trigger URL -- NOT through
                          │  this middleware. Payload includes
                          │  envelopeId, status, and the
                          │  elementum_record_id custom field.
                          ▼
Elementum webhook trigger fires
   │
   │ parse the payload (envelopeId, status, elementum_record_id)
   │ find the record by elementum_record_id
   │
   │ api_task: GET /signed-document/{envelopeId}
   ▼
                          mints a fresh token, fetches the
                          combined signed PDF + Certificate
                          of Completion, names the file
                          "<original-name>-signed.pdf"
                                    │
                                    ▼
   ◄──────────────────── returns the file
   │
   │ attach the file to the record found above
   ▼
record now has the signed document attached
```

**Why the webhook is direct (not routed through the middleware):**
Elementum has a native webhook trigger that can receive a POST from any
external system, including DocuSign Connect. Routing the "envelope
completed" notification through the middleware first would add a hop for
no benefit — Elementum can receive it directly. The middleware is only
needed for the two things Elementum genuinely can't do on its own:
authenticating to DocuSign (a JWT signed with an RSA private key — the
sandboxed script-task runtime that Elementum automations run in has no
crypto or network access, confirmed directly with Elementum's own
documentation agent) and knowing DocuSign's specific REST API shapes.

**Why the envelope custom field, not a lookup:** When the middleware
creates an envelope, it attaches an **envelope custom field** named
`elementumRecordId` carrying whatever record ID value the calling
Elementum app passed in. DocuSign Connect can be configured to include
custom fields in its webhook payload, so when the "completed" notification
arrives, Elementum already knows which record to update — no search
required to correlate "which envelope was this for."

## 3. What's in this repo

| File | Purpose |
|---|---|
| `server.py` | The Flask app — the two endpoints Elementum calls (`/create-envelope`, `/signed-document/<id>`), and a shared-secret auth check in front of both. |
| `auth.py` | JWT Grant authentication (mint an access token, look up account info). Shared by every script and by `server.py`. |
| `envelope.py` | Builds the DocuSign envelope definition — documents, recipient, signature/date field placement, the `elementumRecordId` custom field. Shared by `server.py` and `send_envelope.py`. |
| `send_envelope.py`, `get_token.py`, `get_account_info.py`, `download_signed_document.py`, `make_test_pdf.py` | Standalone scripts used to build and test the middleware locally before it existed as a live server. Not part of the deployed app, kept for local testing/debugging. |
| `requirements.txt` | Python dependencies. |
| `DocuSign_Integration_Brief.md` | The original project kickoff brief — business/compliance context and the initial target architecture (since revised — see Section 2 above for what actually got built). |

**Not committed to git** (see `.gitignore`): `.env` (local secrets),
`secrets/` (the RSA private key file), `venv/`, and any signed PDFs
generated during testing (they contain a real signer's name, IP address,
and handwritten signature image).

## 4. Current deployment

- Middleware: `https://docusign-bridge.vercel.app` (Vercel, auto-deploys
  from the `main` branch of this GitHub repo)
- GitHub: `https://github.com/cebudd/DocusignBridge` (public repo; no
  secrets are committed to it)
- DocuSign: a personal developer/demo account (`account-d.docusign.com`)
  — **not** a production or CFR Part 11 account. See Section 1's
  limitation note.

## 5. Known limitations

- **No true Part 11 support yet** (Section 1). An access-code-based
  "authenticate before viewing" stopgap was tried and deliberately removed
  — it read as unconvincing for a customer demo and doesn't represent the
  real Part 11 module's behavior (which also re-authenticates at the
  moment of signing, not just at document access).
- **Single account, currently.** Every envelope this middleware creates
  goes through one DocuSign account. If multiple Elementum apps share this
  deployment, DocuSign Connect will notify *every* connected Elementum
  webhook about *every* envelope's completion on that account, not just
  the ones each app created. See
  [docs/ADDING_A_NEW_APP.md](docs/ADDING_A_NEW_APP.md) for how receiving
  automations should handle this defensively.
- **No webhook authentication yet**, on either leg. Elementum's webhook
  trigger currently has "Bypass Authentication" enabled (anyone who
  discovers the URL could POST a fake completion event), and the
  middleware's own endpoints are protected only by a static shared-secret
  Bearer token (adequate for now, but not a substitute for per-request
  signing).
- **Single signer per envelope.** The envelope definition supports exactly
  one signer with one signature and one date field, placed near the
  bottom of whichever page turns out to be last in the uploaded PDF. Multi
  -signer routing isn't built.
