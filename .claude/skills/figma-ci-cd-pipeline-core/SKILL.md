---
name: figma-ci-cd-pipeline-core
description: "Provides complete CI/CD pipeline patterns for Figma design automation — webhook event selection, design diff algorithms, visual regression pixel math, asset export throughput modeling, git-integrated semantic versioning, and pipeline queuing theory. Use when building automated design system pipelines, visual regression testing workflows, token sync automation, or Code Connect publication workflows integrated with GitHub Actions or GitLab CI. Keywords: figma ci cd pipeline, figma webhook github actions, visual regression testing figma, figma design diff automation, figma code connect ci, design token pipeline cicd, figma asset export automation"
allowed-tools: Read,Glob,Grep,Bash,Edit,Write,WebFetch,WebSearch
user-invocable: true
---


<!-- generated-by: claude-global-library/tools/project_sync -->
<!-- source: skills/figma-ci-cd-pipeline-core/SKILL.md -- edit the library, then re-run sync_project.py -->

# figma-ci-cd-pipeline-core

## Description

Complete CI/CD pipeline patterns for Figma design automation. Covers webhook event selection and delivery reliability, Code Connect GitHub Actions integration, visual regression testing (pHash/dHash/Hamming distance), asset export throughput modeling, design token sync pipeline, semantic version bump automation, and M/M/c queuing theory for pipeline capacity planning.

## 1. Webhook Event Selection and Pipeline Trigger Strategy

**Figma Webhooks v2 event types:**
| Event | Trigger | CI Suitability |
|-------|---------|----------------|
| `PING` | Connectivity test on webhook creation | Health check only |
| `FILE_UPDATE` | Every auto-save (multiple times per hour) | Too frequent — avoid for CI |
| `FILE_DELETE` | File removed | Cleanup automation |
| `FILE_VERSION_UPDATE` | Named version published (design handoff trigger) | Recommended for design handoff CI |
| `LIBRARY_PUBLISH` | Shared library components/styles updated | Recommended for token sync CI |
| `FILE_COMMENT` | Comment added | Notification workflows |

**Trigger hierarchy (most reliable → least reliable for CI):**
```
LIBRARY_PUBLISH > FILE_VERSION_UPDATE > FILE_UPDATE
```

**Reasoning:**
- `LIBRARY_PUBLISH`: Only fires when a designer explicitly publishes library changes. Low frequency, high signal.
- `FILE_VERSION_UPDATE`: Only fires when designer saves a named version. Intentional signal.
- `FILE_UPDATE`: Fires on every auto-save — multiple times per hour. Generates pipeline noise.

**Webhook registration:**
```bash
curl -X POST https://api.figma.com/v2/webhooks \
  -H "X-Figma-Token: $FIGMA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "LIBRARY_PUBLISH",
    "team_id": "YOUR_TEAM_ID",
    "endpoint": "https://your-server.com/webhook",
    "passcode": "YOUR_WEBHOOK_SECRET"
  }'
```

**GitHub Actions `repository_dispatch` integration:**
```yaml
# Webhook receiver → triggers GitHub Actions
POST /github/repos/{owner}/{repo}/dispatches
{
  "event_type": "figma-library-updated",
  "client_payload": { "file_key": "...", "timestamp": "..." }
}
```

## 2. Code Connect CI/CD Integration

**Official GitHub Actions workflow (confirmed pattern):**
```yaml
name: Publish Code Connect
on:
  push:
    branches: [main]
permissions:
  contents: read          # restrict GITHUB_TOKEN to minimum required
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npm audit --audit-level=high
      - run: npx figma connect publish --token ${{ secrets.FIGMA_ACCESS_TOKEN }}
```

**End-to-end token + component pipeline:**
```
LIBRARY_PUBLISH webhook
  → GitHub Actions dispatch
  → GET /v1/files/:key/variables/local
  → Token Transformer (Tokens Studio → DTCG format)
  → Style Dictionary v4 transform
  → PR: updated CSS/Android/iOS token files
  → (on PR merge) npx figma connect publish
  → Dev Mode shows true-to-production code snippets
```

