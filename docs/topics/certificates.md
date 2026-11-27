# Certificates

Enroll C2PA Claim Signing certificates from Trufo Certificate Authority (TCA), rehearse enrollment in Test Flow, store keys in KMS/HSM, and rotate or revoke certificates.

> **Note:** You only need this if you operate **your own C2PA signer** (`c2pa-rs`, `c2patool`, etc.). If Trufo signs for you via `/c2pa/sign` or Local mode, Trufo handles certificates automatically. For the onboarding roadmap and key-custody best practices, see [Build Your Own Generator Product](../guides/5_build-your-own-generator-product.md). For RFC 3161 timestamping and OCSP stapling, see [Timestamping and OCSP](timestamping.md).

---

## Dummy Certificate (Conformance Applications)

Obtain a structurally valid test certificate carrying your company and app name — no Trufo account, validation, or plan required. Dummy certificates are enrolled on `https://ca.trufo.ai` under the dummy leaf types (not on `test.ca.trufo.ai`, which serves Test Flow `c2pa-l1` only), chain to **TCA Test Root CA** (not trusted by public validators; downloadable at `https://test.ca.trufo.ai/root-ca.crt` for local verification), and are not listed, revocable, or covered by OCSP.

```python
from trufo import generate_keypair, request_c2pa_dummy_cert
from trufo.crypt.algorithms import SigningAlgorithm

private_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_dummy_cert(
    org_name="Example Corp",
    common_name="Example Camera",
    private_key_signer=private_pem,
    country="US",
)
```

Dummy enrollment issues Assurance Level 1 certificates only (`c2pa-l1-test`); `c2pa-l2-test` is disabled. Use `https://test.tsa.trufo.ai/` for test timestamps alongside dummy certs.

---

## Test Flow (Rehearse Production Enrollment)

Exercise the full instance, credential, EST enrollment, OCSP, and revocation pipeline on the test hosts (`test.api.trufo.ai`, `test.ca.trufo.ai`, `test.ocsp.trufo.ai`, `test.tsa.trufo.ai`) before purchasing a plan or completing OV/PV. Requires only a Trufo account with MFA and an owner/admin role.

