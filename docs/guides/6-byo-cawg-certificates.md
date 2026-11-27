# 6. BYO CAWG Certificates

This guide covers the Bring Your Own (BYO) route for Creator Assertions Working Group (CAWG) identity: enrolling a CAWG Organization Identity certificate (`cawg-interim`) from Trufo Certificate Authority (TCA) for a C2PA signer you run yourself, so that signer can produce `cawg.identity` assertions under your organization's verified identity.

If Trufo signs for you (Cloud or Local mode), you do not enroll a certificate: pass `["cawg_identity", {"cawg_identity_id": "org_interim"}]` to use your organization's Trufo-managed interim certificate (CAWG Organization Certificate plan), or `"test"` on `test.api.trufo.ai`; see [CAWG Identity and Metadata](../topics/cawg-identity.md). Certificates you enroll yourself cannot be selected through `cawg_identity_id`.

`cawg-interim` is an organization-scoped leaf type (maximum validity 366 days, EC P-256 or P-384 keys) that chains through `https://ca.trufo.ai/temp-cawg-ca.crt` to `https://ca.trufo.ai/root-ca.crt`, with OCSP at `https://ocsp.trufo.ai/cawg`, and needs no Product Validation (PV) or instance. Your outer C2PA claim still needs a C2PA Claim Signing certificate from [5. BYO C2PA Certificates](5-byo-c2pa-certificates.md) or another C2PA CA; see [Certificate Types and Accepted Keys](../reference/certificates-api.md#certificate-types-and-accepted-keys).

---

## 1. Test with a Dummy Certificate

No account is required. Dummy certificates use the `cawg-interim-test` leaf type, are enrolled on `https://ca.trufo.ai`, and chain to **TCA Test Root CA** (`https://test.ca.trufo.ai/root-ca.crt`) through the TCA Test CAWG Interim Issuing CA. They are not listed, not revocable, and not covered by OCSP.

```python
from pathlib import Path

from trufo import generate_keypair, request_cawg_dummy_cert
from trufo.crypt.algorithms import SigningAlgorithm

cawg_priv_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cawg_chain_pem = request_cawg_dummy_cert(
    org_name="Example Corp",
    common_name="Example Corp",
    private_key_signer=cawg_priv_pem,
    country="US",  # required; the CA refuses an enrollment without it
)
Path("dummy_cawg_chain.pem").write_bytes(cawg_chain_pem)
```

To verify assets signed with a dummy certificate, add TCA Test Root CA as a CAWG trust anchor in your validator ([Verification](../topics/verification.md#2-verifying-test-host-assets-in-ci)).

---

## 2. Complete the Production Prerequisites

1. Trufo account with MFA, an owner or admin role, and a `trufo-api` key; run `trufo login` ([2. Trufo Account Setup](2-trufo-account-setup.md)).
2. Active Organization Validation (OV).
3. Active **CAWG Organization Certificate** plan (`cawg_cert_organization`).

Missing prerequisites return `403 NoEligiblePlan`, `403 OVNotActive`, or `403 OrgNotValidated` when you request enrollment.

---

## 3. Enroll and Wire the Certificate into Your Signer

### Enroll

`request_cawg_interim_cert()` requests a short-lived enrollment token (CSR JWT) with `POST /ra/cawg-interim/csr-jwt` (MFA-verified owner/admin access token) and uses it to enroll through Enrollment over Secure Transport (EST) at `POST https://ca.trufo.ai/.well-known/est/cawg-interim/simpleenroll`.

```python
from pathlib import Path

from trufo import generate_keypair, request_cawg_interim_cert
from trufo.crypt.algorithms import SigningAlgorithm
from trufo.util.credentials import load_session

session = load_session()  # saved by `trufo login`

# or an AWSKMSPrivateKey / GCPKMSPrivateKey from trufo.crypt.kms
cawg_key, _ = generate_keypair(SigningAlgorithm.ES256)

cawg_chain_pem = request_cawg_interim_cert(session, cawg_key, validity_days=366)
Path("cawg_chain.pem").write_bytes(cawg_chain_pem)
```

The returned PEM chain holds the leaf and the issuing CA; the root is omitted.

Non-Python clients call [`POST /ra/cawg-interim/csr-jwt`](../reference/certificates-api.md#post-racawg-interimcsr-jwt) and the EST endpoint directly, following [Wire notes for Rust, Go, and C clients](../reference/certificates-api.md#wire-notes-for-rust-go-and-c-clients).

### Store the key

Keep the leaf key in a KMS or HSM. `request_cawg_interim_cert()` accepts `AWSKMSPrivateKey` and `GCPKMSPrivateKey` from `trufo.crypt.kms`. Generate a fresh key for each enrollment; reusing a public key returns `409 PublicKeyAlreadyUsed`.

### Configure your signer

Configure your C2PA library's CAWG X.509 identity signer with the `cawg-interim` key and certificate chain. The `cawg.identity` assertion it produces covers the assertions it references (such as `cawg.metadata` and `cawg.training-mining`). The claim itself is still signed with your C2PA Claim Signing certificate.

### List and revoke

- [`POST /cert/list`](../reference/certificates-api.md#certificates-certlist-certrevoke) returns every certificate issued to your organization; organization-level CAWG certificates have `gpi_id` and `gp_id` set to `null`.
- [`POST /cert/revoke`](../reference/certificates-api.md#certificates-certlist-certrevoke) revokes a certificate you enrolled (MFA-verified owner/admin session). Trufo-managed CAWG certificates (`org_interim`) show `revocable: false` and return `400 NotRevocable`.

Plan renewal before the certificate expires, and refresh the stapled OCSP response after rotating or revoking.

---

## Next Steps

- Add RFC 3161 timestamps and staple OCSP responses from `https://ocsp.trufo.ai/cawg` in [7. BYO Timestamps and OCSP](7-byo-timestamps-and-ocsp.md).
- Verify signed assets, including CAWG trust anchors, with [Verification](../topics/verification.md).

## Reference

- [Certificates](../topics/certificates.md)
- [CAWG Identity and Metadata](../topics/cawg-identity.md)
- [Certificates, TSA, and OCSP API](../reference/certificates-api.md)
- [Timestamping and OCSP](../topics/timestamping.md)