**GitLab CI equivalent:**
```yaml
publish-code-connect:
  stage: publish
  only:
    - main
  script:
    - npm ci
    - npx figma connect publish --token $FIGMA_ACCESS_TOKEN
```

**Monorepo (Nx/Turborepo) considerations:**
- Scope Code Connect publication to packages that changed: `nx affected --target=figma-connect-publish`
- Use `--config` flag to point to package-specific Code Connect config file

## 3. Visual Regression Testing

**Three primary tools:**
| Tool | Algorithm | Storybook Integration | PR Gate |
|------|-----------|----------------------|---------|
| Chromatic | pHash-based perceptual diff | Native | ✅ Blocks merge |
| Percy | Screenshot comparison | Via integration | ✅ Blocks merge |
| Applitools Eyes | AI-powered layout diff | Via SDK | ✅ Blocks merge |

**Recommended for React design systems:** Chromatic (native Storybook integration, minimal config).

**Chromatic setup:**
```yaml
# .github/workflows/chromatic.yml
name: Chromatic
on: [push]
permissions:
  contents: read          # restrict GITHUB_TOKEN to minimum required
jobs:
  chromatic:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm audit --audit-level=high
      - run: npx chromatic --project-token=${{ secrets.CHROMATIC_PROJECT_TOKEN }}
```

**Threshold configuration:**
- Pixel diff threshold: 0.1%–1% of pixels changed (minimum 0.1% to avoid anti-aliasing false positives)
- pHash Hamming distance threshold: ≤10 (visually similar); >10 → flag as regression
- Anti-aliasing tolerance: ignore isolated changed pixels with no changed-pixel neighbors

**Figma → Storybook alignment strategy:**
1. Code Connect maps Figma components to production components
2. Storybook stories generated from variant matrix (see figma-codegen-core)
3. Chromatic captures baseline from production components
4. Visual regression detects when Figma design changes cause unexpected code changes

## 4. Asset Export Pipeline and Throughput Modeling

**Figma REST API image export:**
```
GET /v1/images/:key?ids=id1,id2,id3&format=png&scale=2
```
Returns: `{ images: { "id1": "https://cdn.figma.com/...", "id2": "https://..." } }`

**Format selection guide:**
| Format | Use Case |
|--------|----------|
| SVG | Icons, illustrations (vector, resolution-independent) |
| PNG | Complex raster elements (with density scales @1×/@2×/@3×) |
| PDF | Print assets |
| JPG | Photography/photorealistic imagery |

**Batch + concurrent export pattern:**
```typescript
async function exportAssets(fileKey: string, nodeIds: string[], format: string) {
  const BATCH_SIZE = 50;  // nodes per API call
  const CONCURRENT = 3;   // parallel API calls
  
  const batches = chunk(nodeIds, BATCH_SIZE);
  const results: Record<string, string> = {};
  
  for (let i = 0; i < batches.length; i += CONCURRENT) {
    const concurrentBatches = batches.slice(i, i + CONCURRENT);
    const responses = await Promise.all(
      concurrentBatches.map(batch => 
        fetch(`https://api.figma.com/v1/images/${fileKey}?ids=${batch.join(',')}&format=${format}`,
              { headers: { 'X-Figma-Token': process.env.FIGMA_TOKEN ?? '' } })
        .then(r => r.json())
      )
    );
    responses.forEach(r => Object.assign(results, r.images));
    // Rate limit governor: wait between concurrent batches
    await sleep(1000 / RATE_LIMIT_PER_SEC);
  }
  return results;
}
```

**Storage destination pattern:** Figma CDN URLs are temporary (expire after 30 days). Download assets to persistent storage (S3, GCS) immediately after export. CDN cache invalidation on token update: use version-stamped URLs or CloudFront invalidation.

## 5. Design System Token Sync Pipeline

**Complete pipeline stages:**
```
1. LIBRARY_PUBLISH webhook received
2. Verify HMAC-SHA256 signature → reject if invalid (HTTP 401)
3. Deduplicate: check event_id against Redis/DB cache (idempotency)
4. GET /v1/files/:key/variables/local → fetch current variables
5. Compare to previous snapshot (design diff)
6. Token Transformer → convert Figma variables to DTCG format
7. Style Dictionary v4 → generate CSS/Android/iOS/Compose outputs
8. git diff → compute changed files
9. Compute semantic version bump from change magnitude score
10. Create PR with updated token files + change summary
11. Auto-merge if all CI gates pass (visual regression + accessibility contrast check)
```

**Design diff — three change categories:**
```typescript
interface TokenDiff {
  added: string[];      // tokens in new snapshot not in old
  removed: string[];    // tokens in old snapshot not in new
  modified: string[];   // tokens in both with changed values
}

