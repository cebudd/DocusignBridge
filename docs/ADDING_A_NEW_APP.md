# Adding e-signature to a new Elementum app

This walks through wiring up a new Elementum app to send documents out for
signature via DocuSign Bridge, and receive the signed copy back
automatically. Read [../README.md](../README.md) first if you haven't —
it explains the overall architecture this guide assumes, including why
each app gets its own private completion notification instead of sharing
one account-wide DocuSign Connect configuration.

## Before you start: which DocuSign account and middleware deployment?

Two options:

- **Reuse the existing shared deployment** (`https://docusign-bridge.vercel.app`
  and its DocuSign account). Simplest — there's no DocuSign Admin console
  configuration needed per app at all (see Part 3 below for why). Each
  app's envelopes and notifications stay isolated from every other app's
  automatically.
- **Stand up your own account and deployment**, fully isolated from other
  apps at the account level too (separate sending limits/plan, separate
  branding). See [SETUP_FROM_SCRATCH.md](SETUP_FROM_SCRATCH.md).

If you're not sure which, ask whoever owns this integration — it's an org
decision, not a per-app one. The rest of this guide assumes you have a
middleware base URL and its `MIDDLEWARE_API_KEY`.

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
  | `callback_url` | Text (optional) | The webhook URL from your Part B automation (below). Omit entirely if you just want the document signed with no callback — e.g. a one-off signature that doesn't need to come back into Elementum. |

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
Build this *before* Part A goes live, since Part A needs this automation's
webhook URL as its `callback_url`.

### B1. Webhook Trigger

Create a new automation with a **Webhook Trigger** as its first step. Save
it to generate a unique webhook URL — this is the value you'll pass as
`callback_url` in Part A. Leave "Bypass Authentication" on for now (see
README's Known Limitations on why this isn't hardened yet).

### B2. Parse the webhook body (Execute Script task)

Add an **Execute Script** task right after the trigger. Give it one input:

- **Name:** `rawBody`
- **Value:** the webhook trigger's `$body` reference

Code:

```javascript
const payload = JSON.parse(input.parameters.rawBody);

const envelopeId = payload.envelopeId;
const status = payload.status;
const customFields = payload.customFields.textCustomFields || [];
const recordIdField = customFields.find(f => f.name === "elementumRecordId");
const elementumRecordId = recordIdField ? recordIdField.value : null;

return { envelopeId, status, elementumRecordId };
```

Note the payload is read from the **top level** (`payload.envelopeId`,
`payload.status`, `payload.customFields`) — this is the shape DocuSign's
per-envelope notification actually sends, confirmed by capturing a real
payload. It's flatter than what an account-level Connect configuration
would send (which nests everything under `payload.data.envelopeSummary`)
— don't mix the two shapes up if you ever look at older reference
material or DocuSign's general Connect docs, which mostly describe the
account-level format.

**Your automation will also fire on a decline — branch accordingly.**
The bridge subscribes to both `completed` and `declined` envelope events,
so this script runs for either outcome; `result.status` will be
`"completed"` or `"declined"`. Nothing past this point in this guide
(B3–B5) distinguishes between them, and it should — as written, a
decline flows through the exact same find-record → fetch-document →
attach path as a real signature. That's usually not what you want: a
declined envelope still has *a* document available at `/signed-document`
(DocuSign generates a Certificate of Completion even for a decline,
showing 0 signatures and the decline reason — the bridge names this file
`<name>-declined.pdf` rather than `<name>-signed.pdf` so it's not mistaken
for a real signature), but what your automation *does* with that outcome
— attach it as a record of the refusal, skip any stage advancement,
notify someone, whatever fits your app — is specific to your app's
business logic. Add a switch/branch on `result.status` after B2 and route
accordingly. Not yet built into any existing automation as of this
writing; retrieving the actual decline reason text isn't wired up either
(confirmed absent from this webhook payload — would need an extra
`GET /envelopes/{id}/recipients` call).

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

## Part 3: DocuSign Connect setup — none needed

Unlike a typical DocuSign Connect integration, **there is nothing to
configure in the DocuSign Admin console for a new app**. The completion
notification is set per-envelope, directly in the `/create-envelope` API
call the middleware already makes on your behalf (via the `callback_url`
you passed in Part A) — DocuSign sends the notification straight to your
app's own webhook URL, no account-wide Connect configuration involved.

This is a deliberate change from an earlier version of this integration,
which did use one shared account-level Connect configuration. That
approach was abandoned because it fires for *every* envelope on the
account regardless of which app created it — with more than one app
sharing a DocuSign account, every app's webhook would get notified about
every other app's envelope completions too. Per-envelope notification
avoids that entirely: each envelope only ever notifies the one URL it was
given.

If you're standing up your own DocuSign account
([SETUP_FROM_SCRATCH.md](SETUP_FROM_SCRATCH.md)) rather than sharing the
existing one, you still don't need to touch DocuSign Connect in the Admin
console — the same per-envelope mechanism applies regardless of which
account is being used.

Test by running your Part A automation on a real record, signing the
resulting email, and confirming your Part B automation fires exactly
once and correctly finds/updates the record.
