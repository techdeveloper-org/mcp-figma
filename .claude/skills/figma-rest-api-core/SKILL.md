---
name: figma-rest-api-core
description: "Provides complete implementation patterns for Figma REST API v1, including OAuth2 PKCE authentication, rate-limit-aware request management, cursor-based pagination, HMAC-SHA256 webhook verification, ETag caching, and batch variable mutations. Use when building integrations that read file data, write variables, export assets, respond to webhooks, or authenticate users against the Figma platform. Keywords: figma api integration, figma authentication oauth, figma webhook verification, figma rate limiting, figma variables api, figma token management, figma asset export automation"
allowed-tools: Read,Glob,Grep,WebFetch,WebSearch
user-invocable: true
---


<!-- generated-by: claude-global-library/tools/project_sync -->
<!-- source: skills/figma-rest-api-core/SKILL.md -- edit the library, then re-run sync_project.py -->

# figma-rest-api-core

## Description

Complete implementation patterns for the Figma REST API v1 — OAuth2 PKCE authentication, rate-limit-aware request management, cursor-based pagination, HMAC-SHA256 webhook verification, ETag-based caching, and batch variable mutations. Covers all Figma API capabilities from file reading to programmatic design token writes.

## 1. REST API v1 Overview and Endpoint Taxonomy

All requests target `https://api.figma.com/v1/`. Endpoints split into read-only and write categories:

**Read endpoints (GET):**
- `/files/:key` — full file document tree (JSON)
- `/files/:key/nodes?ids=id1,id2` — specific nodes
- `/images/:key?ids=id1,id2&format=png|svg|jpg|pdf&scale=N` — rendered exports
- `/files/:key/image_fills` — image fill URLs
- `/files/:key/comments` — comment list
- `/files/:key/versions` — version history (paginated, creation-time order as of November 2024)
- `/teams/:id/projects` — team projects
- `/teams/:id/components`, `/teams/:id/component_sets` — library components (page_size max 1,000)
- `/teams/:id/styles` — library styles
- `/files/:key/variables/local` — locally defined variables
- `/files/:key/variables/published` — published library variables
- `/me` — current user

**Write endpoints (POST/DELETE):**
- `POST /files/:key/variables` — batch variable mutations (collections, modes, variables, values)
- `POST /files/:key/comments` — add comment
- `DELETE /files/:key/comments/:id` — delete comment
- `POST /webhooks` — register webhook
- `DELETE /webhooks/:id` — delete webhook

**Authentication headers:**
- OAuth2 bearer token: `Authorization: Bearer {access_token}`
- Personal Access Token: `X-Figma-Token: {personal_access_token}`

**Rate limit regime:** Updated November 17 2025. Rate limit response headers include `X-Figma-Rate-Limit-Type`. HTTP 429 responses include `Retry-After` header (may be multi-day for severe violations on low-tier plans). Apps created before September 23 2025 required re-publication by November 17 2025.

## 2. OAuth2 PKCE Flow and Personal Access Tokens

**Two authentication paths:**

**OAuth2 Authorization Code + PKCE (RFC 7636) — for user-delegated access:**
1. Generate `code_verifier`: 43–128 characters, alphabet [A-Za-z0-9-._~]
2. Derive `code_challenge`: `BASE64URL(SHA-256(ASCII(code_verifier)))`
3. Authorization request: `GET https://www.figma.com/oauth?client_id=...&redirect_uri=...&scope=...&state=CSRF_TOKEN&response_type=code&code_challenge=...&code_challenge_method=S256`
4. Receive `authorization_code` at redirect URI; verify `state` matches CSRF token
5. Token exchange: `POST https://www.figma.com/api/oauth/token` with `code`, `code_verifier`, `client_id`, `redirect_uri`
6. Receive `access_token`, `refresh_token`, `expires_in`
7. Refresh: `POST https://www.figma.com/api/oauth/token` with `grant_type=refresh_token`

**OAuth2 state parameter implementation (CSRF protection):**
- Generate `state` using a CSPRNG: `crypto.randomBytes(32).toString('hex')` in Node.js or `secrets.token_hex(32)` in Python — minimum 128 bits of entropy.
- Store in server-side session (HttpOnly, Secure cookie) — never in localStorage or URL parameters.
- On redirect callback, compare the received `state` against the stored value using timing-safe comparison before accepting the `code`.
- Register only exact-match redirect URIs at the Figma OAuth app settings (no wildcards, no open redirects, HTTPS mandatory).