function computeTokenDiff(oldTokens: Record<string, unknown>, newTokens: Record<string, unknown>): TokenDiff {
  const allKeys = new Set([...Object.keys(oldTokens), ...Object.keys(newTokens)]);
  const diff: TokenDiff = { added: [], removed: [], modified: [] };
  for (const key of allKeys) {
    if (!(key in oldTokens)) diff.added.push(key);
    else if (!(key in newTokens)) diff.removed.push(key);
    else if (JSON.stringify(oldTokens[key]) !== JSON.stringify(newTokens[key])) diff.modified.push(key);
  }
  return diff;
}
```

## 6. Pipeline Security and Compliance

**Webhook security hardening checklist:**
- HMAC-SHA256 verification: first operation in webhook receiver before any processing
- HTTPS only: no HTTP webhook endpoints
- Event deduplication: store event ID in Redis/DB; reject duplicate delivery (at-least-once semantics). **TTL: minimum 24 hours** (covers Figma's at-least-once retry window); combine with a ±5-minute timestamp freshness check on the event `created_at` field to prevent replay attacks after cache expiry.
- Secrets in GitHub Secrets: `${{ secrets.FIGMA_ACCESS_TOKEN }}`, `${{ secrets.WEBHOOK_SECRET }}`
- Secret rotation: rotate PAT and webhook passcode on team member offboarding; schedule 90-day rotation (automate via GitHub Actions scheduled workflow — do not rely on calendar reminders).
- OIDC federation preferred over long-lived PAT in GitHub Actions (no stored secret needed). **Trust policy sub claim scope:** restrict the OIDC trust policy to the specific repository and branch using `StringEquals` conditions on `token.actions.githubusercontent.com:sub` — for example: `repo:owner/repo-name:ref:refs/heads/main`. Do not use `repo:owner/*` wildcard patterns as they allow any workflow in the org to assume the role.

**HMAC-SHA256 webhook verification — reference implementation (Node.js/TypeScript):**

```typescript
import { createHmac, timingSafeEqual } from 'node:crypto';
import type { IncomingMessage, ServerResponse } from 'node:http';

/** Verifies Figma webhook X-Figma-Signature-256 header before processing payload. */
function verifyFigmaWebhook(req: IncomingMessage, rawBody: Buffer): boolean {
  const signature = req.headers['x-figma-signature-256'] as string | undefined;
  if (!signature) return false;
  const secret = process.env.FIGMA_WEBHOOK_SECRET ?? '';
  const expected = 'sha256=' + createHmac('sha256', secret).update(rawBody).digest('hex');
  const sigBuffer = Buffer.from(signature);
  const expBuffer = Buffer.from(expected);
  if (sigBuffer.length !== expBuffer.length) return false;
  return timingSafeEqual(sigBuffer, expBuffer);
}

