# Timestamping and OCSP

Attach RFC 3161 timestamps from Trufo Timestamp Authority (`tsa.trufo.ai`) and staple OCSP revocation responses from `ocsp.trufo.ai` when operating your own C2PA signer (`c2pa-rs`, `c2patool`, etc.).

> **Note:** If Trufo signs for you via `/c2pa/sign` or Local mode, Trufo handles timestamping and OCSP automatically. For certificate enrollment, see [Certificates](certificates.md).

---

## Timestamping (`tsa.trufo.ai`)

Attach an RFC 3161 timestamp to every C2PA signature so signed assets remain verifiable after the leaf signing certificate expires.

- **Production endpoint:** `https://tsa.trufo.ai/` (or your dedicated `https://{host}.tsa.trufo.ai/` endpoint for high-throughput workloads)
- **Auth:** `X-API-Key: <your-tsa-key>` (include the full `tsa:` prefix)
- **Test endpoints:**
  - `https://test.tsa.trufo.ai/` — no API key required. Signs with a **self-signed test TSA certificate** that does not chain to `https://test.ca.trufo.ai/root-ca.crt` (or any production root), so validators report the timestamp as untrusted. Use it only with dummy/Test Flow assets.
  - `https://test.tsa.trufo.ai/api-key` — same test response, but requires the literal header `X-API-Key: test-api-key-header`. Point your signer here to confirm it actually sends the `X-API-Key` header (a missing or different header returns `401`) before you buy a `tsa` key; then switch the URL to `https://tsa.trufo.ai/` and the header value to your real key.

### With `c2pa-rs` (TSA + OCSP stapling wrapper)

`create_signer::from_keys` accepts a TSA URL but no custom headers. Wrap `Signer` (or `AsyncSigner`) to supply `timestamp_request_headers()` and a cached `ocsp_val()`:

```rust
use c2pa::{Signer, SigningAlg};

struct TrufoSigner {
    inner: Box<dyn Signer + Send + Sync>,
    tsa_api_key: String,
    // DER OCSP response for the leaf cert, refreshed in the background; empty until first fetch
    cached_ocsp_der: Vec<u8>,
}

impl Signer for TrufoSigner {
    fn sign(&self, data: &[u8]) -> c2pa::Result<Vec<u8>> { self.inner.sign(data) }
    fn alg(&self) -> SigningAlg { self.inner.alg() }
    fn certs(&self) -> c2pa::Result<Vec<Vec<u8>>> { self.inner.certs() }
    fn reserve_size(&self) -> usize {
        // If `inner` was built without a TSA URL (and without OCSP), its reserve_size()
        // does not budget for the timestamp token and stapled OCSP response this wrapper
        // adds, and signing fails with a COSE buffer overflow. Add headroom for both.
        self.inner.reserve_size() + 16 * 1024
    }
    fn time_authority_url(&self) -> Option<String> {
        Some("https://tsa.trufo.ai/".to_owned())
    }
    fn timestamp_request_headers(&self) -> Option<Vec<(String, String)>> {
        Some(vec![("X-API-Key".to_owned(), self.tsa_api_key.clone())])
    }
    fn ocsp_val(&self) -> Option<Vec<u8>> {
        // Never staple an empty response: return None until a response has been fetched
        (!self.cached_ocsp_der.is_empty()).then(|| self.cached_ocsp_der.clone())
    }
}
```

> **Important:** `ocsp.trufo.ai` answers only for certificates issued by Trufo CA. If your signer uses a certificate from another CA, `ocsp_val()` must return that CA's OCSP response (or `None`) — never a Trufo response.

### With `c2patool` or clients without custom headers

Proxy through a private internal reverse proxy that injects `X-API-Key` (never expose this proxy publicly):

```nginx
location /tsa/ {
    proxy_pass https://tsa.trufo.ai/;
    proxy_ssl_server_name on;  # send SNI for tsa.trufo.ai; without it the TLS handshake fails
    proxy_set_header X-API-Key "<YOUR_TSA_API_KEY>";
}
```

Configure your client's TSA URL as `http://<internal-proxy-host>/tsa/` (the trailing slash matters: the proxy maps `/tsa/` to `https://tsa.trufo.ai/`).

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

- **Endpoints:** `https://ocsp.trufo.ai` (production) and `https://test.ocsp.trufo.ai` (Test Flow) — unauthenticated `POST /` (`Content-Type: application/ocsp-request`) or `GET /{base64_request}`, plus optional issuer-pinned paths (`/c2pa`, `/cawg`, `/ctsa`, `/root`). These responders cover Trufo CA-issued certificates only.
- **Build requests against the direct issuing CA:** Fetch the issuing CA cert from `https://ca.trufo.ai/c2pa-ca.crt` (`https://test.ca.trufo.ai/c2pa-ca.crt` in Test Flow) — not the root CA. `c2pa-l1` and `c2pa-l2` leaves share this issuing CA and the `/c2pa` OCSP path.
- **Cache and refresh on a schedule — never per sign:** Each response is valid for **7 days** (`thisUpdate` to `nextUpdate`), is cached and shared, and does not echo request nonces. Fetch one DER response per active signing certificate and refresh it in the background well before `nextUpdate` (for example, every 12–24 hours).
- **Revocation propagation:** The responder re-checks revocation state roughly **every 60 seconds**, so a revocation shows up in newly fetched responses within about a minute. A response you have already stapled stays valid until its own `nextUpdate`; refresh your cached response after revoking or rotating a certificate.

### Verify OCSP directly with OpenSSL

`leaf.pem` is your leaf certificate: the first certificate in the PEM chain the Python SDK returns, or the non-CA certificate in the EST PKCS#7 response (see [wire notes](../reference/certificates-api.md#wire-notes-for-rust-go-and-c-clients)).

```bash
curl -fsS https://ca.trufo.ai/c2pa-ca.crt -o c2pa-ca.der
curl -fsS https://ca.trufo.ai/root-ca.crt -o root-ca.der
openssl x509 -inform DER -in c2pa-ca.der -out c2pa-ca.pem
openssl x509 -inform DER -in root-ca.der -out root-ca.pem
cat c2pa-ca.pem root-ca.pem > ca_bundle.pem

openssl ocsp \
  -issuer c2pa-ca.pem \
  -cert leaf.pem \
  -CAfile ca_bundle.pem \
  -url https://ocsp.trufo.ai/c2pa \
  -no_nonce \
  -respout ocsp_response.der
# Expected: "Response verify OK" and "leaf.pem: good"
```

For Test Flow certificates, use `https://test.ca.trufo.ai` for both downloads and `https://test.ocsp.trufo.ai/c2pa` as the URL. For a quick smoke test that skips response-signature verification, replace `-CAfile ca_bundle.pem` with `-noverify`.

Pass the raw bytes of `ocsp_response.der` into your signer's `ocsp_val()` hook.

---

## Reference

- Full TSA and OCSP wire specification, error codes, and policy discovery (`GET /policy`): [Timestamp Authority](../reference/certificates-api.md#timestamp-authority-rfc-3161) and [OCSP Responder](../reference/certificates-api.md#ocsp-responder-rfc-6960) in the Certificates, TSA, and OCSP API reference
- Certificate enrollment, rotation, and revocation: [Certificates](certificates.md)
- Generator product architecture and TSA sizing: [Build Your Own Generator Product](../guides/5_build-your-own-generator-product.md)
