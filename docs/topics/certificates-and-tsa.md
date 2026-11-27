# Certificates, TSA, and OCSP

Enroll C2PA Claim Signing certificates from Trufo Certificate Authority (TCA), attach RFC 3161 timestamps (`tsa.trufo.ai`), staple OCSP responses (`ocsp.trufo.ai`), and rotate or revoke certificates.

> **Note:** You only need this if you operate **your own C2PA signer** (`c2pa-rs`, `c2patool`, etc.). If Trufo signs for you via `/c2pa/sign` or Local mode, Trufo handles certificates, timestamps, and OCSP automatically. For the onboarding roadmap and key-custody best practices, see [Build Your Own Generator Product](../guides/5_build-your-own-generator-product.md).

---

## Dummy Certificate (Conformance Applications)

Obtain a structurally valid test certificate carrying your company and app name — no Trufo account, validation, or plan required. Dummy certificates chain to Trufo's test CA (not trusted by public validators) and are not revocable.

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

Use `https://test.tsa.trufo.ai/` for test timestamps alongside dummy certs.

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

Nothing from the Test Flow carries over to production.

---

## Production Certificate Enrollment

Prerequisites in [app.trufo.ai](https://app.trufo.ai): approved **Organization Validation (OV)**, approved **Product Validation (PV)** (yielding `gp_id`), and an active C2PA Certificate subscription.

### 1. Create an instance and register a KMS-backed credential

Model one instance (`gpi_id`) per independent key holder. Storing the instance key (and leaf key) in **AWS KMS** or **Google Cloud KMS** keeps private keys non-exportable:

```python
import boto3
from trufo import create_instance, register_credential
from trufo.crypt.kms import AWSKMSPrivateKey
from trufo.util.credentials import load_session

session = load_session()  # MFA-verified session from TrufoSession.init_session()
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

## Timestamping (`tsa.trufo.ai`)

Attach an RFC 3161 timestamp to every signature so signed assets remain verifiable after the leaf certificate expires. Authenticate with `X-API-Key: <your-tsa-key>` (include the full `tsa:` prefix).

### With `c2pa-rs` (TSA + OCSP stapling wrapper)

`create_signer::from_keys` accepts a TSA URL but no custom headers. Wrap `Signer` (or `AsyncSigner`) to supply `timestamp_request_headers()` and cached `ocsp_val()`:

```rust
use c2pa::{create_signer, Builder, Context, Signer, SigningAlg};

struct TrufoSigner {
    inner: Box<dyn Signer + Send + Sync>,
    tsa_api_key: String,
    cached_ocsp_der: Vec<u8>,
}

impl Signer for TrufoSigner {
    fn sign(&self, data: &[u8]) -> c2pa::Result<Vec<u8>> { self.inner.sign(data) }
    fn alg(&self) -> SigningAlg { self.inner.alg() }
    fn certs(&self) -> c2pa::Result<Vec<Vec<u8>>> { self.inner.certs() }
    fn reserve_size(&self) -> usize { self.inner.reserve_size() }
    fn time_authority_url(&self) -> Option<String> {
        Some("https://tsa.trufo.ai/".to_owned())
    }
    fn timestamp_request_headers(&self) -> Option<Vec<(String, String)>> {
        Some(vec![("X-API-Key".to_owned(), self.tsa_api_key.clone())])
    }
    fn ocsp_val(&self) -> Option<Vec<u8>> {
        // DER OCSP response fetched from https://ocsp.trufo.ai and refreshed before nextUpdate
        Some(self.cached_ocsp_der.clone())
    }
}
```

To test sending the header before purchasing a `tsa` key, call `https://test.tsa.trufo.ai/api-key` with `X-API-Key: test-api-key-header`.

### With `c2patool` or clients without custom headers

Proxy through a private internal reverse proxy that adds `X-API-Key` (never expose this proxy publicly):

```nginx
location /tsa {
    proxy_pass https://tsa.trufo.ai/;
    proxy_set_header X-API-Key "<YOUR_TSA_API_KEY>";
}
```

### Verify TSA directly with OpenSSL

```bash
echo "Hello, C2PA" > test_data.txt
openssl ts -query -data test_data.txt -sha256 -cert -out request.tsq
curl -fsS -H "Content-Type: application/timestamp-query" \
     -H "X-API-Key: <YOUR_TSA_API_KEY>" \
     --data-binary @request.tsq https://tsa.trufo.ai/ -o response.tsr

curl -fsS https://ca.trufo.ai/.well-known/est/ctsa/cacerts | base64 -d \
  | openssl pkcs7 -inform DER -print_certs -out ctsa_chain.pem
openssl ts -verify -data test_data.txt -in response.tsr -CAfile ctsa_chain.pem
# Expected: Verification: OK
```

---

## OCSP Stapling, Rotation, and Revocation

- **OCSP stapling:** Fetch one DER OCSP response per active signing certificate from `https://ocsp.trufo.ai` (`https://test.ocsp.trufo.ai` in Test Flow) against its direct issuing CA (`/c2pa-ca.crt`), cache it, and refresh it on a schedule well before its 7-day `nextUpdate` — never fetch OCSP per sign.
- **Zero-downtime rotation:** Each instance supports up to **2 active credentials** and **3 active certificates**. Register the replacement credential or enroll the replacement leaf cert first, cut over signing traffic, then revoke or let the old one expire.
- **Revocation:** Revoke compromised or retired certificates in the dashboard or via `POST /cert/revoke` (MFA-verified owner/admin session required; supports optional backdated `revocation_time` in UTC). Revocation is permanent and publishes through OCSP.

---

## Reference

- Full EST, OCSP, TSA, and RA wire reference: [Certificates, TSA, and OCSP API](../reference/certificates-api.md)
- Complete runnable script: [certificates.py](certificates.py)
