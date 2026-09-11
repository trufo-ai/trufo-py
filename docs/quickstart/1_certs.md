# Quickstart: C2PA Signing Certificates

A C2PA Signing Certificate identifies the signing entity (software or hardware) embedded in a manifest. Two tracks are available:

| Track          | Purpose                             | Auth Required |
| -------------- | ----------------------------------- | ------------- |
| **Test**       | Development and integration testing | No            |
| **Production** | Real-world publishing               | Yes           |


> **Note:** You do not need a C2PA Signing Certificate to use the Trufo C2PA signing endpoints (`POST /c2pa/sign`) — that endpoint uses Trufo's own C2PA signer. A C2PA Signing Certificate is only required if you are operating your own conformant C2PA Generator Product. See the [C2PA Signing Certificate product page](https://app.trufo.ai/tca/certs/c2pa) for more details.

See [1_certs.py](1_certs.py) for a runnable example of both tracks.

---

## Test Certificate

No account authentication required. Uses a publicly known test HMAC secret; issued certificates are signed by Trufo's test CA and will not pass public validators.

```python
from trufo import generate_keypair, request_c2pa_test_cert
from trufo.crypt.algorithms import SigningAlgorithm

private_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_test_cert(
    org_name="My Company",
    common_name="My App",
    private_key_signer=private_pem,
)
```

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

C2PA signatures should carry an RFC 3161 timestamp so they remain verifiable after
the signing certificate expires. Trufo's TSA is at `https://tsa.trufo.ai/` and
authenticates with a `tsa`-scoped API key in the `X-API-Key` header.

**With trufo-py**, timestamping is automatic — the signing helpers fetch the key
from your stored credentials.

**With c2patool or another C2PA implementation**, point the tool at a TSA URL. Tools
built on older c2pa-rs releases send no custom headers, so they cannot present an
`X-API-Key`. Two options:

- **Use the keyless test endpoint** while developing:
  `https://test.tsa.trufo.ai/`. It speaks the same protocol with no credential, but
  its tokens carry the Trufo test policy and are deliberately untrusted — never use
  them for production content.
- **Front the production TSA with a small proxy** that adds the header, and point
  the tool at your proxy:

  ```nginx
  location /tsa {
      proxy_pass https://tsa.trufo.ai/;
      proxy_set_header X-API-Key "tsa:<your-api-key>";
  }
  ```

  Keep the proxy inside your own network — it holds a credential.

Organizations with a dedicated endpoint use `https://{your-host}.tsa.trufo.ai/`,
which takes the same key.

Verify a timestamp response with OpenSSL:

```bash
openssl ts -query -data file.jpg -sha256 -cert -out request.tsq
curl -s -H "Content-Type: application/timestamp-query" \
     -H "X-API-Key: tsa:<your-api-key>" \
     --data-binary @request.tsq https://tsa.trufo.ai/ -o response.tsr
openssl ts -reply -in response.tsr -text
```

## Revocation and Rotation

Certificates are issued for at most a year (90 days at assurance level 2), so plan
renewal rather than treating enrollment as one-time. Because an instance may hold
two active credentials at once, rotation is non-disruptive: register the new
credential, move signing to it, then revoke the old one.

Revoke a certificate when a key is compromised or a deployment is retired — from
the dashboard, or `POST /cert/revoke` with the serial number and a reason. Choose
**Now** or specify an effective date, time, and UTC offset in the dashboard. API
callers can provide `revocation_time`; omitting it uses the processing time.
See the [certificate API reference](../api/api_certs.md#certificates) for the
request format and authentication requirements.

Revocation is permanent and publishes through OCSP. A trusted timestamp lets
validators assess whether content was signed before the effective revocation
cutoff, subject to the applicable validation rules.

### OCSP stapling

C2PA expects the signer to **staple** a revocation response into the signature
rather than leaving validators to fetch one. The response is embedded in the COSE
signature's unprotected header, under `rVals.ocspVals` — so it travels with the
asset and remains checkable offline, and long after the OCSP responder has moved on.
This matters because a validator that cannot reach the responder may otherwise
report the signature as unverifiable.

Trufo certificates carry `https://ocsp.trufo.ai` in their AIA extension, so tooling
finds the responder automatically.

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

