# Build Your Own Generator Product

If you build a camera, creative desktop or mobile app, or high-scale media backend that signs C2PA manifests directly using `c2pa-rs`, `c2patool`, or your own signer, Trufo Certificate Authority (TCA) provides the PKI layer: C2PA Claim Signing certificates (EST), RFC 3161 timestamping (TSA), and OCSP revocation status.

This guide walks through the real-world path from early prototyping to a conformant, auto-renewing production signer — including the operational details that trip teams up during C2PA conformance review.

---

## 1. Understand the Order of Operations

The most common mistake teams make is starting Product Validation or production enrollment in the wrong order. Here is the clean sequence:

```text
1. Test & design         Dummy cert (for conformance drafts) + Test Flow (rehearse real EST/OCSP/TSA)
        │
2. Parallel reviews      Start Trufo Organization Validation (OV)  +  C2PA Generator Product Conformance
        │
3. Product Validation    Submit Trufo Product Validation (PV) with your conformance details + subscribe
        │
4. Provision & enroll    Create instances → register KMS/HSM instance keys → enroll leaf certs via EST
        │
5. Operate               Embed TSA timestamps + staple OCSP + automate renewal before expiry
```

### Dummy certs vs. Test Flow vs. Production

| Track | Use it for | Needs account / OV / PV? |
| --- | --- | --- |
| **Dummy certificate** | Getting a well-formed test cert carrying your company/app name for a C2PA conformance application | None |
| **Test Flow** (`test.api.trufo.ai`, `test.ca.trufo.ai`, `test.ocsp.trufo.ai`, `test.tsa.trufo.ai`) | Rehearsing the exact production enrollment, instance credential, OCSP, and revocation pipeline before you buy (useful when writing your conformance security architecture doc) | Account + MFA (owner/admin); no OV, PV, or subscription |
| **Production** | Issuing trusted certificates recognized on the C2PA Trust List | Active OV + approved PV + subscription |

Nothing from the Test Flow carries over to production: when you go live, create your production product, instances, credentials, and keys fresh.

---

## 2. Key Custody Best Practices (Start With KMS/HSM)

Two separate keys are involved for every signing instance — keep them distinct and never reuse a leaf key across renewals:

1. **Instance credential key (`gpic_id`):** Long-lived authentication key (`ES256` P-256 or `EdDSA` Ed25519) used only to sign short-lived `client_assertion` JWTs when requesting a certificate. It never signs media.
2. **Leaf signing key:** Fresh **EC P-256** (recommended for widest validator compatibility; P-384 also accepted) key generated per certificate enrollment. Re-enrolling an existing public key is rejected (`409 PublicKeyAlreadyUsed`).

**Best practice — store keys in a cloud KMS or HSM from day one:** Even at Assurance Level 1 (`c2pa-l1`), C2PA conformance reviewers strongly favor non-exportable keys in AWS KMS, Google Cloud KMS, or an HSM over encrypted files on disk. Both `instance_key_pem` and `private_key_signer` in `trufo-py` accept `AWSKMSPrivateKey` / `GCPKMSPrivateKey` wrappers directly, and `c2pa-rs` supports custom `Signer` / `AsyncSigner` traits backed by KMS or PKCS#11.

For hardware-backed **Assurance Level 2 (`c2pa-l2`, 90-day max validity)**, contact [support@trufo.ai](mailto:support@trufo.ai) to enable `c2pa-l2` on your product.

---

## 3. Modeling Instances and Automating Rotation

Model **one instance (`gpi_id`) per independent key holder** — for example, one per signing microservice/region with its own KMS key, or one per HSM partition.

- **Two active credentials per instance:** Register your replacement instance key first, cut over your enrollment job to the new `gpic_id`, then revoke the old credential — zero downtime.
- **Three active certificates per instance:** Certificates last up to **366 days** (`c2pa-l1`) or **90 days** (`c2pa-l2`). Automate renewal well ahead of expiry (e.g., at 60–75% of lifetime) with a fresh leaf key pair, switch signing to the new cert, and let the old one expire (or revoke it if retired early).
- **Watch OV and PV expiry:** Enrollment requires active (unexpired) OV and PV (`403 OVNotActive` / `403 PVNotActive`). Track `validated_expires_at` from `/gproduct/list` and renew validations ahead of your certificate renewal window.
- **Never ship org-scoped credentials to client devices:** Your `tsa` API key and interactive MFA sessions belong on backend infrastructure, never embedded in desktop binaries, mobile apps, or camera firmware. Unattended certificate enrollment (`csr-jwt`) authenticates with each instance's registered credential key; MFA sessions are only needed to provision instances and credentials and to revoke. For distributed clients, proxy TSA requests through your own backend.