1. In [app.trufo.ai/tca/certs/c2pa](https://app.trufo.ai/tca/certs/c2pa), switch to **Test** view and click **Create Test Product** (name ≤ 54 UTF-8 bytes; becomes `CN=[TESTING] <name>`). Copy its `gp_id`.
2. Create an instance, register an instance credential, and enroll a `c2pa-l1` test certificate:

```python
from trufo import (
    create_instance,
    generate_keypair,
    register_credential,
    request_c2pa_cert_test,
)
from trufo.api.endpoints import TRUFO_API_URL_TEST
from trufo.api.session import TrufoSession
from trufo.crypt.algorithms import SigningAlgorithm
from trufo.util.credentials import TrufoAPIKey, load_api_key

session = TrufoSession(base_api_url=TRUFO_API_URL_TEST)
session.init_session(api_key=load_api_key(TrufoAPIKey.TRUFO_API))

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

- **`c2pa-l1` only:** Test Flow enrolls `c2pa-l1` certificates; `c2pa-l2` is not available on the test CA.
- **Sign-in for non-Python callers:** `test.api.trufo.ai` has no sign-in or token-refresh routes. Run device authorization (`/account/device/*`) and token refresh (`/account/refresh`) against `https://api.trufo.ai`, then send the resulting access token to `https://test.api.trufo.ai`. `TrufoSession(base_api_url=TRUFO_API_URL_TEST)` does this routing automatically.

Nothing from the Test Flow carries over to production.

---

## Production Certificate Enrollment

Prerequisites in [app.trufo.ai](https://app.trufo.ai): approved **Organization Validation (OV)**, approved **Product Validation (PV)** (yielding `gp_id`), and an active C2PA Certificate subscription.

The C2PA Certificate plan is purchased per generator product, for one of three implementation types (the PV `implementation` field). Each type issues `c2pa-l1` certificates, and PV asks you to attest to the matching signing architecture:

| Plan | `implementation` | Where C2PA claim signing happens |
| --- | --- | --- |
| `c2pa_cert_lv1_backend` | `backend` | Entirely on your backend servers. |
| `c2pa_cert_lv1_distributed` | `distributed` | Split between edge devices (for example, cameras) and a central signing backend; every input passed between the two must be cryptographically authenticated, and each edge subsystem uses its own credentials. |
| `c2pa_cert_lv1_edge` | `edge` | Directly on conformant cameras or other edge devices. |

*(Organizations that sign `cawg.identity` assertions with their own key, rather than letting Trufo sign them, enroll an organization-level CAWG interim certificate with `request_cawg_interim_cert(session, private_key_signer)` — requires approved OV and an active `cawg_cert_organization` subscription. See [CAWG Identity](cawg-identity.md).)*

### Assurance levels (`c2pa-l1` and `c2pa-l2`)

- **`LeafType.C2PA_L1` (`c2pa-l1`):** C2PA Assurance Level 1, max **366 days** validity.
- **`LeafType.C2PA_L2` (`c2pa-l2`):** C2PA Assurance Level 2 (hardware-backed keys / HSM / FIPS-validated boundary), max **90 days** validity. Contact [support@trufo.ai](mailto:support@trufo.ai) to enable `c2pa-l2` on your product.

### 1. Create an instance and register a KMS-backed credential

Model one instance (`gpi_id`) per independent key holder. Storing the instance key (and leaf key) in **AWS KMS** or **Google Cloud KMS** keeps private keys non-exportable:

```python
import boto3
from trufo import create_instance, register_credential
from trufo.crypt.kms import AWSKMSPrivateKey
from trufo.util.credentials import load_session

session = load_session()  # reads ~/.trufo/session (written by `trufo login` or save_session()) or session env vars; sign in with MFA
gpi_id = create_instance(session, gp_id="gp_...", name="Production signer, us-east")

# AWS KMS P-256 key (key spec ECC_NIST_P256, usage SIGN_VERIFY; requires boto3)
instance_key = AWSKMSPrivateKey(boto3.client("kms"), "alias/<your-instance-key>")

# Or Google Cloud KMS P-256 key (algorithm EC_SIGN_P256_SHA256; requires google-cloud-kms):
# from google.cloud import kms
# from trufo.crypt.kms import GCPKMSPrivateKey
# instance_key = GCPKMSPrivateKey(
#     kms.KeyManagementServiceClient(),
#     "projects/<project>/locations/<location>/keyRings/<ring>/cryptoKeys/<key>/cryptoKeyVersions/1",
# )

gpic_id = register_credential(
    session,
    gpi_id=gpi_id,
    label="prod-key-1",
    key_algorithm="ES256",
    public_key_pem=instance_key.public_key_pem,
)
```

*(You can also pass PEM bytes from `generate_keypair(SigningAlgorithm.ES256)` for local/HSM workflows.)*

> **Instance credential key types:** `register_credential()` accepts only **EC P-256 (`key_algorithm="ES256"`)** or **Ed25519 (`key_algorithm="EdDSA"`)** public keys; `key_algorithm` must match the key (`400 AlgorithmMismatch`). A P-384 KMS key works as a **leaf** key but cannot be registered as an instance credential.

### 2. Enroll a leaf certificate (repeat each renewal cycle)

Always generate a **fresh EC P-256** (recommended; P-384 also accepted) leaf key per enrollment — reusing a public key fails with `409 PublicKeyAlreadyUsed`. The subject DN (`O`, `C`, `CN`, `OU`) comes from your OV and PV records.

```python
from trufo import request_c2pa_cert
from trufo.crypt.tca_certs import LeafType

# leaf_key can be an AWSKMSPrivateKey, GCPKMSPrivateKey, or PEM bytes
cert_chain_pem = request_c2pa_cert(
    gpi_id=gpi_id,
    gpic_id=gpic_id,
    instance_key_pem=instance_key,
    private_key_signer=leaf_key,
    leaf_type=LeafType.C2PA_L1,  # max 366 days (LeafType.C2PA_L2: max 90 days)
    validity_days=366,
)
```

For non-Python callers implementing RA `POST /ra/c2pa/csr-jwt` + EST `POST /.well-known/est/{leaf_type}/simpleenroll` directly in Rust, Go, or C, see [Certificates, TSA, and OCSP API](../reference/certificates-api.md).

---

## Rotation and Revocation

- **Zero-downtime rotation:** Each instance supports up to **2 active credentials** and **3 active (unexpired, unrevoked) certificates**. Register the replacement credential or enroll the replacement leaf cert first, cut over signing traffic, then revoke or let the old one expire.
- **Hitting the caps on frequent rotation:** A 4th enrollment while 3 certificates are still active fails with `403` (the error tells you to revoke one or wait for one to expire); a 3rd credential returns `400`. Expired and revoked certificates (and revoked credentials) do not count, so revoking the retired certificate via `POST /cert/revoke` (reason `superseded`) — or the retired credential via `POST /gproduct/instance/credential/revoke` — frees a slot immediately. If you rotate more often than every few months, enroll with a shorter `validity_days` so retired certificates age out on their own.
- **Listing & revocation:** List issued certificates via `POST /cert/list`, and revoke compromised or retired certificates in the dashboard or via `POST /cert/revoke` (MFA-verified owner/admin session required; supports optional backdated `revocation_time` in UTC). Revocation is permanent and publishes through OCSP (see [Timestamping and OCSP](timestamping.md)).

---

## Reference

- Full EST and RA wire reference: [Certificates, TSA, and OCSP API](../reference/certificates-api.md)
- RFC 3161 timestamping and OCSP stapling: [Timestamping and OCSP](timestamping.md)
- Complete runnable script: [certificates.py](certificates.py)
