# Adding e-signature to a new Elementum app

This walks through wiring up a new Elementum app to send documents out for
signature via DocuSign Bridge, and receive the signed copy back
automatically. Read [../README.md](../README.md) first if you haven't —
it explains the overall architecture this guide assumes.

## Before you start: which DocuSign account and middleware deployment?

Two options:

- **Reuse the existing shared deployment** (`https://docusign-bridge.vercel.app`
  and its DocuSign account). Simplest — nothing to set up on the DocuSign
  side beyond a new Connect configuration (Part 3 below). The tradeoff:
  every app sharing this account will get notified about every other
  app's envelope completions too (see the callout in Part 3), so your
  receiving automation needs to handle "this notification isn't for me"
  gracefully.
- **Stand up your own account and deployment**, fully isolated from other
  apps. See [SETUP_FROM_SCRATCH.md](SETUP_FROM_SCRATCH.md). More setup
  work up front, no cross-app notification concerns.

If you're not sure which, ask whoever owns this integration — it's an org
decision, not a per-app one.

The rest of this guide assumes you have: a middleware base URL, its
`MIDDLEWARE_API_KEY`, and (if setting up Connect yourself) access to that
DocuSign account's Admin console.

## Part A: the "send for signature" automation

Add a step (to an existing automation, or a new one) that fires whenever
your app's record is ready to be signed. The step itself is an **API
task** (Elementum's generic outbound HTTP request task):

- **Method:** `POST`
- **URL:** `{middleware base URL}/create-envelope`
- **Authorization:** Bearer token, value = `MIDDLEWARE_API_KEY`
- **Request body type:** Multipart Form Data (not JSON — the endpoint
  expects a real file upload)
- **Parts:**

  | Part name | Type | Value |
  |---|---|---|
  | `document` | File/attachment | The PDF to send — a value reference to whatever record/task produced it |
  | `elementum_record_id` | Text | Your record's human-readable ID (e.g. the app's ID/handle field) — this is what comes back later to identify which record to update |
  | `signer_email` | Text | The signer's email |
  | `signer_name` | Text | The signer's full name |
  | `email_subject` | Text (optional) | Defaults to "Please sign your document" if omitted |

- **Response type:** JSON
- **Continue on Error Status:** leave unchecked — if envelope creation
  fails, the automation should stop, not proceed as if it worked.

Response is `{"envelopeId": "...", "status": "sent"}`. You generally don't
need to store the `envelopeId` yourself — the completion webhook (Part B)
will hand it back to you.

**A note on the PDF's content:** the middleware places the signature and
date fields near the bottom of whichever page turns out to be the *last*
page of your uploaded PDF, computed dynamically from the actual file (not
a hardcoded page number or fixed coordinates). You don't need to add
anything special to your report template for this to work — no anchor
tags, no fixed layout assumptions.

## Part B: the "receive signed document" automation

This automation is triggered by DocuSign, not by anything in your app.

### B1. Webhook Trigger

Create a new automation with a **Webhook Trigger** as its first step. Save
it to generate a unique webhook URL — you'll need this for Part 3. Leave
"Bypass Authentication" on for now (see README's Known Limitations on why
this isn't hardened yet).

### B2. Parse the webhook body (Execute Script task)

Add an **Execute Script** task right after the trigger. Give it one input:

- **Name:** `rawBody`
- **Value:** the webhook trigger's `$body` reference

Code:

```javascript
const payload = JSON.parse(input.parameters.rawBody);

const envelopeId = payload.data.envelopeId;
const status = payload.data.envelopeSummary.status;
const customFields = payload.data.envelopeSummary.customFields.textCustomFields || [];
const recordIdField = customFields.find(f => f.name === "elementumRecordId");
const elementumRecordId = recordIdField ? recordIdField.value : null;

return { envelopeId, status, elementumRecordId };
```

**Do not** wrap the return value in your own `result`/`textResult` keys
(e.g. `return { result: {...}, textResult: status }`). Elementum
automatically wraps every script's return value as `refs["result"]` (JSON)
and `refs["textResult"]` (text) — if your own return object *also* has
keys literally named `result`/`textResult`, you end up with confusing
double-nesting (`result.result.envelopeId` instead of `result.envelopeId`)
and things silently resolve to `null` downstream. Just return the flat
object above.

Then, in this task's **Output Schema** panel, manually declare three
`Text` properties: `envelopeId`, `status`, `elementumRecordId`. The
property names must match the script's returned keys **exactly**,
including case — a mismatch (e.g. `envelopeID` vs `envelopeId`) resolves
to a silent `null` rather than an error. Once declared, this script task
exposes `result.envelopeId`, `result.status`, and
`result.elementumRecordId` directly as refs for downstream tasks — you
don't need a separate JSON File Reader task to destructure them.

**A tooling gotcha, not a logic bug:** the "Test value" box in the script
editor's Execute-preview panel has a bug — pasting real JSON into it
produces `Unexpected token o in JSON at position 1`, which is the
signature of a JS object being coerced to the string `"[object Object]"`
before your script ever sees it. This is the test harness mishandling the
input, not your script. Don't spend time debugging against it — instead,
make sure the `rawBody` input's source is the trigger's real `$body`
(not a manually-typed test value), save, and validate by triggering a
real envelope completion end to end.

### B3. Find the record

Add a **Search Records** (find record) task. Filter on your app's ID/
handle field, where the value equals `result.elementumRecordId` from the
script task.

If you're sharing a DocuSign account with other apps (see the callout at
the top of this doc), this search will sometimes find nothing — that's
expected when the webhook fired for a different app's envelope. Make sure
your automation handles a zero-result search gracefully (skip the
remaining steps) rather than erroring.