**Personal Access Token (PAT) — for server/CLI tools:**
- Scoped to the generating user's permissions
- Never embed in client-side browser code
- Set via: `X-Figma-Token: {pat_value}`
- Generated at figma.com → Settings → Personal Access Tokens

**2025 OAuth scope model update:** The OAuth scope model was updated in 2025. Apps must be re-published if created before September 23 2025. Review current scope list at developers.figma.com.

## 3. Pagination and Cursor Management

Figma uses opaque cursor-based pagination for collections that can exceed a single response.

**Breaking change November 22 2024:** The `/files/:key/versions` endpoint changed cursor ordering to explicit creation-time ordering. Cursor values from before this date became invalid. Any integration relying on cursor value structure must be updated.

**Cursor usage pattern:**
```javascript
async function* paginateVersions(fileKey, token) {
  let url = `https://api.figma.com/v1/files/${fileKey}/versions`;
  while (url) {
    const resp = await fetch(url, { headers: { 'X-Figma-Token': token } });
    const data = await resp.json();
    yield* data.versions;
    // cursor fields are opaque URLs — never parse internals
    url = data.pagination?.next_page ?? null;
  }
}
```

**Cursor opacity rule:** Treat cursors as opaque strings. Never parse, reconstruct, or manually build cursor values. Format may change without notice (as demonstrated November 2024). If a cursor expires (HTTP 400/404 on cursor page), restart from page 1.

**Page size:** `GET /teams/:id/components?page_size=1000` — maximum page_size is 1000 (increased 2024).

**Pagination cost comparison:**
- Cursor-based: O(log(k×p)) — B-tree seek to cursor position; independent of page number
- Offset-based: O(k×p) — must scan k pages × p items; Figma does not support offset pagination

## 4. Variables API — Collections, Modes, and Batch Mutations

**Read endpoints:**
```
GET /v1/files/:key/variables/local    — locally defined variables and collections
GET /v1/files/:key/variables/published — library-published variables
```

**Batch mutation endpoint:**
```
POST /v1/files/:key/variables
Content-Type: application/json
Body size: ≤ 4MB
```

**Processing order within a single POST body (atomic):**
1. `variableCollections` — create/update/delete collections first
2. `variableModes` — create/update/delete modes (reference collections by tempId)
3. `variables` — create/update/delete variables (reference collections by tempId)
4. `variableModeValues` — set variable values per mode (reference variables and modes by tempId)

**Temporary ID mechanism:** Use `"tempId:xyz"` as the `id` field for CREATE actions. Within the same request body, all references to `"tempId:xyz"` resolve to the server-assigned real ID after creation. Temporary IDs are injective (one-to-one mapping to real IDs) within a request.

**Complete POST body example:**
```json
{
  "variableCollections": [
    {
      "action": "CREATE",
      "id": "tempId:collection1",
      "name": "Token System",
      "initialModeId": "tempId:mode_light"
    }
  ],
  "variableModes": [
    {
      "action": "CREATE",
      "id": "tempId:mode_light",
      "name": "Light",
      "variableCollectionId": "tempId:collection1"
    },
    {
      "action": "CREATE",
      "id": "tempId:mode_dark",
      "name": "Dark",
      "variableCollectionId": "tempId:collection1"
    }
  ],
  "variables": [
    {
      "action": "CREATE",
      "id": "tempId:var_primary",
      "name": "primary/color",
      "variableCollectionId": "tempId:collection1",
      "resolvedType": "COLOR",
      "scopes": ["ALL_FILLS"],
      "codeSyntax": {}
    }
  ],
  "variableModeValues": [
    {
      "variableId": "tempId:var_primary",
      "modeId": "tempId:mode_light",
      "value": { "r": 0.2, "g": 0.4, "b": 1.0, "a": 1.0 }
    },
    {
      "variableId": "tempId:var_primary",
      "modeId": "tempId:mode_dark",
      "value": { "r": 0.4, "g": 0.6, "b": 1.0, "a": 1.0 }
    }
  ]
}
```

**⚠️ Bulk DELETE safety boundary:** A single POST body can atomically DELETE an entire variable collection, all its modes, and all its variables in one irreversible operation. The 4MB body limit means thousands of DELETE actions can be sent in one call. Observe these mandatory constraints:
- Apply `"action": "DELETE"` only to individual variables — never batch-DELETE an entire collection in a single automated pipeline run without a human-approved PR gate.
- Bin-packing optimization (M6 FFD algorithm) applies only to CREATE and UPDATE actions. DELETE payloads must be single-item batches confirmed via dry-run first.
- Recovery path for accidental bulk DELETE: Figma version history (File menu → Show Version History) restores prior states; document this in your runbook.
- Require PR approval (not auto-merge) for any pipeline job that issues DELETE mutations to the Variables API.

**Variables API write attribution — structured log pattern:**
Every POST to `/v1/files/:key/variables` must emit a structured log record for audit trail compliance (CERT-In Direction 6: 180-day retention):
```json
{
  "event": "figma_variables_mutation",
  "timestamp": "<ISO-8601>",
  "actor": "<PAT-owner or OAuth-user-id>",
  "file_key": "<file_key>",
  "actions_summary": { "create": 0, "update": 0, "delete": 0 },
  "correlation_id": "<pipeline-run-id>",
  "http_status": 200
}
```
Log immediately after the API response is received. For DELETE actions, log the names of all deleted variables before issuing the request (post-delete, the names are no longer retrievable from the API).

**Variable types:** `BOOLEAN`, `COLOR`, `FLOAT`, `STRING`

**Variable scopes (2024–2025 additions):** Typography scopes added: `FONT_FAMILY`, `FONT_STYLE`, `FONT_WEIGHT`, `FONT_SIZE`, `LINE_HEIGHT`, `LETTER_SPACING`, `PARAGRAPH_SPACING`, `PARAGRAPH_INDENT`. Also: `ALL_FILLS`, `STROKE_COLOR`, `EFFECT_COLOR`, `EFFECT_FLOAT`, `OPACITY`, `WIDTH_HEIGHT`, `GAP`, `CORNER_RADIUS`.

## 5. Webhook Integration and Security

**Webhooks v2 event types:**
| Event | Description | Best Use |
|-------|-------------|----------|
| `PING` | Connectivity test | Validate webhook registration |
| `FILE_UPDATE` | File saved (fires on every auto-save) | Avoid for CI — too frequent |
| `FILE_DELETE` | File removed | Cleanup automation |
| `FILE_VERSION_UPDATE` | Named version published | Design handoff CI trigger |
| `LIBRARY_PUBLISH` | Library components/styles updated | Design system token sync trigger |
| `FILE_COMMENT` | Comment added | Notification workflows |

**Trigger hierarchy for CI/CD:** LIBRARY_PUBLISH > FILE_VERSION_UPDATE > FILE_UPDATE

**Webhook delivery:** HTTPS POST to configured endpoint. At-least-once delivery semantics — implement idempotent handlers using event ID + timestamp deduplication.

**Signature verification:** Figma sends an HMAC-SHA256 signature in the request headers (header name: verify against current Figma webhook documentation [UNVERIFIED — `X-Figma-Signature` vs `figma-signature`]). Compute `HMAC(webhook_passcode, raw_request_body_bytes)` and compare using timing-safe equality.

**Webhook registration:**
```
POST https://api.figma.com/v2/webhooks
{
  "event_type": "LIBRARY_PUBLISH",
  "team_id": "...",
  "endpoint": "https://your-server.com/webhook",
  "passcode": "your-secret"
}
```

## 6. Caching Strategy and Image Export Batching

**ETag-based conditional GET:**
```http
# First request
GET /v1/files/:key
→ Response: ETag: "abc123", body: full JSON

