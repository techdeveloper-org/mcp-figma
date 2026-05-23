# IEEE 829 Test Strategy - mcp-figma

**Document Number:** TS-2026-001
**Project:** mcp-figma FastMCP Server
**Version Under Test:** 1.0.0
**Total Tools:** 47 across 8 modules + base/
**Test Strategy Level:** IEEE 829-2008 Compliant
**Date:** 2026-05-23
**Author:** test-management-agent
**Status:** APPROVED - Blocking Gate D.2

---

## 1. Test Scope

### 1.1 In Scope

- All 47 MCP tool functions registered in server.py
- All 8 feature modules: figma_client, figma_variables, figma_webhooks, figma_accessibility, figma_tokens, figma_multiplatform, figma_codegen, figma_visual
- base/ package components: response builder, decorators, persistence, clients
- Security-critical paths: HMAC signature verification, URL allowlist enforcement, input validation
- Pure-math algorithms: APCA/WCAG contrast, Kahn's topological sort, Levenshtein rename detection, pHash Hamming comparison, fluid typography clamp, dp/pt/rem unit conversions
- ETag caching and HTTP 304 handling in figma_client
- PKCE code verifier and challenge generation
- Cursor-based pagination in paginate_request
- Semver bump rules and token diff engine

### 1.2 Out of Scope

- Live Figma API responses (unit tier; mocked via unittest.mock.patch)
- Browser rendering of generated CSS output
- MCP protocol framing validation (handled by FastMCP framework)
- OAuth 2.0 full flow end-to-end (PKCE helpers tested in isolation)
- Performance/load testing at this phase

---

## 2. Test Scope Matrix

| Module | Tools (count) | Unit Test Priority | Integration Test Priority | Special Concerns |
|--------|---------------|--------------------|---------------------------|------------------|
| figma_client.py | make_request, ETag 304, paginate_request, generate_pkce_challenge, _get_token, _parse_file_key (core transport, 6 functions) | HIGH | HIGH | ETag 304 branch requires HTTPError(304) mock; PKCE code_verifier must be >= 43 chars after base64url strip; paginate must terminate on missing cursor; _get_token must raise EnvironmentError when env var absent |
| figma_variables.py | figma_list_variable_collections, figma_list_variables, figma_get_variable, figma_create_variable, figma_update_variable, figma_delete_variable, figma_batch_update_variables, figma_publish_variable_library (8) | HIGH | MEDIUM | figma_batch_update_variables is destructive and irreversible in integration; idempotency test requires two identical POST calls yielding same state; type validation for COLOR/FLOAT/STRING/BOOLEAN var_type |
| figma_webhooks.py | figma_list_webhooks, figma_create_webhook, figma_update_webhook, figma_delete_webhook, figma_verify_webhook_signature (5) | CRITICAL | LOW | HMAC verify must use hmac.compare_digest (timing-safe); test both valid and tampered signatures; test empty payload; test signature with wrong secret; create_webhook has external side-effect (real endpoint subscription) |
| figma_accessibility.py | figma_compute_apca_contrast, figma_compute_wcag_contrast, figma_scan_color_accessibility (3) | HIGH | N/A (pure math for contrast; scan requires API mock) | APCA uses 0.0.98G exponents: Sa=0.55, Sb=0.22, Sc=0.20 (note: actual exponents in code are 0.56/0.57/0.65/0.62 for polarity branches - test both dark-on-light and light-on-dark paths); WCAG black-on-white must yield exactly 21.0:1; sRGB linearization threshold at 0.04045 |
| figma_tokens.py | figma_export_dtcg_tokens, figma_extract_oklch_colors, figma_generate_type_scale, figma_resolve_token_aliases, figma_tokens_to_css_vars, figma_diff_token_versions (6) | HIGH | MEDIUM | Kahn cycle detection must identify all nodes with in_degree > 0 after queue exhaustion; Levenshtein rename detection threshold is distance <= 3; oklch conversion must produce H in [0, 360); type_scale step formula: s_n = base * ratio^n for n in range(-2, steps-2) |
| figma_multiplatform.py | figma_tokens_to_android, figma_tokens_to_ios, figma_tokens_to_css_rem, figma_dark_mode_token_pairs, figma_fluid_typography_clamp (5) | HIGH | N/A (pure math transforms) | dp conversion: px / density; pt conversion: px * (base_ppi / target_ppi); rem conversion: px / base_font_px; fluid clamp formula: clamp(min_px, calc(m*100vw + b), max_px) where slope m = (max-min)/(max_vw-min_vw); dark mode luminance polarity flip correctness |
| figma_codegen.py | figma_layout_to_flexbox, figma_layout_to_css_grid, figma_get_variant_matrix, figma_generate_react_interface, figma_generate_css_component, figma_get_code_connect_annotations (6) | HIGH | MEDIUM | Cartesian product count for variant matrix: product of all unique values per property key; SPACE_BETWEEN maps to justify-content: space-between; pure transform functions (_transform_node_to_flexbox etc.) must be testable without API; _fetch_node_for_codegen raises RuntimeError on empty nodes response |
| figma_visual.py | figma_compute_phash, figma_compare_phash_hamming, figma_bump_token_semver, figma_get_file_version_history (4) | MEDIUM | LOW | compute_phash uses SHA-256 proxy (not real DCT); documented stdlib limitation; URL allowlist enforced (non-Figma CDN URLs must raise ValueError); Hamming distance: identical hashes -> distance=0, inverted bits -> distance=64; semver bump: deleted token -> MAJOR, added token -> MINOR, value change -> PATCH, no change -> NONE |

