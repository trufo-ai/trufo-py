# AI Labeling for Compliance

If you operate a generative AI model, API, or creative AI product, your users and regulators expect machine-readable proof that an image, video, or audio clip was AI-generated or AI-edited — even after it gets downloaded and re-uploaded elsewhere.

This guide covers the practical decisions behind a clean, compliant AI labeling implementation (including EU AI Act Article 50 and California SB 942) without over-engineering day one.

---

## 1. How Validators Actually Decide Something Is "AI"

C2PA carries AI information in two distinct places, and confusing them is the #1 reason teams are surprised when testing outputs on third-party platforms:

1. **The action's `digitalSourceType`** (most important for display today):
   - A `c2pa.created` action with `trainedAlgorithmicMedia` is the primary signal social platforms and C2PA validators look for when showing an **"AI-generated"** label.
   - An edit or creation carrying `compositeWithTrainedAlgorithmicMedia` signals **"AI-modified"** (partly AI).
   - **Watch out for gathered ingredients:** If an asset is merely wrapped as a *gathered* AI parent ingredient (rather than a `c2pa.created` action), many existing validators will not display a prominent "AI-generated" badge.
2. **The `c2pa.ai-disclosure` assertion:**
   - Carries structured model details (model type, name, identifier, human oversight level). It complements `digitalSourceType` and is good practice to include when registering your AI system, but should not be relied on alone for platform badges.

**Best practice:** Always test a sample signed output against the exact downstream platforms and validators that matter to your business, because platforms differ in how they render `ai_generated` vs. `ai_modified` and gathered vs. created assertions.

---

## 2. Match Your Scenario to the Right Setup

### Scenario A: First-party generative model (`ai_generated`)

You operate the model on your own infrastructure (or on-device in your own app whose output flows through your backend) and want to label newly generated images, video, or audio.

- **What you need:** Standard Managed Signing (Cloud or Local) + accept the *Created Assertion Acknowledgement* in the dashboard + register your AI system with `c2pa_first_party_attestable: true`.
- **What Trufo writes:** A `c2pa.created` action (`trainedAlgorithmicMedia`) naming your AI system as the software agent, plus your `c2pa.ai-disclosure` if configured.
- **Why this works cleanly:** You do not need a Branded Generator Product just to emit strong, interoperable `ai_generated` labels for a model you operate.

### Scenario B: AI editing, inpainting, upscaling, or dubbing (`ai_modified`)

Your product modifies an existing user-uploaded photo, video, or audio track with AI (image-to-image, background replacement, AI voice dubbing, lip-sync).

- **What you need:** A **Branded Generator Product** (`branded_gp_id`, approved via Branded Product Validation) — or your own conformant Generator Product certificate.
- **Why:** Attesting that an asset was modified by AI (`ai_modified`) or linking an original source via `parentOf` + `action_history` is a `created` assertion that C2PA requires a validated generator product to vouch for.
- **Handling user uploads that already have a camera/human manifest:** Under the default `signed_input_policy: "auto"`, Trufo rejects signing a `camera_captured` or `human_created` input with an `ai_system` assertion (regardless of actions) so you do not accidentally overwrite a camera photo's history with a conflicting claim. `signed_input_policy: "keep"` skips that check but only preserves the incoming manifest — it does not declare a new AI source type. To declare an AI edit on a user photo, sign the edited output (without the old manifest) under your `branded_gp_id`, link the original photo as a `parentOf` ingredient, and declare the edit in `action_history` (e.g., `compositeWithTrainedAlgorithmicMedia`). Leave `ai_system` out of that request: it cannot be combined with `parentOf` when `branded_gp_id` is set.

### Scenario C: Wrapping third-party hosted models

Your application calls a third-party model API that you do not operate.

- **Be truthful about first-party status:** Do not set `c2pa_first_party_attestable: true` for a model operated by someone else. Register the AI system with `c2pa_first_party_attestable: false` (which records the output as a declared AI ingredient), or preserve the upstream provider's C2PA manifest if they already sign their outputs.
- If your product adds substantial creative composition or editing on top of third-party AI components and needs to vouch for the combined output, plan for a Branded Generator Product.

---

## 3. Watermarking: `per_ai_system` vs. `per_embed`

C2PA manifests are routinely stripped by social platforms, messaging apps, and image optimizers. Adding a Trufo Pawprint watermark lets provenance survive stripping — and choosing the right allocation mode directly affects both compliance fit and cost:

| Mode | What it embeds | What recovery tells you | Typical compliance fit | Cost profile |
| --- | --- | --- | --- | --- |
| **`per_ai_system`** | One shared ID per registered AI system (and involvement mode) | Which organization and AI system generated or modified the content | **EU AI Act Art. 50(2)** minimal machine-readable AI marking | Lowest: one ID per AI system + per-embed fee only |
| **`per_embed`** (default) | A unique ID per signed file, linked to that file's manifest | The exact C2PA manifest for that specific asset | **California SB 942** / per-asset provenance & audit trails | Higher: 1 new ID + active-ID retention per file (can deactivate old records via `/content/status`) |

**Three practical watermarking habits:**

1. **Always put the `watermark` action last.** If you also `resize`, `crop`, `trim`, or `transcode` in the same call, put `watermark` after those actions so transforms don't weaken the mark (Trufo emits a warning if a media action runs after `watermark`).
2. **Pick the right `effort_policy` for mixed-format pipelines.** A bare `["watermark", {}]` defaults to `"require"` (fails the sign if the format isn't watermarkable, such as PDF or SVG). If your pipeline handles mixed formats and still wants C2PA signing on unsupported formats, use `"require_if_supported"` (or `"best_effort"` if runtime watermark failures should never block delivery) and monitor `TrufoServerWarning` / `warnings`. Note that `"require_if_supported"` only checks the MIME type: a supported container that fails at embed time (e.g., a CMYK or 1-bit JPEG/TIFF) still fails the sign.
3. **Never ship without checking the watermark format rules.** Watermarking supports SDR progressive video (H.264, HEVC, ProRes 422), common 8/16-bit images, and mono/stereo or multichannel lossless audio; HDR video and 1-bit/CMYK images are not watermark-encodable. Check [Media Format Support](../reference/media-formats.md) before turning on `"require"` in production.

---

## 4. Scaling Media & Choosing Deployment Topology

- **Images under 10 MB:** Cloud `REQUEST` mode is simplest and requires zero local setup.
- **Large files (>10 MB), and any audio or video with media actions (`watermark`, `resize`, `crop`, `trim`, `transcode`, `repackage`) in Cloud mode:** Use `ExecutionMode.TASK` (S3 upload → submit → poll → stream download). `REQUEST` mode only handles files up to 10 MB and applies media actions to images only. Note that `TASK` mode runs on production hosts only; use small images on `test.api.trufo.ai` during early integration.
- **High-volume video, strict VPC residency, or non-Python backends (Node.js, Go, .NET):**
  - Run **Local mode via Docker** (`ghcr.io/trufo-ai/trufo-local:2.4` or `2.4-full`) as a sidecar alongside your application container — works from any language over local HTTP and keeps raw media inside your network.
  - If you run Python GPU workers and embed video watermarks at scale, **`trufo[local-full]`** automatically uses an NVIDIA CUDA GPU when present (Docker `2.4-full` is CPU-only, where `WatermarkSettings(profile="fast")` offers ~5× faster CPU video watermarking with a modest durability trade-off).
  - Keep `trufo[local-full]` in its own worker container or virtualenv if your inference workers pin a specific PyTorch/CUDA build.
- **EU data residency:** Send Cloud signing requests to `https://eu.api.trufo.ai`. AI system registrations work across both Global and Europe endpoints automatically.
- **Already running your own C2PA signer?** You can still use Trufo's watermarking via the standalone `/bind/*` routes without handing Trufo the signing step.

---

## 5. Lifecycle Hygiene

- **Version every model cleanly:** AI system registrations are immutable. Register a new AI system when you ship a new major model version, and deactivate retired ones with `/ai-system/status` (`"inactive"`) so old pipeline configs fail loudly instead of stamping stale model names.
- **Use `ai_system`, not `ai_disclosure`:** If you have an older integration using `ai_disclosure` or the watermark `mode` parameter, migrate to `ai_system` and `wid_allocation_mode` well ahead of the January 31, 2027 sunset (see [Deprecations](../reference/deprecations.md)).
- **Combine with organization identity when publishing publicly:** Pairing `ai_system` (what generated it) with `cawg_identity` (who published it) gives downstream validators both AI transparency and verified publisher attribution.

---

## Next Steps

- **Step-by-step code:** [AI Labeling](../topics/ai-labeling.md), [Watermarking and Recovery](../topics/watermarking.md)
- **Keeping media local:** [Local Signing (Python SDK)](../topics/signing-local-python.md), [Local Signing (Docker)](../topics/signing-local-docker.md)
- **Normative schemas:** [Actions and Assertions](../reference/actions-and-assertions.md), [Watermarking and Content API](../reference/watermarking-api.md)