# Subsequent request
GET /v1/files/:key
If-None-Match: "abc123"
→ Response: 304 Not Modified (body: empty, ~200 bytes)
OR
→ Response: 200 OK, new ETag: "xyz789", body: updated JSON
```

**Batched image export:**
```
GET /v1/images/:key?ids=id1,id2,id3&format=png&scale=2
```
Returns `{ images: { "id1": "https://...", "id2": "https://..." } }` — all nodes in one API call.

**Export format parameters:**
- `format`: `png`, `svg`, `jpg`, `pdf`
- `scale`: `0.01` to `4` (multiplier; 2 = @2×)
- `svg_include_id`: include node IDs in SVG attributes
- `use_absolute_bounds`: export at absolute position

**Cache-Control recommendations:**
- Figma file data (frequently updated): `max-age=0, must-revalidate`
- Metadata (component list, team projects): `max-age=300, stale-while-revalidate=60`
- OAuth access tokens: `no-store` in any cache

## Deep Mathematical Foundations

### M1: OAuth2 PKCE Math (RFC 7636)

**code_verifier entropy derivation:**
- Alphabet size: 66 characters [A-Za-z0-9-._~]
- Entropy per character: log₂(66) ≈ 6.044 bits
- Minimum length N = 43 characters: entropy = 43 × 6.044 ≈ 259.9 bits ≥ 256 bits (RFC minimum — satisfied)
- Recommended generation: 32 random bytes → base64url-encode → 43-character verifier (256 bits, no alphabet waste from the 66-char encoding)

**code_challenge derivation (S256 method):**
- Step 1: SHA-256(ASCII(code_verifier)) → 32-byte digest
- Step 2: BASE64URL(digest) → 43-character string
- BASE64URL encoding: standard base64 with character substitutions '+' → '-', '/' → '_', trailing '=' stripped
- Output length: ⌈32 × 4/3⌉ = 43 characters after padding removal

**Security proof (pre-image resistance):**
An intercepted authorization_code without code_verifier provides zero information about the verifier. An attacker would need to invert SHA-256, which has 2²⁵⁶ brute-force bound — computationally infeasible. The code_challenge stored at the authorization server reveals only SHA-256(verifier), not the verifier itself.

**Token exchange verification:**
```
Client: POST code + code_verifier
Server: re-derives challenge = BASE64URL(SHA-256(code_verifier))
Server: constant-time compare(challenge, stored_code_challenge)
```
Constant-time comparison prevents timing side-channel attacks on the comparison.

### M2: Rate Limiting Algorithms (Token Bucket + Sliding Window)

**Token Bucket algorithm:**
- State: (t, T_last) where t = current tokens, T_last = last refill timestamp
- Refill: t_new = min(b, t_old + r × (T_now − T_last)); b = burst capacity, r = refill rate (tokens/sec)
- Request: if t ≥ 1: t -= 1, allow request; else: reject → HTTP 429

**Exponential backoff with jitter (full jitter variant):**
- delay_k = min(BASE × 2^k + Uniform(0, BASE), MAX_DELAY)
- BASE = 1s (initial), MAX_DELAY = 300s; k = attempt number (0-indexed)
- Expected delay at attempt k: E[delay_k] = min(BASE × 2^k + BASE/2, MAX_DELAY)

**Thundering herd prevention analysis:**
Without jitter: N clients all retry at t = BASE × 2^k → N concurrent requests spike
With full jitter: requests uniformly distributed over [BASE × 2^k, BASE × 2^(k+1)] → peak concurrency ≈ N / (BASE × 2^k) × Δt — proportionally reduced

**Sliding Window Counter (O(1) approximation):**
```
C_eff = C_prev × (W − elapsed) / W + C_curr
```
Where C_prev = count in previous window, C_curr = count in current window, elapsed = time since window start, W = window size. Error bound ≤ 1% at window boundary.

**Sliding Window Log (exact, O(N) space):**
Maintain sorted list of request timestamps. Before each request: prune timestamps older than window W. Count remaining: if count < limit, allow request and append timestamp.

**Figma-specific:** Per-token limits (not per-IP). X-Figma-Rate-Limit-Type header on 429. Retry-After may be multi-day for severe violations. Exact req/min thresholds: [UNVERIFIED — not publicly documented; use Retry-After value as authoritative governor; do not assume 60/min].

### M3: Cursor Pagination Math

**Complexity comparison:**
- Offset pagination: O(k × p) — database must scan k pages × p items to reach page k; performance degrades linearly with page number
- Cursor pagination: O(log(k × p)) — B-tree index seek directly to cursor position; performance independent of page number
- Crossover: cursor superior for all k ≥ 2, any page size p ≥ 2 (log(k×p) < k×p for k ≥ 2, p ≥ 2)

**Optimal page size derivation:**
```
p* = √(2 × C_call / C_item)
```
Where C_call = per-API-call overhead cost, C_item = per-item memory/processing cost. Minimizes total cost = (N/p) × C_call + N × C_item.

**Cursor opacity theorem:** The cursor value is an opaque server-defined string. Its internal format may encode position, sort key, timestamp, or any combination. Clients must not parse, decode, or reconstruct cursor values. Post-November 2024: Figma `/versions` cursors encode creation-time ordering (previously undefined).

**Hyperloglog cardinality estimation (when total count unavailable):**
```
N_est = sample_count / sample_rate
```
Alternatively, accumulate count during full traversal. Figma API does not guarantee `total_count` in all paginated responses.

### M4: HMAC-SHA256 Webhook Signature (RFC 2104)

**Full HMAC construction:**
```
HMAC(K, M) = SHA-256((K XOR opad) ‖ SHA-256((K XOR ipad) ‖ M))
```
Where:
- ipad = 0x36 repeated 64 times (512 bits)
- opad = 0x5C repeated 64 times (512 bits)
- Block size B = 64 bytes (SHA-256 block)
- Output length L = 32 bytes (256 bits)

**Key normalization:**
- If |K| > 64 bytes: K = SHA-256(K) (hash to block size)
- If |K| < 64 bytes: K = K ‖ 0x00...0x00 (zero-pad to 64 bytes)

**Inner hash:**
```
K_ipad = K XOR ipad
inner_hash = SHA-256(K_ipad ‖ raw_body_bytes)
```

**Outer hash:**
```
K_opad = K XOR opad
HMAC = SHA-256(K_opad ‖ inner_hash)  → hex-encode → 64-character string
```

**Timing-safe comparison (mandatory):**
- Naïve string comparison (`===`) exits on first mismatch → reveals position-of-first-mismatch via response time
- Information leaked: O(log₂(position)) bits per comparison
- Timing-safe comparison runs in O(L) constant time regardless of mismatch position → 0 bits leaked
- Implementation: `hmac.compare_digest()` in Python; `crypto.timingSafeEqual()` in Node.js

**Verification implementation:**
```python
import hmac, hashlib
def verify_figma_webhook(secret: str, raw_body: bytes, received_sig: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)
```

### M5: HTTP Caching Math (ETag + Conditional GET)

**Bandwidth model per polling cycle:**
```
E[B] = p × B_headers + (1 − p) × B_full
```
Where p = P(resource unchanged since last poll), B_headers ≈ 200 bytes (304 response), B_full = full response body size.

**Bandwidth reduction factor:**
```
savings = p × (B_full − B_headers) / B_full ≈ p (for large B_full)
```
At p = 0.90, B_full = 50KB: E[B] ≈ 0.90 × 200 + 0.10 × 50,000 = 5,180 bytes (89.6% reduction vs no-cache).

**Optimal polling interval derivation:**
Minimize total cost rate = (1/T) × C_call + (f/T) × B_full × B_rate_cost, where f = fraction of polls that produce changed content.
```
dCost/dT = 0 → T* = √(2 × C_call / (f × B_rate_cost))
```
Higher change frequency f → shorter optimal interval T* (poll more frequently when content changes often).

**Strong vs weak ETags:**
- Strong ETag (e.g., `"abc123"`): byte-for-byte identical content comparison
- Weak ETag (e.g., `W/"abc123"`): semantically equivalent content; may differ in whitespace/ordering

### M6: Batch Request Optimization (Bin-Packing)

**Variables POST batching:**
All collections → modes → variables → modeValues processed atomically in a single 4MB request.
Body size limit: 4MB = 4,194,304 bytes.

**Bin-packing formulation:**
- Items: operation payloads (size s_i bytes each)
- Bin capacity: C = 4,194,304 bytes
- Objective: minimize number of bins (API calls) subject to Σ_i s_i ≤ C per bin

**First-Fit Decreasing (FFD) approximation:**
1. Sort operations by s_i descending
2. Greedily assign each operation to first bin with remaining capacity ≥ s_i
3. FFD gives ≤ (11/9) × OPT + 6/9 extra bins

**Dependency constraint:** Ordering must follow `collections → modes → variables → modeValues` within each bin. FFD must respect topological dependency order before packing.

**Pareto frontier (latency vs cost):**
- k batches → pipeline latency = k × RTT; cost ∝ k
- Minimize α × k × RTT + β × k; solved by maximizing batch size subject to total_size(batch) ≤ 4MB
- Optimal: one batch per atomic set of interdependent mutations

**Image export batching throughput:**
```
T_throughput = p_concurrent / avg_response_time
p_concurrent = min(rate_limit_per_sec, max_TCP_connections)
```
At 1 req/sec rate limit with avg_response_time = 0.8s: T_throughput ≈ 1.25 exports/sec.

## Anti-Patterns to Avoid

- **Parsing or reconstructing pagination cursor internals**: §3's cursor-opacity rule exists because Figma changed cursor ordering semantics with no advance notice (the November 22 2024 `/files/:key/versions` breaking change) — any integration that assumed a stable cursor structure broke silently on that date, while an integration treating cursors as opaque strings (fetch `next_page` verbatim, restart from page 1 on expiry) was unaffected.
- **Storing the OAuth2 PKCE `state` parameter in localStorage or a URL parameter**: §2 requires it in a server-side HttpOnly/Secure session, compared with timing-safe equality on callback — state stored client-side accessible to JavaScript defeats its purpose as CSRF protection, since an attacker who can read or inject into localStorage can also forge a matching state value.
- **Registering a wildcard or partial-match OAuth redirect URI**: §2 mandates exact-match, HTTPS-only redirect URIs with no wildcards — a registered pattern like `https://app.example.com/*` allows an attacker-controlled path under that origin to receive the authorization code, turning a legitimate OAuth flow into an open-redirect token-theft vector.
- **Batch-DELETEing an entire variable collection through the Variables API in one automated pipeline run**: §4's bulk-DELETE safety boundary is explicit that this must never happen without a human-approved PR gate — because a single POST body can atomically remove a collection, all its modes, and all its variables in one irreversible call, an automated script with a bug in its DELETE-action list can destroy an entire token system with no PR-review checkpoint to catch it first.
- **Logging DELETE mutations to the Variables API only after the request succeeds**: §4's audit pattern specifically requires logging deleted variable names *before* issuing the request — after a successful DELETE, the API can no longer return the names of what was removed, so a post-hoc log entry recording only counts (not names) is permanently unable to answer "what exactly was deleted" during an incident review.
- **Wiring CI/CD pipeline triggers to `FILE_UPDATE` instead of `LIBRARY_PUBLISH`**: §5's trigger hierarchy places `FILE_UPDATE` last precisely because it fires on every auto-save (multiple times per hour) — a pipeline triggered on this event generates far more CI noise than the deliberate, low-frequency `LIBRARY_PUBLISH` signal a design-system token sync actually needs.
- **Caching Figma file data (`/v1/files/:key`) with a long `max-age` instead of `max-age=0, must-revalidate`**: §6's cache-control guidance distinguishes frequently-updated file data from stable metadata — applying a long TTL to file JSON (rather than relying on ETag/If-None-Match conditional GETs) means a plugin or pipeline can serve a stale design snapshot well after the designer's actual changes have published.
- **Storing an OAuth access token in any cache layer, even briefly**: §6 explicitly flags access tokens as `no-store` — caching a bearer token (even in a short-TTL response cache meant for file data) creates a token-leakage surface that a `no-store` directive is specifically designed to eliminate, since intermediary caches and shared infrastructure should never persist credential material.

