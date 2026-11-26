# Choosing Your C2PA Path

There are three ways to sign media with Trufo, and two levels of implementation maturity. Most teams overestimate how much infrastructure they need to get started — and underestimate what downstream platforms will expect as C2PA adoption matures through 2027.

This guide helps you pick the right starting point today without painting yourself into a corner for next year.

---

## 1. Basic Today vs. Full Implementation (The 2027 Norm)

A practical way to plan C2PA is in two stages:

### Stage 1: Basic implementation (fast early adoption)

Get valid, trusted Content Credentials onto your outputs in days rather than months:

- **Trufo signs for you** using Trufo's own C2PA certificate (no conformance audit or PKI operations on your side).
- **Minimal, truthful declarations:**
  - If you operate a generative AI model: register your AI system and send an `ai_system` assertion (`ai_generated`), optionally paired with `per_ai_system` watermarking for lightweight EU AI Act disclosure.
  - If you publish brand or editorial content: add `cawg_identity` (`org_interim`) and basic `cawg_metadata` / `cawg_training` assertions.
- **Standard media handling:** keep incoming manifests intact (`signed_input_policy: "auto"`) and run simple format/resize transforms through Trufo's built-in media actions when needed.

**When Stage 1 is enough:** You want compliant AI labels or verified publisher identity live quickly, you are signing outputs directly from your own model or publishing pipeline, and you do not yet need to vouch for complex multi-step external edits under your own product's signing certificate.

### Stage 2: Full implementation (what is becoming the 2027 norm)

As platforms, regulators, and enterprise buyers tighten validation rules, "basic" manifests start hitting real limits:

- **Your own product identity on the signature:** Validators and platforms increasingly distinguish *who* vouched for an edit (`created` assertions vs. `gathered` claims). Declaring AI edits (`ai_modified`), linking original assets (`parentOf`) after external editing tools, or recording `action_history` with `all_actions_included: true` requires either a **Branded Generator Product** (Trufo hosts the signing, your product is validated) or **your own Conformant Generator Product** (your keys, Trufo CA certificates).
- **End-to-end provenance continuity:** Media rarely moves straight from camera or model to web — it passes through Photoshop, Figma, DAMs, and transcoders. Full implementations preserve history across edits (either via built-in media actions or external `parentOf` + `action_history`) and verify manifests automatically in CI.
- **Resilience to stripping:** Social networks and CDNs routinely strip C2PA boxes. Where per-asset provenance recovery matters (for example, California SB 942 or high-value editorial/brand assets), teams pair C2PA manifests with **per-embed watermarking** so provenance survives re-encoding.
- **Automated key hygiene and offline-verifiable trust:** Teams operating their own signer move keys into KMS/HSM, automate certificate renewal before expiry, embed RFC 3161 timestamps, and staple OCSP responses so assets stay verifiable years later.

**Best practice:** Start with Stage 1 to get real signed assets flowing through your pipeline and tested against the platforms that matter to you, while kicking off Organization Validation (and, if needed, Branded Product Validation or C2PA conformance) in parallel.

---

## 2. Three Ways to Sign With Trufo

