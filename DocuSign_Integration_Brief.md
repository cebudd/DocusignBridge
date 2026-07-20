# CAPA E-Signature via DocuSign — Project Kickoff Brief

> **Purpose:** portable context to seed a Claude Code build session. Drop this file
> into the new project repo (rename to `CLAUDE.md` if you want Claude Code to load it
> automatically), or paste it as your opening message. It captures the business
> context, the target architecture, the compliance requirements, and a DocuSign
> primer so the build starts with full context.
>
> **First instruction for Claude Code:** treat the DocuSign details below as a mental
> model, not gospel — verify against the current official docs at
> https://developers.docusign.com before writing integration code.

---

## 1. Business context (why this exists)

- **Customer:** Edwards Lifesciences (Class III medical devices — heart valves). Highly regulated.
- **Deal:** replace their legacy quality suite (ETQ Reliance) by re-hosting quality workloads on **Elementum** (an AI process-orchestration platform that runs on Snowflake). Land with **CAPA** (Corrective and Preventive Action), expand across six modules.
- **The gating constraint:** 21 CFR Part 11-compliant **electronic signatures**. If we can't offer an agreeable Part 11 approach, the deal is a non-starter. Native e-signature in Elementum is a product feature request with **no near-term timeline**, so we need an interim path.
- **This project = that interim path:** integrate a validated third party (**DocuSign**) so Elementum can capture compliant e-signatures without waiting on native support. Validated as a legitimate pattern by an internal SME (Brian Carter, who built CAPA + Supplier CAPA at GE Healthcare).

## 2. Compliance requirements (what "done" must satisfy)

Edwards' own SOPs (CAPA Process + Reliance EQMS CAPA Instruction) show CAPA is **not** a sign-once document:

- **Four approver e-signatures per CAPA**, one at each phase gate: Determination, Investigation, Implementation, and Control (the Control approval closes the CAPA).
- Signer role: **CAPA Approver = Sr. Director of Quality or higher**.
- Part 11 essentials the solution must honor (per Brian's GE experience):
  - **Re-authenticate at the moment of signing** (not just "logged in earlier").
  - **Capture a signing reason** and a trustworthy **timestamp**.
  - **Lock/version the exact snapshot that was signed**; if the record changes afterward, it must be **re-signed**.
  - **Immutable audit trail** of every signature event.
- DocuSign's **Certificate of Completion** (who signed, when, IP, auth method) and its **Part 11 module** (forced re-auth + signing reason) map directly onto these requirements — confirm current capabilities in their docs.

## 3. Target architecture (Curt's model, refined)

```
Elementum CAPA record
   │  (1) stage transition fires an automation
   ▼
Elementum  ──REST──►  Middleware server (TO BUILD)
   ▲                      │  (2) create DocuSign envelope with the PDF + signer(s)
   │                      ▼
   │                   DocuSign (demo env)
   │                      │  (3) emails signer(s); they authenticate + sign
   │                      ▼
   │                   DocuSign Connect ──webhook──► Middleware server
   │                      (4) "envelope complete" + signed PDF (or fetch via API)
   └──────────────◄───────┘
   (5) signed PDF (with Certificate of Completion) attached to the CAPA record;
       record advances to the next stage
```

**Components to build:**
1. **Middleware server** (Node or Python — pick in CC). Exposes REST endpoints Elementum calls; talks to DocuSign; hosts the webhook listener.
2. **DocuSign client** — OAuth (JWT Grant), envelope creation, document/tab placement, status + document retrieval.
3. **Webhook listener** — receives DocuSign Connect callbacks, verifies them (HMAC), downloads the signed PDF + certificate, calls back to Elementum.
4. **Elementum callback** — attaches the signed PDF to the CAPA record and advances the workflow.

**The thing that gets signed:** Elementum generates a **PDF "report"** — a point-in-time snapshot of the CAPA record at that phase. Elementum sends it to the middleware; the middleware puts it in a DocuSign envelope; once signed it comes back and is attached to the CAPA record. (Elementum owns PDF generation; the middleware just moves and wraps it.)

## 4. DocuSign primer (remedial — the mental model)

- **Environments:** developer/**demo** (`account-d.docusign.com`, `demo.docusign.net`) vs **production** (`account.docusign.com`). Build and test in demo. You already have a developer account.
- **Authentication — OAuth 2.0 JWT Grant** (server-to-server, no interactive login):
  - You need: an **Integration Key** (client ID), an **RSA keypair**, the **impersonated user's API User ID (GUID)**, your **Account ID**, and the OAuth base host (demo).
  - Grant **consent once** (a one-time consent URL), then the server mints access tokens with a JWT signed by your private key. Scope: `signature impersonation`.
  - (There's also Authorization Code Grant for user-interactive apps — not what we want for backend automation.)
- **Envelope** — the central object. Container for documents + recipients + the routing workflow. Create it with status `sent` to start signing.
  - **Documents** — the PDF(s), base64-encoded into the envelope definition (or referenced from a template).
  - **Recipients** — signers (with name, email, routing order), plus carbon copies, etc.
  - **Tabs (fields)** — where signature/date/reason fields sit on the page. Prefer **anchor tabs** (place relative to anchor text like `/sig1/` embedded in the PDF) over absolute x/y.
- **Templates** — reusable envelope definitions (document layout + recipient roles + tab positions). Good fit for a **standard CAPA report** so every envelope is consistent.
- **Signing modes:** **remote/email** (DocuSign emails the signer — matches Curt's model) vs **embedded** (signer signs inside your app via a generated URL/iframe — an option if Edwards later wants signing inside Elementum's UI).
- **Webhooks — DocuSign Connect:** configure notifications (per-account, or **per-envelope** via `eventNotification` in the create call). It POSTs status changes (e.g., `completed`) to your listener URL. Options: include the signed documents in the payload, or just get notified and **download** them. Secure it with **HMAC** verification.
- **Retrieving the signed artifact:** `GET /envelopes/{envelopeId}/documents/combined` returns the signed PDF **plus the Certificate of Completion** in one file — the artifact to attach to the CAPA record.
- **Envelope lifecycle:** `created → sent → delivered → completed` (or `declined` / `voided`).

## 5. Suggested build order (milestones)

1. **Auth spike:** get a JWT access token from the demo account (integration key + RSA key + consent). Nothing works until this does.
2. **Send envelope:** from a hardcoded local PDF, create + send an envelope to your own email; sign it manually. Confirm you can then download the combined signed PDF + certificate.
3. **Webhook listener:** stand up the Connect listener (use ngrok to expose localhost), receive the `completed` event, auto-download the signed PDF.
4. **Wrap in REST:** expose a `POST /sign-request` endpoint (accepts a PDF + signer info) and a `/webhook` endpoint; this is the middleware contract Elementum will call.
5. **Elementum ends:** simulate the Elementum-side calls (send report → receive completion), then wire to the real record/attachment + stage advance.
6. **Part 11 hardening:** enable re-authentication + signing reason; confirm the certificate captures what auditors expect; handle the "record changed after signing → re-sign" rule.

## 6. Open questions / decisions

- Node vs Python for the middleware (CC can recommend based on your comfort + Elementum's ecosystem).
- Where the middleware is hosted (local for the demo; later a proper environment).
- Exactly how Elementum triggers the call and attaches the returned PDF (depends on Elementum's automation + API capabilities — a discovery item).
- What Edwards specifically accepts as a valid e-signature (their policy / gold-standard system) — **customer discovery question, still open with Kevin Young.**
- Volume/scale target (Edwards runs hundreds–low-thousands of CAPAs/yr + supplier CAPAs).

## 7. Setup checklist before coding

- [ ] DocuSign **developer account** (done).
- [ ] Create an **Integration Key** in the developer console; generate an **RSA keypair**.
- [ ] Note your **API Account ID** and **API User ID (GUID)**.
- [ ] Grant **consent** for the impersonation scope (one-time URL).
- [ ] Install **ngrok** (or similar) for local webhook testing.
- [ ] New git repo; put this brief in it (as `CLAUDE.md` or `PROJECT_BRIEF.md`).
- [ ] Keep secrets out of git (`.env` + `.gitignore`).

## 8. People & pointers

- **Brian Carter** (Elementum) — CAPA/Part 11 SME (GE Healthcare). Offered to help design the e-sig integration; **Luc** offered as extra hands.
- **DocuSign docs:** https://developers.docusign.com (eSignature REST API, JWT auth, Connect, Certificate of Completion, Part 11).
- This brief was assembled from the Cowork CAPA discovery work; the design deck and speaker script live in the `/CAPA/` project folder.