## India-Specific Layer

**IT Act 2000 §43A (read with IT (Reasonable Security Practices) Rules 2011, Rule 3):**
Bodies corporate handling sensitive personal data in Figma design files (financial UI mockups, medical app prototypes containing PII) must implement reasonable security. HMAC-SHA256 webhook signature verification satisfies the technical control requirement under §43A. Rule 3 mandates an information security policy that must cover API credential management (PAT rotation, OAuth token storage).

**DPDP Act 2023 §4 (Lawful Processing):**
Design files accessed via Figma REST API constitute personal data if they contain PII (user photos in mockups, real names in UI prototypes). Processing Indian users' design data via automation scripts requires a lawful basis under §4 — either consent or a legitimate purpose. Programmatic API access logs themselves are processing records.

**GIGW v3.0 Chapter 4 (API Design) + Chapter 7 (Security):**
Government of India portals consuming Figma API must follow GIGW API standards: token-based authentication (OAuth2 or PAT), HTTPS mandatory, secure token storage (never plaintext in code). [Chapter/section numbers: CONFIDENCE: MED — confirm from official NIC/MeitY GIGW v3.0 document.]

**CERT-In Directions 2022, Direction 1 (Incident Reporting) + Direction 6 (Log Retention):**
API-integrated systems must report security incidents (webhook HMAC bypass, token theft, unauthorized API access) to CERT-In within 6 hours of detection. Build artifact and API call logs must be retained for minimum 180 days. Log retention infrastructure must be provisioned before pipeline goes to production.

