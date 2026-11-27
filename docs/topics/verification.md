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

Files signed on `https://test.api.trufo.ai`, with Test Flow certificates from `https://test.ca.trufo.ai`, or with dummy certificates (`c2pa-l1-test` / `cawg-interim-test`, enrolled on `https://ca.trufo.ai`) chain to **TCA Test Root CA**, which public C2PA trust lists deliberately do not trust.

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

The exact settings keys depend on your `c2patool` / `c2pa-rs` version (recent releases group claim-signing, CAWG, and timestamp trust lists under `trust.anchors`); check the settings reference for the version you run.

What to expect from test-host assets even with the test root trusted:

- **Timestamps:** `test.api.trufo.ai` and `https://test.tsa.trufo.ai/` timestamp with a **self-signed test TSA certificate** that does not chain to `test.ca.trufo.ai/root-ca.crt`, so validators report the timestamp as untrusted (`timeStamp.untrusted`). In CI, treat that code as expected for test assets (or disable timestamp-trust verification in your test settings, e.g. `verify.verify_timestamp_trust = false` in `c2pa-rs`) — never in production checks.
- **`cawg.identity`:** Identity assertions are verified against a separate CAWG trust list, not the claim-signing anchors above. On the test host, `cawg_identity_id="test"` signs with a shared test CAWG certificate (and dummy `cawg-interim-test` certificates are issued) under the TCA Test CAWG Interim Issuing CA, which also chains to TCA Test Root CA — add `test_root.pem` as a CAWG trust anchor too. Production assertions signed with your organization's Trufo-managed interim certificate (`org_interim`) or a `cawg-interim` certificate you enrolled chain through the **Interim CAWG Identity CA** (`https://ca.trufo.ai/temp-cawg-ca.crt`) to `https://ca.trufo.ai/root-ca.crt`; add that root as a CAWG trust anchor if your validator does not already trust it.

*(Production files signed via `api.trufo.ai` / `eu.api.trufo.ai` or with production TCA certificates chain to `Trufo C2PA Root CA`, downloadable at `https://ca.trufo.ai/root-ca.crt`, and validate against the C2PA Trust List.)*

---

## 3. Validating a Manifest Recovered via Watermark (`/content/recover`)

When a file has been stripped or re-encoded (for example by a social platform), `POST /content/recover` decodes the embedded Trufo Pawprint watermark and — for `per_embed` marks — returns the stored C2PA manifest store in `manifest_bytes`.

**Important:** Do **not** run a standard hard-binding hash check of `manifest_bytes` directly against the re-encoded/stripped file and expect it to pass. Re-encoding changed the file's bytes, so C2PA hard-binding (`assertion.hashedURI` / `c2pa.hash.data` / `c2pa.hash.bmff`) validation **will** report a hash mismatch.

Instead, verify a recovered `per_embed` manifest in two checks:

1. **Cryptographic integrity of the recovered manifest store:** Verify the manifest's COSE signature, certificate chain against the C2PA Trust List, RFC 3161 timestamp, and stapled OCSP response.
2. **Soft-binding match:** Confirm the recovered manifest contains a `c2pa.soft-binding` assertion with `alg == "ai.trufo.pawprint.watermark"` whose block `value` is the `wid` decoded from the media (and visually/perceptually compare the manifest's thumbnail if present).

### Recipe

**Step 1 — recover and save the detached store.** `manifest_bytes` is a complete C2PA manifest store (JUMBF), the same bytes a `.c2pa` sidecar holds:

```python
from trufo import recover_content

result = recover_content(recover_key, media_bytes, parse_manifest_json=True)
if result.detected and result.manifest_bytes:
    with open("recovered.c2pa", "wb") as f:
        f.write(result.manifest_bytes)
```

`detected=True` with `manifest_bytes=None` is normal — not an error — for `per_ai_system` marks (inspect `result.ai_system` and `result.ai_involvement` instead) and for `per_embed` records another organization has set `inactive` (only detection is disclosed). Your own organization's records always return their manifest.

**Step 2 — validate the store cryptographically.** Load the detached store together with the recovered media in a C2PA library — in `c2pa-rs`, `Reader::from_context(context).with_manifest_data_and_stream(&manifest_bytes, format, stream)` (in the C API, `c2pa_reader_from_context()` then `c2pa_reader_with_manifest_data_and_stream()`) — with your usual trust settings, then read the validation results:

- **Must pass:** claim signature, signing certificate chain and trust, timestamp, and OCSP/revocation status.
- **Expected to fail on re-encoded media:** hard-binding hash codes such as `assertion.dataHash.mismatch` or `assertion.bmffHash.mismatch`. Ignore only these; any other failure means the store itself is not trustworthy.

**Step 3 — match the soft binding to the decoded `wid`.** The helper below reads Trufo's `result.manifest_json` (crJSON: `manifests` is a list and each manifest's `assertions` is an object keyed by label — not the layout of `c2pa-rs`'s default `Reader::json()`; adapt the lookup if you read your library's report instead). There, the soft-binding block `value` is the `wid`'s UTF-8 bytes; JSON reports render that byte string as a list of byte values, while manifests signed before the byte-string encoding carry plain text:

