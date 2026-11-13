# Quickstart: C2PA Signing Certificates

A C2PA Signing Certificate identifies the signing entity (software or hardware) embedded in a manifest. Three tracks are available:

| Track | Purpose | Requires |
| ----- | ------- | -------- |
| **[Dummy](#dummy-certificate)** | A well-formed certificate for a conformance application | Nothing |
| **[Test flow](#test-flow)** | The whole production flow on test hosts | A Trufo account with MFA and an owner or admin role in an organization |
| **[Production](#production-certificate)** | Real-world publishing | Organization Validation, Product Validation and a subscription |


> **Note:** You do not need a C2PA Signing Certificate to use the Trufo C2PA signing endpoints (`POST /c2pa/sign`) — that endpoint uses Trufo's own C2PA signer. A C2PA Signing Certificate is only required if you are operating your own conformant C2PA Generator Product. See the [C2PA Signing Certificate product page](https://app.trufo.ai/tca/certs/c2pa) for more details.

See [1_certs.py](1_certs.py) for a runnable example of the dummy and production certificates.

---

## Dummy Certificate

For users who cannot yet get a trusted certificate but need a well-formed one to submit their conformance applications. No account authentication required. Uses a publicly known dummy HMAC secret; issued certificates are signed by Trufo's test CA and will not pass public validators. Dummy certificates are not listed or revocable. Use `https://test.tsa.trufo.ai/` for timestamps.

```python
from trufo import generate_keypair, request_c2pa_dummy_cert
from trufo.crypt.algorithms import SigningAlgorithm

private_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_dummy_cert(
    org_name="My Company",
    common_name="My App",
    private_key_signer=private_pem,
    country="US",
)
```

---

## Test Flow

Run the whole production flow before you buy: instances, credentials, enrollment,
OCSP status and revocation. A conformance application's security document
describes this enrollment workflow, so run it before you apply; the certificate you
submit can still be a dummy certificate, which carries your organization's name. You
need a Trufo account with MFA and an owner or admin role in an organization; there
is no Organization Validation, Product Validation or subscription. Test certificates
are signed by Trufo's test CA and are not trusted by C2PA validators.

Requests use the same paths and bodies as production. Only the host changes, to
`test.api.trufo.ai`, `test.ca.trufo.ai`, `test.ocsp.trufo.ai` and `test.tsa.trufo.ai`
(`TRUFO_API_URL_TEST`, `TRUFO_CA_URL_TEST`, `TRUFO_OCSP_URL_TEST` and
`TRUFO_TSA_URL_TEST` in `trufo.api.endpoints`). See the
[certificate API reference](../api/api_certs.md#test-flow) for details.

### Create a test product

On [app.trufo.ai/tca/certs/c2pa](https://app.trufo.ai/tca/certs/c2pa), switch to the
**Test** view and choose **Create Test Product**. The name you enter becomes the
certificate's common name as `[TESTING] <name>`, so it can be at most 54 UTF-8 bytes.
The dashboard shows the new product's `gp_id`.

### Create an instance and a credential

Use the dashboard's Test view, or the SDK as in production
[steps 3 and 4](#step-3--create-an-instance). Build the session with
`TrufoSession(base_api_url=TRUFO_API_URL_TEST)`, not `load_session()`: it signs in at
`api.trufo.ai` with your `trufo-api` key and sends requests to `test.api.trufo.ai`.
To reuse an earlier sign-in, pass its tokens instead:
`TrufoSession(access_token=..., refresh_token=..., base_api_url=TRUFO_API_URL_TEST)`.

```python
from trufo import create_instance, generate_keypair, register_credential
from trufo.api.endpoints import TRUFO_API_URL_TEST
from trufo.api.session import TrufoSession
from trufo.crypt.algorithms import SigningAlgorithm
from trufo.util.credentials import TrufoAPIKey, load_api_key

session = TrufoSession(base_api_url=TRUFO_API_URL_TEST)
session.init_session(api_key=load_api_key(TrufoAPIKey.TRUFO_API))

gpi_id = create_instance(session, gp_id="gp_...", name="Test signer")

instance_private_pem, instance_public_pem = generate_keypair(SigningAlgorithm.ES256)
gpic_id = register_credential(
    session,
    gpi_id=gpi_id,
    label="test-key-1",
    key_algorithm="ES256",
    public_key_pem=instance_public_pem.decode(),
)
```

### Enroll a test certificate

```python
from trufo import generate_keypair, request_c2pa_cert_test
from trufo.crypt.algorithms import SigningAlgorithm

leaf_private_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_cert_test(
    gpi_id=gpi_id,
    gpic_id=gpic_id,
    instance_key_pem=instance_private_pem,
    private_key_signer=leaf_private_pem,
)
```

`request_c2pa_cert_test()` is `request_c2pa_cert()` on the test hosts. It issues C2PA
Level 1 certificates only. As in production, use a fresh leaf key each time; an
instance holds at most three active certificates.

### Sign, check status and revoke

Sign as in [production step 6](#step-6--sign), using the test hosts for
[timestamps](#timestamping), [OCSP](#ocsp-stapling) and
[revocation](#revocation-and-rotation).

### Move to production

Nothing from the test flow carries over. Start at
[step 1](#step-1--validate-your-organization) with a new product, instance,
credential and key.

---

## Production Certificate

Production enrollment is a chain of one-time setup steps followed by a renewable
enrollment. Work through them in order — each step's output feeds the next.

```
Step 1  Organization Validation        (dashboard, once per organization)
Step 2  Generator Product + PV         (dashboard, once per product)
Step 3  Instance                       (once per signing identity)
Step 4  Instance credential            (once per instance; rotate as needed)
Step 5  Certificate enrollment         (per renewal cycle)
```

### Step 1 — Validate your organization

Complete Organization Validation at [app.trufo.ai](https://app.trufo.ai). OV
establishes your legal identity: the validated legal name and registration country
become the `O` and `C` fields of every certificate you are issued. Approval is a
review process, so start it early.

### Step 2 — Create the product and pass Product Validation

Also in the dashboard. A *generator product* is the thing that produces C2PA
manifests — your application, camera pipeline, or service. Submitting its Product
Validation application creates the product and starts review; approval yields a
product record id that is embedded in every certificate the product signs, and
supplies the certificate's common name.

You will need an active subscription for the product tier you are enrolling under.
When PV is approved the dashboard shows the product's `gp_id` — carry it to step 3.

### Step 3 — Create an instance

An instance is one signing identity: it holds its own credentials and gets its own
certificates. Create one per independent key holder — one per signing service, one
per regional server with its own HSM key, one per device in a fleet.

```python
from trufo import create_instance
from trufo.util.credentials import load_session

session = load_session()          # run `trufo login` first
gpi_id = create_instance(session, gp_id="gp_...", name="Production signer, us-east")
```

### Step 4 — Register an instance credential

The instance key authorizes certificate requests; it never signs manifests and never
leaves your environment. Generate it where it will live — ideally in an HSM or a
secure enclave — and register only the public half.

```python
from trufo import generate_keypair, register_credential
from trufo.crypt.algorithms import SigningAlgorithm

instance_private_pem, instance_public_pem = generate_keypair(SigningAlgorithm.ES256)

gpic_id = register_credential(
    session,
    gpi_id=gpi_id,
    label="prod-key-1",
    key_algorithm="ES256",
    public_key_pem=instance_public_pem.decode(),
)
```

Persist `gpi_id`, `gpic_id`, and the instance private key securely — together they
are what lets this deployment request certificates. An instance may hold two active
credentials at once, which is what makes rotation non-disruptive (see
[Revocation and Rotation](#revocation-and-rotation)).

#### Keep the instance key in a KMS

Keep the instance key in AWS KMS or Google Cloud KMS so it never leaves the KMS. The
instance key must be P-256. Any other P-256 `ec.EllipticCurvePrivateKey` that signs in
your KMS also works.

**AWS KMS:** create a key with key spec `ECC_NIST_P256` and key usage `SIGN_VERIFY`, and
`pip install boto3`:

```python
import boto3

from trufo.crypt.kms import AWSKMSPrivateKey

instance_private_key = AWSKMSPrivateKey(boto3.client("kms"), "alias/<your-key>")
```

**Google Cloud KMS:** create a key with purpose `ASYMMETRIC_SIGN` and algorithm
`EC_SIGN_P256_SHA256`, and `pip install google-cloud-kms`:

```python
from google.cloud import kms

from trufo.crypt.kms import GCPKMSPrivateKey

instance_private_key = GCPKMSPrivateKey(
    kms.KeyManagementServiceClient(),
    "projects/<project>/locations/<location>/keyRings/<ring>/cryptoKeys/<key>/cryptoKeyVersions/1",
)
```

Then register its public key:

```python
from trufo import register_credential

gpic_id = register_credential(
    session,
    gpi_id=gpi_id,
    label="prod-key-1",
    key_algorithm="ES256",
    public_key_pem=instance_private_key.public_key_pem,
)
```

In [step 5](#step-5--enroll-a-certificate), pass `instance_key_pem=instance_private_key`
to `request_c2pa_cert()`. The leaf key (`private_key_signer`) can be a KMS key in the
same way.

### Step 5 — Enroll a certificate

Repeat each renewal cycle. Generate a **fresh leaf key every time** — a public key
that already holds a certificate is rejected — and generate it in the environment
that will sign, so the private key never moves.

```python
from trufo import generate_keypair, request_c2pa_cert
from trufo.crypt.algorithms import SigningAlgorithm
from trufo.crypt.tca_certs import LeafType

leaf_private_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_cert(
    gpi_id=gpi_id,
    gpic_id=gpic_id,
    instance_key_pem=instance_private_pem,
    private_key_signer=leaf_private_pem,
    leaf_type=LeafType.C2PA_L1,
    validity_days=366,
)
```

`request_c2pa_cert()` performs both halves of enrollment: it signs a client
assertion with the instance key to obtain a short-lived authorization from Trufo's
Registration Authority, then submits your CSR to the CA over EST and returns the
issued chain (leaf first, then the CA chain).

The certificate subject comes from your validations, not from your request — you
cannot choose the organization or product name at enrollment time.

| Leaf type | Assurance level | Maximum validity |
| --------- | --------------- | ---------------- |
| `LeafType.C2PA_L1` | 1 | 366 days |
| `LeafType.C2PA_L2` | 2 (hardware-backed keys) | 90 days |

**ES256 (EC P-256) is recommended** — it is the most widely supported curve across
C2PA validators. P-384 is also accepted.

### Step 6 — Sign

You now have a certificate chain and a leaf private key. Use them with your own
C2PA implementation — `c2pa-rs`, `c2patool`, or another conformant library — and
wire in [timestamping](#timestamping) and [OCSP stapling](#ocsp-stapling) below.

Signing with your own certificate happens outside trufo-py: the SDK's signing
helpers use Trufo's signer, not yours.

### Common enrollment errors

| Error | Meaning |
| ----- | ------- |
| `403 OVNotActive` | Organization Validation is missing or expired (step 1) |
| `403 PVNotActive` / `400 ProductNotValidated` | Product Validation is missing or expired (step 2) |
| `403 BillingNotActive` | No active subscription for the product |
| `401 ClientAssertionFailed` | The client assertion was rejected — wrong instance key, revoked credential, or a clock more than a few minutes out |
| `409 PublicKeyAlreadyUsed` | The leaf key already holds a certificate; generate a new one |
| `400 KeyTypeNotAllowed` | The CSR key is not EC P-256 or P-384 |

---

## Timestamping

A timestamp authority (TSA) issues signed evidence that data existed by a given
time. Your C2PA signing library embeds this timestamp so signatures can remain
verifiable after the signing certificate expires.

Use `https://tsa.trufo.ai/` (or your assigned dedicated TSA URL). Authenticate with
an HTTP `X-API-Key` header containing a `tsa`-scoped key from
[dashboard → API Keys](https://app.trufo.ai/settings/org). Copy the complete key,
including any `tsa:` prefix; do not add another. See [credential setup](0_setup.md#api-key-scopes).

For dummy and test certificates, use `https://test.tsa.trufo.ai/` instead; it needs
no key ([test endpoint](../api/api_certs.md#test-endpoint)).

**Using Trufo's signing helpers?** Timestamping is automatic with your stored
credentials. The instructions below are for your own signing toolchain.

### With c2pa-rs

`create_signer::from_keys` accepts a TSA URL but no headers. This wrapper adds
`timestamp_request_headers()`. Set `TRUFO_TSA_API_KEY` in your process environment
or secret manager; keep it outside source control. To try the wrapper before you have
a key, use `https://test.tsa.trufo.ai/api-key` with the key `test-api-key-header`
([test endpoint](../api/api_certs.md#test-endpoint)).

Supply an ES256 certificate chain (`signing-chain.pem`), matching private key
(`private-key.pem`), C2PA manifest definition (`manifest.json`), and `input.jpg`.
The example writes `signed.jpg`.

```rust
use c2pa::{create_signer, Builder, Context, Signer, SigningAlg};

struct TsaSigner {
    inner: Box<dyn Signer + Send + Sync>,
    api_key: String,
}

impl Signer for TsaSigner {
    fn sign(&self, data: &[u8]) -> c2pa::Result<Vec<u8>> {
        self.inner.sign(data)
    }
    fn alg(&self) -> SigningAlg {
        self.inner.alg()
    }
    fn certs(&self) -> c2pa::Result<Vec<Vec<u8>>> {
        self.inner.certs()
    }
    fn reserve_size(&self) -> usize {
        self.inner.reserve_size()
    }
    fn time_authority_url(&self) -> Option<String> {
        Some("https://tsa.trufo.ai/".to_owned())
    }
    fn timestamp_request_headers(&self) -> Option<Vec<(String, String)>> {
        Some(vec![("X-API-Key".to_owned(), self.api_key.clone())])
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let api_key = std::env::var("TRUFO_TSA_API_KEY")?;
    if api_key.trim().is_empty() {
        return Err("TRUFO_TSA_API_KEY must not be empty".into());
    }
    let signer = TsaSigner {
        inner: create_signer::from_keys(
            &std::fs::read("signing-chain.pem")?,
            &std::fs::read("private-key.pem")?,
            SigningAlg::Es256,
            None, // The wrapper supplies the TSA URL.
        )?,
        api_key,
    };
    let mut builder = Builder::from_context(Context::new())
        .with_definition(std::fs::read_to_string("manifest.json")?)?;
    let mut input = std::fs::File::open("input.jpg")?;
    let mut output = std::fs::File::create("signed.jpg")?;
    builder.sign(&signer, "image/jpeg", &mut input, &mut output)?;
    Ok(())
}
```

Already have a custom `Signer`? Add only the two timestamp methods, preserving
its OCSP stapling and other extensions. `AsyncSigner` has the same header hook.
c2pa-rs supplies `Content-Type` automatically. See the
[Signer reference](https://docs.rs/c2pa/latest/c2pa/trait.Signer.html#method.timestamp_request_headers);
upgrade or use the proxy below if your SDK lacks the hook.

### With c2patool or clients without custom headers

For clients that cannot set `X-API-Key`, set the TSA URL (`ta_url` in c2patool) to:

- **Development:** `https://test.tsa.trufo.ai/` — no key required; timestamps are
  deliberately untrusted and unsuitable for production.
- **Production:** a private proxy that adds the header. Add this location to your
  existing Nginx server configuration:

  ```nginx
  location /tsa {
      proxy_pass https://tsa.trufo.ai/;
      proxy_set_header X-API-Key "<YOUR_TSA_API_KEY>";
  }
  ```

  Replace `<YOUR_TSA_API_KEY>` with your complete key and set `ta_url` to the proxy
  URL ending in `/tsa`. Keep the proxy inside your network — it holds a credential.

### Test the production TSA with OpenSSL

This checks timestamp requests and verification directly, not C2PA asset signing:

```bash
echo "Hello, C2PA world" > test_data.txt
openssl ts -query -data test_data.txt -sha256 -cert -out request.tsq
curl -s -H "Content-Type: application/timestamp-query" \
     -H "X-API-Key: <YOUR_TSA_API_KEY>" \
     --data-binary @request.tsq https://tsa.trufo.ai/ -o response.tsr
openssl ts -reply -in response.tsr -text
```

To verify the response against the TSA CA chain:

```bash
curl -fsS https://ca.trufo.ai/.well-known/est/ctsa/cacerts -o ca_chain.p7b
base64 -d ca_chain.p7b > ca_chain.der
openssl pkcs7 -in ca_chain.der -inform DER -print_certs -out ca_chain.pem
openssl ts -verify -data test_data.txt -in response.tsr -CAfile ca_chain.pem
```

Expected output: `Verification: OK`.

## Revocation and Rotation

Certificates are issued for at most a year (90 days at assurance level 2), so plan
renewal rather than treating enrollment as one-time. Because an instance may hold
two active credentials at once, rotation is non-disruptive: register the new
credential, move signing to it, then revoke the old one.

Revoke a certificate when a key is compromised or a deployment is retired — from
the dashboard, or `POST /cert/revoke` with the serial number and a reason. Choose
**Now** or specify an effective date, time, and named timezone in the dashboard.
API callers can provide `revocation_time`; omitting it uses the processing time.
See the [certificate API reference](../api/api_certs.md#certificates) for the
request format and authentication requirements. Revoke a test certificate in the
dashboard's Test view or with `POST https://test.api.trufo.ai/cert/revoke`.

Revocation is permanent and publishes through OCSP (`https://test.ocsp.trufo.ai/`
for test certificates). A trusted timestamp lets validators assess whether content
was signed before the effective revocation cutoff, subject to the applicable
validation rules.

### OCSP stapling

C2PA expects the signer to **staple** a revocation response into the signature
rather than leaving validators to fetch one. The response is embedded in the COSE
signature's unprotected header, under `rVals.ocspVals` — so it travels with the
asset and remains checkable offline, and long after the OCSP responder has moved on.
This matters because a validator that cannot reach the responder may otherwise
report the signature as unverifiable.

Trufo certificates carry `https://ocsp.trufo.ai` in their AIA extension, and test
certificates `https://test.ocsp.trufo.ai`, so tooling finds the responder
automatically. trufo-provenance 2.2.1 or later accepts both for stapling.

**With trufo-py**, stapling happens on every sign: the SDK fetches a response for
the signing chain and hands it to the engine, which places it in the COSE header.
Nothing to configure.

**With c2pa-rs directly**, the `Signer` trait exposes `ocsp_val()`, which returns the
DER OCSP response to staple; c2pa-rs writes it into `rVals.ocspVals` for you.
Implement it on your signer:

```rust
fn ocsp_val(&self) -> Option<Vec<u8>> {
    // DER OCSP response for the signing certificate, fetched from
    // https://ocsp.trufo.ai and cached until nextUpdate
    Some(self.cached_ocsp_response.clone())
}
```

Fetch one response per signing certificate and reuse it until its `nextUpdate`
(Trufo responses are valid for 7 days) — do not fetch per sign.

**With c2patool**, stapling depends on how the signer is configured; if your build
does not staple, validators fall back to fetching from the AIA URL, which works but
requires them to be online at validation time.

---

## Reference

- Certificate, OCSP, and TSA reference: [api_certs.md](../api/api_certs.md)
- Complete runnable example: [1_certs.py](1_certs.py)