### B4. Fetch the signed document

Add another **API task**:

- **Method:** `GET`
- **URL:** `{middleware base URL}/signed-document/` + the `result.envelopeId`
  ref from the script task (use the `$` picker to insert it)
- **Authorization:** Bearer token, value = `MIDDLEWARE_API_KEY`
- **Response type:** File (not JSON — this endpoint returns raw PDF bytes)
- **Continue on Error Status:** unchecked

The middleware names the returned file `<original document name>-signed.pdf`
automatically via the response's `Content-Disposition` header — Elementum
reads this and names the attachment accordingly, so you don't need to set
a filename yourself.

### B5. Attach it to the record

Add a **Save Attachment** task: `record_id` = the record found in B3,
`file` = the file ref from B4 (something like `refs["response.file"]` —
check what's actually exposed on that task and use the matching ref
name).

From here, do whatever else your app needs — advance a workflow stage,
send a notification, etc.

### Draft vs. Published

Elementum automations have separate Draft and Published versions. Editing
a task and clicking **Save** only updates the Draft — live webhook
traffic keeps running whatever's currently **Published** until you
explicitly publish your changes. If a fix "isn't working" after you've
saved it, check this first.

## Part 3: configure DocuSign Connect for this app

This is done in the DocuSign account's Admin console, not in Elementum.

1. **Admin → Integrations → Connect → Add Configuration → Custom.**
2. **Name:** something identifying this app (e.g. "Elementum — CAPA
   Bridge" or your app's name).
3. **URL to Publish:** the webhook URL from step B1.
4. **Data Format:** `REST v2.1` (this is JSON; cannot be changed after
   saving).
5. **Event Message Delivery Mode:** `Send Individual Messages (SIM)`.
6. Expand **Envelope and Recipients**, check **Envelope Signed/Completed**
   under Envelope Events.
7. In the **Include Data** panel (nested inside that same section), check
   **Custom Fields** — this is what makes `elementumRecordId` show up in
   the webhook payload. Leave **Documents** unchecked; the middleware
   fetches the actual signed PDF separately (Part B4), so including it
   here would just bloat the payload for no reason.
8. **Associated Users/Groups:** see the callout below if you're sharing
   an account with other apps.
9. Leave the security options (HMAC, OAuth, Basic Auth, Mutual TLS)
   unchecked for now — not yet hardened across this integration (see
   README's Known Limitations).
10. **Add Configuration.**

Test by running your Part A automation on a real record, signing the
resulting email, and confirming your Part B automation fires and
correctly finds/updates the record.

### If you're sharing a DocuSign account with other apps

DocuSign Connect configurations are account-wide by default (Associated
Users/Groups = "All Users/Groups") — every configuration fires for every
qualifying event on the entire account, regardless of which app's
automation actually created the envelope. With multiple apps sharing one
account, that means **every app's webhook gets notified about every
envelope completion**, not just its own.

Two ways to handle this:

- **Defensive receiving automations (simplest):** each app's Part B3
  search will just find zero records for envelopes that weren't its own,
  and the automation should skip the rest of the steps in that case
  (already called out in B3). No DocuSign-side changes needed.
- **Scope by sender identity:** if each app impersonates a distinct
  DocuSign user when creating envelopes (a different signer/sender
  identity per app), you can set each Connect configuration's
  **Associated Users/Groups** to "Select Users/Groups to include" and
  scope it to just that app's sending identity, so only relevant events
  reach each webhook. More setup work, cleaner isolation.

Whichever you pick, make it consistent across all apps sharing the
account — don't mix approaches.
