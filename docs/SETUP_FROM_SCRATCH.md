# Setting up your own DocuSign account and middleware deployment

Use this when you need a fully independent instance of DocuSign Bridge —
your own DocuSign account, your own middleware deployment — rather than
reusing an existing shared one. If you just need to connect a new
Elementum app to an **existing** deployment, see
[ADDING_A_NEW_APP.md](ADDING_A_NEW_APP.md) instead; most of this document
is unnecessary for that case.

## 1. DocuSign developer account setup

You need a DocuSign account (a free developer/demo account is fine for
building and testing; production use requires a real DocuSign
subscription — see the note on CFR Part 11 in the main README if that's
relevant to your use case).

1. Log into your DocuSign account at `account-d.docusign.com` (developer)
   or your production domain.
2. Go to **Apps and Keys**. Click **Add App / Integration Key**, name it,
   and note the generated **Integration Key** (a GUID — this is your
   `DOCUSIGN_INTEGRATION_KEY`).
3. On that same Integration Key's page, add a **Redirect URI** (required
   for JWT Grant even though it's never actually used for a redirect in
   this flow — `http://localhost:5000` works fine).
4. Generate an **RSA Keypair** on that page. **Copy the private key text
   immediately** (the block starting `-----BEGIN RSA PRIVATE KEY-----`) —
   DocuSign typically only displays it once.
5. Note your **API Account ID** and your **User ID** (your own user GUID)
   — both shown on the Apps and Keys page. These become
   `DOCUSIGN_ACCOUNT_ID` and `DOCUSIGN_USER_ID`.

## 2. Grant consent (one-time)

JWT Grant requires the impersonated user to consent once. Build this URL,
substituting your Integration Key and redirect URI (URL-encoded):

```
https://account-d.docusign.com/oauth/auth?response_type=code&scope=signature%20impersonation&client_id=YOUR_INTEGRATION_KEY&redirect_uri=YOUR_REDIRECT_URI
```

Visit it in a browser while logged into the DocuSign account you want to
impersonate, and click **Accept**. The page will fail to load afterward
(it tries to redirect to your non-running local server) — that's
expected; close the tab. If you're unsure whether consent actually took,
don't worry about it: the very first API call in Step 4 will fail with an
explicit `consent_required` error (with a fresh consent link) if it
didn't.

## 3. Fork/clone this repo and deploy to Vercel

1. Fork or clone `github.com/cebudd/DocusignBridge`.
2. In Vercel: **Add New → Project**, import your repo. Vercel
   auto-detects the Flask app (`server.py` + `requirements.txt`) with no
   extra configuration needed.
3. Before deploying, add these **Environment Variables** in Vercel:

   | Name | Value |
   |---|---|
   | `DOCUSIGN_INTEGRATION_KEY` | From Step 1.2 |
   | `DOCUSIGN_USER_ID` | From Step 1.5 |
   | `DOCUSIGN_ACCOUNT_ID` | From Step 1.5 |
   | `DOCUSIGN_AUTH_SERVER` | `account-d.docusign.com` (developer) or your production auth host |
   | `DOCUSIGN_BASE_URI` | Your account's API base URI — see the note below; don't guess this |
   | `DOCUSIGN_PRIVATE_KEY` | The full RSA private key text from Step 1.4, including the `BEGIN`/`END` lines |
   | `MIDDLEWARE_API_KEY` | A random secret you generate yourself (e.g. `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`) — this is what every Elementum `api_task` calling this deployment needs to send as its Bearer token |

   **On `DOCUSIGN_BASE_URI`:** don't assume `demo.docusign.net` — DocuSign
   accounts can live on different hosts. The correct way to get it is to
   call `/oauth/userinfo` after you have an access token and read the
   `base_uri` and `account_id` it returns for your account — this
   middleware already does that internally on every request (see
   `auth.py`'s `get_user_info`), so the env var mainly needs to be *a*
   valid value to satisfy the code's startup checks; it isn't load-
   bearing for correctness at request time. If you want to confirm it
   ahead of time, mint a token and call that endpoint yourself.

4. **Deploy.**

## 4. Verify the deployment

```bash
# Should return 401 -- confirms the auth check is active
curl -s -o /dev/null -w "%{http_code}\n" https://your-deployment.vercel.app/signed-document/test

# Should return 200 and a real PDF, once you have a real completed envelope ID
curl -s -H "Authorization: Bearer YOUR_MIDDLEWARE_API_KEY" \
  https://your-deployment.vercel.app/signed-document/{a-real-completed-envelope-id} \
  -o test.pdf && file test.pdf
```

To fully exercise the create-envelope path:

```bash
curl -X POST https://your-deployment.vercel.app/create-envelope \
  -H "Authorization: Bearer YOUR_MIDDLEWARE_API_KEY" \
  -F "document=@some-test.pdf" \
  -F "elementum_record_id=TEST-001" \
  -F "signer_email=you@example.com" \
  -F "signer_name=Your Name"
```

If that succeeds, you'll get a real signature-request email — sign it,
then use the returned `envelopeId` with the `/signed-document/` call
above.

## 5. Next: wire up an Elementum app

Once the deployment is verified, go to
[ADDING_A_NEW_APP.md](ADDING_A_NEW_APP.md) to connect an Elementum app to
it.
