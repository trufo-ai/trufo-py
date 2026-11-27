# Brands and Creative Workflows

Most brand, agency, and publishing assets do not go straight from a camera or AI generator to the public web. They bounce through cameras, stock libraries, Photoshop, Figma, retouching agencies, DAMs, and CDNs — and almost every step in that chain can silently strip or break C2PA provenance if you don't design for it.

This guide covers best practices for stamping verified brand identity, preserving provenance across creative pipelines, and handling edits and redactions cleanly.

---

## 1. Stamping Verified Brand Identity

Every file signed through Trufo automatically carries `ai.trufo.identity` with your organization ID and (once Organization Validation is active) your validated legal name. For public publishing, pair that with **CAWG assertions** so validators display clear creator, brand, and rights information:

- **`cawg_identity` (`"org_interim"`):** Cryptographically binds your organization's verified identity to the gathered assertions in your manifest (requires the CAWG Organization Certificate plan).
- **`cawg_metadata`:** Carries byline/creator (`dc:creator`), copyright (`dc:rights`), creation date, alt text (`Iptc4xmpCore:AltTextAccessibility`), and IPTC location/credit fields in JSON-LD.
- **`cawg_training`:** Declares whether AI training, generative training, inference, or data mining are `allowed`, `notAllowed`, or `constrained`.
- **`custom` assertions:** When you need brand-specific provenance data (for example, campaign IDs or internal asset IDs), validate your domain in the dashboard and emit a reverse-DNS assertion such as `com.example.asset`.

**Tip on IPTC/XMP metadata preservation:** When converting between image formats (for example JPEG → WebP or AVIF), formats that lack native IPTC segments drop IPTC on transcode. Copying key credit, copyright, and creator fields into `cawg_metadata` keeps them cryptographically bound inside the C2PA manifest across format conversions.

---

## 2. Surviving Photoshop, Figma, and DAM Edits

The #1 operational headache for brands and creative agencies is **provenance getting stripped or invalidated mid-workflow** by design tools, retouching steps, or DAM renditions.

You have two clean patterns depending on where edits happen:

### Pattern A: Let Trufo perform delivery transforms (simplest)

For routine delivery operations — resizing for web/social, cropping, trimming video/audio, transcoding formats (e.g., TIFF/HEIC/PNG → JPEG/WebP, MOV → MP4), or repackaging — run them as **Trufo media actions** (`resize`, `crop`, `trim`, `transcode`, `repackage`) inside the signing call.

- Trufo performs the edit, preserves the incoming manifest as the `parentOf` ingredient, updates EXIF/XMP dimensions, records the exact C2PA action (`c2pa.resized.proportional`, `c2pa.cropped`, `c2pa.transcoded`, etc.), and signs the result in one atomic step.
- **No Branded Product Validation required** for Trufo's built-in media actions.
- **Note on `transcode` + newly created assets:** You cannot combine `transcode` or `repackage` with a `c2pa.created` sign in the same request — sign the original asset first, then transcode the signed file (or transcode before signing when no prior manifest needs to be preserved).

### Pattern B: External creative edits (Photoshop, Figma, NLEs, custom DAM pipelines)

When an editor modifies an image or video outside Trufo and the editing tool strips or breaks the original manifest:

- **With a Branded Generator Product (`branded_gp_id`):** Send the edited asset as the input, attach the original unedited file as a `parentOf` ingredient (`media`), and declare what changed in `action_history` (e.g., `c2pa.cropped`, `c2pa.adjustedColor`, `c2pa.edited`, with truthful `digitalSourceType` values such as `humanEdits` or `compositeWithTrainedAlgorithmicMedia`). Set `ManifestSettings(all_actions_included=True)` only when your `action_history` covers every edit since the parent.
- **Without a Branded Generator Product:** You can still sign the final asset with `cawg_identity`, `cawg_metadata`, and `publish`, and declare contributing assets as gathered `componentOf` / `inputTo` ingredients — just be aware that `parentOf` + `action_history` requires a Branded Generator Product.
- **Watch out for broken embedded manifests:** If an external tool edited pixels *without* removing the old C2PA box, the file arrives with a mismatched hash. Under default `signed_input_policy: "auto"`, Trufo keeps readable manifests and records their validation failures in the new manifest (with a warning). Keep the clean original file alongside your DAM job if you want to link it cleanly via `parentOf`.

