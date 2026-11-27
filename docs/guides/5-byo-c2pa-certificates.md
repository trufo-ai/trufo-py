# 5. BYO C2PA Certificates

This guide covers the Bring Your Own (BYO) certificate route: obtaining and operating C2PA Claim Signing certificates from Trufo Certificate Authority (TCA) for a signer you run yourself (`c2pa-rs`, `c2patool`, or firmware on a camera or other edge device). If Trufo signs for you (Cloud or Local mode), Trufo manages certificates and you can skip this guide.

The path has three tracks:

| Track | Purpose | Requires |
| --- | --- | --- |
| Dummy certificate | A structurally valid certificate carrying your company and product name, for C2PA conformance applications | Nothing |
| Test Flow | Rehearse the full instance, credential, Enrollment over Secure Transport (EST), Online Certificate Status Protocol (OCSP), and revocation pipeline | Trufo account, MFA, owner/admin role |
| Production | Certificates that chain to the Trufo C2PA Root CA | Organization Validation (OV), Product Validation (PV), and a C2PA Certificate plan |

Nothing from the dummy or Test Flow tracks carries over to production.

---

## 1. Get a Dummy Certificate for Conformance Testing

No account is required. Dummy certificates use `c2pa-l1-test`, the Assurance Level 1 dummy leaf type, and are enrolled on `https://ca.trufo.ai` (not `test.ca.trufo.ai`, which serves Test Flow `c2pa-l1` only).

```python
from pathlib import Path

from trufo import generate_keypair, request_c2pa_dummy_cert
from trufo.crypt.algorithms import SigningAlgorithm

leaf_priv_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_dummy_cert(
    org_name="Example Corp",
    common_name="Example Camera",
    private_key_signer=leaf_priv_pem,
    country="US",  # required; the CA refuses an enrollment without it
)
Path("dummy_cert_chain.pem").write_bytes(cert_chain_pem)
```

