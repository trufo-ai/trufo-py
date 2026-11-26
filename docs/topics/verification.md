# Verification

Verify signed media programmatically in development and CI pipelines, inspect assertions before publishing, and validate manifests recovered from stripped files.

---

## 1. Inspecting and Verifying Signed Files (`c2patool`)

Use standard C2PA tooling such as [`c2patool`](https://github.com/contentauth/c2pa-rs/tree/main/cli) or `c2pa-rs` to inspect and validate signed outputs in automated tests:

```bash
# Print the manifest store JSON and validation status
c2patool signed.jpg
```

What to check in a healthy Trufo-signed asset:
- **No failure codes** in `validation_status` (signature valid, hard-binding data hash matches, timestamp valid, certificate chain trusted).
- **Expected assertions present:**
  - `ai.trufo.identity` (`oid` and, with active OV, `orgName`).
  - `c2pa.actions` (`c2pa.created` with `trainedAlgorithmicMedia` for first-party AI generation, `c2pa.opened` + `c2pa.published` / media actions, etc.).
  - `c2pa.ai-disclosure`, `cawg.identity`, `cawg.metadata`, `cawg.training-mining`, or `c2pa.soft-binding` where requested.
- **Ingredients & redactions:** Check `ingredients[]` for preserved parent manifests and `redacted_assertions` when using `redact`.

---

## 2. Verifying Test-Host Assets in CI

Files signed on `https://test.api.trufo.ai` (or with certificates from `https://test.ca.trufo.ai`) chain to **TCA Test Root CA**, which public C2PA trust lists deliberately do not trust.

To verify test-signed files in local tests or CI without disabling signature checks, download the test root certificate and pass it as a local trust anchor:

```bash
curl -fsS https://test.ca.trufo.ai/root-ca.crt -o test_root.der
openssl x509 -inform DER -in test_root.der -out test_root.pem
```

Point `c2patool` / `c2pa-rs` `trust.trust_anchors` at `test_root.pem` in your test configuration:

```toml
# c2pa_test_settings.toml
[trust]
trust_anchors = """
-----BEGIN CERTIFICATE-----
... contents of test_root.pem ...
-----END CERTIFICATE-----
"""
```

```bash
c2patool --settings c2pa_test_settings.toml signed_test.jpg
```

*(Production files signed via `api.trufo.ai` / `eu.api.trufo.ai` or with production TCA certificates chain to `Trufo C2PA Root CA`, downloadable at `https://ca.trufo.ai/root-ca.crt`, and validate against the C2PA Trust List.)*

---

## 3. Validating a Manifest Recovered via Watermark (`/content/recover`)

When a file has been stripped or re-encoded (for example by a social platform), `POST /content/recover` decodes the embedded Trufo Pawprint watermark and — for `per_embed` marks — returns the stored C2PA manifest store in `manifest_bytes`.

**Important:** Do **not** run a standard hard-binding hash check of `manifest_bytes` directly against the re-encoded/stripped file and expect it to pass. Re-encoding changed the file's bytes, so C2PA hard-binding (`assertion.hashedURI` / `c2pa.hash.data` / `c2pa.hash.bmff`) validation **will** report a hash mismatch.

Instead, verify a recovered `per_embed` manifest in two checks:

1. **Cryptographic integrity of the recovered manifest store:** Verify the manifest's COSE signature, certificate chain against the C2PA Trust List, RFC 3161 timestamp, and stapled OCSP response.
2. **Soft-binding match:** Confirm the recovered manifest contains a `c2pa.soft-binding` assertion with `alg == "ai.trufo.pawprint.watermark"` whose block `value` matches the `wid` decoded from the media (and visually/perceptually compare the manifest's thumbnail if present).

If you only need to inspect fields without a local C2PA library, `recover_content(..., parse_manifest_json=True)` returns `manifest_json` as a convenience parse, not a cryptographic validation result.

---

## 4. Incoming Signed Files and Remote Manifests

When you pass an already-signed file into Trufo's signing API:

- Trufo validates the incoming embedded manifest, keeps it as the `parentOf` ingredient, and records its validation results in the new manifest (emitting a `TrufoServerWarning` if the incoming manifest is invalid or chains to an untrusted signer).
- Check [Signed inputs and ingredients](../reference/actions-and-assertions.md#signed-inputs-and-ingredients) for exact `signed_input_policy` and `signed_ingredient_policy` rules (`auto` vs. `keep`).

---

## Reference

- CA root & intermediate certificate downloads: [Certificates, TSA, and OCSP API](../reference/certificates-api.md#ca-certificate-downloads)
- Watermark recovery schema: [Watermarking and Content API](../reference/watermarking-api.md#post-contentrecover)
- Signed input & ingredient validation rules: [Actions and Assertions](../reference/actions-and-assertions.md#signed-inputs-and-ingredients)