export function webhookHandler(req: IncomingMessage, res: ServerResponse, rawBody: Buffer): void {
  if (!verifyFigmaWebhook(req, rawBody)) {
    res.writeHead(401).end('Unauthorized');
    return;
  }
  const payload = JSON.parse(rawBody.toString('utf8'));
  processWebhookEvent(payload);
  res.writeHead(200).end('OK');
}
```

Note: FIGMA_WEBHOOK_SECRET must be set as a GitHub Actions secret (`${{ secrets.FIGMA_WEBHOOK_SECRET }}`) and passed as an environment variable; never hardcode.

**Supply chain security:**
- `npm audit` on all packages in design system pipeline
- SBOM (Software Bill of Materials) generation: `npm sbom --format cyclonedx` or Syft
- Pin action versions in GitHub Actions: `uses: actions/checkout@v4` (not `@main`)
- Dependabot for automated dependency updates

**Log retention (CERT-In Directions 2022 Direction 6):**
```yaml
# AWS CloudWatch Log Group retention example
Resource: LogRetentionPolicy
Properties:
  LogGroupName: /figma-pipeline/webhook-events
  RetentionInDays: 180  # CERT-In minimum: 180 days
```

**Incident response (CERT-In Directions 2022 Direction 1 — 6-hour reporting SLA):**
Trigger incident report to CERT-In if: webhook HMAC bypass detected, API token theft, unauthorized artifact injection, build system compromise. Pipeline must have alert triggers configured with <6-hour detection-to-report SLA.

## Deep Mathematical Foundations

### M1: Webhook Event Math (Delivery Reliability + Exponential Backoff)

**Webhook delivery semantics:** At-least-once delivery (Figma retries on non-2xx response from receiver endpoint). Idempotency key required on receiver to deduplicate retries.

**Delivery success probability per attempt:**
```
P(delivery within k attempts) = 1 − (1 − p_success)^k
```
Where p_success = probability a single delivery attempt succeeds (e.g., 0.95).
For p_success = 0.95, k=3 attempts: P = 1 − (0.05)^3 = 1 − 0.000125 ≈ 99.99%.

**Exponential backoff with full jitter:**
```
delay_k = min(BASE × 2^k + Uniform(0, BASE), MAX_DELAY)
BASE = 1s, MAX_DELAY = 300s, k = attempt index (0-based)
Expected delay at attempt k: E[delay_k] = min(BASE × 2^k + BASE/2, MAX_DELAY)
```

**Thundering herd analysis:**
- Without jitter: N clients all retry at t = BASE × 2^k → spike of N concurrent requests
- With full jitter: requests uniformly distributed over interval [BASE × 2^k, BASE × 2^(k+1)] → peak concurrency ≈ N × Δt / (BASE × 2^k) per time unit Δt — proportionally reduced

**Expected total wait time (k=5 retries, BASE=1s):**
```
E[T_total] = Σ_{i=0}^{4} E[delay_i] = 1 + 2 + 4 + 8 + 16 + (5 × 0.5) = 31 + 2.5 = 33.5s
```

**Event ordering:** Figma webhooks deliver events in creation order per file. No global ordering across different files. Pipeline must handle out-of-order delivery across file webhooks using event timestamps for reconciliation.

### M2: Design Diff Algorithms (Structural Delta + Edit Distance)

**Token JSON structural diff:**
```
classify(token):
  if key ∈ new_tokens AND key ∉ old_tokens: ADD
  if key ∈ old_tokens AND key ∉ new_tokens: REMOVE
  if key ∈ both AND value_old ≠ value_new: MODIFY