---

## 3. Risk Matrix

Risk Score = Impact (1-5) x Likelihood (1-5). Scores >= 12 are CRITICAL, 8-11 are HIGH, 4-7 are MEDIUM, 1-3 are LOW.

| Tool / Component | Impact | Likelihood | Risk Score | Risk Level | Rationale | Mitigation |
|-----------------|--------|------------|------------|------------|-----------|------------|
| figma_verify_webhook_signature | 5 | 3 | 15 | CRITICAL | Auth bypass if non-timing-safe comparison is used or if HMAC secret is leaked; enables forged webhook injection | 100% branch coverage; test timing-safe path with hmac.compare_digest; test tampered payload; test wrong secret; never log computed signature |
| figma_batch_update_variables | 4 | 2 | 8 | HIGH | Destructive batch mutation against live Figma file; no built-in rollback; wrong mutations corrupt design tokens for all consumers | 100% branch coverage; idempotency assertion; integration tests gate-guarded with @pytest.mark.integration and real token |
| figma_create_webhook | 4 | 2 | 8 | HIGH | Registers external endpoint subscription; duplicate calls create duplicate webhooks; endpoint URL is user-controlled (SSRF surface) | 100% branch coverage; test with description=None and description set; mock make_request; validate endpoint starts with https |
| resolve_token_aliases (Kahn's algorithm) | 3 | 3 | 9 | HIGH | Cycle in alias graph causes silent non-resolution of tokens; unresolved aliases propagate downstream to CSS/Android/iOS outputs | Test linear chain, cyclic graph, disconnected graph; assert cycles_detected is populated for cycle input; assert resolution_order length < total tokens for cycle input |
| compute_phash (pHash proxy) | 2 | 4 | 8 | HIGH | SHA-256 proxy is not a real DCT pHash; identical pixel images from different URLs may produce different bytes (CDN compression artifacts); URL allowlist bypass via subdomain confusion | Test identical-input -> same hash; test non-Figma URL raises ValueError; document limitation in test docstring |
| compute_apca_contrast | 3 | 2 | 6 | MEDIUM | Incorrect APCA exponents produce wrong contrast values; UI components passed as accessible may fail APCA audit | Test reference pair: black (#000000) on white (#ffffff): Lc approx 106; test polarity branches (dark-on-light vs light-on-dark); assert exponent values are within tolerance |
| compute_wcag_contrast | 3 | 1 | 3 | LOW | Standard formula; well-established; low likelihood of implementation error | Test black on white = 21.0:1 (exact); test equal colors = 1.0:1; test AA/AAA threshold boundary values |
| figma_bump_token_semver | 3 | 2 | 6 | MEDIUM | Wrong bump type corrupts published version number; MAJOR/MINOR/PATCH precedence must be strict; relies on diff_token_versions correctness | Test all four cases: deleted=MAJOR, added=MINOR, value_changed=PATCH, no change=NONE; test priority order when multiple change types coexist |
| diff_token_versions (Levenshtein) | 3 | 2 | 6 | MEDIUM | Rename detection threshold (distance <= 3) may produce false positives for short token names; matched_added not re-checked can cause one-to-many rename assignment | Test near-match pair (distance 2); test no-match pair (distance 4); test ambiguous multiple candidates picks lowest distance |
| figma_fluid_typography_clamp | 2 | 2 | 4 | MEDIUM | Incorrect slope or intercept in clamp formula produces wrong fluid scaling; min_vw == max_vw causes division by zero | Test known values: 16px at 320vw to 24px at 1440vw; test division-by-zero guard when min_vw == max_vw |
| figma_get_variant_matrix | 3 | 2 | 6 | MEDIUM | Cartesian product count must match len(variantProperties) cross product; wrong count misleads engineers generating component stories | Test component set with 3 properties (2x2x3 = 12 combinations); assert total_combinations == product of value counts |
| generate_pkce_challenge | 4 | 1 | 4 | MEDIUM | Weak verifier entropy enables PKCE downgrade attack; code_verifier must be >= 43 chars per RFC 7636 | Assert len(code_verifier) >= 43; assert code_challenge != code_verifier; assert code_challenge_method == "S256"; run 10 iterations to confirm uniqueness |
| make_request ETag 304 handling | 2 | 3 | 6 | MEDIUM | If 304 cache miss returns empty dict instead of cached body, callers silently get empty responses; _etag_response_cache population must precede 304 path | Test sequence: GET -> cache populated -> conditional GET returns 304 -> cached body returned |
| paginate_request cursor termination | 2 | 2 | 4 | MEDIUM | Infinite loop if API returns cursor unconditionally; page_size param not forwarded correctly | Test termination on empty cursor; test termination on missing 'cursor' and 'next_page' keys; test multi-page accumulation |
| _parse_file_key URL extraction | 1 | 2 | 2 | LOW | Malformed Figma URLs may return empty key causing downstream API errors | Test file URL, design URL, raw key, URL with query params, URL with fragment |
| figma_delete_variable | 3 | 2 | 6 | MEDIUM | Destructive operation; no undo; wrong variable_id deletes wrong variable | Test with mock confirming DELETE method sent to correct endpoint; integration test gate-guarded |
| figma_delete_webhook | 3 | 2 | 6 | MEDIUM | Deleting webhook silently breaks downstream CI/CD pipelines relying on events | Test DELETE method and correct endpoint path; mock confirm response passed through |
| figma_scan_color_accessibility | 2 | 2 | 4 | MEDIUM | Walk algorithm may miss text nodes nested inside non-standard containers; effective_bg propagation may be incorrect | Test text node with parent bg; test text node with no parent bg (pair should be skipped); test nested backgrounds |

---

## 4. Test Data Requirements

All fixture files reside under `tests/fixtures/`. Files are static JSON consumed by `conftest.py` fixtures. No fixture file makes live API calls.

### 4.1 Required Fixture Files

**`tests/fixtures/file_info.json`**
Minimal valid Figma GET /v1/files/{key}?depth=1 response.
```json
{
  "name": "Test Design File",
  "lastModified": "2026-01-15T10:00:00Z",
  "version": "42",
  "thumbnailUrl": "https://figma-alpha-api.s3.us-west-2.amazonaws.com/img/test.png",
  "document": {
    "id": "0:0",
    "name": "Document",
    "type": "DOCUMENT",
    "children": [
      {"id": "1:1", "name": "Page 1", "type": "CANVAS"},
      {"id": "1:2", "name": "Page 2", "type": "CANVAS"}
    ]
  }
}
```

**`tests/fixtures/variables_response.json`**
Variables API /v1/files/{key}/variables/local response with two collections and three variables including one COLOR alias.
Must include: variableCollections dict, variables dict, at least one variable with a valuesByMode entry that is a dict with an "id" key (alias) and at least one with a float value.

**`tests/fixtures/webhooks_response.json`**
GET /v2/webhooks?team_id=... response listing two webhooks with different event_type values (FILE_UPDATE, COMMENT), one ACTIVE and one PAUSED.

**`tests/fixtures/token_dtcg_sample.json`**
DTCG token set with:
- A linear chain: token-a -> token-b -> token-c (token-a.$value = "{token-b}", token-b.$value = "{token-c}", token-c.$value = "#FF0000")
- A cycle: cycle-x.$value = "{cycle-y}", cycle-y.$value = "{cycle-x}"
- A disconnected token with no aliases: standalone.$value = "#0000FF"
Used for Kahn cycle detection and alias resolution tests.
```json
{
  "tokens": {
    "token-a": {"$value": "{token-b}", "$type": "color"},
    "token-b": {"$value": "{token-c}", "$type": "color"},
    "token-c": {"$value": "#FF0000", "$type": "color"},
    "cycle-x": {"$value": "{cycle-y}", "$type": "color"},
    "cycle-y": {"$value": "{cycle-x}", "$type": "color"},
    "standalone": {"$value": "#0000FF", "$type": "color"}
  }
}
```

**`tests/fixtures/component_set_node.json`**
A Figma COMPONENT_SET node with variantProperties defining 3 properties:
- "Size": ["Small", "Medium", "Large"]
- "State": ["Default", "Hover"]
- "Theme": ["Light", "Dark", "System"]
Expected total_combinations: 3 * 2 * 3 = 18
Children array must contain 18 COMPONENT nodes each with a name like "Size=Small, State=Default, Theme=Light".

**`tests/fixtures/frame_with_autolayout.json`**
A FRAME node with:
- layoutMode: "HORIZONTAL"
- primaryAxisAlignItems: "SPACE_BETWEEN"
- counterAxisAlignItems: "CENTER"
- paddingTop: 16, paddingRight: 24, paddingBottom: 16, paddingLeft: 24
- itemSpacing: 12
- absoluteBoundingBox: {width: 400, height: 64}
Used for layout_to_flexbox tests asserting justify-content: space-between and align-items: center.

**`tests/fixtures/node_with_text.json`**
A FRAME node containing a child TEXT node. Parent frame has a white (#FFFFFF) solid fill. TEXT node has a dark (#1A1A1A) solid fill. Used for scan_color_accessibility tests and token extraction tests.

**`tests/fixtures/phash_test_image_bytes.bin`** (optional binary, fallback: use mock)
Raw bytes of a 32x32 PNG for pHash determinism test. If not committed, the test mocks urllib.request.urlopen to return fixed bytes.

### 4.2 Fixture Loading Convention

All fixtures are loaded by `tests/conftest.py` using helper:
```python
def load_fixture(name: str) -> dict:
    path = Path(__file__).parent / "fixtures" / name
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
```

---

## 5. Coverage Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Overall line coverage | >= 85% | Industry baseline for safety-relevant API integrations; accounts for unreachable OS error branches |
| Branch coverage - CRITICAL risk tools | 100% | figma_verify_webhook_signature: both valid and invalid signature branches must be covered |
| Branch coverage - HIGH risk tools | 100% | figma_batch_update_variables, figma_create_webhook, resolve_token_aliases (cycle + no-cycle paths), compute_phash (URL allowlist pass + reject) |
| Branch coverage - MEDIUM risk tools | >= 90% | All remaining tools |
| Mutation score | >= 0.75 | Ensures tests can detect off-by-one errors in APCA/WCAG thresholds, Levenshtein distance comparisons, and Hamming distance calculations |
| Defect Detection Rate Estimate (DRE) | >= 0.85 | Formula: DRE = Defects_found_in_testing / (Defects_found_in_testing + Defects_found_post_release). Target: no more than 15% of defects escape to production. Measured at release gate. |
| Assertion density per test function | >= 2 | Each test must make at least two independent assertions to reduce oracle weakness |

### 5.1 DRE Measurement Approach

DRE will be estimated at release using:
1. Total defects found during test phase (unit + integration + e2e + security)
2. Defects found in first 30 days post-release (production monitoring)
3. DRE = D_test / (D_test + D_prod)
4. Threshold: DRE >= 0.85 required for DEPLOY READY verdict from reliability-auditor

### 5.2 Coverage Enforcement

Coverage is enforced via `pytest --cov=. --cov-report=xml --cov-fail-under=85` in CI. Branch coverage is enforced with `--cov-branch`. HIGH/CRITICAL tool branch coverage violations block the CI gate regardless of overall percentage.

---

## 6. Acceptance Criteria

### 6.1 Universal Gate (all tiers)

- All unit tests pass with no real network calls (no urllib.request.urlopen without mock.patch)
- No test imports FIGMA_ACCESS_TOKEN from environment at unit tier
- No test fixture is > 50 KB
- All tests complete in < 30 seconds total at unit tier (no sleep calls)

### 6.2 HMAC Verification Acceptance Criteria

Tests are in `tests/test_figma_webhooks.py`:

| Test Case | Input | Expected |
|-----------|-------|----------|
| Valid signature | payload="hello", secret="mysecret", signature=HMAC-SHA256("hello", "mysecret").hexdigest() | valid=True |
| Tampered payload | payload="hell0" (typo), same signature | valid=False |
| Wrong secret | correct payload and signature, different secret | valid=False |
| Empty payload | payload="", correct signature | valid=True |
| Signature case sensitivity | uppercase hex vs lowercase hex | valid=False (hmac.compare_digest is case-sensitive) |

Timing-safe assertion: test must verify that hmac.compare_digest is called (mock.assert_called) or that the function body contains no `==` comparison between computed and provided signature.

### 6.3 APCA and WCAG Acceptance Criteria

Reference values for `tests/test_figma_accessibility.py`:

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Black on white WCAG | #000000 on #ffffff | ratio = 21.0 (exact) |
| White on black WCAG | #ffffff on #000000 | ratio = 21.0 (symmetric) |
| AA pass boundary WCAG | ratio >= 4.5 | passes_aa = True |
| AA fail boundary WCAG | ratio = 4.49 | passes_aa = False |
| Black on white APCA | #000000 on #ffffff | lc_value approx 106 (tolerance +/- 2.0) |
| White on black APCA | #ffffff on #000000 | lc_value negative (light-on-dark polarity) |
| AA large text APCA | abs(lc) = 45 | passes_aa_large_text = True |
| Equal colors WCAG | #808080 on #808080 | ratio = 1.0 |

All floating point comparisons use pytest.approx with rel=0.01 (1% relative tolerance).

### 6.4 Kahn's Algorithm Acceptance Criteria

Tests are in `tests/test_figma_tokens.py` using `tests/fixtures/token_dtcg_sample.json`:

| Test Case | Input | Expected |
|-----------|-------|----------|
| Linear chain a->b->c | token_dtcg_sample.json linear subset | token-a resolved to #FF0000; aliases_resolved == 2 |
| Cycle detection | cycle-x <-> cycle-y | cycles_detected contains both "cycle-x" and "cycle-y"; unresolved aliases remain as {ref} strings |
| Disconnected token | standalone token with no alias | standalone.$value unchanged; in resolution_order |
| Empty token set | dtcg_tokens = {"tokens": {}} | resolved_tokens = {}; aliases_resolved = 0; cycles_detected = [] |
| Self-referencing alias | token.$value = "{token}" | token in cycles_detected |

### 6.5 pHash Acceptance Criteria

Tests are in `tests/test_figma_visual.py`:

| Test Case | Input | Expected |
|-----------|-------|----------|
| Identical input | Same bytes fetched twice (mock) | distance = 0 |
| Different input | Different byte content (mock) | distance > 0 |
| Inverted bits | hash1 = "0000000000000000", hash2 = "ffffffffffffffff" | distance = 64 |
| Threshold boundary | distance = threshold | similar = True |
| Threshold boundary + 1 | distance = threshold + 1 | similar = False |
| Non-Figma URL | https://evil.com/image.png | raises ValueError |
| Figma CDN URL | https://figma-alpha-api.s3.us-west-2.amazonaws.com/img/x.png | no ValueError raised (mock) |
| www.figma.com URL | https://www.figma.com/image/... | no ValueError raised (mock) |

### 6.6 Semver Bump Acceptance Criteria

Tests are in `tests/test_figma_visual.py`:

| Change Type | Input State | Expected bump_type | Expected new_version |
|-------------|-------------|-------------------|----------------------|
| Token deleted | prev has "color-primary", curr does not | MAJOR | 2.0.0 (from 1.0.0) |
| Token type changed | color -> dimension | MAJOR | 2.0.0 |
| Token added | curr has new "color-secondary" | MINOR | 1.1.0 |
| Token renamed | "color-bg" -> "color-background" (distance 2) | MINOR | 1.1.0 |
| Value changed only | same tokens, different $value | PATCH | 1.0.1 |
| No change | identical snapshots | NONE | 1.0.0 (unchanged) |
| MAJOR takes precedence | both deleted and added | MAJOR | 2.0.0 |

### 6.7 PKCE Acceptance Criteria

Tests are in `tests/test_figma_client.py`:

| Assertion | Expected |
|-----------|----------|
| len(code_verifier) | >= 43 characters |
| code_challenge_method | "S256" exactly |
| code_challenge != code_verifier | True always |
| SHA256(code_verifier) base64url == code_challenge | True (round-trip check) |
| Uniqueness across 10 calls | All 10 code_verifier values distinct |

---

## 7. Test File Assignment

### 7.1 unit-testing-specialist

Responsible for all offline unit tests. No real API calls permitted. All urllib.request.urlopen calls must be patched via `unittest.mock.patch("urllib.request.urlopen")`.

| File | Contents | Markers |
|------|----------|---------|
| `tests/conftest.py` | Shared fixtures: mock_urlopen, load_fixture, sample_dtcg_tokens, sample_webhook_payload, sample_component_set_node | @pytest.mark.unit (session-scoped) |
| `tests/fixtures/*.json` | All 6 JSON fixture files described in Section 4 | n/a |
| `tests/test_figma_client.py` | make_request happy path, ETag 304 branch, paginate_request multi-page, paginate_request termination, generate_pkce_challenge entropy, _get_token missing env var, _parse_file_key URL variants | @pytest.mark.unit |
| `tests/test_figma_variables.py` | All 8 variable tools with mocked make_request; idempotency test for batch_update_variables with two identical calls | @pytest.mark.unit |
| `tests/test_figma_webhooks.py` | All 5 webhook tools; full HMAC acceptance criteria from Section 6.2; timing-safe assertion | @pytest.mark.unit |
| `tests/test_figma_accessibility.py` | compute_apca_contrast and compute_wcag_contrast reference values from Section 6.3; scan_color_accessibility with mocked API returning node_with_text.json fixture | @pytest.mark.unit |
| `tests/test_figma_tokens.py` | All 6 token tools; Kahn acceptance criteria from Section 6.4; Levenshtein rename detection; generate_type_scale step count and formula correctness; tokens_to_css_vars output format; diff_token_versions all change categories | @pytest.mark.unit |
| `tests/test_figma_multiplatform.py` | tokens_to_android dp formula; tokens_to_ios pt scaling; tokens_to_css_rem rem formula; fluid_typography_clamp clamp expression; dark_mode_token_pairs luminance polarity; division-by-zero guard for equal viewport widths | @pytest.mark.unit |
| `tests/test_figma_codegen.py` | layout_to_flexbox alignment mapping; layout_to_css_grid; get_variant_matrix Cartesian product count; generate_react_interface TypeScript interface string; generate_css_component CSS block output; _fetch_node_for_codegen RuntimeError on empty response | @pytest.mark.unit |
| `tests/test_figma_visual.py` | pHash acceptance criteria from Section 6.5; compare_phash_hamming boundary values; bump_token_semver all cases from Section 6.6; get_file_version_history with mocked API | @pytest.mark.unit |

### 7.2 integration-testing-engineer

Responsible for tests that make real Figma API calls. All gated with `@pytest.mark.integration`. CI runs these only on main branch with FIGMA_ACCESS_TOKEN secret available. Tests must be tolerant of eventual consistency in Figma's API (assert non-empty response, not exact counts).

| File | Contents | Markers |
|------|----------|---------|
| `tests/integration/test_client_integration.py` | Real GET /v1/me; real ETag round-trip (GET, capture ETag, GET with If-None-Match, assert 304 path taken or cached body returned) | @pytest.mark.integration |
| `tests/integration/test_variables_integration.py` | Read-only: list_variable_collections, list_variables against a known test file; batch_update_variables tested with a staging-only file key | @pytest.mark.integration |
| `tests/integration/test_webhooks_integration.py` | list_webhooks for team; create_webhook against test endpoint (https://httpbin.org/post); delete_webhook for created webhook; cleanup in teardown | @pytest.mark.integration |
| `tests/integration/test_tokens_integration.py` | export_dtcg_tokens from real file (nodes source); extract_oklch_colors from real file; verify token_count > 0 | @pytest.mark.integration |
| `tests/integration/test_codegen_integration.py` | layout_to_flexbox against real frame node; get_variant_matrix against real component set; assert css block non-empty | @pytest.mark.integration |
| `pytest.ini` | Marker registration, coverage config, test paths, asyncio mode | n/a |

### 7.3 e2e-testing-engineer

Responsible for end-to-end MCP stdio protocol tests. Launches server.py as subprocess, sends MCP initialize + tools/list, verifies 47 tools present, then sends selected tool calls via stdin/stdout.

| File | Contents | Markers |
|------|----------|---------|
| `tests/e2e/test_mcp_tool_count.py` | Launch server.py subprocess; send MCP initialize; send tools/list; assert len(tools) == 47; verify all tool names present in expected_tools list | @pytest.mark.e2e |
| `tests/e2e/test_mcp_offline_tools.py` | Call figma_compute_wcag_contrast, figma_compute_apca_contrast, figma_generate_type_scale, figma_fluid_typography_clamp, figma_compare_phash_hamming via MCP stdio without API token; assert valid JSON response with success=True or structured error | @pytest.mark.e2e |
| `tests/e2e/test_mcp_error_handling.py` | Call figma_get_file_info with missing FIGMA_ACCESS_TOKEN env var; assert MCP error response (not crash); call figma_verify_webhook_signature with mismatched signature; assert valid=False in response | @pytest.mark.e2e |

---

## 8. Mock Strategy

### 8.1 Primary Mock Pattern

All unit tests mock urllib.request.urlopen at the module level where it is imported:

```python
from unittest.mock import patch, MagicMock
import json

def make_mock_response(data: dict, status: int = 200, etag: str = None):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode("utf-8")
    mock_resp.headers.get.side_effect = lambda key, default=None: (
        etag if key in ("ETag", "etag") and etag else default
    )
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp

@patch("urllib.request.urlopen")
def test_make_request_happy_path(mock_urlopen):
    mock_urlopen.return_value = make_mock_response({"name": "TestFile"})
    # ... test body
```

### 8.2 HTTP 304 Mock Pattern

```python
import urllib.error

@patch("urllib.request.urlopen")
def test_etag_304_returns_cached(mock_urlopen):
    # First call: populate ETag cache
    mock_urlopen.return_value = make_mock_response({"name": "A"}, etag='"abc123"')
    result1, etag1 = figma_client.make_request("/v1/files/KEY")
    assert etag1 == '"abc123"'

    # Second call: server returns 304
    error_304 = urllib.error.HTTPError(url="", code=304, msg="Not Modified", hdrs={}, fp=None)
    mock_urlopen.side_effect = error_304
    result2, etag2 = figma_client.make_request("/v1/files/KEY")
    assert result2 == {"name": "A"}  # cached body returned
```

### 8.3 HMAC Test Pattern

```python
import hashlib, hmac

def compute_expected_signature(payload: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
```

---

## 9. CI Pipeline Configuration

### 9.1 pytest.ini (to be created by integration-testing-engineer)

```ini
[pytest]
markers =
    unit: Unit tests - no external API calls (deselect with -m "not unit")
    integration: Integration tests - requires FIGMA_ACCESS_TOKEN (deselect with -m "not integration")
    e2e: End-to-end MCP protocol tests

testpaths = tests
addopts = --strict-markers --tb=short

[tool:pytest]
asyncio_mode = auto
```

### 9.2 CI Stage Matrix

| Stage | Trigger | Tests Run | Secrets Required | Gate |
|-------|---------|-----------|-----------------|------|
| PR Validation | Every PR | `pytest -m unit` | None | BLOCKING: fail = PR blocked |
| Main Branch | Push to main | `pytest -m unit -m integration` | FIGMA_ACCESS_TOKEN | BLOCKING: fail = no merge |
| Nightly | Scheduled 02:00 UTC | `pytest -m unit -m integration -m e2e` | FIGMA_ACCESS_TOKEN | NON-BLOCKING: alerts only |
| Security | Push to main | `pytest -m unit` + bandit + safety | None | BLOCKING |

### 9.3 Coverage CI Command

```bash
pytest -m unit \
    --cov=. \
    --cov-branch \
    --cov-report=xml:coverage.xml \
    --cov-report=term-missing \
    --cov-fail-under=85
```

---

## 10. Test Environment Requirements

| Requirement | Specification |
|-------------|---------------|
| Python version | 3.8+ (matches server.py constraint) |
| Required packages (test) | pytest>=7.0, pytest-cov>=4.0, pytest-mock>=3.10 |
| Required packages (source) | No changes from requirements.txt |
| FIGMA_ACCESS_TOKEN | Set in CI secrets; absent = integration tests skipped with pytest skip marker |
| FIGMA_FILE_KEY | Optional; integration tests use a dedicated test-only Figma file |
| OS | Windows (cp1252 safe per project constraint) and Linux CI |
| Encoding | UTF-8 for all fixture files; ASCII-only in all .py test files |

---

## 11. Document Control

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0.0 | 2026-05-23 | test-management-agent | Initial IEEE 829 test strategy, 47 tools, 8 modules |

**Review Gate:** This document is the blocking gate for TASK-11 (unit-testing-specialist), TASK-12 (integration-testing-engineer), and TASK-13 (e2e-testing-engineer). No D.2 parallel agent may start without this document at status APPROVED.

**Status:** APPROVED