---

## 4. Timestamping (TSA) and OCSP Stapling Are Not Optional

Without a trusted timestamp and stapled OCSP response, signed assets can become unverifiable once your signing certificate expires or if a validator is offline.

### Timestamping (`tsa.trufo.ai`)

- Send RFC 3161 requests (`Content-Type: application/timestamp-query`) with your `X-API-Key` header (`tsa`-scoped key). Copy the complete key including its `tsa:` prefix.
- **Throughput planning:** The shared `tsa.trufo.ai` endpoint comfortably serves moderate workloads (plan around ~10 RPS on the shared service). If you have high sustained throughput, bursty peak traffic, or strict SLA/regional requirements (e.g., dedicated EU or US-East capacity), talk to us about a **dedicated TSA endpoint** (`https://{your-host}.tsa.trufo.ai/`).
- **You can adopt Trufo TSA independently:** You do not need to wait for C2PA certificate conformance to start using `tsa.trufo.ai` with your existing certificates.
- **Clients without custom header support (`c2patool`):** Put a lightweight private reverse proxy (such as Nginx) inside your network that injects `X-API-Key` and forwards to `https://tsa.trufo.ai/`.

### OCSP Stapling (`ocsp.trufo.ai`)

- C2PA expects signers to **staple** a DER OCSP response into each COSE signature (`rVals.ocspVals`) rather than forcing every validator to query OCSP live.
- **Cache, do not fetch per sign:** Trufo OCSP responses are valid for **7 days** (`thisUpdate` to `nextUpdate`). Fetch one response per active signing certificate on a background timer (for example every 12–24 hours, well before `nextUpdate`) and serve the cached bytes from your signer's `ocsp_val()` method.
- **Build OCSP requests against the direct issuing CA** (`/c2pa-ca.crt` for `c2pa-l1` and `c2pa-l2`), not the responder cert; Trufo certificates include `https://ocsp.trufo.ai` in their AIA extension.

---

## 5. Incident Response: Certificate Revocation

If a signing key is compromised or a deployment is retired:

1. Revoke via the dashboard or `POST /cert/revoke` (requires an MFA-verified owner/admin session — an API key alone cannot revoke a certificate).
2. **Use `revocation_time` thoughtfully:** If you know when a compromise started, you can set an explicit UTC cutoff (`revocation_time`) so assets timestamped *before* the compromise remain distinguishable from assets signed after it.
3. **Never blindly retry a `502 RevocationFailed`:** Re-list certificates via `POST /cert/list` first to confirm state.

---

## 6. Optional: Adding Trufo Watermarking to Your Own Signer

If you sign C2PA manifests with your own certificates but still want Trufo Pawprint watermarks that survive social/CDN stripping, you can pair your signer with Trufo's standalone binding routes (`/bind/watermark` in Cloud mode or `/bind/reserve` + local embedding, followed by `/bind/commit`). See [Watermarking and Recovery](../topics/watermarking.md#binding-without-trufo-signing-bind) and [Watermarking and Content API](../reference/watermarking-api.md) for the exact `c2pa.soft-binding` assertion format your signer should write.

---

## Next Steps

- **Certificate enrollment, KMS, rotation, and revocation:** [Certificates](../topics/certificates.md)
- **RFC 3161 timestamping and OCSP stapling (`c2pa-rs`, `c2patool`, OpenSSL):** [Timestamping and OCSP](../topics/timestamping.md)
- **Wire specs (EST, JWS `client_assertion`, PKCS#10, OCSP, TSA, RA):** [Certificates, TSA, and OCSP API](../reference/certificates-api.md)
- **Verifying test and production assets in CI:** [Verification](../topics/verification.md)