```
Complexity: O(N_tokens) time, O(N_tokens) space.

**Edit distance (Levenshtein) for rename detection:**
```
d(s₁, s₂) = minimum edit operations (insert, delete, substitute) to transform s₁ → s₂
```
Dynamic programming: O(|s₁| × |s₂|) time, O(min(|s₁|, |s₂|)) space (optimized).

**Normalized edit distance:**
```
d_norm = d(s₁, s₂) / max(|s₁|, |s₂|)
```
d_norm < 0.2 → likely rename (not separate ADD + REMOVE events). Pair as rename for cleaner changelog.

**Figma file AST diff:**
Compare two snapshots of `/v1/files/:key` JSON:
- O(N_nodes) for flat property comparison (all nodes at same level)
- O(N_nodes × log N_nodes) for tree-structured comparison using hash-based subtree matching

**Change magnitude scoring:**
```
M = Σ_i w_i × Δ_i
```
| Change Type | Weight w_i |
|-------------|-----------|
| Color token changed | 3 |
| Spacing token changed | 2 |
| Typography token changed | 2 |
| Token renamed | 2 |
| Token added | 1 |
| Token removed (breaking) | 3 |

### M3: Visual Regression Pixel Math (pHash + dHash + Hamming Distance)

**Pixel-wise diff:**
```
diff_pixels = count({(x,y) : |R₁(x,y) − R₂(x,y)| > threshold
                           OR |G₁(x,y) − G₂(x,y)| > threshold
                           OR |B₁(x,y) − B₂(x,y)| > threshold})
```
Failure condition: `diff_pixels / (W × H) > diff_threshold` (e.g., 0.01 = 1% of pixels).

**Perceptual hash (pHash) — full algorithm:**
1. Resize image to 32×32 pixels (bilinear interpolation)
2. Convert to grayscale: `Y = 0.299R + 0.587G + 0.114B` (Rec. 601 luma)
3. Compute 2D DCT of the 32×32 grayscale image
4. Take top-left 8×8 DCT coefficients (low frequencies capture structure, not noise)
5. Compute median of the 64 DCT coefficient values
6. Encode: bit_i = 1 if coeff_i > median, else 0 → 64-bit hash

**Hamming distance:**
```
d_H(h₁, h₂) = popcount(h₁ XOR h₂)
```
Counts number of differing bits. Range: [0, 64].
- d_H ≤ 10: visually similar (Chromatic default threshold)
- d_H > 10: visual regression detected

**dHash (difference hash — simpler, faster):**
1. Resize to 9×8 pixels
2. Compute horizontal gradient: for each row, compare adjacent pixels
3. Encode gradient sign as 64 bits (9−1=8 comparisons per row × 8 rows)
4. dHash: slightly less robust to scaling than pHash but 5–10× faster to compute

**Anti-aliasing noise filtering:**
Before counting diff pixels, apply morphological erosion: ignore isolated changed pixels with zero changed-pixel neighbors. Eliminates single-pixel anti-aliasing artifacts from font rendering differences.

**Perceptual comparison color space:** Compare images in YCbCr or CIELAB rather than RGB. Human eye is 10× more sensitive to luminance (Y/L) than to chroma (Cb/Cr or a/b). Weighting luminance differences more heavily reduces false negatives on color tone changes.

### M4: Asset Export Pipeline Math (Concurrent Throughput + Size Estimation)

**Concurrent export throughput:**
```
T_throughput = p_concurrent / avg_response_time
p_concurrent = min(rate_limit_per_sec, max_TCP_connections)
```
At rate limit 1 req/sec and avg_response_time = 0.8s: T_throughput ≈ 1.25 assets/sec.

**PNG size estimation:**
```
S_PNG ≈ W × H × bytes_per_pixel × (1 − compression_ratio)
```
For UI screenshots: compression_ratio ≈ 0.70–0.85 (repetitive solid fills compress well).
@2× export: 4× pixel area → ≈4× PNG file size.
Typical: 1440×900 @2× UI screenshot ≈ 200–400KB compressed PNG.

**SVG size estimation:** O(N_paths × avg_path_complexity). Simple icon (≤10 paths): 0.5–2KB. Complex illustration (>100 paths): 10–100KB. SVG size independent of display resolution.

**Export schedule optimization:**
```
total_time = Σ_format ceil(n_format / p_format) × RTT
```
Minimize by maximizing p_format per format type. Schedule PNG and SVG exports in parallel if they use separate rate-limit pools (unconfirmed whether Figma API image export shares rate limit with file API — [UNVERIFIED]).

**Storage cost model:**
```
total_storage = Σ_format Σ_density S_format_density × n_assets
```
For 500 icons at 1×/2×/3× PNG + SVG:
`total = 500 × (3 × avg_PNG_size + avg_SVG_size) ≈ 500 × (3 × 15KB + 2KB) ≈ 23.5MB`

### M5: Git Diff Integration Math (Semantic Version Bump)

**Change magnitude score:**
```
M = Σ_i w_i × Δ_i
```
(Same weights as M2 structural delta.)

**Semantic version bump rules:**
```
M ≥ threshold_major (default 10): MAJOR bump    → breaking changes (removed/renamed tokens)
threshold_minor ≤ M < threshold_major (default 3): MINOR bump  → new tokens added
M < threshold_minor: PATCH bump                 → value adjustments only
```

**Git diff extraction:**
```bash
git diff --unified=0 HEAD~1 HEAD -- tokens/**/*.json \
  | grep '^[+-]' \
  | grep -v '^[+-][+-][+-]'
