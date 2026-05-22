# DocuSign eSignature API — OMNI-ANCHOR Mastery Reference
# Account: glenn@hudsonvalleysold.com | docusign.com
# Built: 2026-05-21 | API Version: v2.1

---

## 1. AUTHENTICATION

### Two OAuth Flows

#### A. JWT Grant (Machine-to-Machine — recommended for OMNI-ANCHOR)
Best for server-side automation (Hermes, MCP Interceptor) where no user interaction is required.

**Requirements:**
- Integration Key (Client ID) from DocuSign Apps & Keys
- RSA Key Pair (private key in app, public key uploaded to DocuSign)
- User ID GUID (impersonated user — Glenn's user GUID)
- Redirect URI registered in app settings

**JWT Token Claims:**
```json
{
  "iss": "<integration_key>",
  "sub": "<user_id_guid>",
  "aud": "account-d.docusign.com",  // demo; "account.docusign.com" for prod
  "iat": <now_unix>,
  "exp": <now + 3600>,
  "scope": "signature impersonation"
}
```

**Token endpoint:**
- Demo: `https://account-d.docusign.com/oauth/token`
- Prod: `https://account.docusign.com/oauth/token`

**Consent URL (one-time, admin visits in browser):**
```
https://account-d.docusign.com/oauth/auth?
  response_type=code&
  scope=signature%20impersonation&
  client_id=<integration_key>&
  redirect_uri=<redirect_uri>
```

**Python JWT flow:**
```python
import jwt, time, requests
from cryptography.hazmat.primitives import serialization

private_key = open("private.key", "rb").read()
payload = {
    "iss": INTEGRATION_KEY,
    "sub": USER_ID_GUID,
    "aud": "account-d.docusign.com",  # or account.docusign.com
    "iat": int(time.time()),
    "exp": int(time.time()) + 3600,
    "scope": "signature impersonation",
}
token = jwt.encode(payload, private_key, algorithm="RS256")
resp = requests.post(
    "https://account-d.docusign.com/oauth/token",
    data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
          "assertion": token},
)
access_token = resp.json()["access_token"]
```

**Get Account ID + Base URI:**
```python
user_info = requests.get(
    "https://account-d.docusign.com/oauth/userinfo",
    headers={"Authorization": f"Bearer {access_token}"}
).json()
account_id = user_info["accounts"][0]["account_id"]
base_uri   = user_info["accounts"][0]["base_uri"]  # e.g. https://na3.docusign.net
base_path  = f"{base_uri}/restapi"
```

#### B. Authorization Code Grant (User-initiated)
Use when Glenn logs in interactively (e.g., widget.hvsold.com).
- Redirect user to consent URL → DocuSign returns `code` → exchange for token
- No refresh token: re-authenticate when token expires
- Token lifetime: 8 hours

---

## 2. API CLIENT SETUP (Python SDK)

```python
pip install docusign-esign
```

```python
from docusign_esign import ApiClient, EnvelopesApi

def create_api_client(base_path: str, access_token: str) -> ApiClient:
    api_client = ApiClient()
    api_client.host = base_path  # e.g. "https://na3.docusign.net/restapi"
    api_client.set_default_header("Authorization", f"Bearer {access_token}")
    return api_client

api_client = create_api_client(base_path=base_path, access_token=access_token)
envelope_api = EnvelopesApi(api_client)
```

**Base URL patterns:**
- Demo: `https://demo.docusign.net/restapi`
- Production: use `base_uri` from userinfo response → `{base_uri}/restapi`

---

## 3. ENVELOPES API

Base path: `/v2.1/accounts/{accountId}/envelopes`

### 3a. Create Envelope — Email Signing (send to recipients via email)

```python
from docusign_esign import (
    EnvelopeDefinition, Document, Signer, CarbonCopy,
    SignHere, Tabs, Recipients
)
import base64

def make_envelope(signer_email, signer_name, cc_email, cc_name,
                  pdf_bytes, status="sent"):
    doc_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    doc = Document(
        document_base64=doc_b64,
        name="Purchase Agreement",
        file_extension="pdf",   # pdf | html | docx
        document_id="1"
    )

    signer = Signer(
        email=signer_email,
        name=signer_name,
        recipient_id="1",
        routing_order="1",
        # Omit client_user_id for email mode
    )
    cc = CarbonCopy(
        email=cc_email,
        name=cc_name,
        recipient_id="2",
        routing_order="2"
    )

    # Tab placement: anchor string in document
    sign_here = SignHere(
        anchor_string="**signature_1**",   # text in doc marks position
        anchor_units="pixels",
        anchor_y_offset="10",
        anchor_x_offset="20"
    )
    signer.tabs = Tabs(sign_here_tabs=[sign_here])

    env = EnvelopeDefinition(
        email_subject="Please sign: Purchase Agreement",
        documents=[doc],
        recipients=Recipients(signers=[signer], carbon_copies=[cc]),
        status=status  # "sent" = send now, "created" = draft
    )
    return env

# Execute
env = make_envelope(...)
(result, status_code, headers) = envelope_api.create_envelope_with_http_info(
    account_id=account_id,
    envelope_definition=env
)
envelope_id = result.envelope_id

# Rate limit awareness
remaining = headers.get("X-RateLimit-Remaining")
reset_ts   = headers.get("X-RateLimit-Reset")
```

### 3b. Embedded Signing (In-App — no email, opens in iframe)

Key difference: add `client_user_id` to `Signer`. Then generate a recipient view URL.

```python
signer = Signer(
    email=signer_email,
    name=signer_name,
    recipient_id="1",
    routing_order="1",
    client_user_id="1001"  # any string; ties to this session
)

# After creating envelope, generate the signing URL:
from docusign_esign import RecipientViewRequest

view_request = RecipientViewRequest(
    authentication_method="none",  # or "email", "phone", "kba"
    client_user_id="1001",         # must match Signer.client_user_id
    recipient_id="1",
    return_url="https://widget.hvsold.com/signed?envelope_id=" + envelope_id,
    user_name=signer_name,
    email=signer_email,
)

(view_result, _, _) = envelope_api.create_recipient_view_with_http_info(
    account_id=account_id,
    envelope_id=envelope_id,
    recipient_view_request=view_request
)
signing_url = view_result.url  # embed in iframe or redirect
# URL expires in ~5 minutes — generate fresh each time
```

**Iframe embedding:**
```html
<iframe src="{{ signing_url }}" width="100%" height="800"
        allow="payment *"
        sandbox="allow-forms allow-scripts allow-same-origin allow-top-navigation allow-popups">
</iframe>
```

**Return URL events** (appended as query params):
- `?event=signing_complete`
- `?event=cancel`
- `?event=decline`
- `?event=session_timeout`
- `?event=ttl_expired`
- `?event=viewing_complete` (CC recipients)

### 3c. Other Envelope Operations

```python
# Get envelope status
env = envelope_api.get_envelope(account_id, envelope_id)
print(env.status)  # created | sent | delivered | signed | completed | declined | voided

# List envelopes (last 10 days)
from docusign_esign.models import ListStatusChangesOptions
opts = envelope_api.ApiListStatusChangesOptions()
opts.from_date = "2026-05-01"
result = envelope_api.list_status_changes(account_id, options=opts)

# Void an envelope
from docusign_esign import Envelope
envelope_api.update(account_id, envelope_id,
                    envelope=Envelope(status="voided", voided_reason="Transaction cancelled"))

# Download completed document
doc_bytes = envelope_api.get_document(account_id, envelope_id, document_id="combined")
with open("signed.pdf", "wb") as f:
    f.write(doc_bytes)
```

---

## 4. TEMPLATES API

Base path: `/v2.1/accounts/{accountId}/templates`

### 4a. Send from Template (simplest pattern)

```python
from docusign_esign import EnvelopeDefinition, TemplateRole

env = EnvelopeDefinition(
    status="sent",
    template_id="<your-template-id>"
)

# role_name MUST match the role name defined inside the DocuSign template editor
signer_role = TemplateRole(
    email=signer_email,
    name=signer_name,
    role_name="signer"   # case-sensitive
)
cc_role = TemplateRole(
    email=cc_email,
    name=cc_name,
    role_name="cc"
)
env.template_roles = [signer_role, cc_role]

result = envelope_api.create_envelope(account_id, envelope_definition=env)
```

### 4b. Composite Templates (template + dynamic addendum)

Critical pattern for real estate: standard purchase agreement (template) + property-specific addendum (dynamic HTML/PDF).

```python
from docusign_esign import (
    CompositeTemplate, ServerTemplate, InlineTemplate,
    Recipients, Signer, CarbonCopy, Document, Tabs, SignHere
)

# --- Composite 1: server template with recipient overlay ---
signer = Signer(email=..., name=..., recipient_id="1", routing_order="1")
cc     = CarbonCopy(email=..., name=..., recipient_id="2", routing_order="2")

comp1 = CompositeTemplate(
    composite_template_id="1",
    server_templates=[ServerTemplate(sequence="1", template_id=TEMPLATE_ID)],
    inline_templates=[InlineTemplate(
        sequence="2",
        recipients=Recipients(signers=[signer], carbon_copies=[cc])
    )]
)

# --- Composite 2: inline addendum document ---
addendum_html = f"<html>...property disclosure content...</html>"
doc_b64 = base64.b64encode(bytes(addendum_html, "utf-8")).decode("ascii")

sign_here = SignHere(
    anchor_string="**signature_2**",
    anchor_units="pixels",
    anchor_y_offset="10", anchor_x_offset="20"
)

# Same recipient_id="1" chains to same signer — one signing session, two docs
signer2 = Signer(
    email=signer.email, name=signer.name,
    recipient_id="1", routing_order="1",
    tabs=Tabs(sign_here_tabs=[sign_here])
)
comp2 = CompositeTemplate(
    composite_template_id="2",
    inline_templates=[InlineTemplate(
        sequence="1",
        recipients=Recipients(signers=[signer2], carbon_copies=[cc])
    )],
    document=Document(
        document_base64=doc_b64,
        name="Property Disclosure",
        file_extension="html",
        document_id="1"
    )
)

env = EnvelopeDefinition(status="sent", composite_templates=[comp1, comp2])
result = envelope_api.create_envelope(account_id, envelope_definition=env)
```

---

## 5. TABS (FIELDS)

Tabs are placed in documents either by anchor string or by absolute position (page, x, y).

### Tab Types

| Tab Class | Purpose |
|---|---|
| `SignHere` | Signature field |
| `InitialHere` | Initials field |
| `DateSigned` | Auto-filled date |
| `FullName` | Auto-filled signer name |
| `EmailAddress` | Auto-filled signer email |
| `Title` | Job title input |
| `Text` | Free text input |
| `Number` | Numeric input |
| `Date` | Date input |
| `Checkbox` | Boolean checkbox |
| `RadioGroup` | Radio button group |
| `List` | Dropdown selector |
| `FormulaTab` | Calculated field |
| `Approve` | Approve button |
| `Decline` | Decline button |
| `SSN` | Social security number |
| `Zip` | ZIP code |

### Anchor placement (recommended):
```python
SignHere(
    anchor_string="/sig1/",      # text in document marks position
    anchor_units="pixels",
    anchor_y_offset="10",
    anchor_x_offset="20"
)
```

### Absolute placement:
```python
SignHere(
    document_id="1",
    page_number="1",
    x_position="191",
    y_position="148"
)
```

### Text tab with validation:
```python
from docusign_esign import Text
Text(
    label="PropertyAddress",
    anchor_string="/prop_addr/",
    anchor_units="pixels",
    required="true",
    locked="false",
    tab_label="PropertyAddress",
    value=""  # pre-populate or leave empty
)
```

### Formula tab (calculated totals):
```python
from docusign_esign import FormulaTab
FormulaTab(
    anchor_string="/total_price/",
    formula="[purchase_price] + [earnest_money]",   # references other tab labels
    round_decimal_places="2",
    tab_label="total_price",
    locked="true"
)
```

---

## 6. RECIPIENTS

### Recipient Types

| Class | Type | Description |
|---|---|---|
| `Signer` | signer | Must sign; primary actor |
| `CarbonCopy` | cc | Receives a copy; no signing required |
| `CertifiedDelivery` | certifiedDelivery | Must acknowledge receipt |
| `InPersonSigner` | inPersonSigner | Signs in-person with a host |
| `Intermediary` | intermediary | Can update recipients before next step |
| `Editor` | editor | Can edit envelope details |
| `Witness` | witness | Witnesses a signature |
| `Notary` | notary | Notarizes a signature |
| `Agent` | agent | Routes the envelope |
| `Viewer` | viewer | View-only access |

### Routing Order
Lower `routing_order` goes first. Same number = parallel (all must complete before next group proceeds).

```python
buyer  = Signer(email=..., routing_order="1")  # signs first
seller = Signer(email=..., routing_order="2")  # signs after buyer
agent  = CarbonCopy(email=..., routing_order="3")  # gets copy after seller
```

### Identity Verification
```python
# Access code (simple)
signer = Signer(
    ...,
    access_code="1234"  # recipient must enter this before signing
)

# Phone authentication
from docusign_esign import RecipientPhoneAuthentication
signer = Signer(
    ...,
    phone_authentication=RecipientPhoneAuthentication(
        recipient_may_provide_phone_number="true",
        record_voice_print="false"
    )
)

# Knowledge-Based Authentication (KBA)
from docusign_esign import RecipientIdentityVerification
signer = Signer(
    ...,
    id_check_configuration_name="ID Check$",
    id_check_information_input=...
)
```

---

## 7. POWERFORMS

PowerForms = self-service signing URLs backed by templates. No code needed to initiate.

### PowerForms API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/v2.1/accounts/{accountId}/powerforms` | List all PowerForms |
| POST | `/v2.1/accounts/{accountId}/powerforms` | Create a PowerForm |
| DELETE | `/v2.1/accounts/{accountId}/powerforms` | Delete multiple |
| GET | `/v2.1/accounts/{accountId}/powerforms/{powerFormId}` | Get one |
| PUT | `/v2.1/accounts/{accountId}/powerforms/{powerFormId}` | Update |
| DELETE | `/v2.1/accounts/{accountId}/powerforms/{powerFormId}` | Delete one |
| GET | `/v2.1/accounts/{accountId}/powerforms/{powerFormId}/form_data` | Get submissions |
| GET | `/v2.1/accounts/{accountId}/powerforms/senders` | List senders |

### Create PowerForm (Python SDK)

```python
from docusign_esign import PowerFormsApi, PowerForm

pf_api = PowerFormsApi(api_client)

power_form = PowerForm(
    name="Seller Property Disclosure",
    template_id="<template-id>",
    signing_mode="direct",    # "direct" = URL access, "email" = email invite
    is_active="true",
    email_subject="Disclosure Form — Please Complete",
    email_body="Please complete your property disclosure form.",
    instructions="Fill out all required fields for the property at 123 Main St.",
    # Rate limiting
    limit_use_interval_enabled="true",
    limit_use_interval="1",
    limit_use_interval_units="day",    # hour | day | week | month
    # Use cap
    max_use_enabled="false",
)
result = pf_api.create_power_form(account_id, power_form=power_form)
power_form_url = result.power_form_url  # share this URL with seller
```

### Query PowerForm Submissions

```python
# Get all form data submitted via a PowerForm
from_date = "2026-01-01"
to_date   = "2026-12-31"
form_data = pf_api.get_power_form_form_data(
    account_id,
    power_form_id,
    from_date=from_date,
    to_date=to_date
)
for env in form_data.envelopes:
    for signer in env.recipients.signers:
        for field in signer.form_data:
            print(f"{field.name}: {field.value}")
```

### PowerForm Modes

- **`direct`**: Anyone with the URL can open and complete the form immediately
- **`email`**: DocuSign sends an invitation email; more controlled, requires collecting recipient email first

### Pre-populating PowerForm fields via URL params

Append signer info to the URL to skip data entry:
```
https://powerforms.docusign.com/...?env=live
  &acct=<account_id>
  &Username=Glenn+Fitzgerald
  &Email=buyer@email.com
  &RoleName=Buyer
  &Field_PropertyAddress=123+Main+St
```

---

## 8. CONNECT (WEBHOOKS)

DocuSign Connect pushes envelope events to your webhook URL in real time.

### Event Types

| Event | Trigger |
|---|---|
| `envelope-sent` | Envelope sent to recipients |
| `envelope-delivered` | All recipients received |
| `envelope-completed` | All recipients signed |
| `envelope-declined` | Recipient declined |
| `envelope-voided` | Sender voided |
| `recipient-sent` | Individual recipient notified |
| `recipient-delivered` | Individual recipient opened |
| `recipient-completed` | Individual recipient signed |
| `recipient-declined` | Individual recipient declined |

### Connect Configuration (via API)

```python
from docusign_esign import ConnectApi, ConnectCustomConfiguration

connect_api = ConnectApi(api_client)
config = ConnectCustomConfiguration(
    url_to_publish_to="https://api.hvsold.com/webhooks/docusign",
    name="OMNI-ANCHOR Events",
    allow_envelope_publish="true",
    enable_log="true",
    include_documents="false",     # true = attach signed PDF in payload
    include_envelope_void_reason="true",
    include_time_zone_information="true",
    event_data=ConnectEventData(
        format="json",
        version="restv2.1",
        include_data=["custom_fields", "documents", "extensions",
                      "folders", "recipients", "tabs"]
    ),
    # HMAC signature for payload verification
    sign_message_with_x509_certificate="false",
    hmac_secret="<your-hmac-secret>",
    all_users="true",
    envelope_events=[
        EnvelopeEvent(envelope_event_status_code="completed"),
        EnvelopeEvent(envelope_event_status_code="declined"),
        EnvelopeEvent(envelope_event_status_code="voided"),
    ]
)
result = connect_api.create_connect_configuration(account_id, connect_custom_configuration=config)
```

### Webhook Payload (JSON, v2.1)

```json
{
  "event": "envelope-completed",
  "apiVersion": "v2.1",
  "uri": "/restapi/v2.1/accounts/{accountId}/envelopes/{envelopeId}",
  "retryCount": 0,
  "configurationId": 123,
  "generatedDateTime": "2026-05-21T18:00:00.000Z",
  "data": {
    "accountId": "...",
    "envelopeId": "...",
    "envelopeSummary": {
      "status": "completed",
      "envelopeId": "...",
      "recipients": { "signers": [...] },
      "customFields": { "textCustomFields": [...] },
      "completedDateTime": "2026-05-21T18:00:00.000Z"
    }
  }
}
```

### HMAC Verification (webhook handler)

```python
import hmac, hashlib, base64

def verify_docusign_hmac(payload: bytes, signature_header: str, secret: str) -> bool:
    expected = base64.b64encode(
        hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature_header)
```

### Retry Behavior
- DocuSign retries on HTTP non-2xx: 1h, 3h, 12h, 24h, 48h (5 attempts total)
- Return 200 immediately; process async

---

## 9. BULK SEND

For sending identical (or parameterized) agreements to many recipients at once — e.g., end-of-month closings, all leads in a pipeline.

```python
from docusign_esign import (
    BulkEnvelopesApi, BulkSendingList, BulkSendingCopy,
    BulkSendingCopyRecipient, BulkSendRequest,
    CustomFields, TextCustomField, EnvelopesApi,
    EnvelopeDefinition, Signer, CarbonCopy, Document, Recipients, Tabs
)

# Step 1: Build the bulk recipient list
bulk_copies = []
for contact in leads:  # list of {signer_email, signer_name, cc_email, cc_name}
    bulk_copies.append(BulkSendingCopy(
        recipients=[
            BulkSendingCopyRecipient(
                role_name="signer",   # must match placeholder role_name below
                name=contact["signer_name"],
                email=contact["signer_email"]
            ),
            BulkSendingCopyRecipient(
                role_name="cc",
                name=contact["cc_name"],
                email=contact["cc_email"]
            )
        ],
        custom_fields=[]
    ))

bulk_list = BulkSendingList(name="May Closings", bulk_copies=bulk_copies)
bulk_api = BulkEnvelopesApi(api_client)
created_list = bulk_api.create_bulk_send_list(account_id, bulk_sending_list=bulk_list)
bulk_list_id = created_list.list_id

# Step 2: Create a DRAFT envelope (status="created") with placeholder recipients
placeholder_signer = Signer(
    name="Multi Bulk Recipient::signer",
    email="multiBulkRecipients-signer@docusign.com",
    role_name="signer",
    routing_order="1",
    status="created",
    recipient_id="1"
)
placeholder_cc = CarbonCopy(
    name="Multi Bulk Recipient::cc",
    email="multiBulkRecipients-cc@docusign.com",
    role_name="cc",
    routing_order="2",
    status="created",
    recipient_id="2"
)
draft_env = EnvelopeDefinition(
    email_subject="Please sign your agreement",
    documents=[...],
    recipients=Recipients(signers=[placeholder_signer], carbon_copies=[placeholder_cc]),
    status="created"
)
created_env = envelope_api.create_envelope(account_id, envelope_definition=draft_env)
envelope_id = created_env.envelope_id

# Step 3: Link bulk list to draft via custom field (magic binding)
custom_fields = CustomFields(
    text_custom_fields=[TextCustomField(
        name="mailingListId",
        required="false",
        show="false",
        value=bulk_list_id
    )]
)
envelope_api.create_custom_fields(account_id, envelope_id, custom_fields=custom_fields)

# Step 4: Fire the bulk send
batch = bulk_api.create_bulk_send_request(
    account_id,
    bulk_send_list_id=bulk_list_id,
    bulk_send_request=BulkSendRequest(envelope_or_template_id=envelope_id)
)
batch_id = batch.batch_id

# Step 5: Poll status
status = bulk_api.get_bulk_send_batch_status(account_id, bulk_send_batch_id=batch_id)
print(f"Queued: {status.queued}, Sent: {status.sent}, Failed: {status.failed}")
```

**Limits:** DocuSign processes bulk sends asynchronously. Max 1,000 recipients per bulk list on most plans.

---

## 10. RATE LIMITS

```python
# Always extract from response headers
(result, status_code, headers) = envelope_api.create_envelope_with_http_info(...)

remaining = int(headers.get("X-RateLimit-Remaining", 999))
reset_ts   = int(headers.get("X-RateLimit-Reset", 0))

if remaining < 50:
    from datetime import datetime, timezone
    reset_dt = datetime.fromtimestamp(reset_ts, tz=timezone.utc)
    wait = (reset_dt - datetime.now(tz=timezone.utc)).total_seconds()
    time.sleep(max(0, wait))
```

**Default limits (Standard/Business Pro plans):**
- 1,000 API calls/hour per integration key
- Burst: up to 2,500/hour

---

## 11. REAL ESTATE WORKFLOWS (OMNI-ANCHOR Patterns)

### A. Send Purchase Agreement via Template

```python
env = EnvelopeDefinition(status="sent", template_id=PA_TEMPLATE_ID)
env.template_roles = [
    TemplateRole(email=buyer_email, name=buyer_name, role_name="buyer"),
    TemplateRole(email=seller_email, name=seller_name, role_name="seller"),
    TemplateRole(email=agent_email, name=agent_name, role_name="agent_cc"),
]
result = envelope_api.create_envelope(account_id, envelope_definition=env)
```

### B. PA + Property Addendum (composite)

Use composite templates (Section 4b). Template = boilerplate PA; inline document = property-specific generated addendum.

### C. Seller Disclosure via PowerForm (no agent needed)

```python
pf = PowerForm(
    name=f"Disclosure - {property_address}",
    template_id=DISCLOSURE_TEMPLATE_ID,
    signing_mode="direct",
    is_active="true",
    instructions=f"Property: {property_address}. Fill out all fields.",
    limit_use_interval_enabled="true",
    limit_use_interval="1",
    limit_use_interval_units="day",
)
result = pf_api.create_power_form(account_id, power_form=pf)
disclosure_url = result.power_form_url
# → embed in FUB note, text to seller, or include in listing email
```

### D. Embedded Signing in widget.hvsold.com

```python
# In FUB webhook handler / MCP Interceptor: generate signing URL
signer = Signer(
    email=lead_email, name=lead_name,
    recipient_id="1", routing_order="1",
    client_user_id=lead_fub_id  # FUB contact ID as client_user_id
)
# ... create envelope with signer ...
# ... then:
view = envelope_api.create_recipient_view(
    account_id, envelope_id,
    recipient_view_request=RecipientViewRequest(
        authentication_method="none",
        client_user_id=lead_fub_id,
        recipient_id="1",
        return_url=f"https://widget.hvsold.com/signed?env={envelope_id}&fub={lead_fub_id}",
        user_name=lead_name,
        email=lead_email,
    )
)
# Return view.url to the widget frontend → open in iframe
```

### E. Post-Signing Automation (DocuSign Connect → MCP Interceptor)

Configure DocuSign Connect to POST to `https://api.hvsold.com/webhooks/docusign` on `envelope-completed`.

Handler:
```python
@app.post("/webhooks/docusign")
async def docusign_webhook(request: Request):
    payload = await request.body()
    # Verify HMAC
    sig = request.headers.get("X-DocuSign-Signature-1", "")
    if not verify_docusign_hmac(payload, sig, DOCUSIGN_HMAC_SECRET):
        return JSONResponse({"error": "invalid signature"}, status_code=401)

    data = json.loads(payload)
    envelope_id  = data["data"]["envelopeId"]
    event        = data["event"]
    status       = data["data"]["envelopeSummary"]["status"]

    if event == "envelope-completed":
        # 1. Download signed PDF
        pdf = envelope_api.get_document(account_id, envelope_id, "combined")
        # 2. Store in Drive / FUB note
        # 3. Update FUB deal stage via MCP Interceptor
        await update_fub_deal_stage(envelope_id)

    return JSONResponse({"received": True})
```

---

## 12. DOCUMENT TYPES SUPPORTED

| Extension | Notes |
|---|---|
| `pdf` | Most reliable; anchors by text string or coordinates |
| `html` | Easy programmatic generation; responsive |
| `docx` | Word documents; DocuSign converts to PDF internally |
| `xlsx` / `pptx` | Less common; supported |
| `png` / `jpg` | Image documents |

**Max document size:** 5MB per document, 25MB total per envelope.

---

## 13. KEY API OBJECTS REFERENCE

```python
# Core imports for real estate workflows
from docusign_esign import (
    ApiClient, EnvelopesApi, PowerFormsApi, BulkEnvelopesApi,
    ConnectApi, TemplatesApi,
    EnvelopeDefinition, Document, Envelope,
    Signer, CarbonCopy, CertifiedDelivery, InPersonSigner,
    Recipients, TemplateRole,
    SignHere, InitialHere, DateSigned, FullName, EmailAddress,
    Text, Number, Date, Checkbox, RadioGroup, List, ListItem,
    FormulaTab, Tabs,
    RecipientViewRequest, SenderViewRequest,
    CompositeTemplate, ServerTemplate, InlineTemplate,
    PowerForm, PowerFormRecipient,
    BulkSendingList, BulkSendingCopy, BulkSendingCopyRecipient,
    BulkSendRequest, CustomFields, TextCustomField,
    ConnectCustomConfiguration, EnvelopeEvent,
)
```

---

## 14. ENVIRONMENT VARIABLES (add to /root/omni-anchor/.env)

```bash
# DocuSign
DOCUSIGN_INTEGRATION_KEY=        # from Apps & Keys in DocuSign admin
DOCUSIGN_USER_ID=                # Glenn's User ID GUID
DOCUSIGN_ACCOUNT_ID=             # Account ID (from userinfo response)
DOCUSIGN_BASE_URI=               # e.g. https://na3.docusign.net
DOCUSIGN_PRIVATE_KEY_PATH=/root/omni-anchor/docusign/private.key
DOCUSIGN_HMAC_SECRET=            # for Connect webhook verification
DOCUSIGN_ENVIRONMENT=production  # or demo
```

---

## 15. QUICK HEALTH CHECK

```python
from docusign_esign import AccountsApi

accounts_api = AccountsApi(api_client)
account_info = accounts_api.get_account_information(account_id)
print(account_info.account_name)   # "Glenn Fitzgerald - HudsonValleySOLD"
print(account_info.plan_name)      # current plan
print(account_info.default_account_id)
```

---
*Reference compiled 2026-05-21 from DocuSign eSignature REST API v2.1 docs, official Python SDK, and code-examples-python repo.*