| Approach | Who signs the manifest? | What you need to set up | Best for |
| --- | --- | --- | --- |
| **Managed Signing** (standard) | Trufo (Trufo's C2PA certificate) | Account + MFA + OV + Signing plan | Fastest path to production; first-party `ai_generated` labeling; CAWG org publishing; media actions & watermarking |
| **Branded Generator Product** (managed signing + BPV) | Trufo (a dedicated certificate in your product's name) | Everything above + Branded Product Validation (BPV) | Declaring `ai_modified`, `parentOf` + `action_history` (after external edits), `created` assertions, and showing your product name as the signer — without running PKI |
| **Your Own Generator Product** (TCA certificates) | You (`c2pa-rs`, `c2patool`, etc. with your own KMS/HSM key) | C2PA Conformance + OV + Product Validation (PV) + Certificate/TSA plan | Camera/device makers, creative desktop/mobile apps, or high-scale backends that already operate `c2pa-rs` and want full custody of signing keys |

**You can graduate cleanly:** Many teams launch on Managed Signing (or Branded Signing) to ship immediately, then transition to their own Generator Product certificate later once their C2PA conformance review completes. The C2PA manifests and assertions you design stay the same.

---

## 3. Cloud Mode vs. Local Mode (for Managed & Branded Signing)

If Trufo signs for you, choose where media bytes are processed:

| Mode | Media bytes sent to Trufo? | Languages / platforms | When to choose it |
| --- | --- | --- | --- |
| **Cloud, direct** (`REQUEST`) | Yes (base64 in JSON, up to 10 MB) | Any language (REST or Python SDK) | Default for images under 10 MB; zero local dependencies |
| **Cloud, via S3** (`TASK`) | Yes (ephemeral presigned upload) | Any language (REST or Python SDK) | Large images (>10 MB), audio, video, or cloud watermarking |
| **Local, Python SDK** (`sign_c2pa_local`) | **No** (stays on your machine) | Python on Linux (`x86_64` / `arm64`) | Media cannot leave your VPC/on-prem, large video files, or GPU-accelerated local watermarking |
| **Local, Docker sidecar** (`trufo-local`) | **No** (stays on your machine) | **Any language** (Node.js, Go, .NET, Java, Rust…) over local HTTP | Non-Python backends or containerized services that want media to stay local |

### Be explicit about data egress in Local mode

Local mode keeps your original media file on your own infrastructure: Trufo's local engine hashes the file and builds the manifest on your machine, and sends only the claim signing request to Trufo.

One detail security reviewers always ask about: **by default, Trufo receives and stores the finished manifest** for debugging and watermark recovery, and by default a C2PA manifest includes a small thumbnail (512 px WebP) plus any embedded assertions (such as prompts in `ingredient.data`). If your privacy policy prohibits thumbnails or manifest copies leaving your infrastructure:

- Set `thumbnail_settings.policy` to `"none"` to suppress generated thumbnails.
- Set `skip_manifest_storage: true` so Trufo does not retain a copy of the finished manifest. *(Note: `skip_manifest_storage` cannot be combined with `per_embed` watermarking, because per-embed recovery returns that stored manifest; it works fine with `per_ai_system` watermarking or signing without watermarks.)*

---

## 4. Production Readiness Checklist

You can build and test against `https://test.api.trufo.ai` on day one with a test API key — no OV or paid plan required. Just keep in mind that test outputs carry Trufo's test certificate (untrusted by public validators) and S3 `TASK` mode runs on production hosts only.

When preparing for production:

1. **Submit Organization Validation (OV) early** — review typically takes 2–5 business days, and the most common delay is completing the verification callback to a publicly listed company phone number.
2. **Choose your region intentionally** — `https://api.trufo.ai` (Global) or `https://eu.api.trufo.ai` (Europe). Your endpoint choice determines where Cloud-mode media is processed; see [Account Management](account-management.md#4-regions-and-data-residency).
3. **Accept required agreements** in [Organization Settings → Agreements](https://app.trufo.ai/settings/org#agreements) before creating keys or registrations:
   - *Trufo Library License* (required for `sdk-download` keys / Local mode).
   - *Created Assertion Acknowledgement* (required for first-party AI systems).
4. **Decide early if you need Branded Product Validation (BPV)** — if your workflow needs `ai_modified`, `parentOf` with `action_history`, or your own product name on the signing cert, start BPV right alongside OV.
5. **Handle warnings, not just errors** — Trufo returns non-fatal notices (skipped watermarks, dropped metadata on transcode, untrusted incoming manifests) in `warnings` (emitted as `TrufoServerWarning` in Python). Log and monitor them in production.

---

## Next Steps

- **AI product or compliance deadline?** Read [AI Labeling for Compliance](ai-labeling-for-compliance.md).
- **Agency, brand, publisher, or DAM pipeline?** Read [Brands and Creative Workflows](brands-and-creative-workflows.md).
- **Running your own `c2pa-rs` / camera / desktop signer?** Read [Build Your Own Generator Product](build-your-own-generator-product.md).
- **Ready to write code?** Go straight to [Setup and Credentials](../topics/setup.md).
