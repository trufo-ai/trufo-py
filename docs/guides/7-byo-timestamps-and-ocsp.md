# 7. BYO Timestamps and OCSP

This guide covers the Bring Your Own (BYO) signer route for timestamps and revocation status: adding RFC 3161 timestamps from Trufo Timestamp Authority (TSA) and stapled Online Certificate Status Protocol (OCSP) responses to a C2PA signer you run yourself. It applies whether your certificates come from Trufo CA ([5. BYO C2PA Certificates](5-byo-c2pa-certificates.md), [6. BYO CAWG Certificates](6-byo-cawg-certificates.md)) or from another CA. If Trufo signs for you, Trufo handles both.

An RFC 3161 timestamp proves the signature was made while the signing certificate was valid, so the asset stays verifiable after the certificate expires. A stapled OCSP response embeds the certificate's revocation status at signing time, so validators do not depend on a live OCSP lookup later. You can use Trufo TSA with a certificate from any CA; OCSP must come from the CA that issued your certificate.

---

## 1. Wire Your Signer to the Test TSA

`https://test.tsa.trufo.ai/` is free and needs no API key.

- It signs with a self-signed test certificate outside TCA Test Root CA, so `c2pa-rs` reports `timeStamp.untrusted` unless you relax timestamp trust in your test settings ([Verification](../topics/verification.md#2-verifying-test-host-assets-in-ci)). Use it only for test assets (such as Trufo dummy and Test Flow certificates).
- `https://test.tsa.trufo.ai/api-key` returns the same response but requires the literal header `X-API-Key: test-api-key-header` (`401` otherwise). Point your signer here to confirm it sends the header before you switch to production.

---

## 2. Set Up the Production TSA

### Prerequisites

1. Trufo account with MFA ([2. Trufo Account Setup](2-trufo-account-setup.md)).
2. Active **C2PA TSA** plan (`c2pa_tsa_api`).
3. An API key with the `tsa` scope, stored with `trufo set-api-key tsa <key>` or `TRUFO_TSA_API_KEY`. Keep it on backend infrastructure, not in client apps or device firmware ([2. Trufo Account Setup](2-trufo-account-setup.md#5-create-api-keys)).

The shared endpoint is `https://tsa.trufo.ai/`. For high sustained throughput or regional requirements (for example, a dedicated EU endpoint), contact [support@trufo.ai](mailto:support@trufo.ai) about a dedicated `https://{host}.tsa.trufo.ai/` endpoint.

### Send requests

`POST` a DER `TimeStampReq` to `https://tsa.trufo.ai/` with `Content-Type: application/timestamp-query` and `X-API-Key: tsa:<key>` (the full key, including the `tsa:` prefix). The unauthenticated `GET /policy` returns the policy OID and accepted digests. Limits and error codes are in [Timestamp Authority (RFC 3161)](../reference/certificates-api.md#timestamp-authority-rfc-3161).

### Wire it into your signer

- **`c2pa-rs`:** wrap your `Signer` (or `AsyncSigner`) so that `time_authority_url()` returns `https://tsa.trufo.ai/` and `timestamp_request_headers()` returns the `X-API-Key` header. The full wrapper, which also serves OCSP, is in [With `c2pa-rs`](../topics/timestamping.md#with-c2pa-rs-tsa--ocsp-stapling-wrapper).
- **`c2patool`, C FFI, and other clients without custom headers:** run a private reverse proxy that adds the header, and set the client's TSA URL to `http://<internal-proxy-host>/tsa/` (the trailing slash matters). Do not expose the proxy publicly. See [With `c2patool` or clients without custom headers](../topics/timestamping.md#with-c2patool-or-clients-without-custom-headers).

```nginx
location /tsa/ {
    proxy_pass https://tsa.trufo.ai/;
    proxy_ssl_server_name on;  # sends SNI for tsa.trufo.ai
    proxy_set_header X-API-Key "<YOUR_TSA_API_KEY>";
}
```

---

## 3. Staple OCSP Responses

`https://ocsp.trufo.ai` covers certificates issued by Trufo CA only. If you use Trufo TSA with another CA's certificate, fetch OCSP from that CA, or do not staple.

Requests are unauthenticated (`POST` with `Content-Type: application/ocsp-request`, or `GET /{base64_request}`). Operational rules:

- Use the issuer-pinned path for the certificate's direct issuing CA: `/c2pa` for `c2pa-l1` and `c2pa-l2`, `/cawg` for `cawg-interim`. `https://test.ocsp.trufo.ai` serves `/c2pa` only, for Test Flow certificates.
- Each response is valid for 7 days (`thisUpdate` to `nextUpdate`); the responder refreshes its revocation cache about every 60 seconds.
- Cache one response per active leaf certificate and refresh it on a schedule well before `nextUpdate` (for example, every 12–24 hours), and immediately after rotating or revoking a certificate. Never fetch per signature.

Endpoint and response details are in [OCSP Responder (RFC 6960)](../reference/certificates-api.md#ocsp-responder-rfc-6960).

### Wire it into `c2pa-rs`

In the same `Signer` wrapper, return `None` from `ocsp_val()` until the first response is fetched, never an empty slice, and add 16 KB headroom in `reserve_size()` to avoid a COSE buffer overflow. See [With `c2pa-rs`](../topics/timestamping.md#with-c2pa-rs-tsa--ocsp-stapling-wrapper).

---

## 4. Verify End to End

Three checks confirm the setup:

1. **Timestamp:** a token from the TSA verifies with `openssl ts` against the C2PA Timestamping CA (CTSA) chain.
2. **OCSP:** `openssl ocsp` reports your leaf certificate as `good`, after you convert the downloaded DER `.crt` issuer and root files to PEM.
3. **Signed asset:** a test file signed by your signer, read with the `c2pa-rs` Reader, shows a trusted timestamp and the stapled OCSP status.

The commands for the first two checks are in [Timestamping and OCSP](../topics/timestamping.md#verify-tsa-directly-with-openssl), and the third in [Verification](../topics/verification.md).

---

## Next Steps

- Add durable watermarks to assets from your own signer: [8. Watermarking with Pawprint](8-watermarking-with-pawprint.md).

## Reference

- [Timestamping and OCSP](../topics/timestamping.md)
- [Certificates, TSA, and OCSP API](../reference/certificates-api.md)
- [Verification](../topics/verification.md)
