# mcp-figma — Claude Project Context

**Type:** FastMCP Server
**Transport:** stdio
**Python:** 3.8+

---

## What This Server Does

Figma design file operations via REST API for design-to-code workflows. Fetches file metadata, nodes, styles, components, design tokens (colors/typography/spacing), frame layouts, and exports. Adds implementation comments. Uses stdlib urllib only — no heavy SDK dependency.

---

## Entry Point

```
server.py
```

Run via `python server.py` — communicates over stdio using the MCP protocol.

---

## Available Tools (47 total)

### Core (10 tools -- original)
- `figma_get_file_info` -- Fetch Figma file metadata (name, version, last modified)
- `figma_get_node` -- Retrieve a specific node by ID with full properties
- `figma_get_styles` -- List all styles defined in the file (colors, text, effects)
- `figma_get_components` -- List all reusable components with metadata
- `figma_extract_design_tokens` -- Extract design tokens: colors, typography, spacing, border-radius
- `figma_get_frame_layout` -- Get frame layout properties (auto-layout, constraints, grid)
- `figma_export_image` -- Export a frame/node as PNG/SVG/PDF
- `figma_get_comments` -- List all comments on the file
- `figma_add_comment` -- Add an implementation comment to a frame/component
- `figma_health_check` -- Verify Figma API token and connectivity

### Variables (8 tools -- figma_variables.py)
- `figma_get_variable_collections` -- List all variable collections
- `figma_get_variables` -- Get all variables in a collection with resolved values
- `figma_set_variable_value` -- Set a variable value for a specific mode
- `figma_create_variable` -- Create a new design variable
- `figma_resolve_variable_alias` -- Resolve a variable alias to its underlying value
- `figma_get_local_variables` -- Fetch all local variables from REST API
- `figma_publish_variable_collection` -- Publish a variable collection to team library
- `figma_batch_update_variables` -- Batch-update multiple variable values atomically

### Webhooks (5 tools -- figma_webhooks.py)
- `figma_create_webhook` -- Register a webhook for Figma file events
- `figma_list_webhooks` -- List all webhooks for the current team
- `figma_delete_webhook` -- Delete a registered webhook by ID
- `figma_get_webhook_events` -- Retrieve recent webhook events
- `figma_verify_webhook_signature` -- Verify HMAC-SHA256 webhook payload signature

### Accessibility (3 tools -- figma_accessibility.py)
- `compute_apca_contrast` -- Compute APCA Lc contrast (APCA 0.0.98G coefficients)
- `compute_wcag_contrast` -- Compute WCAG 2.1 contrast ratio
- `get_accessible_color_pairs` -- Find accessible foreground/background color pairs

### Tokens (6 tools -- figma_tokens.py)
- `extract_dtcg_tokens` -- Extract DTCG-format tokens from a Figma file
- `validate_token_schema` -- Validate a token set against DTCG W3C spec
- `diff_token_sets` -- Compute diff between two token sets (Levenshtein rename detection)
- `resolve_token_aliases` -- Resolve alias chains using Kahn topological sort
- `generate_token_transforms` -- Generate platform-specific token transforms
- `export_tokens_dtcg` -- Export resolved tokens in DTCG JSON format

### Multiplatform (5 tools -- figma_multiplatform.py)
- `generate_android_tokens` -- Generate Android XML resources from design tokens
- `generate_ios_tokens` -- Generate Swift token constants from design tokens
- `generate_css_tokens` -- Generate CSS custom properties from design tokens
- `generate_fluid_typography` -- Generate fluid type scale with CSS clamp()
- `generate_type_scale` -- Generate modular type scale from base size + ratio

### Code Generation (6 tools -- figma_codegen.py)
- `generate_react_component` -- Generate React component stub from Figma frame
- `generate_swift_component` -- Generate SwiftUI view stub from Figma frame
- `generate_android_component` -- Generate Android XML layout from Figma frame
- `generate_css_from_frame` -- Generate CSS styles from Figma frame properties
- `generate_flutter_component` -- Generate Flutter widget stub from Figma frame
- `get_codegen_context` -- Extract structured codegen context from a Figma node

### Visual Regression (4 tools -- figma_visual.py)
- `compute_phash` -- Compute perceptual hash of a Figma CDN image (SSRF-safe allowlist)
- `compare_phash_hamming` -- Compare two pHash digests using Hamming distance
- `bump_token_semver` -- Compute semantic version bump from two DTCG token snapshots
- `get_file_version_history` -- Retrieve version history for a Figma file

---

## Shared Utilities (in this repo)

- `base/` — Shared MCP infrastructure package (response builder, decorators, persistence, clients)
- `mcp_errors.py` — Structured error response helpers
- `input_validator.py` — Null-byte strip, length limits, prompt injection detection
- `rate_limiter.py` — Token bucket rate limiter (enable via ENABLE_RATE_LIMITING=1)

---

## Environment Variables

- `FIGMA_ACCESS_TOKEN` — Figma personal access token (required)
- `FIGMA_FILE_KEY` — Default Figma file key (optional, can be passed per-call)

---

## Development

### Running locally

```bash
# Install deps
pip install -r requirements.txt

# Run the MCP server (stdio mode)
python server.py
```

### Testing a tool call manually

```python
import subprocess, json

proc = subprocess.Popen(
    ["python", "server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)
# Send MCP initialize + tool call via stdin
```

### File structure

```
mcp-figma/
+-- server.py                 # Main FastMCP server -- all 47 tools registered
+-- figma_client.py           # HTTP client (ETag, PKCE, pagination, retry)
+-- figma_variables.py        # 8 variable tools
+-- figma_webhooks.py         # 5 webhook tools (HMAC-SHA256 verification)
+-- figma_accessibility.py    # 3 accessibility tools (APCA 0.0.98G, WCAG 2.1)
+-- figma_tokens.py           # 6 token tools (DTCG, Kahn sort, Levenshtein)
+-- figma_multiplatform.py    # 5 multiplatform tools (Android/iOS/CSS/fluid)
+-- figma_codegen.py          # 6 codegen tools (React/SwiftUI/Android/CSS/Flutter)
+-- figma_visual.py           # 4 visual regression tools (pHash, semver)
+-- base/                     # Shared MCP infrastructure package
+-- mcp_errors.py             # Structured error response helpers
+-- input_validator.py        # Input validation (null-byte strip, injection detection)
+-- rate_limiter.py           # Token bucket rate limiter (ENABLE_RATE_LIMITING=1)
+-- tests/                    # Test suite: 202 unit + 14 integration + 22 e2e tests
+-- requirements.txt
+-- pytest.ini
+-- mypy.ini
+-- .pre-commit-config.yaml
+-- .github/workflows/ci.yml
+-- VERSION                   # 1.1.0
+-- .gitignore
+-- README.md
+-- CLAUDE.md
```

---

## Key Rules

1. Do NOT edit `base/` directly — it is a copy from `mcp-base` repo
2. To update shared utilities, edit in `mcp-base` and re-copy
3. Keep `server.py` as the single entry point
4. All tool handlers must use `@mcp_tool_handler` decorator for consistent error handling
5. All responses must use `success()` / `error()` / `MCPResponse` builder from `base.response`

---

**Last Updated:** 2026-05-23
