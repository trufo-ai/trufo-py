# 3. Product Signing Setup

Set up C2PA signing through Trufo: choose a signing route and execution mode, integrate against the test host, validate a Branded Generator Product if you need one, and move to production.

Prerequisites: an account with MFA, an organization, and API keys ([2. Trufo Account Setup](2-trufo-account-setup.md)).

---

## 1. Choose Standard or Branded Signing

| Route | Who signs | Use it when | Validation |
| --- | --- | --- | --- |
| **Standard Trufo signing** | Trufo, with Trufo's C2PA certificate | Publishing, AI-generated labels (`ai_generated`), CAWG identity and metadata, media actions, watermarking | Organization Validation (OV) |
| **Branded Generator Product** | Trufo, with a certificate issued for your product | You need AI-edit labels (`ai_modified`), asset creation (`creation`, `placement="created"`), or external edit histories (`parentOf` with `action_history`), or you want your product name on the signing certificate | OV + Branded Product Validation (BPV) |

A self-serve BPV certificate carries your product name (`CN`) with `O=Trufo Inc., C=US`. To have your own organization in `O`, contact [support@trufo.ai](mailto:support@trufo.ai).

To sign with your own C2PA signer and Trufo-issued certificates, which requires Product Validation (PV), see [5. BYO C2PA Certificates](5-byo-c2pa-certificates.md). For a comparison of all three architectures, see [1. Choose Your C2PA Route](1-choose-your-c2pa-route.md#signing-architectures).

Standard signing and branded signing use the same functions and request fields; branded signing adds `branded_gp_id`.

---

## 2. Choose an Execution Mode and Region

| Mode | How to call | Original media sent to Trufo | Requirements |
| --- | --- | --- | --- |
| Cloud, direct (`REQUEST`) | `sign_c2pa_cloud()` / `POST /c2pa/sign` with `media_input` | Yes | `pip install trufo`; ≤ 10 MB |
| Cloud, via S3 (`TASK`) | `sign_c2pa_cloud(..., execution_mode=ExecutionMode.TASK, mime_type=...)` | Yes (ephemeral S3, deleted after 1–2 days) | Production hosts only; required above 10 MB and for media actions (`watermark`, `resize`, `crop`, `trim`, `transcode`, `repackage`) on audio, video, PDF, or SVG |
| Local, Python SDK | `sign_c2pa_local()` | No | Linux `x86_64`/`arm64` (glibc 2.28+), CPython 3.10–3.15, `sdk-download` key; `trufo[local-sign-only]`, or `trufo[local-full]` for watermarking |
| Local, Docker | `POST /c2pa/sign` on `ghcr.io/trufo-ai/trufo-local:2.4` (`2.4-full` for watermarking) | No | Docker, `sdk-download` key; any language over local HTTP |

In Local mode, Trufo receives your request parameters (ingredient bytes replaced by hashes), the claim to sign, and the finished manifest. To keep generated thumbnails and stored manifest copies off Trufo, set `thumbnail_settings.policy` to `"none"` and `skip_manifest_storage=True` (not compatible with `per_embed` watermarking). See [Storage Options and Privacy](../topics/storage-options.md).

**Region:** the host you call decides where Cloud-mode media is processed. Use `https://eu.api.trufo.ai` (`TRUFO_API_URL_EUROPE`) to keep processing in EU infrastructure; set `TRUFO_API_URL=https://eu.api.trufo.ai` for the Docker image. Poll tasks on the host that accepted them.

Setup details: [Cloud Signing](../topics/signing-cloud.md), [Local Signing (Python SDK)](../topics/signing-local-python.md), [Local Signing (Docker)](../topics/signing-local-docker.md).

---

## 3. Integrate on the Test Host

1. Create a `c2pa-sign-test` key ([2. Trufo Account Setup](2-trufo-account-setup.md#5-create-api-keys)) and store it as `TRUFO_C2PA_SIGN_TEST_API_KEY`.
2. Sign against `https://test.api.trufo.ai`:

```python
from pathlib import Path

from trufo import sign_c2pa_cloud_test
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
assert api_key, "Set TRUFO_C2PA_SIGN_TEST_API_KEY or run: trufo set-api-key c2pa-sign-test <KEY>"

signed_bytes = sign_c2pa_cloud_test(
    api_key,
    Path("input.jpg").read_bytes(),
    manifest_title="signed.jpg",
    ingredient_title="input.jpg",
    actions=[["publish", {}]],
    assertions=[["cawg_identity", {"cawg_identity_id": "test"}]],  # optional CAWG identity assertion; "test" works on the test host only
)
Path("signed.jpg").write_bytes(signed_bytes)
```

For Local mode, call `sign_c2pa_local_test(api_key, media_bytes, ...)` with the same keyword arguments, or point the Docker image at `TRUFO_API_URL=https://test.api.trufo.ai`. The full runnable script is [signing_cloud.py](../topics/signing_cloud.py).

3. Prototype branded flows before BPV approval with `branded_gp_id="test"`. This example declares an edit made outside Trufo by attaching the original as `parentOf`:

```python
import base64
from pathlib import Path

from trufo import sign_c2pa_cloud_test
from trufo.c2pa import DigitalSourceType
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_TEST)
original_b64 = base64.b64encode(Path("original.jpg").read_bytes()).decode()

signed_bytes = sign_c2pa_cloud_test(
    api_key,
    Path("edited.jpg").read_bytes(),  # must not carry its own C2PA manifest
    manifest_title="edited.jpg",
    branded_gp_id="test",
    assertions=[
        ["ingredient", {
            "relationship": "parentOf",
            "title": "original.jpg",
            "media": original_b64,
            "action_history": [
                {
                    "action": "c2pa.cropped",
                    "digitalSourceType": DigitalSourceType.HUMAN_EDITS.value,
                },
            ],
        }],
    ],
)
Path("edited_signed.jpg").write_bytes(signed_bytes)
```

Test-host behavior to plan around (see [Setup and Credentials — Hosts](../topics/setup.md#hosts)):

- Outputs carry a test certificate that public validators do not trust; see [Verification](../topics/verification.md#2-verifying-test-host-assets-in-ci) to validate them in CI.
- Only `REQUEST` execution is available; exercise media actions on audio and video with `sign_c2pa_local_test()` or the Docker image.
- Register AI systems and software agents on `https://api.trufo.ai` (a `c2pa-sign-test` key is accepted) and reference them on the test host.
- `cawg_identity_id="test"` and `branded_gp_id="test"` are accepted only on the test host.

---

## 4. Branded Product Validation (BPV) and Product Validation (PV)

Skip this step for standard signing.

### Prerequisites

- **BPV:** submitting needs only an MFA-verified owner or admin, so you can submit BPV while OV is in review. Approval requires active OV and the `c2pa_signing_api_branded` plan.
- **PV:** submitting requires an active `c2pa_cert_lv1_backend`, `c2pa_cert_lv1_distributed`, or `c2pa_cert_lv1_edge` plan; approval and certificate enrollment require active OV. PV also requires C2PA Conformance. The PV path continues in [5. BYO C2PA Certificates](5-byo-c2pa-certificates.md).

### Prepare the draft

Each organization has one BPV draft and one PV draft. An owner or admin (MFA-verified session, see [2. Trufo Account Setup](2-trufo-account-setup.md#6-sign-in-from-the-cli-and-agents)) can save fields and upload documents before the final submission:

| Step | BPV | PV |
| --- | --- | --- |
| Read the draft | `GET /gproduct/bpv/draft` | `GET /gproduct/pv/draft` |
| Save fields (only the fields sent are changed) | `POST /gproduct/bpv/draft/save` | `POST /gproduct/pv/draft/save` |
| Upload a document (`multipart/form-data`, max 50 MB) | `POST /gproduct/bpv/upload` | `POST /gproduct/pv/upload` |
| Discard the draft | `POST /gproduct/bpv/draft/discard` | `POST /gproduct/pv/draft/discard` |

An upload returns an `s3_key`; add it to the matching list field (`trademark_evidence_files`, `sec_arch_diagram_files`, or `security_certification_files` for BPV; `supporting_files` for PV) and save the draft:

```python
import requests
from trufo.util.credentials import load_session

session = load_session()  # api.trufo.ai; make_request() refreshes the access token on 401

session.make_request("/gproduct/bpv/draft/save", {
    "product_name": "<PRODUCT_NAME>",
    "product_url": "https://<your-domain>/",
    "name_has_trademarks": True,
})

with open("trademark-registration.pdf", "rb") as f:
    resp = requests.post(
        "https://api.trufo.ai/gproduct/bpv/upload",
        headers={"Authorization": f"Bearer {session.access_token}"},
        files={"file": f},
        timeout=120,
    )
resp.raise_for_status()

session.make_request(
    "/gproduct/bpv/draft/save",
    {"trademark_evidence_files": [resp.json()["s3_key"]]},
)
```

Prepare before submitting a BPV application:

- **Product name:** the name that appears as `CN` on the product's certificate, and the product URL.
- **Source types:** the set of `digitalSourceType` values the product will declare. Declaring captured media or non-generative digital creation, or running part of the product on apps or devices you do not operate, also needs security architecture diagrams.
- **Trademarks:** if the product name includes trademarks, a clearance attestation and supporting evidence.
- **Security posture:** credential storage, scanning tools, access controls, and any ISO 27001 or SOC 2 certification with its documents.

The exact field schemas are in [Certificates API — PV and BPV](../reference/certificates-api.md#product-validation-pv-and-branded-product-validation-bpv-drafts-uploads-and-status).

### Submit and track approval

1. An owner or admin reviews and submits the application in [app.trufo.ai](https://app.trufo.ai).
2. Find the product and track its review:

```python
from trufo.util.credentials import load_session

session = load_session()
oid = session.make_request("/org/info", {})["oid"]

for gp in session.make_request("/gproduct/list", {"oid": oid})["gproducts"]:
    if gp["branded"]:
        status = session.make_request("/gproduct/bpv/status", {"gp_id": gp["gp_id"]})
        print(gp["gp_id"], gp["name"], status["status"], status["bpv_active"])
```

When `status` is `"approved"` and `bpv_active` is `true`, use that `gp_...` value as `branded_gp_id`. The ID is also shown in the dashboard under **C2PA Signing API → Manage**. `reviewer_notes` carries reviewer feedback.

---

## 5. Move to Production

1. Confirm OV is active and a C2PA Signing plan (`c2pa_signing_api` or `c2pa_signing_api_branded`) is subscribed ([2. Trufo Account Setup](2-trufo-account-setup.md)).
2. Create a `c2pa-sign-prod` key and store it as `TRUFO_C2PA_SIGN_PROD_API_KEY`.
3. Switch to the production helpers and host:

```python
from pathlib import Path

from trufo import sign_c2pa_cloud
from trufo.api.endpoints import TRUFO_API_URL_EUROPE
from trufo.util.credentials import TrufoAPIKey, load_api_key

api_key = load_api_key(TrufoAPIKey.C2PA_SIGN_PROD)
assert api_key, "Set TRUFO_C2PA_SIGN_PROD_API_KEY or run: trufo set-api-key c2pa-sign-prod <KEY>"

signed_bytes = sign_c2pa_cloud(
    api_key,
    Path("input.jpg").read_bytes(),
    manifest_title="signed.jpg",
    ingredient_title="input.jpg",
    branded_gp_id="gp_...",  # approved product; omit for standard signing
    assertions=[["cawg_identity", {"cawg_identity_id": "org_interim"}]],  # optional; requires the cawg_cert_organization plan
    trufo_api_url=TRUFO_API_URL_EUROPE,  # omit for https://api.trufo.ai
)
Path("signed.jpg").write_bytes(signed_bytes)
```

For Local mode, use `sign_c2pa_local()` (or a `c2pa-sign-prod` key with the Docker image). Test keys are refused on production hosts in Local mode (`410`).

4. Verify sample outputs with `c2patool` or `c2pa-rs` against the C2PA Trust List ([Verification](../topics/verification.md)).
5. Handle non-fatal `warnings` (emitted as `TrufoServerWarning` in Python) and avoid blind retries of `POST /c2pa/sign`, which is metered on completion and not deduplicated ([Error Handling](../topics/error-handling.md)).

Common production errors: `403 MissingOrganizationValidation` (OV not active), `403 BPVNotActive: <reason>` (the reason names what is not active), `404 GProductNotFound` (unknown `branded_gp_id`), `403 C2PACreatedUserAssertionsNotAuthorized` (created assertions without an authorized `branded_gp_id`).

---

## Reference

- Signing modes and tasks: [Cloud Signing](../topics/signing-cloud.md), [Local Signing (Python SDK)](../topics/signing-local-python.md), [Local Signing (Docker)](../topics/signing-local-docker.md)
- Manifest content: [C2PA Manifests, Actions, and Assertions](../topics/c2pa-manifests.md), [Ingredients and Redaction](../topics/ingredients-and-redaction.md), [CAWG Identity and Metadata](../topics/cawg-identity.md)
- Privacy and retention: [Storage Options and Privacy](../topics/storage-options.md)
- Failures and retries: [Error Handling, Warnings, and Retries](../topics/error-handling.md)
- Specifications: [Signing API](../reference/signing-api.md), [Actions and Assertions](../reference/actions-and-assertions.md), [Certificates, TSA, and OCSP API](../reference/certificates-api.md)