- Dummy certificates chain to **TCA Test Root CA** (`https://test.ca.trufo.ai/root-ca.crt`), which public validators do not trust. Add it as a local trust anchor to verify them ([Verification](../topics/verification.md#2-verifying-test-host-assets-in-ci)).
- They are not listed, not revocable, and not covered by OCSP.
- `c2pa-l2-test` is disabled.
- For test timestamps, use `https://test.tsa.trufo.ai/` ([7. BYO Timestamps and OCSP](7-byo-timestamps-and-ocsp.md)).

Non-Python callers can mint the dummy CSR JWT themselves; see [CSR JWT Format](../reference/certificates-api.md#csr-jwt-format-hs256-300s-lifetime).

---

## 2. Rehearse Enrollment with the Test Flow

Test Flow runs on `test.api.trufo.ai`, `test.ca.trufo.ai`, `test.ocsp.trufo.ai`, and `test.tsa.trufo.ai`. It skips OV, PV, and plan checks, and issues `c2pa-l1` certificates only.

### Prerequisites

Create a Trufo account with MFA, an owner or admin role, and a `trufo-api` key, then run `trufo login` ([2. Trufo Account Setup](2-trufo-account-setup.md)).

Non-Python callers sign in and refresh tokens on `https://api.trufo.ai`, then send the access token to `https://test.api.trufo.ai` ([API hosts](2-trufo-account-setup.md#6-sign-in-from-the-cli-and-agents)).

### Steps

1. In [app.trufo.ai/tca/certs/c2pa](https://app.trufo.ai/tca/certs/c2pa), switch to **Test** view and click **Create Test Product**. The name must be at most 54 UTF-8 bytes; the certificate subject becomes `CN=[TESTING] <name>`. Copy the `gp_id`.
2. Create an instance (`POST /gproduct/instance/create`) and register an instance credential (`POST /gproduct/instance/credential/register`). Credentials must be EC P-256 (ES256) or Ed25519 (EdDSA); P-384 is for leaf keys only.
3. Request a CSR JWT from the Registration Authority (RA) (`POST /ra/c2pa/csr-jwt` on `test.api.trufo.ai`) and enroll `c2pa-l1` on `https://test.ca.trufo.ai`. `request_c2pa_cert_test()` performs both calls.

   ```python
   from trufo import create_instance, generate_keypair, register_credential, request_c2pa_cert_test
   from trufo.api.endpoints import TRUFO_API_URL_TEST
   from trufo.crypt.algorithms import SigningAlgorithm
   from trufo.util.credentials import load_session

   session = load_session()  # saved by `trufo login`
   session.base_api_url = TRUFO_API_URL_TEST  # sign-in and refresh stay on api.trufo.ai

   gpi_id = create_instance(session, gp_id="gp_...", name="Test signer")

   instance_priv_pem, instance_pub_pem = generate_keypair(SigningAlgorithm.ES256)
   gpic_id = register_credential(
       session,
       gpi_id=gpi_id,
       label="test-key-1",
       key_algorithm="ES256",
       public_key_pem=instance_pub_pem.decode(),
   )

   leaf_priv_pem, _ = generate_keypair(SigningAlgorithm.ES256)
   cert_chain_pem = request_c2pa_cert_test(
       gpi_id=gpi_id,
       gpic_id=gpic_id,
       instance_key_pem=instance_priv_pem,
       private_key_signer=leaf_priv_pem,
   )
   ```

4. Check OCSP status on `https://test.ocsp.trufo.ai/c2pa` ([Verify OCSP directly with OpenSSL](../topics/timestamping.md#verify-ocsp-directly-with-openssl)).
5. Revoke the certificate with `POST /cert/revoke` on `https://test.api.trufo.ai` (`api.trufo.ai` returns `404 NotFound` for Test Flow certificates), and confirm that OCSP reports it as revoked within about a minute.

---

## 3. Complete the Production Prerequisites

1. **Organization Validation (OV):** submit and get approval ([2. Trufo Account Setup](2-trufo-account-setup.md)).
2. **Plan:** subscribe to the Assurance Level 1 plan for where claim signing runs, `c2pa_cert_lv1_backend`, `c2pa_cert_lv1_distributed`, or `c2pa_cert_lv1_edge`, which becomes the PV `implementation` field ([2. Trufo Account Setup](2-trufo-account-setup.md#4-add-billing-and-plans), [Certificates](../topics/certificates.md#production-certificate-enrollment)); for Assurance Level 2 (`c2pa-l2`, hardware-backed keys), contact [support@trufo.ai](mailto:support@trufo.ai).
3. **Product Validation (PV):** upload supporting documents with `POST /gproduct/pv/upload`, save the draft with `POST /gproduct/pv/draft/save` (or fill it in the dashboard), then have an owner or admin submit the final application in [app.trufo.ai](https://app.trufo.ai). Submitting PV requires one of the plans above; PV approval requires active OV. Approval yields the production `gp_id`. Field definitions are in [PV draft fields](../reference/certificates-api.md#product-validation-pv-and-branded-product-validation-bpv-drafts-uploads-and-status); see also [3. Product Signing Setup](3-product-signing-setup.md#4-branded-product-validation-bpv-and-product-validation-pv).

Enrollment requires OV and PV to remain active (`403 OVNotActive`, `403 PVNotActive`). Track `validated_expires_at` from `POST /gproduct/list` and renew validations before your certificate renewal window.

---

## 4. Enroll, Store Keys, Rotate, and Revoke

### Create an instance and register a credential

Model one instance (`gpi_id`) per independent key holder, such as one per signing service and region, or one per HSM partition. Keep the instance key and leaf keys in a KMS or HSM.

Create the production instance and credential with the same `create_instance()` and `register_credential()` calls as the Test Flow, on the default production session, but use an `AWSKMSPrivateKey` or `GCPKMSPrivateKey` instance key (registering its `public_key_pem`) in place of `generate_keypair()`. See [Create an instance and register a KMS-backed credential](../topics/certificates.md#1-create-an-instance-and-register-a-kms-backed-credential).

### Enroll a leaf certificate

Generate a fresh EC P-256 (recommended) or P-384 leaf key for every enrollment; reusing a public key returns `409 PublicKeyAlreadyUsed`. The certificate subject Distinguished Name (DN) comes from your OV and PV records.

```python
from trufo import generate_keypair, request_c2pa_cert
from trufo.crypt.algorithms import SigningAlgorithm
from trufo.crypt.tca_certs import LeafType

# or a new AWSKMSPrivateKey / GCPKMSPrivateKey per enrollment
leaf_key, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_cert(
    gpi_id=gpi_id,
    gpic_id=gpic_id,
    instance_key_pem=instance_key,
    private_key_signer=leaf_key,
    leaf_type=LeafType.C2PA_L1,  # LeafType.C2PA_L2 once enabled
    validity_days=366,  # c2pa-l1 max 366; c2pa-l2 max 90
)
```

Production enrollment runs against `https://api.trufo.ai` (RA) and `https://ca.trufo.ai` (EST). For a full script, see [certificates.py](../topics/certificates.py).

Rust, Go, and C clients call the RA and EST endpoints directly; see [Wire notes for Rust, Go, and C clients](../reference/certificates-api.md#wire-notes-for-rust-go-and-c-clients) for JWS signature encoding and PKCS#7 ordering.

### Limits

- **3 active certificates per instance.** A 4th enrollment returns `403`.
- **2 active credentials per instance.** A 3rd registration returns `400`.
- Expired and revoked certificates, and revoked credentials, do not count toward either limit.

### Rotation

1. Enroll the replacement certificate before the current one expires (for example, at 60–75% of its lifetime), with a fresh leaf key.
2. Switch your signer to the new certificate and refresh its stapled OCSP response.
3. Revoke the old certificate with `POST /cert/revoke` (reason `superseded`) or let it expire. Revoking frees a slot immediately.

To rotate an instance credential, register the new credential, move your enrollment job to the new `gpic_id`, then revoke the old one with `POST /gproduct/instance/credential/revoke`. If you rotate certificates more often than every few months, enroll with a shorter `validity_days` so retired certificates age out on their own.

### Emergency revocation

- Revoke in the dashboard or with `POST /cert/revoke` (reason `key_compromise`, with an optional backdated `revocation_time`). Revocation is permanent.
- Revoking requires an MFA-verified owner or admin session; an API key cannot revoke.
- The OCSP responder reflects the revocation within about 60 seconds, but stapled responses fetched earlier stay valid until their own `nextUpdate` (7 days after `thisUpdate`).

Request and error details: [Certificates (`/cert/list`, `/cert/revoke`)](../reference/certificates-api.md#certificates-certlist-certrevoke). Refreshing stapled responses: [7. BYO Timestamps and OCSP](7-byo-timestamps-and-ocsp.md).

---

## Next Steps

- **Required for production manifests:** add RFC 3161 timestamps and OCSP stapling to your signer in [7. BYO Timestamps and OCSP](7-byo-timestamps-and-ocsp.md).
- Optional: sign `cawg.identity` assertions with your own organization certificate ([6. BYO CAWG Certificates](6-byo-cawg-certificates.md)), or add durable watermarks ([8. Watermarking with Pawprint](8-watermarking-with-pawprint.md)).

## Reference

- [Certificates](../topics/certificates.md) and [certificates.py](../topics/certificates.py)
- [Certificates, TSA, and OCSP API](../reference/certificates-api.md)
- [Verification](../topics/verification.md)