## Response Rules

- Always verify webhook signatures using timing-safe comparison (`hmac.compare_digest()` or `crypto.timingSafeEqual()`) before processing any payload. Reject unverified payloads with HTTP 401.
- Apply exponential backoff with full jitter on all HTTP 429 responses. Never retry immediately after a rate limit error. Respect the `Retry-After` header value unconditionally — it may be multi-day.
- Treat all pagination cursors as opaque strings. Never parse cursor internals. If a cursor expires or returns HTTP 400/404, restart pagination from page 1.
- Use Personal Access Tokens only in server-side scripts with environment-variable injection. Never embed PATs in client-side browser code, shared repositories, or container images.
- Enforce the Variables API mutation ordering (collections → modes → variables → modeValues) within every POST body. Out-of-order references within a single request body are resolved by the temporary ID mechanism, but topological order must still be maintained for correctness.

## What Not to Do

- Do not use offset-based pagination for Figma collections — Figma's API provides only cursor-based navigation; offset pagination is not supported and there is no `offset` query parameter.
- Do not parse or reconstruct cursor values from URL parameters — cursors are opaque and their internal format may change without notice (demonstrated November 2024 when `/versions` ordering changed).
- Do not store OAuth access tokens in browser localStorage or client-accessible cookies without HttpOnly and Secure flags — use server-side sessions or secure token stores.
- Do not skip HMAC verification on webhook payloads even in development environments — a bypassable development webhook handler is a persistent security vulnerability that persists to production.
- Do not batch more than 4MB of variable mutations in a single POST body — exceeding the limit causes the entire request to fail with no partial processing; split large mutation sets into multiple requests.