---

## 3. Handling Agencies and Third-Party AI Tools

Creative agencies frequently combine camera photography, stock assets, retouching, and third-party generative AI tools (background fill, voiceovers, concept frames) into a single campaign deliverable.

Two best practices prevent surprises when a client's verifier checks the file:

1. **Be transparent and precise about AI involvement:**
   - Only mark an AI system `c2pa_first_party_attestable: true` if *your organization* operates the model.
   - When an asset is a composite of human photography and AI edits, `ai_modified` (`compositeWithTrainedAlgorithmicMedia`) is the truthful declaration — not `ai_generated` — and requires a Branded Generator Product.
   - If you use third-party AI tools without a Branded Generator Product, Trufo records the AI tool as a declared ingredient; test how your client's validator displays that before committing to a workflow.
2. **Test trust and display separately during onboarding:**
   - Files signed on `test.api.trufo.ai` carry Trufo's test certificate, so public validators will flag the signer as untrusted even when every assertion and AI label is structurally right. Use test signing to check your **assertion structure and metadata**, and a production-signed sample to verify **trust chain display**.

---

## 4. Redacting Sensitive Metadata Safely

Before publishing camera originals or partner assets, you may need to remove sensitive upstream assertions — such as GPS coordinates or device serials in `c2pa.metadata`, or an embargoed contributor's byline in `cawg.metadata` and `cawg.identity` — without throwing away the rest of the provenance chain.

- **Use the `redact` action** with an explicit `reason` (`c2pa.PII.present`, `c2pa.trade-secret.present`, `c2pa.invalid.data`, `c2pa.government.confidential`, or a domain-validated custom reason).
- **To fully remove a contributor's identity**, redact *both* `cawg.metadata` and `cawg.identity` — removing only one leaves the other intact.
- **Redaction is strict and all-or-nothing:** If the input has no C2PA manifest, or if a targeted label doesn't exist anywhere in the input's history, the request fails with `400` and nothing is signed. Inspect incoming manifests (or only send `redact` on inputs known to carry those labels) rather than sending blind redactions on mixed signed/unsigned batches.
- **Check numbered labels:** If a manifest contains multiple assertions of the same type (`c2pa.metadata`, `c2pa.metadata__1`), a bare label only redacts the unnumbered one.

---

## 5. Surviving CDNs and Social Distribution

- **Audit your image CDN:** Many CDNs strip JUMBF/APP11 segments during auto-WebP/auto-AVIF optimization. Either pass through already-signed renditions (generated via Trufo's `resize`/`transcode` actions) or configure your CDN to preserve C2PA metadata.
- **Pair with watermarking when stripping is unavoidable:** If assets are published to social networks that always re-encode and strip manifests, add a `["watermark", {"effort_policy": "require_if_supported"}]` action (placed last) so you can still recover the original manifest later via `/content/recover`.
- **Keep manifests lean for web delivery:** Set explicit `manifest_title` and `ingredient_title` (usually the clean filename) so validators don't show generic names, and set `thumbnail_settings.policy` to `"none"` or `"auto_no_ingredient"` if multi-hop thumbnail bloat is a concern for web bandwidth.

---

## 6. Structuring Multi-Brand Organizations

If your company operates several brands or regional desks:

- **Separate legal entities that sign under their own legal name** → use an **Organization Group** (one management organization for billing and user administration, plus one sub-organization per legal entity, each with its own OV, API keys, and CAWG identity).
- **Multiple brands or products under one legal entity** → a single organization is usually simpler (optionally with separate Branded Generator Products if each product needs its own signing identity), avoiding duplicate OV reviews.

See [Account Management](2_account-management.md) for the full governance and role model.

---

## Next Steps

- **Step-by-step code:** [CAWG Identity and Metadata](../topics/cawg-identity.md), [Ingredients and Redaction](../topics/ingredients-and-redaction.md), [Cloud Signing](../topics/signing-cloud.md)
- **Normative schemas:** [Actions and Assertions](../reference/actions-and-assertions.md), [Media Format Support](../reference/media-formats.md)
