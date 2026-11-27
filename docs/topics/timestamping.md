# Timestamping and OCSP

Attach RFC 3161 timestamps from Trufo Timestamp Authority (`tsa.trufo.ai`) and staple OCSP revocation responses from `ocsp.trufo.ai` when operating your own C2PA signer (`c2pa-rs`, `c2patool`, etc.).

> **Note:** If Trufo signs for you via `/c2pa/sign` or Local mode, Trufo handles timestamping and OCSP automatically. For certificate enrollment, see [Certificates](certificates.md).

---

## Timestamping (`tsa.trufo.ai`)

Attach an RFC 3161 timestamp to every C2PA signature so signed assets remain verifiable after the leaf signing certificate expires.

- **Production endpoint:** `https://tsa.trufo.ai/` (or your dedicated `https://{host}.tsa.trufo.ai/` endpoint for high-throughput workloads)
- **Auth:** `X-API-Key: <your-tsa-key>` (include the full `tsa:` prefix)
- **Test endpoints:**
  - `https://test.tsa.trufo.ai/` — no API key required; signs with a self-signed test TSA certificate (for dummy/Test Flow assets)
  - `https://test.tsa.trufo.ai/api-key` — identical test response, requires `X-API-Key: test-api-key-header` so you can verify header wiring before purchasing a `tsa` key

### With `c2pa-rs` (TSA + OCSP stapling wrapper)

`create_signer::from_keys` accepts a TSA URL but no custom headers. Wrap `Signer` (or `AsyncSigner`) to supply `timestamp_request_headers()` and a cached `ocsp_val()`:

```rust
use c2pa::{Signer, SigningAlg};

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

### With `c2patool` or clients without custom headers

Proxy through a private internal reverse proxy that injects `X-API-Key` (never expose this proxy publicly):

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

## OCSP Stapling (`ocsp.trufo.ai`)

Stapling a fresh DER OCSP response inside every signature lets validators confirm the signing certificate was unrevoked at signing time without live OCSP lookups.

- **Endpoints:** `https://ocsp.trufo.ai` (production) and `https://test.ocsp.trufo.ai` (Test Flow) — unauthenticated `POST /` (`Content-Type: application/ocsp-request`) or `GET /{base64_request}`, plus optional issuer-pinned paths (`/c2pa`, `/cawg`, `/ctsa`, `/root`).
- **Build requests against the direct issuing CA:** Fetch the issuing CA cert from `https://ca.trufo.ai/c2pa-ca.crt` (`https://test.ca.trufo.ai/c2pa-ca.crt` in Test Flow) — not the root CA.
- **Cache and refresh on a schedule — never per sign:** Responses are valid for **7 days** (`thisUpdate` to `nextUpdate`), cached and shared, and do not echo request nonces. Fetch one DER response per active signing certificate and refresh it in the background well before `nextUpdate` (for example, every 12–24 hours).

### Verify OCSP directly with OpenSSL

```bash
curl -fsS https://ca.trufo.ai/c2pa-ca.crt -o c2pa-ca.der
openssl x509 -inform DER -in c2pa-ca.der -out c2pa-ca.pem

openssl ocsp \
  -issuer c2pa-ca.pem \
  -cert leaf.pem \
  -url https://ocsp.trufo.ai/c2pa \
  -no_nonce \
  -respout ocsp_response.der
```

Pass the raw bytes of `ocsp_response.der` into your signer's `ocsp_val()` hook.

---

## Reference

- Full TSA and OCSP wire specification, error codes, and policy discovery (`GET /policy`): [Certificates, TSA, and OCSP API](../reference/certificates-api.md#ocsp-responder-rfc-6960)
- Certificate enrollment, rotation, and revocation: [Certificates](certificates.md)
- Generator product architecture and TSA sizing: [Build Your Own Generator Product](../guides/5_build-your-own-generator-product.md)