## Output Expectations

Responses covering REST API integration provide:
- Complete endpoint reference with HTTP method, authentication header, query parameters, and response schema
- OAuth2 PKCE code samples (Python/Node.js) with CSRF state handling and PKCE derivation
- Rate-limit-aware request queue implementation with exponential backoff and jitter math
- Cursor pagination loop implementation with opacity rule enforcement
- HMAC-SHA256 verification code with timing-safe comparison
- Variables API batch mutation body templates with temp ID usage
- M1–M6 full mathematical derivations with all formulas and proofs

## Skill Scope

**In scope:** Figma REST API v1, Variables API (batch mutations, temp IDs), OAuth2 PKCE authentication, Personal Access Token authentication, Webhooks v2 (event selection, HMAC verification), cursor-based pagination, ETag caching, batch optimization, India regulatory compliance for API integrations.

**Out of scope:** Figma Plugin API (see figma-plugin-widget-core), Widget API (see figma-plugin-widget-core), design token schema and transformation (see design-tokens-automation-core), CI/CD pipeline orchestration (see figma-ci-cd-pipeline-core), AI-powered automation (see figma-ai-automation-core), multi-platform token output (see figma-multiplatform-tokens-core).

## Version: 1.1 — Added Anti-Patterns to Avoid section (cursor internals parsing, client-side PKCE state storage, wildcard OAuth redirect URIs, unattended bulk variable DELETE, post-hoc DELETE audit logging, FILE_UPDATE trigger noise, stale file-data caching, access-token caching)
