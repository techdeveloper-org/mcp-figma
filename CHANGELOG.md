# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [UNRELEASED]

## [1.1.0] - 2026-05-23

### Added
- `figma_get_variable_collections` -- List all variable collections in a Figma file
- `figma_get_variables` -- Get all variables in a collection with resolved values
- `figma_set_variable_value` -- Set a variable value for a specific mode
- `figma_create_variable` -- Create a new design variable in a collection
- `figma_resolve_variable_alias` -- Resolve a variable alias to its underlying value
- `figma_get_local_variables` -- Fetch all local variables from the REST API
- `figma_publish_variable_collection` -- Publish a variable collection to team library
- `figma_batch_update_variables` -- Batch-update multiple variable values atomically
- `figma_create_webhook` -- Register a webhook for Figma file events
- `figma_list_webhooks` -- List all webhooks for the current team
- `figma_delete_webhook` -- Delete a registered webhook by ID
- `figma_get_webhook_events` -- Retrieve recent events delivered to a webhook
- `figma_verify_webhook_signature` -- Verify HMAC-SHA256 webhook payload signature
- `compute_apca_contrast` -- Compute APCA Lc contrast between text and background colors
- `compute_wcag_contrast` -- Compute WCAG 2.1 contrast ratio (relative luminance)
- `get_accessible_color_pairs` -- Find accessible foreground/background color pairs from a palette
- `extract_dtcg_tokens` -- Extract DTCG-format design tokens from a Figma file
- `validate_token_schema` -- Validate a token set against the DTCG W3C specification
- `diff_token_sets` -- Compute diff between two token sets with Levenshtein rename detection
- `resolve_token_aliases` -- Resolve alias chains in a token set using Kahn topological sort
- `generate_token_transforms` -- Generate platform-specific token transforms (CSS, Android, iOS)
- `export_tokens_dtcg` -- Export resolved tokens in DTCG JSON format
- `generate_android_tokens` -- Generate Android XML resources from design tokens
- `generate_ios_tokens` -- Generate Swift/Objective-C token constants from design tokens
- `generate_css_tokens` -- Generate CSS custom properties from design tokens
- `generate_fluid_typography` -- Generate fluid type scale with CSS clamp() expressions
- `generate_type_scale` -- Generate a modular type scale from a base size and ratio
- `generate_react_component` -- Generate a React component stub from a Figma frame
- `generate_swift_component` -- Generate a SwiftUI view stub from a Figma frame
- `generate_android_component` -- Generate an Android XML layout from a Figma frame
- `generate_css_from_frame` -- Generate CSS styles from a Figma frame's properties
- `generate_flutter_component` -- Generate a Flutter widget stub from a Figma frame
- `get_codegen_context` -- Extract structured codegen context from a Figma node
- `compute_phash` -- Compute a perceptual hash (pHash) of a Figma CDN image URL
- `compare_phash_hamming` -- Compare two pHash digests using Hamming distance
- `bump_token_semver` -- Compute semantic version bump from two DTCG token snapshots
- `get_file_version_history` -- Retrieve version history for a Figma file

### Changed
- Expanded from 10 to 47 MCP tools
- Replaced string-based URL allowlist in `compute_phash` with `urlparse` netloc exact-match (SSRF fix)
- Removed traceback exposure from `mcp_safe_execute` error responses (security hardening)

### Security
- PT-01 SSRF vulnerability (CVSS 8.6) resolved in `figma_visual.compute_phash`
- PT-02 stack trace exposure (CVSS 5.3) resolved in `mcp_errors.mcp_safe_execute`
- PT-03 file key path traversal (CVSS 5.0) resolved — `figma_client._parse_file_key` now enforces `^[A-Za-z0-9_-]{1,128}$` allowlist on all extracted and raw keys; path traversal, null-byte, and oversized-key vectors are all blocked
- PT-04 comment injection / DoS (CVSS 4.3) resolved — `figma_add_comment` now sanitizes the `message` parameter via `validate_input(max_length=2000)` before sending to the Figma API
- Corrected APCA-W3 0.0.98G module-level constants in `figma_accessibility.py` (hallucination fix): wrong values `APCA_Sa=0.55/APCA_Sb=0.22/APCA_Sc=0.20` replaced with correct named constants `_APCA_TXT_LIGHT=0.56/_APCA_BG_LIGHT=0.57/_APCA_BG_DARK=0.65/_APCA_TXT_DARK=0.62` which are now used directly in the formula

### Tests
- 82 new unit tests added across 4 new modules, raising the total to 284 unit tests
- `tests/test_input_validator.py` — 38 tests for full branch coverage of `validate_input` and `validate_task_input`
- `tests/test_mcp_errors.py` — 25 tests for `mcp_error_response`, `mcp_success_response`, `mcp_safe_execute`
- `tests/test_figma_client_security.py` — 17 security tests for `_parse_file_key` allowlist (PT-03 regression)
- `tests/test_figma_accessibility_constants.py` — 8 regression tests for APCA constant correctness
- Line coverage increased to >= 95%; reliability score (RS) raised from 0.828 to 0.987

## [1.0.0] - 2026-03-31

### Added
- Initial release with 10 core Figma API tools
- `figma_get_file_info` -- Get file metadata
- `figma_get_node` -- Get node details
- `figma_get_styles` -- List published styles
- `figma_get_components` -- List published components
- `figma_extract_design_tokens` -- Extract design tokens
- `figma_get_frame_layout` -- Get frame layout properties
- `figma_export_image` -- Export frames/nodes as images
- `figma_get_comments` -- List design comments
- `figma_add_comment` -- Post implementation comments
- `figma_health_check` -- Verify API connectivity
- FastMCP stdio transport
- stdlib-only HTTP client (no external SDK)
- ETag caching and retry with exponential backoff
- PKCE OAuth flow support
- Structured error responses via `mcp_errors.py`
- Input validation via `input_validator.py`
- Token-bucket rate limiting via `rate_limiter.py`