```python
def declared_wids(manifest_json: dict) -> set[str]:
    wids = set()
    for manifest in manifest_json.get("manifests", []):
        sb = manifest.get("assertions", {}).get("c2pa.soft-binding")
        if not sb or sb.get("alg") != "ai.trufo.pawprint.watermark":
            continue
        for block in sb.get("blocks", []):
            value = block.get("value")
            wids.add(bytes(value).decode("utf-8") if isinstance(value, list) else value)
    return wids

assert result.wid in declared_wids(result.manifest_json)
```

*(Older manifests may spell the same ID with a legacy `image.` or `audio.` prefix instead of `v1.`.)* `manifest_json` is a convenience parse with per-manifest validation results removed, so use it only for this field match — the verdict comes from Step 2.

---

## 4. Incoming Signed Files and Remote Manifests

When you pass a file that already carries C2PA data into Trufo's signing API, `signed_input_policy` (input file) and `signed_ingredient_policy` (ingredient `media`) decide what happens. Both accept `"auto"` (default) or `"keep"`:

| Existing C2PA data | `"auto"` (default) | `"keep"` |
| --- | --- | --- |
| Readable embedded manifest (valid or invalid) | Kept with its validation results recorded — the input file as the `parentOf` ingredient, an ingredient `media` file with the `relationship` you declared; a `TrufoServerWarning` flags an invalid or untrusted incoming manifest. With an `ai_system` assertion, the input file is also subject to the source-class check described after this table | Kept the same way; no source-class check (with `ai_system`, a warning notes that no new source type was declared) |
| **Remote manifest** — referenced by URL and fetched from an allowed host | Same as a readable embedded manifest (fetched, validated, embedded in the signed output, URL reference removed; emits a `TrufoServerWarning`) | Same as a readable embedded manifest |
| **Remote manifest** — referenced by URL and not fetched | Signed (or ingredient added) with `manifest.inaccessible` recorded and the URL reference removed (with a warning). Refused (`400 RemoteManifestUnavailable`) if the request declares a source type (`creation` or `ai_system`) | Refused with `400 RemoteManifestUnavailable` |
| Unreadable or malformed C2PA data | Removed with a warning; the file is signed as if it carried no C2PA data (a `redact` on that input then fails) | Refused with `400` |

**Remote manifests:** Trufo fetches manifests referenced by URL over HTTPS (default port, ≤ 10 MB, 5s timeout, no redirects) from allowed hosts (`cai-manifests.adobe.com` by default), embeds them in the signed output, and removes the URL reference. In Local mode (`trufo-provenance` 2.4.1+), use `RemoteManifestSettings(fetch=False)` or `allowed_hosts=[...]` to turn fetching off or replace the host list; Trufo's own output always embeds manifests directly. See [Remote Manifests](../reference/actions-and-assertions.md#remote-manifests) and [Storage Options](storage-options.md#remote-manifests).

Under `"auto"`, an `ai_system` assertion additionally triggers a source-class check on the input file's manifest chain (inputs classified as camera-captured or human-created are refused with `400`; `"keep"` skips the check); see [Signed inputs and ingredients](../reference/actions-and-assertions.md#signed-inputs-and-ingredients) for the full rules.

---

## Reference

- CA root & intermediate certificate downloads: [Certificates, TSA, and OCSP API](../reference/certificates-api.md#ca-certificate-downloads)
- Watermark recovery schema: [Watermarking and Content API](../reference/watermarking-api.md#post-contentrecover)
- Signed input & ingredient validation rules: [Actions and Assertions](../reference/actions-and-assertions.md#signed-inputs-and-ingredients)