```
Parse DTCG structure from diff lines: O(N_changed_tokens) parsing complexity.

**Automated PR title generation:**
```
{MAJOR|minor|patch}(tokens): {N} tokens changed ({added} added, {modified} modified, {removed} removed)
```

**Git tag + npm publish:**
```yaml
- name: Create Release
  if: steps.version_bump.outputs.bump_type != 'none'
  run: |
    npm version ${{ steps.version_bump.outputs.bump_type }} --no-git-tag-version
    git tag "v$(node -p "require('./package.json').version")"
    git push --tags
    npm publish
```

### M6: Pipeline Throughput Analysis (M/M/c Queuing Theory)

**M/M/c queue model:**
- λ = Poisson arrival rate (webhook events/second)
- μ = service rate per worker (events processed/second per worker)
- c = number of parallel workers

**Traffic intensity (utilization):**
```
ρ = λ / (c × μ)
```
Stable queue requires ρ < 1. If ρ ≥ 1: queue grows unboundedly.

**Erlang C formula (probability all c workers are busy):**
```
C(c, ρ) = [(c×ρ)^c / (c! × (1 − ρ))] / [Σ_{k=0}^{c-1} (c×ρ)^k / k! + (c×ρ)^c / (c! × (1 − ρ))]
```

**Average queue wait time:**
```
W_q = C(c, ρ) / (c × μ × (1 − ρ))
```

**Total pipeline latency:**
```
W = W_q + 1/μ
```

**Rate limit utilization bound:**
```
c × μ ≤ r_max / 60    [where r_max = rate limit in req/min]
c = floor(r_max / (60 × μ_single_worker))
```

**Optimal worker count:**
```
c* = ceil(λ / (μ × (1 − ρ_target)))
ρ_target = 0.70–0.80 (balance responsiveness vs cost)
```

**Worked example:** λ=0.1 events/sec, μ=0.5 events/sec per worker, target ρ=0.75:
```
c* = ceil(0.1 / (0.5 × 0.25)) = ceil(0.8) = 1 worker
ρ = 0.1 / (1 × 0.5) = 0.20 (well below target)
```
At λ=0.5 events/sec (design sprint): c* = ceil(0.5 / 0.125) = 4 workers.

## Anti-Patterns to Avoid

- **Triggering CI on `FILE_UPDATE` instead of `LIBRARY_PUBLISH`/`FILE_VERSION_UPDATE`**: §1's trigger hierarchy exists because `FILE_UPDATE` fires on every auto-save, multiple times per hour — wiring a token-sync or Code Connect pipeline to this event floods CI with noise runs on unintentional saves rather than the deliberate publish signal `LIBRARY_PUBLISH` provides.
- **Retrying failed webhook deliveries without jitter**: M1's thundering-herd analysis shows that without jitter, N clients all retry at the same `t = BASE × 2^k`, producing a synchronized spike of N concurrent requests — using plain exponential backoff (no `Uniform(0, BASE)` term) on a receiver endpoint under load risks the retry storm itself causing further failures, which is exactly the failure mode full jitter is designed to spread out.
- **Deduplicating webhook events with a short or missing TTL**: §6's security checklist specifies a minimum 24-hour dedup TTL to cover Figma's at-least-once retry window — a shorter cache TTL (or none at all) lets a legitimate late retry be reprocessed as a "new" event, silently double-triggering token syncs or Code Connect publishes.
- **Comparing images in RGB instead of a luma-weighted color space for visual regression**: M3 notes the human eye is roughly 10× more sensitive to luminance than chroma — diffing in raw RGB (rather than YCbCr/CIELAB) under- or over-weights color-only changes relative to structural changes, producing both false positives (color-only variance flagged as a big diff) and false negatives (a real structural shift buried under low RGB pixel-value change).
- **Setting the pHash Hamming distance threshold without accounting for anti-aliasing noise**: §3's threshold guidance (`d_H ≤ 10`) and the morphological-erosion step in M3 for isolated single-pixel changes exist together — applying a strict Hamming cutoff without first filtering anti-aliasing artifacts produces spurious visual-regression failures on font-rendering-only differences that never actually changed layout or content.
- **Treating the change-magnitude weights (M2/M5) as a precise semantic-versioning oracle**: `M = Σ w_i × Δ_i` with weights like color=3, spacing=2, token-removed=3 is a heuristic scoring function calibrated to a specific design system's own risk tolerance — reusing the default `threshold_major=10` / `threshold_minor=3` cutoffs on a design system with very different token volume or change patterns can systematically over- or under-trigger MAJOR bumps.
- **Sizing worker/concurrency count from average load instead of the target utilization formula**: M6's `c* = ceil(λ / (μ × (1 − ρ_target)))` explicitly reserves headroom via `ρ_target` (0.70–0.80) — provisioning workers to match only the average arrival rate λ (i.e., implicitly `ρ_target≈1.0`) ignores the Erlang-C queue-wait blowup as ρ approaches 1, producing a pipeline that looks fine under steady load but backs up sharply during a design-sprint burst.
- **Using a wildcard OIDC trust policy (`repo:owner/*`) for CI credential federation**: §6 explicitly calls this out as allowing any workflow in the org to assume the deployment role — scoping only to `repo:owner/repo-name:ref:refs/heads/main` is not an optional hardening step but the difference between a compromised unrelated repo's workflow being unable versus able to publish tokens or Code Connect mappings under this pipeline's identity.

## India-Specific Layer

**CERT-In Directions 2022 (Direction 1 — Incident Reporting):**
CI/CD pipeline security incidents must be reported to CERT-In within 6 hours of detection. Incidents include: webhook HMAC bypass, unauthorized artifact injection, build system compromise, API token theft. Pipeline operators in India must have an incident response playbook meeting the 6-hour SLA. Incident categories from Direction 1: attack on critical information infrastructure, data breaches, identity theft, unauthorized access.

**CERT-In Directions 2022 (Direction 6 — Log Retention):**
All pipeline logs (webhook delivery logs, build logs, artifact logs, API call logs, access logs) must be retained for minimum 180 days. Log storage infrastructure must be provisioned with sufficient capacity. Log rotation policy must not purge logs before the 180-day mark. Log format must enable forensic reconstruction of the incident timeline.

**CERT-In DevSecOps / Supply Chain Advisory (2023):**
Design system pipelines consuming npm packages and Figma plugins must implement dependency scanning (npm audit, Snyk, or equivalent). SBOM generation required for regulated sector deployments. Webhook HMAC verification is a mandatory supply chain security control. Pipeline must scan for malicious code in transitive dependencies. [Exact advisory/direction number: CONFIDENCE: MED — exact reference pending synthesis agent Search 2 confirmation.]

**DPDP Act 2023 §4 (Lawful Processing):**
If the CI/CD pipeline processes design files containing PII (user photos in prototypes, personal data in UI designs), automated processing requires a lawful basis under §4. Pipeline access logs, webhook delivery logs, and artifact metadata constitute processing records and are subject to DPDP obligations.

## Response Rules

- Always use LIBRARY_PUBLISH (for library sync) or FILE_VERSION_UPDATE (for design handoff) as the primary CI/CD webhook trigger. Never use FILE_UPDATE — it fires too frequently and generates excessive pipeline noise.
- Always implement HMAC-SHA256 webhook signature verification as the first operation in the webhook receiver handler before any processing. Reject unsigned or invalid payloads immediately with HTTP 401.
- Always configure pipeline worker count to keep Figma API rate utilization below 80% (ρ ≤ 0.80) to maintain responsive pipeline queue and avoid 429 rate-limit responses.
- Always implement idempotent pipeline handlers — webhook events may be delivered multiple times (at-least-once delivery). Use event ID + timestamp deduplication to prevent duplicate token PRs or duplicate Code Connect publications.
- Always retain pipeline logs for 180 days minimum to comply with CERT-In Directions 2022 Direction 6. Configure log retention policy before pipeline goes to production.

## What Not to Do

- Do not trigger CI/CD pipelines on FILE_UPDATE events — this event fires on every auto-save (potentially many times per hour). This floods the pipeline with redundant runs. Use FILE_VERSION_UPDATE or LIBRARY_PUBLISH.
- Do not skip HMAC signature verification in development or staging environments — an unverified webhook endpoint is a persistent security vulnerability even if not publicly accessible. Replay attacks use captured production payloads.
- Do not set visual regression pixel diff threshold to 0% — font rendering, anti-aliasing, and subpixel differences produce pixel-level noise that creates constant false positives at 0% threshold. Minimum: 0.1%.
- Do not run parallel asset exports without a rate-limit governor — unbounded concurrent requests exhaust the Figma API rate limit and cause pipeline failures for all users sharing the token.
- Do not hardcode Figma API tokens or webhook secrets in GitHub Actions workflow YAML files — always use GitHub Secrets (`${{ secrets.FIGMA_ACCESS_TOKEN }}`). Tokens committed to git history are permanently exposed even after removal.

## Output Expectations

Responses provide:
- GitHub Actions YAML for Code Connect publication and token sync pipelines
- Webhook receiver implementation with HMAC-SHA256 verification and idempotency deduplication
- Visual regression CI configuration for Chromatic, Percy, and Applitools Eyes
- Asset export pipeline with concurrent scheduling and rate-limit governor
- Token diff computation with semantic version bump calculation
- M/M/c queuing analysis for pipeline capacity planning with Erlang C formula
- M1–M6 full mathematical derivations with all formulas and proofs
- CERT-In Directions 2022 compliance checklist (incident reporting + log retention)

## Skill Scope

**In scope:** Webhook event selection (LIBRARY_PUBLISH, FILE_VERSION_UPDATE), Code Connect GitHub Actions integration, visual regression testing (Chromatic/Percy/Applitools, pHash/dHash math), asset export pipeline throughput modeling, design token sync pipeline, semantic version bump automation, pipeline security (HMAC, SBOM, dependency scanning, CERT-In compliance), M/M/c pipeline queuing theory.

**Out of scope:** REST API authentication and rate limiting algorithms (see figma-rest-api-core), design token schema and DTCG transformation (see design-tokens-automation-core), code generation algorithms (see figma-codegen-core), plugin/widget development (see figma-plugin-widget-core), AI-powered automation quality scoring (see figma-ai-automation-core), multi-platform token output (see figma-multiplatform-tokens-core).

## Version: 1.1 — Added Anti-Patterns to Avoid section (FILE_UPDATE trigger noise, jitter-less retry storms, dedup TTL, RGB vs luma-weighted visual diff, anti-aliasing-blind Hamming thresholds, change-magnitude weight overgeneralization, utilization-blind worker sizing, wildcard OIDC trust policy)
